"""Batch Cypher loading of extraction results into Neo4j."""

import hashlib
import time
from collections import defaultdict
from datetime import datetime, timezone

from loguru import logger
from neo4j import GraphDatabase
from neo4j.exceptions import TransientError

from kg_builder_cli.extraction.normalization import normalize_entity_name
from kg_builder_cli.types.config import AppConfig
from kg_builder_cli.types.extraction import ExtractionResult
from kg_builder_cli.types.loading import LoadResult

from .indexes import create_indexes
from .validation import validate_graph


_MAX_RETRIES = 3
_BACKOFF_BASE = 0.5


def _run_with_retry(session, query: str, parameters: dict | None = None) -> object:
    """Execute a Cypher query with exponential backoff on transient errors."""
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return session.run(query, parameters or {})
        except TransientError as exc:
            if attempt == _MAX_RETRIES:
                raise
            wait = _BACKOFF_BASE * (2 ** (attempt - 1))
            logger.warning(
                "transient error on attempt {}/{}, retrying in {:.1f}s: {}",
                attempt,
                _MAX_RETRIES,
                wait,
                exc,
            )
            time.sleep(wait)


def _create_document_node(session, result: ExtractionResult) -> None:
    """MERGE the Document node for this extraction source."""
    query = (
        "MERGE (d:Document {name: $name}) "
        "SET d.source = $source, d.processed_at = $timestamp"
    )
    _run_with_retry(
        session,
        query,
        {
            "name": result.metadata.source,
            "source": result.metadata.source,
            "timestamp": result.metadata.timestamp.isoformat(),
        },
    )
    logger.debug("merged Document node for '{}'", result.metadata.source)


def _create_entity_nodes(
    session, result: ExtractionResult, batch_size: int
) -> int:
    """Create Entity nodes in batches and add type labels via APOC."""
    entities = result.entities
    if not entities:
        return 0

    merge_query = (
        "UNWIND $batch AS row "
        "MERGE (n:Entity {id: row.id}) "
        "SET n.name = row.name, n.type = row.type, "
        "n.description = row.description, n.confidence = row.confidence "
        "SET n += row.properties "
        "FOREACH (_ IN CASE WHEN row.embedding IS NOT NULL THEN [1] ELSE [] END | "
        "SET n.embedding = row.embedding)"
    )

    label_query_apoc = (
        "UNWIND $batch AS row "
        "MATCH (n:Entity {id: row.id}) "
        "CALL apoc.create.addLabels(n, [row.type]) YIELD node "
        "RETURN count(node)"
    )

    # Keys that must not be overwritten by entity properties
    _RESERVED_KEYS = {"id", "name", "type", "description", "confidence", "embedding"}

    total = 0
    for offset in range(0, len(entities), batch_size):
        batch = [
            {
                "id": e.id,
                "name": e.name,
                "type": e.type,
                "description": e.description,
                "confidence": e.confidence,
                "embedding": e.embedding,
                "properties": {
                    k: v for k, v in e.properties.items()
                    if k not in _RESERVED_KEYS
                },
            }
            for e in entities[offset : offset + batch_size]
        ]
        _run_with_retry(session, merge_query, {"batch": batch})
        total += len(batch)

        # add dynamic type labels via APOC; fall back to string-formatted SET
        try:
            _run_with_retry(session, label_query_apoc, {"batch": batch})
        except Exception:
            logger.debug("APOC unavailable, adding labels via formatted Cypher")
            types_grouped: dict[str, list[str]] = defaultdict(list)
            for row in batch:
                types_grouped[row["type"]].append(row["id"])
            for label, ids in types_grouped.items():
                safe_label = label.replace("`", "``")
                fallback_query = (
                    "UNWIND $ids AS eid "
                    f"MATCH (n:Entity {{id: eid}}) SET n:`{safe_label}`"
                )
                _run_with_retry(session, fallback_query, {"ids": ids})

        logger.debug("loaded entity batch {}-{}", offset, offset + len(batch))

    return total


def _create_chunk_nodes(
    session, result: ExtractionResult, batch_size: int
) -> None:
    """Create Chunk nodes with content and link them to the Document node."""
    chunks = result.chunks
    if not chunks:
        # Fallback: build chunk records from entity source_chunks references
        chunk_ids: set[str] = set()
        for entity in result.entities:
            chunk_ids.update(entity.source_chunks)
        for rel in result.relationships:
            chunk_ids.update(rel.source_chunks)
        if not chunk_ids:
            return
        chunk_list = [
            {"id": cid, "text": None, "page": None, "token_count": 0}
            for cid in chunk_ids
        ]
    else:
        chunk_list = [
            {
                "id": c.id,
                "text": c.text,
                "page": c.metadata.page,
                "token_count": c.token_count,
            }
            for c in chunks
        ]

    merge_query = (
        "UNWIND $batch AS row "
        "MERGE (c:Chunk {id: row.id}) "
        "SET c.text = row.text, c.page = row.page, c.token_count = row.token_count"
    )
    link_query = (
        "UNWIND $batch AS row "
        "MATCH (c:Chunk {id: row.id}), (d:Document {name: $doc_name}) "
        "MERGE (d)-[:HAS_CHUNK]->(c)"
    )

    for offset in range(0, len(chunk_list), batch_size):
        batch = chunk_list[offset : offset + batch_size]
        _run_with_retry(session, merge_query, {"batch": batch})
        _run_with_retry(
            session, link_query, {"batch": batch, "doc_name": result.metadata.source}
        )


def _create_chunk_chain(session, result: ExtractionResult) -> None:
    """Create NEXT_CHUNK relationships between sequential chunks."""
    chunks = result.chunks
    if len(chunks) < 2:
        return

    # Sort by index to ensure correct ordering
    sorted_chunks = sorted(chunks, key=lambda c: c.index)
    pairs = [
        {"from_id": sorted_chunks[i].id, "to_id": sorted_chunks[i + 1].id}
        for i in range(len(sorted_chunks) - 1)
    ]

    query = (
        "UNWIND $pairs AS row "
        "MATCH (a:Chunk {id: row.from_id}), (b:Chunk {id: row.to_id}) "
        "MERGE (a)-[:NEXT_CHUNK]->(b)"
    )
    _run_with_retry(session, query, {"pairs": pairs})
    logger.debug("created {} NEXT_CHUNK links", len(pairs))


def _create_has_entity_relationships(
    session, result: ExtractionResult, batch_size: int
) -> None:
    """Create HAS_ENTITY relationships from Chunk nodes to Entity nodes."""
    rows = []
    for entity in result.entities:
        for chunk_id in entity.source_chunks:
            rows.append({"chunk_id": chunk_id, "entity_id": entity.id})

    if not rows:
        return

    query = (
        "UNWIND $batch AS row "
        "MATCH (c:Chunk {id: row.chunk_id}), (e:Entity {id: row.entity_id}) "
        "MERGE (c)-[:HAS_ENTITY]->(e)"
    )

    for offset in range(0, len(rows), batch_size):
        batch = rows[offset : offset + batch_size]
        _run_with_retry(session, query, {"batch": batch})


def _create_relationships(
    session, result: ExtractionResult, batch_size: int
) -> int:
    """Create typed relationships between entities using APOC dynamic types."""
    relationships = result.relationships
    if not relationships:
        return 0

    apoc_query = (
        "UNWIND $batch AS row "
        "MATCH (a:Entity {id: row.source}), (b:Entity {id: row.target}) "
        "CALL apoc.create.relationship(a, row.type, "
        "{description: row.description, confidence: row.confidence}, b) YIELD rel "
        "RETURN count(rel)"
    )

    fallback_relates_query = (
        "UNWIND $batch AS row "
        "MATCH (a:Entity {id: row.source}), (b:Entity {id: row.target}) "
        "MERGE (a)-[r:RELATES_TO {type: row.type}]->(b) "
        "SET r.description = row.description, r.confidence = row.confidence"
    )

    total = 0
    for offset in range(0, len(relationships), batch_size):
        batch = [
            {
                "source": r.source,
                "target": r.target,
                "type": r.type,
                "description": r.description,
                "confidence": r.confidence,
            }
            for r in relationships[offset : offset + batch_size]
        ]

        try:
            _run_with_retry(session, apoc_query, {"batch": batch})
        except Exception:
            logger.debug(
                "APOC unavailable for relationships, falling back to RELATES_TO"
            )
            _run_with_retry(session, fallback_relates_query, {"batch": batch})

        total += len(batch)
        logger.debug(
            "loaded relationship batch {}-{}", offset, offset + len(batch)
        )

    return total


def load_doc_chunks(result: ExtractionResult, config: AppConfig) -> None:
    """Load only Document and Chunk nodes from an ExtractionResult.

    Creates the Document node, Chunk nodes, HAS_CHUNK links, and NEXT_CHUNK
    chain. Does NOT create Entity nodes or relationships. Used to preserve
    per-document chunk linkage during fluid-phase consolidation.
    """
    driver = GraphDatabase.driver(
        config.neo4j.uri,
        auth=(config.neo4j.user, config.neo4j.password),
    )
    try:
        with driver.session() as session:
            _create_document_node(session, result)
            _create_chunk_nodes(session, result, config.load.batch_size)
            _create_has_entity_relationships(session, result, config.load.batch_size)
            _create_chunk_chain(session, result)
    finally:
        driver.close()


def resolve_against_graph(result: ExtractionResult, config: AppConfig) -> ExtractionResult:
    """Resolve incoming entities against existing graph nodes.

    For each entity in the result, query Neo4j for existing entities with the
    same normalized name. If a match exists with a different type, remap the
    incoming entity to adopt the existing entity's type and ID. This prevents
    Neo4j MERGE from creating cross-type duplicates during the cured phase.

    Priority goes to the existing graph entity (already through curing pipeline).
    """
    if not result.entities:
        return result

    # Collect normalized names for batch query
    name_to_entities: dict[str, list] = defaultdict(list)
    for entity in result.entities:
        norm_name = normalize_entity_name(entity.name)
        name_to_entities[norm_name].append(entity)

    all_names = [e.name for e in result.entities]

    driver = GraphDatabase.driver(
        config.neo4j.uri,
        auth=(config.neo4j.user, config.neo4j.password),
    )
    try:
        with driver.session() as session:
            query_result = session.run(
                "MATCH (e:Entity) WHERE e.name IN $names "
                "RETURN e.id AS id, e.name AS name, e.type AS type",
                {"names": all_names},
            )
            existing = {record["name"]: record for record in query_result}
    finally:
        driver.close()

    if not existing:
        return result

    # Build remap: incoming entity old_id -> new_id
    id_remap: dict[str, str] = {}
    remapped = 0

    for entity in result.entities:
        norm_name = normalize_entity_name(entity.name)
        # Check all existing entities by normalized name match
        for ex_name, ex_record in existing.items():
            ex_norm = normalize_entity_name(ex_name)
            if ex_norm == norm_name and ex_record["type"] != entity.type:
                old_id = entity.id
                entity.type = ex_record["type"]
                entity.id = ex_record["id"]
                if old_id != entity.id:
                    id_remap[old_id] = entity.id
                    remapped += 1
                break

    # Rewire relationships
    if id_remap:
        for rel in result.relationships:
            if rel.source in id_remap:
                rel.source = id_remap[rel.source]
            if rel.target in id_remap:
                rel.target = id_remap[rel.target]

    if remapped:
        logger.info(
            "[resolve] remapped {} entities to match existing graph types",
            remapped,
        )

    return result


def load_extraction(
    result: ExtractionResult, config: AppConfig, *, skip_doc_chunks: bool = False,
) -> LoadResult:
    """Load an ExtractionResult into Neo4j, returning counts and timing."""
    start = time.monotonic()
    errors: list[str] = []

    driver = GraphDatabase.driver(
        config.neo4j.uri,
        auth=(config.neo4j.user, config.neo4j.password),
    )
    try:
        with driver.session() as session:
            if not skip_doc_chunks:
                _create_document_node(session, result)

            nodes_created = _create_entity_nodes(
                session, result, config.load.batch_size
            )

            if not skip_doc_chunks:
                _create_chunk_nodes(session, result, config.load.batch_size)
                _create_has_entity_relationships(
                    session, result, config.load.batch_size
                )
                _create_chunk_chain(session, result)

            rels_created = _create_relationships(
                session, result, config.load.batch_size
            )

    except Exception as exc:
        logger.error("loading failed: {}", exc)
        errors.append(str(exc))
        nodes_created = 0
        rels_created = 0
    finally:
        driver.close()

    # Post-load steps
    if not errors and config.load.create_indexes:
        try:
            create_indexes(config)
        except Exception as exc:
            logger.error("index creation failed: {}", exc)
            errors.append(f"index creation: {exc}")

    validation_report = None
    if not errors and config.load.validate_graph:
        try:
            validation_report = validate_graph(config)
            if validation_report.warnings:
                errors.extend(validation_report.warnings)
        except Exception as exc:
            logger.error("validation failed: {}", exc)
            errors.append(f"validation: {exc}")

    elapsed_ms = int((time.monotonic() - start) * 1000)
    load_result = LoadResult(
        nodes_created=nodes_created,
        nodes_merged=nodes_created,
        relationships_created=rels_created,
        errors=errors,
        duration_ms=elapsed_ms,
    )
    logger.info(
        "load complete: {} entities, {} relationships in {}ms",
        nodes_created,
        rels_created,
        elapsed_ms,
    )
    return load_result

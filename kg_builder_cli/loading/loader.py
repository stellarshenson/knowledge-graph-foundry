"""Batch Cypher loading of extraction results into Neo4j."""

import time
from collections import defaultdict
from datetime import datetime, timezone

from loguru import logger
from neo4j import GraphDatabase
from neo4j.exceptions import TransientError

from kg_builder_cli.types.config import AppConfig
from kg_builder_cli.types.extraction import ExtractionResult
from kg_builder_cli.types.loading import LoadResult


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
        "SET n += row.properties"
    )

    label_query_apoc = (
        "UNWIND $batch AS row "
        "MATCH (n:Entity {id: row.id}) "
        "CALL apoc.create.addLabels(n, [row.type]) YIELD node "
        "RETURN count(node)"
    )

    total = 0
    for offset in range(0, len(entities), batch_size):
        batch = [
            {
                "id": e.id,
                "name": e.name,
                "type": e.type,
                "description": e.description,
                "confidence": e.confidence,
                "properties": e.properties,
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
    """Create Chunk nodes and link them to the Document node."""
    chunks = result.metadata.chunk_count
    if chunks == 0:
        return

    # build chunk records from entity source_chunks references
    chunk_ids: set[str] = set()
    for entity in result.entities:
        chunk_ids.update(entity.source_chunks)
    for rel in result.relationships:
        chunk_ids.update(rel.source_chunks)

    if not chunk_ids:
        return

    chunk_list = [{"id": cid} for cid in chunk_ids]
    merge_query = (
        "UNWIND $batch AS row "
        "MERGE (c:Chunk {id: row.id})"
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


def load_extraction(result: ExtractionResult, config: AppConfig) -> LoadResult:
    """Load an ExtractionResult into Neo4j, returning counts and timing."""
    start = time.monotonic()
    errors: list[str] = []

    driver = GraphDatabase.driver(
        config.neo4j.uri,
        auth=(config.neo4j.user, config.neo4j.password),
    )
    try:
        with driver.session() as session:
            _create_document_node(session, result)

            nodes_created = _create_entity_nodes(
                session, result, config.load.batch_size
            )

            _create_chunk_nodes(session, result, config.load.batch_size)
            _create_has_entity_relationships(
                session, result, config.load.batch_size
            )

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

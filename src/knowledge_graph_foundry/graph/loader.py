"""Batched, idempotent graph loading.

Entities MERGE on id; description keeps the longer of existing and incoming
(CASE on size), embedding keeps the last non-null value, provenance arrays
are unioned and deduplicated via apoc.coll.toSet. Extraction properties are
flattened to prop_<key>; non-scalar values are JSON-serialized. Type labels
are applied additively via apoc.create.addLabels. Relationships use native
types via apoc.merge.relationship with empty ident props, so reloading the
same batch never duplicates nodes or relationships.
"""

from __future__ import annotations

import json
from typing import Any

from neo4j import Driver

from knowledge_graph_foundry.events import emit
from knowledge_graph_foundry.models import Entity, Relationship

_ENTITY_QUERY = """
UNWIND $rows AS row
MERGE (e:Entity {id: row.id})
SET e.name = row.name,
    e.description = CASE
        WHEN e.description IS NULL OR size(row.description) > size(e.description)
        THEN row.description ELSE e.description END,
    e.embedding = coalesce(row.embedding, e.embedding),
    e.source_documents = apoc.coll.toSet(coalesce(e.source_documents, []) + row.source_documents),
    e.source_chunks = apoc.coll.toSet(coalesce(e.source_chunks, []) + row.source_chunks)
SET e += row.props
WITH e, row
CALL apoc.create.addLabels(e, row.types) YIELD node
RETURN count(node) AS n
"""

_RELATIONSHIP_QUERY = """
UNWIND $rows AS row
MATCH (s:Entity {id: row.source_id})
MATCH (t:Entity {id: row.target_id})
CALL apoc.merge.relationship(s, row.type, {}, {description: row.description}, t, {}) YIELD rel
SET rel.description = CASE
        WHEN rel.description IS NULL OR size(row.description) > size(rel.description)
        THEN row.description ELSE rel.description END,
    rel.source_documents =
        apoc.coll.toSet(coalesce(rel.source_documents, []) + row.source_documents),
    rel.source_chunks = apoc.coll.toSet(coalesce(rel.source_chunks, []) + row.source_chunks)
RETURN count(rel) AS n
"""


def _flatten_properties(properties: dict[str, Any]) -> dict[str, Any]:
    """Flatten extraction properties to prop_<key>; non-scalars become JSON strings."""
    flat: dict[str, Any] = {}
    for key, value in properties.items():
        if value is None or isinstance(value, (str, int, float, bool)):
            flat[f"prop_{key}"] = value
        else:
            flat[f"prop_{key}"] = json.dumps(value, default=str)
    return flat


def ensure_indexes(driver: Driver, vector_dimensions: int, vector_index_name: str) -> None:
    """Create id, name and vector indexes idempotently."""
    vector_query = (
        f"CREATE VECTOR INDEX `{vector_index_name}` IF NOT EXISTS "
        "FOR (e:Entity) ON (e.embedding) "
        "OPTIONS {indexConfig: {"
        f"`vector.dimensions`: {int(vector_dimensions)}, "
        "`vector.similarity_function`: 'cosine'}}"
    )
    with driver.session() as session:
        session.run("CREATE INDEX kgf_entity_id IF NOT EXISTS FOR (e:Entity) ON (e.id)").consume()
        session.run(
            "CREATE INDEX kgf_entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)"
        ).consume()
        session.run(vector_query).consume()


def load_entities(driver: Driver, entities: list[Entity], batch_size: int = 500) -> int:
    """Upsert entities in batches; returns total upserted."""
    total = 0
    with driver.session() as session:
        for start in range(0, len(entities), batch_size):
            batch = entities[start : start + batch_size]
            rows = [
                {
                    "id": e.id,
                    "name": e.name,
                    "description": e.description,
                    "embedding": e.embedding,
                    "types": e.types,
                    "props": _flatten_properties(e.properties),
                    "source_documents": e.source_documents,
                    "source_chunks": e.source_chunks,
                }
                for e in batch
            ]
            session.run(_ENTITY_QUERY, rows=rows).single()
            total += len(batch)
            emit("load.batch", kind="entities", batch=start // batch_size, size=len(batch))
    emit("load.completed", kind="entities", total=total)
    return total


def load_relationships(
    driver: Driver, relationships: list[Relationship], batch_size: int = 500
) -> int:
    """Upsert relationships in batches; rows with missing endpoints are skipped."""
    total = 0
    with driver.session() as session:
        for start in range(0, len(relationships), batch_size):
            batch = relationships[start : start + batch_size]
            rows = [
                {
                    "source_id": r.source_id,
                    "target_id": r.target_id,
                    "type": r.type,
                    "description": r.description,
                    "source_documents": r.source_documents,
                    "source_chunks": r.source_chunks,
                }
                for r in batch
            ]
            record = session.run(_RELATIONSHIP_QUERY, rows=rows).single()
            loaded = record["n"] if record else 0
            total += loaded
            emit(
                "load.batch",
                kind="relationships",
                batch=start // batch_size,
                size=len(batch),
                skipped=len(batch) - loaded,
            )
    emit("load.completed", kind="relationships", total=total)
    return total

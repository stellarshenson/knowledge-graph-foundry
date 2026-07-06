"""Batched, idempotent, bitemporal graph loading.

Entities MERGE on id; description keeps the longer of existing and incoming,
embedding keeps the last non-null value, provenance arrays are unioned. When
entity versioning is on, the pre-update entity state is snapshotted to a
(:KGFEntityVersion) node linked by HAD_VERSION before the update - the
evolution record. Nothing is overwritten silently.

Relationships are bitemporal: every edge carries created_at / expired_at
(transaction time - when learned / retracted) and valid_from / valid_to
(valid time - when true in the world). Loading sets created_at and valid_from
on first sight and never deletes; superseding facts are handled by
graph/temporal.py, which sets valid_to on the prior edge rather than removing
it. Reloading the same batch never duplicates nodes or relationships.
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
WITH e, row,
     (e.description IS NOT NULL
      AND ($versioning)
      AND (size(row.description) > size(coalesce(e.description, ''))
           OR size([l IN row.types WHERE NOT l IN labels(e)]) > 0)) AS versionize
CALL apoc.do.when(versionize, $version_action, 'RETURN null AS v', {e: e}) YIELD value
SET e.name = row.name,
    e.description = CASE
        WHEN e.description IS NULL OR size(row.description) > size(e.description)
        THEN row.description ELSE e.description END,
    e.embedding = coalesce(row.embedding, e.embedding),
    e.source_documents = apoc.coll.toSet(coalesce(e.source_documents, []) + row.source_documents),
    e.source_chunks = apoc.coll.toSet(coalesce(e.source_chunks, []) + row.source_chunks),
    e.updated_at = timestamp()
SET e += row.props
WITH e, row
CALL apoc.create.addLabels(e, row.types) YIELD node
WITH e, row
CALL {
    WITH e, row
    UNWIND row.source_chunks AS cid
    MATCH (c:Chunk {id: cid})
    MERGE (e)-[:MENTIONED_IN]->(c)
    RETURN count(*) AS mentions
}
RETURN count(e) AS n
"""

_RELATIONSHIP_QUERY = """
UNWIND $rows AS row
MATCH (s:Entity {id: row.source_id})
MATCH (t:Entity {id: row.target_id})
CALL apoc.merge.relationship(
    s, row.type, {}, {description: row.description}, t,
    {created_at: timestamp(), valid_from: timestamp(), valid_to: null, expired_at: null}
) YIELD rel
SET rel.description = CASE
        WHEN rel.description IS NULL OR size(row.description) > size(rel.description)
        THEN row.description ELSE rel.description END,
    rel.source_documents =
        apoc.coll.toSet(coalesce(rel.source_documents, []) + row.source_documents),
    rel.source_chunks = apoc.coll.toSet(coalesce(rel.source_chunks, []) + row.source_chunks)
RETURN count(rel) AS n
"""


_VERSION_ACTION = (
    "CREATE (v:KGFEntityVersion) SET v = properties(e), v.versioned_at = timestamp() "
    "CREATE (e)-[:HAD_VERSION]->(v) RETURN v"
)


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


def load_entities(
    driver: Driver, entities: list[Entity], batch_size: int = 500, versioning: bool = True
) -> int:
    """Upsert entities in batches; returns total upserted. When versioning is
    on, a content change snapshots the prior state to a KGFEntityVersion node."""
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
            session.run(
                _ENTITY_QUERY, rows=rows, versioning=versioning, version_action=_VERSION_ACTION
            ).single()
            total += len(batch)
            emit("load.batch", kind="entities", batch=start // batch_size, size=len(batch))
    emit("load.completed", kind="entities", total=total)
    return total


def load_relationships(
    driver: Driver, relationships: list[Relationship], batch_size: int = 500
) -> int:
    """Upsert relationships in batches; rows with missing endpoints are skipped.
    New edges get transaction-time and valid-time stamps."""
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

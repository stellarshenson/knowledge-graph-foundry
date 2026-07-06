"""Bitemporal maintenance - contradiction reconciliation and time-aware reads.

A graph maintained for months accumulates superseding facts. For relationship
types declared functional (single-valued: an entity has one current CEO, one
current price), a new target supersedes the prior one. Reconciliation sets the
prior edge's valid_to to the new edge's valid_from - invalidate, never delete -
so history stays queryable. Default reads return only currently-valid edges.

Grounded in the Graphiti/Zep bi-temporal model: valid-time + transaction-time,
non-lossy invalidation.
"""

from __future__ import annotations

from neo4j import Driver

from knowledge_graph_foundry.events import emit
from knowledge_graph_foundry.models import Relationship

# Invalidate prior valid edges of a functional type whose target differs from the
# incoming one; return how many were invalidated (the contradiction count).
_RECONCILE = """
UNWIND $rows AS row
MATCH (s:Entity {id: row.source_id})-[r]->(old:Entity)
WHERE type(r) = row.type
  AND r.valid_to IS NULL
  AND old.id <> row.target_id
SET r.valid_to = timestamp(), r.expired_at = timestamp()
RETURN count(r) AS invalidated
"""

_CURRENT_RELATIONSHIPS = """
MATCH (s:Entity {id: $entity_id})-[r]->(t:Entity)
WHERE r.valid_to IS NULL
RETURN type(r) AS type, t.id AS target_id, t.name AS target_name, r.description AS description
"""

_HISTORY = """
MATCH (s:Entity {id: $entity_id})-[r]->(t:Entity)
WHERE type(r) = $type
RETURN t.name AS target_name, r.valid_from AS valid_from, r.valid_to AS valid_to
ORDER BY r.valid_from
"""


def reconcile_contradictions(
    driver: Driver, relationships: list[Relationship], functional_types: list[str]
) -> int:
    """Invalidate prior functional edges superseded by incoming ones. Returns
    the number of edges invalidated (the contradiction count for drift)."""
    functional = set(functional_types)
    rows = [
        {"source_id": r.source_id, "target_id": r.target_id, "type": r.type}
        for r in relationships
        if r.type in functional
    ]
    if not rows:
        return 0
    with driver.session() as session:
        record = session.run(_RECONCILE, rows=rows).single()
    invalidated = record["invalidated"] if record else 0
    if invalidated:
        emit("drift.decision", action="fact_supersession", invalidated=invalidated)
    return invalidated


def current_relationships(driver: Driver, entity_id: str) -> list[dict]:
    """Currently-valid outgoing edges of an entity (valid_to IS NULL)."""
    with driver.session() as session:
        return [dict(r) for r in session.run(_CURRENT_RELATIONSHIPS, entity_id=entity_id)]


def relationship_history(driver: Driver, entity_id: str, rel_type: str) -> list[dict]:
    """Full history of one relationship type from an entity, ordered by valid_from."""
    with driver.session() as session:
        return [dict(r) for r in session.run(_HISTORY, entity_id=entity_id, type=rel_type)]

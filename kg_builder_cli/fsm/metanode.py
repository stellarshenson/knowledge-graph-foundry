"""KGFControl metanode - graph-resident control plane.

CRUD operations for the :KGFControl metanode, :KGFRun nodes,
and :KGFTransition audit trail nodes. See KGF_DESIGN.md Section 14.5.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger
from neo4j import Driver


def create_control_metanode(driver: Driver, props: dict[str, Any]) -> None:
    """Create the :KGFControl metanode. Idempotent via MERGE on graph_id."""
    query = """
    MERGE (c:KGFControl {graph_id: $graph_id})
    SET c.fsm_state = $fsm_state,
        c.run_id = $run_id,
        c.run_count = $run_count,
        c.ontology_source = $ontology_source,
        c.extraction_mechanism = $extraction_mechanism,
        c.consolidation_started_at = $consolidation_started_at,
        c.ontology_type_count = $ontology_type_count,
        c.ontology_hash = $ontology_hash,
        c.created_at = $created_at,
        c.last_completed_at = $last_completed_at,
        c.last_error = $last_error
    """
    with driver.session() as session:
        session.run(query, props)
    logger.debug("KGFControl metanode created/updated: graph_id={}", props.get("graph_id"))


def read_control_metanode(driver: Driver) -> dict[str, Any] | None:
    """Read the :KGFControl metanode. Returns None if no metanode exists."""
    query = "MATCH (c:KGFControl) RETURN c LIMIT 1"
    with driver.session() as session:
        result = session.run(query)
        record = result.single()
        if record is None:
            return None
        node = record["c"]
        return dict(node)


def update_control_metanode(driver: Driver, updates: dict[str, Any]) -> None:
    """Update specific properties on the :KGFControl metanode."""
    if not updates:
        return
    set_clauses = ", ".join(f"c.{k} = ${k}" for k in updates)
    query = f"MATCH (c:KGFControl) SET {set_clauses}"
    with driver.session() as session:
        session.run(query, updates)
    logger.debug("KGFControl updated: {}", list(updates.keys()))


def write_run_node(
    driver: Driver,
    *,
    run_id: str,
    graph_id: str,
    start_time: str | None = None,
    end_time: str | None = None,
    doc_count: int = 0,
    entity_count: int = 0,
    trigger_type: str | None = None,
) -> None:
    """Create or update a :KGFRun node for an ingestion run."""
    query = """
    MERGE (r:KGFRun {run_id: $run_id})
    SET r.graph_id = $graph_id,
        r.start_time = $start_time,
        r.end_time = $end_time,
        r.doc_count = $doc_count,
        r.entity_count = $entity_count,
        r.trigger_type = $trigger_type
    WITH r
    MATCH (c:KGFControl {graph_id: $graph_id})
    MERGE (c)-[:HAS_RUN]->(r)
    """
    with driver.session() as session:
        session.run(
            query,
            {
                "run_id": run_id,
                "graph_id": graph_id,
                "start_time": start_time or datetime.now(timezone.utc).isoformat(),
                "end_time": end_time,
                "doc_count": doc_count,
                "entity_count": entity_count,
                "trigger_type": trigger_type,
            },
        )


def write_transition_node(
    driver: Driver,
    *,
    graph_id: str,
    from_state: str,
    to_state: str,
    trigger: str,
    run_id: str | None = None,
    detail: str | None = None,
) -> None:
    """Write a :KGFTransition audit trail node."""
    query = """
    CREATE (t:KGFTransition {
        graph_id: $graph_id,
        from_state: $from_state,
        to_state: $to_state,
        trigger: $trigger,
        run_id: $run_id,
        detail: $detail,
        timestamp: $timestamp
    })
    WITH t
    MATCH (c:KGFControl {graph_id: $graph_id})
    MERGE (c)-[:HAS_TRANSITION]->(t)
    """
    with driver.session() as session:
        session.run(
            query,
            {
                "graph_id": graph_id,
                "from_state": from_state,
                "to_state": to_state,
                "trigger": trigger,
                "run_id": run_id,
                "detail": detail,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )


def detect_graph_state(driver: Driver) -> dict[str, Any]:
    """Detect the current graph state for FSM initialization.

    Returns a dict with:
    - ``has_metanode``: True if :KGFControl exists
    - ``metanode``: dict of metanode properties (or None)
    - ``has_entities``: True if Entity nodes exist
    - ``entity_count``: number of Entity nodes
    - ``is_empty``: True if graph has no entities and no metanode
    """
    metanode = read_control_metanode(driver)
    has_metanode = metanode is not None

    entity_count = 0
    if not has_metanode:
        with driver.session() as session:
            result = session.run("MATCH (n:Entity) RETURN count(n) AS cnt")
            entity_count = result.single()["cnt"]

    return {
        "has_metanode": has_metanode,
        "metanode": metanode,
        "has_entities": entity_count > 0,
        "entity_count": entity_count,
        "is_empty": not has_metanode and entity_count == 0,
    }

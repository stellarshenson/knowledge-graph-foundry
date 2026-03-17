"""KGFControl metanode - graph-resident control plane.

CRUD operations for the :KGFControl:KGFState metanode, :KGFControl:KGFRun
nodes, and :KGFControl:KGFTransition audit trail nodes. All control plane
nodes carry :KGFControl as a shared secondary label for namespace isolation.
See KGF_DESIGN.md Section 14.5.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger
from neo4j import Driver


def create_control_metanode(driver: Driver, props: dict[str, Any]) -> None:
    """Create the :KGFControl:KGFState metanode. Idempotent via MERGE on graph_id."""
    query = """
    MERGE (c:KGFControl:KGFState {graph_id: $graph_id})
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
    """Read the :KGFControl:KGFState metanode. Returns None if no metanode exists."""
    query = "MATCH (c:KGFControl:KGFState) RETURN c LIMIT 1"
    with driver.session() as session:
        result = session.run(query)
        record = result.single()
        if record is None:
            return None
        node = record["c"]
        return dict(node)


def update_control_metanode(driver: Driver, updates: dict[str, Any]) -> None:
    """Update specific properties on the :KGFControl:KGFState metanode."""
    if not updates:
        return
    set_clauses = ", ".join(f"c.{k} = ${k}" for k in updates)
    query = f"MATCH (c:KGFControl:KGFState) SET {set_clauses}"
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
    """Create or update a :KGFControl:KGFRun node for an ingestion run."""
    query = """
    MERGE (r:KGFControl:KGFRun {run_id: $run_id})
    SET r.graph_id = $graph_id,
        r.start_time = $start_time,
        r.end_time = $end_time,
        r.doc_count = $doc_count,
        r.entity_count = $entity_count,
        r.trigger_type = $trigger_type
    WITH r
    MATCH (c:KGFControl:KGFState {graph_id: $graph_id})
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
    """Write a :KGFControl:KGFTransition audit trail node."""
    query = """
    CREATE (t:KGFControl:KGFTransition {
        graph_id: $graph_id,
        from_state: $from_state,
        to_state: $to_state,
        trigger: $trigger,
        run_id: $run_id,
        detail: $detail,
        timestamp: $timestamp
    })
    WITH t
    MATCH (c:KGFControl:KGFState {graph_id: $graph_id})
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


def write_ontology_types(
    driver: Driver,
    graph_id: str,
    types: list[dict[str, Any]],
    hierarchy: list[tuple[str, str]],
) -> None:
    """Persist ontology type definitions as :KGFControl:KGFOntologyType nodes.

    Parameters
    ----------
    types:
        List of dicts with keys: name, description, properties.
    hierarchy:
        List of (child_name, parent_name) tuples for IS_A relationships.
    """
    import json

    type_query = """
    UNWIND $batch AS row
    MERGE (t:KGFControl:KGFOntologyType {name: row.name, graph_id: $graph_id})
    SET t.description = row.description, t.properties = row.properties
    """
    batch = [
        {
            "name": t["name"],
            "description": t.get("description", ""),
            "properties": json.dumps(t.get("properties", {})),
        }
        for t in types
    ]
    if batch:
        with driver.session() as session:
            session.run(type_query, {"batch": batch, "graph_id": graph_id})

    # Create IS_A hierarchy relationships
    if hierarchy:
        hier_query = """
        UNWIND $pairs AS row
        MATCH (c:KGFControl:KGFOntologyType {name: row.child, graph_id: $graph_id})
        MATCH (p:KGFControl:KGFOntologyType {name: row.parent, graph_id: $graph_id})
        MERGE (c)-[:IS_A]->(p)
        """
        pairs = [{"child": child, "parent": parent} for child, parent in hierarchy]
        with driver.session() as session:
            session.run(hier_query, {"pairs": pairs, "graph_id": graph_id})

    logger.info(
        "wrote {} KGFOntologyType nodes, {} hierarchy relationships",
        len(batch),
        len(hierarchy),
    )


def write_resolution_guide(driver: Driver, graph_id: str, rules: str) -> None:
    """Persist the resolution guide as a :KGFControl:KGFResolutionGuide node."""
    query = """
    MERGE (g:KGFControl:KGFResolutionGuide {graph_id: $graph_id})
    SET g.rules = $rules, g.updated_at = $ts
    """
    with driver.session() as session:
        session.run(
            query,
            {
                "graph_id": graph_id,
                "rules": rules,
                "ts": datetime.now(timezone.utc).isoformat(),
            },
        )
    logger.info("wrote resolution guide ({} chars)", len(rules))


def write_type_calibration(
    driver: Driver, graph_id: str, calibration: dict[str, dict[str, Any]]
) -> None:
    """Persist per-type calibration state as :KGFControl:KGFTypeCalibration nodes.

    Parameters
    ----------
    calibration:
        Dict keyed by type name, values are dicts with entity_count,
        mean_posterior, observation_count, remap_count, prior_strength.
    """
    if not calibration:
        return

    cal_query = """
    UNWIND $batch AS row
    MERGE (c:KGFControl:KGFTypeCalibration {name: row.name, graph_id: $graph_id})
    SET c.entity_count = row.entity_count,
        c.mean_posterior = row.mean_posterior,
        c.observation_count = row.observation_count,
        c.remap_count = row.remap_count,
        c.prior_strength = row.prior_strength
    WITH c
    MATCH (s:KGFControl:KGFState {graph_id: $graph_id})
    MERGE (s)-[:HAS_CALIBRATION]->(c)
    """
    batch = [
        {
            "name": type_name,
            "entity_count": data.get("entity_count", 0),
            "mean_posterior": data.get("mean_posterior", 0.0),
            "observation_count": data.get("observation_count", 0),
            "remap_count": data.get("remap_count", 0),
            "prior_strength": data.get("prior_strength", 1.0),
        }
        for type_name, data in calibration.items()
    ]
    with driver.session() as session:
        session.run(cal_query, {"batch": batch, "graph_id": graph_id})

    logger.info("wrote {} KGFTypeCalibration nodes", len(batch))


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
            result = session.run("MATCH (n:Entity) WHERE NOT n:KGFControl RETURN count(n) AS cnt")
            entity_count = result.single()["cnt"]

    return {
        "has_metanode": has_metanode,
        "metanode": metanode,
        "has_entities": entity_count > 0,
        "entity_count": entity_count,
        "is_empty": not has_metanode and entity_count == 0,
    }

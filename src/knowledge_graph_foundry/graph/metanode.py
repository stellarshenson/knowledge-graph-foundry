"""Control metanode - the graph is the single source of truth for lifecycle.

One node (:KGFControl {id: 'kgf'}) holds fsm_state, purpose, ontology,
calibration, buffer_cache and metrics_history. Neo4j properties are scalars
or flat arrays only, so dict/list values are JSON-serialized on write under
a json_-prefixed property name and parsed back (prefix stripped) on read.
Scalar values pass through unchanged. write_control stamps updated_at.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Optional

from neo4j import Driver

CONTROL_ID = "kgf"
_JSON_PREFIX = "json_"


def read_control(driver: Driver) -> Optional[dict[str, Any]]:
    """Read the control node state; None when absent (fresh graph)."""
    with driver.session() as session:
        record = session.run("MATCH (c:KGFControl {id: $id}) RETURN c", id=CONTROL_ID).single()
    if record is None:
        return None
    state: dict[str, Any] = {}
    for key, value in dict(record["c"]).items():
        if key == "id":
            continue
        if key.startswith(_JSON_PREFIX):
            state[key[len(_JSON_PREFIX) :]] = json.loads(value)
        else:
            state[key] = value
    return state


def write_control(driver: Driver, state: dict[str, Any]) -> None:
    """MERGE the control node and SET the given state."""
    props: dict[str, Any] = {}
    for key, value in state.items():
        if isinstance(value, (dict, list)):
            props[_JSON_PREFIX + key] = json.dumps(value, default=str)
        else:
            props[key] = value
    props["updated_at"] = datetime.now(timezone.utc).isoformat()
    with driver.session() as session:
        session.run(
            "MERGE (c:KGFControl {id: $id}) SET c += $props",
            id=CONTROL_ID,
            props=props,
        ).consume()

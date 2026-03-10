"""Post-load reasoning: Cypher-based subclass propagation."""

from __future__ import annotations

from loguru import logger

_SUBCLASS_PROPAGATION_QUERY = (
    "MATCH (i:Entity)-[:INSTANCE_OF]->(c)-[:SUBCLASS_OF*]->(sup) "
    "WHERE NOT (i)-[:INSTANCE_OF]->(sup) "
    "WITH i, sup "
    "MERGE (i)-[:INSTANCE_OF]->(sup) "
    "RETURN count(*) AS new_edges"
)


def run_subclass_propagation(session) -> int:
    """Propagate INSTANCE_OF relationships through SUBCLASS_OF chains.

    For any entity that is an INSTANCE_OF a class which has SUBCLASS_OF
    ancestors, creates INSTANCE_OF edges to all ancestor classes.

    Returns the count of new edges inferred.
    """
    result = session.run(_SUBCLASS_PROPAGATION_QUERY)
    record = result.single()
    count = record["new_edges"] if record else 0
    if count > 0:
        logger.info("Subclass propagation: inferred {} new INSTANCE_OF edges", count)
    else:
        logger.debug("Subclass propagation: no new edges to infer")
    return count

"""Post-load graph validation for kg-builder-cli."""

from __future__ import annotations

from loguru import logger
from neo4j import GraphDatabase

from knowledge_graph_foundry.types.config import AppConfig
from knowledge_graph_foundry.types.loading import ValidationReport


def validate_graph(config: AppConfig, *, driver: object | None = None) -> ValidationReport:
    """Run integrity checks against the loaded graph and return a report.

    If ``driver`` is provided it will be used directly (caller owns
    lifecycle).  Otherwise a new driver is created and closed when done.
    """
    owns_driver = driver is None
    if owns_driver:
        driver = GraphDatabase.driver(
            config.neo4j.uri,
            auth=(config.neo4j.user, config.neo4j.password),
        )

    orphan_ids: list[str] = []
    warnings: list[str] = []
    total_entities = 0
    total_relationships = 0
    type_distribution: dict[str, int] = {}
    types_with_rels: set[str] = set()

    try:
        with driver.session() as session:
            # orphan entities - no relationships at all (exclude control plane)
            result = session.run(
                "MATCH (n:Entity) WHERE NOT (n)-[]-() AND NOT n:KGFControl RETURN n.id AS id"
            )
            orphan_ids = [record["id"] for record in result]
            if orphan_ids:
                logger.warning("{} orphan entities detected", len(orphan_ids))

            # total entity count (exclude control plane)
            result = session.run("MATCH (n:Entity) WHERE NOT n:KGFControl RETURN count(n) AS cnt")
            total_entities = result.single()["cnt"]

            # total relationship count (exclude control plane)
            result = session.run(
                "MATCH (a:Entity)-[r]-(b:Entity) "
                "WHERE NOT a:KGFControl AND NOT b:KGFControl "
                "RETURN count(r) AS cnt"
            )
            total_relationships = result.single()["cnt"]

            # type distribution (exclude control plane)
            result = session.run(
                "MATCH (n:Entity) WHERE NOT n:KGFControl "
                "RETURN n.type AS type, count(n) AS cnt ORDER BY cnt DESC"
            )
            type_distribution = {record["type"]: record["cnt"] for record in result}

            # types that participate in at least one relationship (exclude control plane)
            if type_distribution:
                result = session.run(
                    "MATCH (n:Entity)-[]-() WHERE NOT n:KGFControl RETURN DISTINCT n.type AS type"
                )
                types_with_rels = {record["type"] for record in result}
    finally:
        if owns_driver:
            driver.close()

    all_types = set(type_distribution.keys())
    type_coverage = len(types_with_rels) / len(all_types) if all_types else 0.0

    if type_coverage < 1.0:
        missing = all_types - types_with_rels
        warnings.append(f"types without relationships: {', '.join(sorted(missing))}")

    logger.info(
        "validation: {} entities, {} relationships, {:.0%} type coverage, {} orphans",
        total_entities,
        total_relationships,
        type_coverage,
        len(orphan_ids),
    )

    from knowledge_graph_foundry.events import signals as evt_signals
    from knowledge_graph_foundry.events import types as etypes

    evt_signals.graph_validated.send(
        evt_signals.graph_validated,
        event=etypes.GraphValidated(
            entity_count=total_entities,
            rel_count=total_relationships,
            type_coverage=type_coverage,
            orphan_count=len(orphan_ids),
        ),
    )

    return ValidationReport(
        orphan_entities=orphan_ids,
        type_coverage=type_coverage,
        warnings=warnings,
    )

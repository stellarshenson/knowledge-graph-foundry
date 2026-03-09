"""Post-load graph validation for kg-builder-cli."""

from loguru import logger
from neo4j import GraphDatabase

from kg_builder_cli.types.config import AppConfig
from kg_builder_cli.types.loading import ValidationReport


def validate_graph(config: AppConfig) -> ValidationReport:
    """Run integrity checks against the loaded graph and return a report."""
    driver = GraphDatabase.driver(
        config.neo4j.uri,
        auth=(config.neo4j.user, config.neo4j.password),
    )
    orphan_ids: list[str] = []
    warnings: list[str] = []
    total_entities = 0
    total_relationships = 0
    type_distribution: dict[str, int] = {}

    try:
        with driver.session() as session:
            # orphan entities - no relationships at all
            result = session.run(
                "MATCH (n:Entity) WHERE NOT (n)-[]-() RETURN n.id AS id"
            )
            orphan_ids = [record["id"] for record in result]
            if orphan_ids:
                logger.warning("{} orphan entities detected", len(orphan_ids))

            # total entity count
            result = session.run("MATCH (n:Entity) RETURN count(n) AS cnt")
            total_entities = result.single()["cnt"]

            # total relationship count
            result = session.run(
                "MATCH (:Entity)-[r]-(:Entity) RETURN count(r) AS cnt"
            )
            total_relationships = result.single()["cnt"]

            # type distribution
            result = session.run(
                "MATCH (n:Entity) RETURN n.type AS type, count(n) AS cnt "
                "ORDER BY cnt DESC"
            )
            type_distribution = {
                record["type"]: record["cnt"] for record in result
            }
    finally:
        driver.close()

    # compute type coverage as fraction of entity types that have at least one
    # relationship - a rough proxy for ontology completeness
    types_with_rels = set()
    if type_distribution:
        driver = GraphDatabase.driver(
            config.neo4j.uri,
            auth=(config.neo4j.user, config.neo4j.password),
        )
        try:
            with driver.session() as session:
                result = session.run(
                    "MATCH (n:Entity)-[]-() "
                    "RETURN DISTINCT n.type AS type"
                )
                types_with_rels = {record["type"] for record in result}
        finally:
            driver.close()

    all_types = set(type_distribution.keys())
    type_coverage = len(types_with_rels) / len(all_types) if all_types else 0.0

    if type_coverage < 1.0:
        missing = all_types - types_with_rels
        warnings.append(
            f"types without relationships: {', '.join(sorted(missing))}"
        )

    logger.info(
        "validation: {} entities, {} relationships, {:.0%} type coverage, "
        "{} orphans",
        total_entities,
        total_relationships,
        type_coverage,
        len(orphan_ids),
    )

    return ValidationReport(
        orphan_entities=orphan_ids,
        missing_relationships=[],
        type_coverage=type_coverage,
        warnings=warnings,
    )

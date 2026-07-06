"""Neo4j driver factory."""

from __future__ import annotations

from neo4j import Driver, GraphDatabase

from knowledge_graph_foundry.settings import Neo4jSettings


def create_driver(cfg: Neo4jSettings) -> Driver:
    """Create a Neo4j driver and verify connectivity."""
    driver = GraphDatabase.driver(cfg.uri, auth=(cfg.user, cfg.password))
    with driver.session() as session:
        session.run("RETURN 1").consume()
    return driver

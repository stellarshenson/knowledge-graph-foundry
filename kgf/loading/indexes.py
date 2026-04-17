"""Neo4j index creation for kg-builder-cli."""

from loguru import logger
from neo4j import GraphDatabase

from kgf.types.config import AppConfig

_INDEXES = [
    (
        "entity_id_idx",
        "CREATE INDEX entity_id_idx IF NOT EXISTS FOR (n:Entity) ON (n.id)",
    ),
    (
        "entity_name_idx",
        "CREATE INDEX entity_name_idx IF NOT EXISTS FOR (n:Entity) ON (n.name)",
    ),
    (
        "entity_embeddings",
        "CREATE VECTOR INDEX entity_embeddings IF NOT EXISTS "
        "FOR (n:Entity) ON (n.embedding) "
        "OPTIONS {indexConfig: {`vector.dimensions`: 1024, "
        "`vector.similarity_function`: 'cosine'}}",
    ),
    (
        "entity_names",
        "CREATE FULLTEXT INDEX entity_names IF NOT EXISTS FOR (n:Entity) ON EACH [n.name]",
    ),
]


def create_indexes(config: AppConfig) -> None:
    """Create required indexes in Neo4j."""
    driver = GraphDatabase.driver(
        config.neo4j.uri,
        auth=(config.neo4j.user, config.neo4j.password),
    )
    try:
        with driver.session() as session:
            for name, query in _INDEXES:
                session.run(query)
                logger.info("created index: {}", name)
    finally:
        driver.close()

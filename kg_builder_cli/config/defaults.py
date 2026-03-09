"""Built-in default values matching the config.yml structure."""

DEFAULTS: dict = {
    "neo4j": {
        "uri": "${NEO4J_URI:bolt://localhost:7687}",
        "user": "${NEO4J_USERNAME:neo4j}",
        "password": "${NEO4J_PASSWORD:}",
    },
    "llm": {
        "provider": "bedrock",
        "model": "eu.anthropic.claude-sonnet-4-20250514-v1:0",
        "temperature": 0.0,
        "region": "eu-central-1",
        "profile": None,
        "max_retries": 3,
        "timeout": 120,
    },
    "extract": {
        "chunking_strategy": "token",
        "chunk_size": 2000,
        "chunk_overlap": 200,
        "concurrency": 4,
        "extraction_mode": "hybrid",
        "evidence_spans": False,
        "source_frequency": False,
        "describe_images": False,
        "vision_model": None,
        "subgraph_splitting": False,
        "rolling_context_window": 0,
        "resolution_threshold": 0.85,
    },
    "ontology_buffer": {
        "seed_from": None,
        "intent": None,
        "seed_depth": 2,
        "seed_filter": None,
        "refine_every_n_docs": 5,
        "coverage_threshold": 0.5,
        "min_frequency_to_confirm": 2,
        "flush_on_complete": True,
    },
    "load": {
        "merge_strategy": "merge",
        "batch_size": 500,
        "create_indexes": True,
        "validate": True,
    },
    "memory": {
        "enabled": True,
        "max_entries_per_source": 100,
        "ttl_days": 90,
    },
    "paths": {
        "ontology": None,
        "schema": None,
        "memory": ".kg-builder/memory/",
        "migrations": ".kg-builder/migrations/",
    },
}

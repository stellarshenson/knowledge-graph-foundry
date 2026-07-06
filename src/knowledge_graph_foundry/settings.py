"""Settings for Knowledge Graph Foundry.

Precedence: environment variables > .env > config.yml > model defaults.
Neo4j credentials come from env (NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD);
everything else lives in config.yml at the project root (path configurable).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel


class Neo4jSettings(BaseModel):
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = ""


class LLMSettings(BaseModel):
    engine: Literal["frontier", "claude-cli", "local-gpu"] = "frontier"
    model: str = "bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0"
    temperature: float = 0.0
    max_retries: int = 3
    timeout: int = 120
    region: Optional[str] = "eu-central-1"  # Bedrock region
    base_url: Optional[str] = None  # local-gpu OpenAI-compatible endpoint
    claude_cli_path: str = "claude"


class EmbeddingSettings(BaseModel):
    provider: Literal["bedrock", "sentence-transformers"] = "bedrock"
    model: str = "amazon.titan-embed-text-v2:0"
    fallback: Optional[str] = "sentence-transformers"
    fallback_model: str = "all-MiniLM-L6-v2"


class ExtractionSettings(BaseModel):
    chunk_size: int = 2000
    chunk_overlap: int = 200
    concurrency: int = 4


class ResolutionSettings(BaseModel):
    merge_threshold: float = 0.6
    defer_lower: float = 0.4
    name_prior_identical: float = 0.8
    name_prior_fuzzy: float = 0.2
    description_lr_floor: float = 0.3
    synonym_cluster_threshold: float = 0.82
    calibration_min_observations: int = 50


class CuringSettings(BaseModel):
    jsd_threshold: float = 0.02
    chao1_threshold: float = 0.95
    entropy_delta_threshold: float = 0.01
    min_documents: int = 3
    max_fluid_documents: int = 20
    min_encounters_to_confirm: int = 2


class DriftSettings(BaseModel):
    remap_rate_threshold: float = 0.3
    window: int = 3
    rebuild_jsd_threshold: float = 0.15


class GraphRAGSettings(BaseModel):
    community_min_size: int = 3
    vector_index_name: str = "kgf_entity_embeddings"
    vector_dimensions: int = 1024
    top_k: int = 8


class LoadSettings(BaseModel):
    batch_size: int = 500
    entity_versioning: bool = True  # snapshot prior entity state on content change
    functional_relationship_types: list[str] = []  # single-valued rels: a new target supersedes


class Settings(BaseModel):
    lease_ttl_seconds: int = 180  # ingest run lease staleness window
    neo4j: Neo4jSettings = Neo4jSettings()
    llm: LLMSettings = LLMSettings()
    embeddings: EmbeddingSettings = EmbeddingSettings()
    extraction: ExtractionSettings = ExtractionSettings()
    resolution: ResolutionSettings = ResolutionSettings()
    curing: CuringSettings = CuringSettings()
    drift: DriftSettings = DriftSettings()
    graphrag: GraphRAGSettings = GraphRAGSettings()
    load: LoadSettings = LoadSettings()
    event_log: Optional[str] = None  # path to JSONL event log, None disables


def load_settings(config_path: Optional[Path] = None) -> Settings:
    """Load settings from config.yml (if present) with env overrides."""
    import yaml

    load_dotenv()

    data: dict = {}
    path = config_path or Path("config.yml")
    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    else:
        logger.warning(f"config file {path} not found, using defaults")

    settings = Settings(**data)

    if os.environ.get("NEO4J_URI"):
        settings.neo4j.uri = os.environ["NEO4J_URI"]
    if os.environ.get("NEO4J_USER"):
        settings.neo4j.user = os.environ["NEO4J_USER"]
    if os.environ.get("NEO4J_PASSWORD"):
        settings.neo4j.password = os.environ["NEO4J_PASSWORD"]

    return settings

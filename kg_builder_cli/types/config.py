"""Configuration models for kg-builder-cli."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Neo4jConfig(BaseModel):
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = ""


class LLMConfig(BaseModel):
    provider: Literal["bedrock", "openai", "anthropic"] = "bedrock"
    model: str = "eu.anthropic.claude-sonnet-4-20250514-v1:0"
    temperature: float = 0.0
    region: str = "eu-central-1"
    profile: Optional[str] = None
    max_retries: int = 3
    timeout: int = 120


class ExtractConfig(BaseModel):
    chunking_strategy: Literal["token", "semantic"] = "token"
    chunk_size: int = 2000
    chunk_overlap: int = 200
    concurrency: int = 4
    extraction_mode: Literal["entity_relationship", "graph_reader", "hybrid"] = "hybrid"
    evidence_spans: bool = False
    source_frequency: bool = False
    describe_images: bool = False
    vision_model: Optional[str] = None
    subgraph_splitting: bool = False
    rolling_context_window: int = 0
    resolution_threshold: float = 0.85
    use_embeddings: bool = False
    embedding_model: str = "amazon.titan-embed-text-v2:0"


class OntologyBufferConfig(BaseModel):
    seed_from: Optional[str] = None
    intent: Optional[str] = None
    seed_depth: int = 2
    seed_filter: Optional[str] = None
    refine_every_n_docs: int = 5
    coverage_threshold: float = 0.5
    min_frequency_to_confirm: int = 2
    flush_on_complete: bool = True


class LoadConfig(BaseModel):
    model_config = {"populate_by_name": True}

    merge_strategy: Literal["merge", "replace", "skip"] = "merge"
    batch_size: int = 500
    create_indexes: bool = True
    validate_graph: bool = Field(default=True, alias="validate")


class MemoryConfig(BaseModel):
    enabled: bool = True
    max_entries_per_source: int = 100
    ttl_days: int = 90


class PathsConfig(BaseModel):
    model_config = {"populate_by_name": True}

    ontology: Optional[str] = None
    schema_dir: Optional[str] = Field(default=None, alias="schema")
    memory: str = ".kg-builder/memory/"
    migrations: str = ".kg-builder/migrations/"


class AppConfig(BaseModel):
    neo4j: Neo4jConfig = Neo4jConfig()
    llm: LLMConfig = LLMConfig()
    extract: ExtractConfig = ExtractConfig()
    ontology_buffer: OntologyBufferConfig = OntologyBufferConfig()
    load: LoadConfig = LoadConfig()
    memory: MemoryConfig = MemoryConfig()
    paths: PathsConfig = PathsConfig()

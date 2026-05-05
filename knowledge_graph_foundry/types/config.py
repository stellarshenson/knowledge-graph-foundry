"""Configuration models for Knowledge Graph Foundry."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from knowledge_graph_foundry.config import CONFIG_DIR_NAME


class Neo4jConfig(BaseModel):
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = ""


class RateLimitConfig(BaseModel):
    requests_per_second: float = 1.0


class LLMConfig(BaseModel):
    provider: Optional[Literal["bedrock", "openai", "anthropic"]] = None
    model: Optional[str] = None
    temperature: float = 0.0
    region: Optional[str] = None
    profile: Optional[str] = None
    max_retries: int = 3
    timeout: int = 120
    rate_limit: Optional[RateLimitConfig] = None


class ExtractConfig(BaseModel):
    chunk_size: int = 2000
    chunk_overlap: int = 200
    concurrency: int = 4
    resolution_threshold: float = 0.85
    name_threshold: float = 0.65
    embedding_threshold: float = 0.80
    use_embeddings: bool = False
    embedding_model: Optional[str] = None
    embedding_provider: Optional[str] = None
    embedding_fallback: Optional[str] = "sentence-transformers"
    embedding_fallback_model: Optional[str] = None
    bayesian_resolution: bool = False
    llm_escalation: bool = False
    schema_signal_extraction: bool = False
    cross_type_description_threshold: float = 0.3
    cross_type_embedding_threshold: float = 0.75
    cross_type_merge_threshold: float = 0.6
    deferred_dedup: bool = False
    deferred_dedup_ambiguous_lower: float = 0.4
    deferred_dedup_llm_escalation: bool = False
    hierarchy_resolution: bool = True
    event_log: bool = False


class OntologyBufferConfig(BaseModel):
    seed_from: Optional[str] = None
    resolution_intent: Optional[str] = None
    seed_depth: int = 2
    seed_filter: Optional[str] = None
    refine_every_n_docs: int = 5
    coverage_threshold: float = 0.5
    min_frequency_to_confirm: int = 2
    min_frequency_to_emerge: int = 1
    flush_on_complete: bool = True
    max_type_exemplars: int = 5
    type_resolution_top_k: int = 3
    type_resolution_entropy_threshold: float = 0.8
    post_load_reasoning: bool = False
    resolution_guide_evolution: bool = True


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
    memory: str = f"{CONFIG_DIR_NAME}/memory/"
    migrations: str = f"{CONFIG_DIR_NAME}/migrations/"


class CuringConfig(BaseModel):
    enabled: bool = False
    min_documents: int = 3
    max_fluid_documents: int = 20
    coverage_delta_threshold: float = 0.05
    stability_window: int = 3
    auto_cure: bool = True
    metrics_variance_window: int = 5
    enforcement_threshold: float = 0.5
    jsd_convergence_threshold: float = 0.01
    entropy_delta_threshold: float = 0.05
    plateau_entropy_delta: float = 0.1
    drift_remap_threshold: float = 0.3
    drift_window: int = 3
    re_cure_on_drift: bool = False
    generative_curing: bool = False
    generative_patience: float = 0.4
    generative_max_tool_calls: int = 2
    min_chao1_coverage: float = 0.5
    merge_confidence_threshold: float = 0.4


class AppConfig(BaseModel):
    neo4j: Neo4jConfig = Neo4jConfig()
    llm: LLMConfig = LLMConfig()
    extract: ExtractConfig = ExtractConfig()
    ontology_buffer: OntologyBufferConfig = OntologyBufferConfig()
    load: LoadConfig = LoadConfig()
    memory: MemoryConfig = MemoryConfig()
    paths: PathsConfig = PathsConfig()
    curing: CuringConfig = CuringConfig()

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


class ChannelEmbedding(BaseModel):
    """Per-channel embedding space (acc-crit Embeddings): any model connects
    through config; the (provider, model) pair is pinned to every index built
    with it. `device` is the nvidia-smi index or GPU UUID for local-gpu
    (PCI_BUS_ID order set before torch import); "cpu" only by explicit
    config, never as a silent fallback."""

    provider: Literal["bedrock", "local-gpu", "openai"] = "local-gpu"
    model: str = "BAAI/bge-m3"
    device: str = "2"  # nvidia-smi index or UUID; "cpu" explicit only
    endpoint: Optional[str] = None  # openai provider: base URL of /v1/embeddings


class EmbeddingChannels(BaseModel):
    """Retrieval channels may pin different embedding models (acc-crit
    per-channel spaces). The entity channel stays on EmbeddingSettings
    (Titan - the live index space, fixed control arm)."""

    passages: ChannelEmbedding = ChannelEmbedding()


class IngestSettings(BaseModel):
    text_column_median_chars: int = 200  # DEF-2: column median cell length above which a structured file is text-heavy and each row chunk-extracts as its own document


class ExtractionSettings(BaseModel):
    chunk_size: int = 2000
    chunk_overlap: int = 200
    concurrency: int = 4
    document_concurrency: int = 1  # DEF-12/R30-H343: cross-doc extraction look-ahead in STABLE; 1 = serial (shipped default until the R30 verdict)
    union_k: int = 1  # DEF-11/DEF-13/R31-H349: independent extraction passes per chunk, results unioned; 1 = single pass (shipped default until the H349 verdict)
    gleaning_rounds: int = 1  # R3: extra "what did we miss" passes (0 disables)
    split_entity_relation: bool = True  # R3: separate entity and relation passes
    parser_union: bool = True  # R15-H146-151: pypdf text-layer union partner to pymupdf4llm
    glyph_normalization: bool = True  # R15-H190: strip trademark/unicode glyphs (parser+resolver)
    header_carryover: bool = True  # R15-H153: re-print table header on severed continuation chunks
    recipe: Literal["single", "enumerate", "mention"] = (
        "enumerate"  # R24-SLOT2/SLOT-4: enumerate (H246) ships as default; mention (H258) refuted, single retained
    )


class ResolutionSettings(BaseModel):
    merge_threshold: float = 0.6
    defer_lower: float = 0.4
    name_prior_identical: float = 0.8
    name_prior_fuzzy: float = 0.2
    description_lr_floor: float = 0.3
    synonym_cluster_threshold: float = 0.82
    calibration_min_observations: int = 50
    ann_top_k: int = 10  # R4: FAISS neighbours per entity for blocking
    ann_min_entities: int = 200  # R4: use ANN blocking above this per-type size
    llm_defer_judge: bool = False  # R4: route the 0.4-0.6 band to an LLM judge
    calibration_min_labels: int = 100  # R7: below this, use a fixed threshold not a curve
    split_guard: bool = True  # R8: correlation-clustering split after union-find
    split_guard_min_avg_similarity: float = 0.5  # R8: cut components below this cohesion
    identity_stack: Literal["v1", "v2"] = (
        "v1"  # R15-H158: v2 = calibrated cosine + NLI veto + logistic
    )
    identity_stack_artifact: str = (
        "data/processed/identity-calibration-v2.json"  # v2 baked coefficients
    )
    nli_veto_threshold: float = 0.5  # R15-H158: contradiction prob that vetoes a merge (H122/H128)
    soft_links: bool = True  # R15-H268: materialize defer-zone pairs as posterior-weighted SIMILAR_TO edges (link, never merge)
    demotion_court: bool = True  # R15-R27/H290: ingest-close single-shot judge over the SAME_AS docket; judged-false edges demoted to soft links
    calibration_path: Optional[str] = (
        None  # R15-H157/H142: per-corpus frozen isotonic artifact; None = current behavior
    )


class CuringSettings(BaseModel):
    jsd_threshold: float = 0.02
    chao1_threshold: float = 0.95
    entropy_delta_threshold: float = 0.01
    min_documents: int = 3
    max_fluid_documents: int = 100  # DEF-3: was 20; force-cure must not preempt the evidence gate
    min_encounters_to_confirm: int = 2
    min_samples_before_cure: int = 3  # R7: Chao1 floor - block the gate below this
    missing_mass_threshold: float = 0.05  # DEF-3: Good-Turing missing-mass UCB ceiling to cure
    missing_mass_z: float = 1.64  # DEF-3: one-sided 95% confidence multiplier on the UCB
    recure_type_burst: int = 3  # R5: post-cure new-type count that reopens consolidation
    value_type_demotion: bool = True  # R02-H10: fold value-like types (PressureRange) at cure
    value_type_fraction: float = 0.6  # mean member value-likeness above which a type is demoted
    value_type_target: str = "Specification"  # type that absorbs demoted value-like types


class DriftSettings(BaseModel):
    remap_rate_threshold: float = 0.3
    window: int = 3
    rebuild_jsd_threshold: float = 0.15
    contradiction_rate_threshold: float = 0.2  # R8: fact-drift alarm on invalidations/window


class GraphRAGSettings(BaseModel):
    community_min_size: int = 3
    vector_index_name: str = "kgf_entity_embeddings"
    vector_dimensions: int = 1024
    top_k: int = 16  # R15-H53: vector seed budget (+28% relative pure-seed recall over 8)
    overfetch_factor: int = 4  # R15-H195a: fetch top_k*factor then truncate to top_k (GEN_K=64/16)
    fanout_cap: int = 5  # R19-H180: query-ranked 1-hop neighbor cap per seed (0 disables)
    miss_detector: bool = True  # R19-H181: short-circuit to an abstention render on the miss class
    miss_threshold: float = 0.668  # R19-H181: top-seed similarity below which the detector fires
    escalation_gate: bool = False  # R37-H382: sufficiency-gated render escalation
    # R38-H384: a-priori gate cut in index-score units - pile-fitted (H382), CRC
    # alpha=0.08 (H383), corpus-class-bound (H157); upgraded per corpus, never final
    escalation_threshold_prior: float = 0.765
    escalation_min_labels: int = 12  # R38-H385: refit floor; below it the record stands
    gate_calibration_path: Optional[str] = None  # R38-H384: frozen artifact, wins over graph
    passages_enabled: bool = False  # R34-H366: span store + query-anchored window (rung 2)
    passage_index_name: str = "kgf_passage_embeddings"
    passage_span_chars: int = 900  # H366 s900k1: window size; stride is half
    passage_top_k: int = 1  # spans appended to the render under escalation
    render_budget: float = 0.6  # R19-H182: keep the top-similarity mass share (1.0 disables)
    foreign_device_exclusion: bool = False  # R19-H205: optional - drop foreign-device sections
    prop_val_linkage: bool = True  # R19-H211: surface entities whose property value == a seed name
    proposition_split_max_tokens: int = 300  # R15-H173: split fat propositions (0 disables)
    ppr_enabled: bool = False  # R2 lever, H37-refuted: PPR is theater (0.994 containment in seeds+1hop) - off in the promoted composition, code retained for ablation
    ppr_top_n: int = 15  # R2: PPR nodes taken into the answer context
    ppr_damping: float = 0.85  # R2: PageRank damping
    propositions_enabled: bool = True  # R02-H11: fact sentences as retrieval targets
    proposition_index_name: str = "kgf_proposition_embeddings"
    proposition_top_k: int = 8  # propositions retrieved per query
    proposition_seeding: bool = True  # R03-H14: proposition hits extend the PPR seed set
    decompose_comparisons: bool = True  # R03-H15: split "A vs B" into per-entity retrievals
    abstention_enabled: bool = True  # R03-H17: structural coverage gate before generation
    abstention_min_score: float = 0.75  # min top seed/proposition score to attempt an answer
    context_head_tail: bool = True  # R03-H16: relevance-ordered head+tail context placement
    similarity_edges_enabled: bool = True  # R02-H13: kNN densification for PPR reach
    similarity_threshold: float = 0.8  # cosine gate for SIMILAR_TO edges
    similarity_top_k: int = 5  # neighbours considered per entity


class LoadSettings(BaseModel):
    batch_size: int = 500
    entity_versioning: bool = True  # snapshot prior entity state on content change
    provenance_nodes: bool = True  # R02-H12/S6: Chunk+Document nodes, MENTIONED_IN edges
    functional_relationship_types: list[str] = []  # single-valued rels: a new target supersedes


class Settings(BaseModel):
    lease_ttl_seconds: int = 180  # ingest run lease staleness window
    neo4j: Neo4jSettings = Neo4jSettings()
    # llm is the orchestrator/reasoning model: type clustering, contradiction and
    # defer judging, community summaries, query answering, seed normalization.
    llm: LLMSettings = LLMSettings()
    # extraction_llm is the high-volume per-chunk entity/relation extractor; when
    # None it falls back to llm. Splitting them lets a cheaper model do the bulk
    # extraction while a stronger model orchestrates (R9).
    extraction_llm: Optional[LLMSettings] = None
    embeddings: EmbeddingSettings = EmbeddingSettings()
    embedding_channels: EmbeddingChannels = EmbeddingChannels()
    ingest: IngestSettings = IngestSettings()
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

    # env fills gaps only - an explicit config-file value wins over ambient env
    # (a .env NEO4J_URI silently redirecting writes away from --config's target
    # contaminated a live graph on 2026-07-07; see docs/defects.md)
    yaml_neo4j = data.get("neo4j") or {}
    if os.environ.get("NEO4J_URI") and "uri" not in yaml_neo4j:
        settings.neo4j.uri = os.environ["NEO4J_URI"]
    if os.environ.get("NEO4J_USER") and "user" not in yaml_neo4j:
        settings.neo4j.user = os.environ["NEO4J_USER"]
    if os.environ.get("NEO4J_PASSWORD") and "password" not in yaml_neo4j:
        settings.neo4j.password = os.environ["NEO4J_PASSWORD"]

    return settings

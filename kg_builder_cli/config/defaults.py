"""Built-in default values matching the config.yml structure.

This file is the authoritative reference for all configuration parameter semantics.
Every setting includes its purpose, default value rationale, and valid range.

Not all parameters will be exposed in the user-facing config YAML. Expert-level
tuning parameters (thresholds, likelihood ratios, boost caps) are hardcoded here.
Only high-level feature toggles and parameters that meaningfully affect pipeline
behavior for non-expert users appear in config.yml.
"""

DEFAULTS: dict = {
    # ── Neo4j Connection ──────────────────────────────────────────────
    # Database connection settings. Values support ${ENV_VAR:default} interpolation.
    "neo4j": {
        # Bolt protocol URI for the Neo4j instance
        "uri": "${NEO4J_URI:bolt://localhost:7687}",
        # Database user for authentication
        "user": "${NEO4J_USERNAME:neo4j}",
        # Database password - should be set via environment variable, not config file
        "password": "${NEO4J_PASSWORD:}",
    },
    # ── LLM Provider ──────────────────────────────────────────────────
    # Language model configuration for extraction, resolution, and curing decisions.
    # No default provider or model - must be explicitly configured by the user.
    "llm": {
        # LLM provider backend: "bedrock" | "openai" | "anthropic"
        # No default - user must choose their provider
        "provider": None,
        # Model identifier - provider-specific format
        # Bedrock example: "eu.anthropic.claude-sonnet-4-20250514-v1:0"
        # OpenAI example: "gpt-4o"
        # Anthropic example: "claude-sonnet-4-20250514"
        # No default - user must choose their model
        "model": None,
        # Sampling temperature. 0.0 = deterministic output for reproducible extraction
        "temperature": 0.0,
        # AWS region for Bedrock. Ignored for other providers
        "region": None,
        # AWS profile name for credential resolution. None = default chain
        "profile": None,
        # Number of automatic retries on transient LLM errors (rate limits, timeouts)
        "max_retries": 3,
        # Request timeout in seconds. Extraction prompts with large chunks need 60-120s
        "timeout": 120,
    },
    # ── Extraction Pipeline ───────────────────────────────────────────
    # Controls document parsing, chunking, entity/relationship extraction, and resolution.
    "extract": {
        # Chunking strategy: "token" (fixed token windows) | "semantic" (embedding-based)
        # Token is cheaper and sufficient for most documents
        "chunking_strategy": "token",
        # Target chunk size in tokens. 2000 balances context richness with LLM cost.
        # Smaller chunks (500-1000) improve precision but miss cross-paragraph relationships.
        # Larger chunks (3000-4000) capture more context but increase extraction cost
        "chunk_size": 2000,
        # Overlap between consecutive chunks in tokens. Ensures entities spanning chunk
        # boundaries are captured in at least one chunk. 200 tokens ~= 1-2 paragraphs
        "chunk_overlap": 200,
        # Maximum concurrent LLM extraction calls per document. Limited by API rate limits
        # and memory. 4 is conservative; increase for high-throughput API tiers
        "concurrency": 4,
        # Extraction mode: "entity_relationship" (standard triplets) |
        # "graph_reader" (atomic facts) | "hybrid" (both, ~2x cost but best coverage)
        "extraction_mode": "hybrid",
        # When true, extraction output includes character offset spans linking each entity
        # and relationship back to exact source text positions. Adds latency (~10-15%)
        "evidence_spans": False,
        # When true, tracks how many source documents/chunks mention each entity.
        # Enables cross-document corroboration scoring. Small overhead per entity
        "source_frequency": False,
        # When true, extracts images from PDFs and generates text descriptions via
        # vision model before chunking. Dramatically enriches extraction from visual content
        "describe_images": False,
        # Vision model for image description. Required when describe_images=true.
        # Example: "anthropic.claude-sonnet-4-20250514-v1:0" (must support vision)
        "vision_model": None,
        # When true, splits large ontology schemas into subgraphs for separate extraction
        # passes. Prevents prompt overflow for ontologies with 20+ entity types
        "subgraph_splitting": False,
        # Number of recent extraction results passed as context to the next chunk's prompt.
        # 0 = no rolling context. 2-3 helps sequential documents maintain entity consistency
        "rolling_context_window": 0,
        # ── Within-type entity resolution ──
        # Levenshtein similarity threshold for merging entities within the same type block.
        # 0.85 catches "CPAP Machine" vs "CPAP machine" without false merges.
        # Range: 0.0-1.0. Lower = more aggressive merging
        "resolution_threshold": 0.85,
        # Minimum name similarity for the dual-threshold gate (name + embedding).
        # Lower than resolution_threshold because embeddings provide a second signal.
        # Only used when use_embeddings=true. Range: 0.0-1.0
        "name_threshold": 0.65,
        # Minimum cosine similarity between entity embeddings for merge approval.
        # Only used when use_embeddings=true. 0.80 = strong semantic match required.
        # Range: 0.0-1.0
        "embedding_threshold": 0.80,
        # When true, generates entity embeddings (Titan v2, 1024-dim) after dedup
        # for resolution and downstream vector search. Adds Bedrock embedding API cost.
        # Enabled by default for best extraction quality - embeddings significantly
        # improve entity resolution accuracy via dual-threshold matching
        "use_embeddings": True,
        # Embedding model for entity vectors. No default - must be configured by the user.
        # Bedrock example: "amazon.titan-embed-text-v2:0" (1024-dim)
        # OpenAI example: "text-embedding-3-small" (1536-dim)
        "embedding_model": None,
        # Embedding provider backend. Currently only "bedrock" is implemented.
        # Future: "openai", "anthropic", "sentence-transformers" (local).
        # No default - inherits from llm.provider if not set
        # TODO: implement multi-provider embedding support in embeddings.py
        "embedding_provider": None,
        # ── Bayesian type resolution (cured phase) ──
        # When true, enables Bayesian type resolver using exemplar index, relationship
        # context, co-occurrence, and description similarity. Activates after curing.
        # Enabled by default for best type assignment accuracy in cured phase
        "bayesian_resolution": True,
        # When true AND bayesian_resolution=true, ambiguous type assignments (high entropy)
        # are escalated to the LLM for a final decision. Adds 1 LLM call per ambiguous entity
        "llm_escalation": False,
        # When true, runs a lightweight LLM pre-flight pass to detect category signals
        # before full extraction. Helps the ontology buffer adapt constraints per document
        "schema_signal_extraction": False,
        # ── Cross-type entity resolution ──
        # Minimum description Jaccard similarity for cross-type merge evidence.
        # Floored at 0.3 in the Bayesian model to prevent descriptions that naturally
        # diverge across types from fully vetoing merges. Range: 0.0-1.0
        "cross_type_description_threshold": 0.3,
        # Minimum embedding cosine similarity for cross-type merge evidence.
        # Only used when both entities have embeddings. Range: 0.0-1.0
        "cross_type_embedding_threshold": 0.75,
        # Bayesian posterior threshold for cross-type entity merges.
        # Pairs with identical normalized names start at prior=0.8, so 0.6 merges most
        # same-name cross-type pairs unless evidence signals are weak. Range: 0.0-1.0
        "cross_type_merge_threshold": 0.6,
        # ── Deferred cross-type dedup (H5f, v21) ──
        # When true, ambiguous cross-type pairs (posterior between ambiguous_lower and
        # merge_threshold) are deferred to a buffer instead of permanently blocked.
        # Evidence accumulates across documents and pairs are resolved at curing time.
        # Enabled by default for best cross-type dedup quality
        "deferred_dedup": True,
        # Posterior below this value blocks the pair immediately (no deferral).
        # Pairs between this value and cross_type_merge_threshold are deferred.
        # Range: 0.0-cross_type_merge_threshold. Default 0.4 captures the ambiguous zone
        "deferred_dedup_ambiguous_lower": 0.4,
        # When true AND deferred_dedup=true, pairs still ambiguous after evidence
        # accumulation (posterior 0.4-0.6 with 2+ encounters) are escalated to the LLM.
        # The LLM receives entity name, both types with descriptions, evidence summary,
        # and optional graph context. Returns structured merge/block decision
        "deferred_dedup_llm_escalation": False,
    },
    # ── Ontology Buffer ───────────────────────────────────────────────
    # Controls the in-memory ontology buffer that evolves during ingestion.
    # Tracks entity types, relationship types, frequencies, and convergence.
    "ontology_buffer": {
        # Path to ontology seed file. Any format: OWL, YAML, markdown, plain text.
        # OWL parsed programmatically; others normalized via LLM. None = free extraction
        "seed_from": None,
        # Intent prompt guiding extraction toward a specific use case. Can be short
        # ("medical device comparison") or long (multi-sentence description of what
        # the knowledge graph should capture and how it will be queried). Passed to
        # extraction prompts to focus the LLM on relevant entity types, relationships,
        # and properties. A well-crafted intent dramatically improves extraction relevance.
        # None = generic extraction without domain focus
        "intent": None,
        # Maximum depth for OWL class hierarchy traversal during seed import.
        # 2 = classes and their direct subclasses. Deeper values import more specificity
        "seed_depth": 2,
        # Regex filter for OWL class URIs during seed import. Only matching classes
        # are imported. None = import all classes. Example: "^http://example.org/medical/"
        "seed_filter": None,
        # Ontology refinement frequency: run type clustering/merging every N documents.
        # Lower values refine more frequently (more LLM cost, tighter ontology sooner)
        "refine_every_n_docs": 5,
        # Minimum coverage ratio to consider ontology stable for the current document.
        # Coverage = fraction of extracted types matching known buffer types.
        # Below this threshold, extraction loosens type constraints. Range: 0.0-1.0
        "coverage_threshold": 0.5,
        # Minimum document frequency for a discovered type to be promoted to confirmed.
        # Types appearing fewer times remain candidates. 2 = seen in at least 2 documents
        "min_frequency_to_confirm": 2,
        # Minimum frequency for type emergence tracking. 1 = any single occurrence counts
        "min_frequency_to_emerge": 1,
        # When true, flush the final ontology state to .kg-builder/ontology.yml at
        # run completion. Free extraction produces a usable ontology as a side effect
        "flush_on_complete": True,
        # Maximum exemplar entities stored per type for Bayesian resolution.
        # More exemplars improve similarity matching but increase memory and comparison cost
        "max_type_exemplars": 5,
        # Number of top candidate types considered during Bayesian type resolution.
        # Higher values consider more alternatives but increase computation
        "type_resolution_top_k": 3,
        # Shannon entropy threshold for Bayesian type resolution confidence.
        # Below this = confident assignment; above = ambiguous, may trigger LLM escalation.
        # Range: 0.0-log2(top_k). Lower = stricter confidence requirement
        "type_resolution_entropy_threshold": 0.8,
        # When true, runs OWL reasoning (HermiT via owlready2) after graph loading
        # to materialize inferred relationships from ontology axioms
        "post_load_reasoning": False,
    },
    # ── Graph Loading ─────────────────────────────────────────────────
    # Controls how extracted entities and relationships are loaded into Neo4j.
    "load": {
        # How to handle existing entities: "merge" (MERGE Cypher, combines properties) |
        # "replace" (DELETE + CREATE) | "skip" (skip if exists)
        "merge_strategy": "merge",
        # Number of entities/relationships per Cypher batch transaction.
        # Higher values reduce transaction overhead but increase memory. 500 is safe default
        "batch_size": 500,
        # When true, creates Neo4j indexes (vector, fulltext, btree) after loading.
        # Uses IF NOT EXISTS for idempotency. Disable for append-only workflows
        "create_indexes": True,
        # When true, runs post-load validation: orphan node check, relationship counts,
        # entity type coverage against ontology
        "validate": True,
    },
    # ── Agent Memory ──────────────────────────────────────────────────
    # Persistent operational knowledge stored in .kg-builder/memory/.
    "memory": {
        # When true, agent stores and retrieves operational knowledge across sessions
        "enabled": True,
        # Maximum memory entries per data source. Older entries are evicted via LRU
        "max_entries_per_source": 100,
        # Time-to-live for memory entries in days. Entries older than this are pruned
        "ttl_days": 90,
    },
    # ── Curing ────────────────────────────────────────────────────────
    # Controls the two-phase fluid->cured ontology lifecycle. During the fluid phase,
    # the ontology evolves freely. Curing freezes the ontology when convergence is detected.
    "curing": {
        # When true, enables the fluid->cured lifecycle. When false, all documents
        # are processed in fluid mode with no schema freezing.
        # Enabled by default for best ontology quality through convergence detection
        "enabled": True,
        # Minimum documents before curing can trigger. Ensures enough data for stable
        # type distribution. Range: 1+. 3 prevents premature curing on small corpora
        "min_documents": 3,
        # Maximum documents in fluid phase before forced curing. Safety valve to prevent
        # unbounded fluid accumulation. Range: min_documents+. 20 suits medium corpora
        "max_fluid_documents": 20,
        # Maximum coverage ratio change between consecutive documents to signal stability.
        # Below this = ontology is stable. Range: 0.0-1.0. 0.05 = 5% tolerance
        "coverage_delta_threshold": 0.05,
        # Number of consecutive stable documents required before curing triggers.
        # Higher = more conservative curing. Range: 1+
        "stability_window": 3,
        # When true, curing triggers automatically when convergence criteria are met.
        # When false, curing requires manual approval (interactive mode)
        "auto_cure": True,
        # Window size for computing variance of stability metrics (JSD, entropy).
        # Used to detect metric plateau vs continued drift. Range: 3+
        "metrics_variance_window": 5,
        # Minimum ontology coverage ratio for cured-phase type enforcement.
        # Entities below this coverage threshold are remapped to nearest known type.
        # Range: 0.0-1.0
        "enforcement_threshold": 0.5,
        # Jensen-Shannon divergence threshold for convergence detection.
        # JSD below this between consecutive documents = type distribution is stable.
        # Range: 0.0-1.0. 0.01 = very tight convergence
        "jsd_convergence_threshold": 0.01,
        # Maximum Shannon entropy change between consecutive documents.
        # Below this = type diversity is stabilizing. Range: 0.0+
        "entropy_delta_threshold": 0.05,
        # Entropy delta threshold for plateau detection in the variance window.
        # When all recent entropy deltas are below this, the ontology has plateaued.
        # Range: 0.0+. 0.1 = moderate plateau sensitivity
        "plateau_entropy_delta": 0.1,
        # Entity type remap rate threshold for drift detection in cured phase.
        # If more than this fraction of entities are remapped over drift_window docs,
        # the pipeline re-enters fluid phase. Range: 0.0-1.0. 0.3 = 30% remap triggers drift
        "drift_remap_threshold": 0.3,
        # Number of consecutive documents to monitor for drift after curing.
        # Drift triggers when remap rate exceeds threshold for this many docs. Range: 1+
        "drift_window": 3,
        # When true AND drift is detected, pipeline re-enters fluid phase.
        # When false, drift is logged but the cured ontology persists
        "re_cure_on_drift": False,
        # When true, curing decisions use LLM analysis of stability metrics rather than
        # pure threshold-based rules. The LLM examines metric trends and graph queries
        "generative_curing": False,
        # Fraction of max_fluid_documents as consecutive "cure" votes needed for
        # auto-trigger. 0.4 * 20 = 8 consecutive docs voting to cure. Range: 0.0-1.0
        "generative_patience": 0.4,
        # Maximum graph query tool calls per LLM curing decision. Limits cost of
        # generative curing's graph inspection phase. Range: 0+
        "generative_max_tool_calls": 2,
        # Minimum Chao1 coverage estimate for curing eligibility.
        # Chao1 estimates total species (types) from observed frequencies.
        # Coverage = observed/estimated. 0.7 = we've likely seen 70%+ of all types.
        # Range: 0.0-1.0
        "min_chao1_coverage": 0.7,
        # Minimum confidence for type merge operations during curing.
        # Merges below this threshold are rejected. Range: 0.0-1.0
        "merge_confidence_threshold": 0.4,
    },
    # ── File Paths ────────────────────────────────────────────────────
    # Paths to resource directories. Relative to project root.
    "paths": {
        # Path to ontology YAML file. None = no seed, free extraction.
        # Supports any format (OWL, YAML, markdown, text) - normalized on load
        "ontology": None,
        # Path to schema descriptions directory for structured ingestion.
        # Contains YAML/markdown files describing JSON field semantics
        "schema": None,
        # Directory for agent memory persistence
        "memory": ".kg-builder/memory/",
        # Directory for schema migration plans and rollback scripts
        "migrations": ".kg-builder/migrations/",
    },
}

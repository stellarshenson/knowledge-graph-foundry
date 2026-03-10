# Design Assumptions Checklist

Tracks alignment between `docs/DESIGN.md` and the actual implementation. Each item is a verifiable fact from the design document checked against code.

Last verified: 2026-03-10 (v0.1.12, ontology grounding - drift detection, semantic resolution, signal-driven curing)

## Ontology Buffer (Section 5.5)

- [x] Buffer supports three initialization modes: from YAML seed, empty, and from OWL import
- [x] Buffer tracks entity types, relationship types, and frequency counts
- [x] Canonical mapping collapses surface variants during accumulation (first-seen wins)
- [x] Type tiers: confirmed (seed OR freq >= threshold), emerging (freq >= emerge_threshold), noise
- [x] Snapshot includes only confirmed + emerging types, excludes noise
- [x] Coverage = confirmed_count / total_entity_types
- [x] Buffer flush writes confirmed types to YAML
- [x] `min_frequency_to_confirm` default = 2
- [x] `min_frequency_to_emerge` default = 2
- [x] `TypeExemplar` model with name, entity_type, frequency fields stored in buffer `_type_exemplars`
- [x] Exemplar accumulation via `_update_exemplars()` in `accumulate_from_result()` with case-insensitive dedup and frequency-based replacement at capacity
- [x] Snapshot freezes exemplars as tuples sorted by descending frequency, included in `OntologyState.type_exemplars`
- [x] `max_type_exemplars` default = 5
- [x] **Schema signal extraction** - `extract_schema_signals()` in `schema_signals.py` provides a standalone lightweight LLM pre-pass via instructor+litellm. Enabled via `extract.schema_signal_extraction` (default false). `compute_coverage()` measures buffer coverage against detected signals. New signals accumulate into buffer before full extraction

## Post-Load Reasoning (Section 5.6)

- [x] **Cypher-based subclass propagation** - `run_subclass_propagation()` in `loading/reasoning.py` executes transitive `SUBCLASS_OF*` traversal to infer `INSTANCE_OF` edges. Integrated into `load_extraction()` when `ontology_buffer.post_load_reasoning` is enabled (default false). Full `owlready2` sync_reasoner and RDF export are not implemented - Cypher-first approach covers the transitive subclass use case

## Schema Curing (Section 5.8)

- [x] Curing disabled by default (`curing.enabled = false`)
- [x] CLI flags: `--fluid` / `--no-fluid` and `--cure` for force-cure
- [x] Three-condition detection: min_documents, coverage delta convergence, type stability window
- [x] Failsafe: `max_fluid_documents` (default 20)
- [x] Two-layer type normalization: deterministic (always-on) + LLM clustering (at curing time)
- [x] `normalize_type_name()` splits on spaces, underscores, hyphens, camelCase boundaries -> PascalCase
- [x] Type clustering via single LLM call with instructor + litellm structured output
- [x] Enforcement threshold prunes low-frequency types before clustering (default 0.5%)
- [x] All 11 stability metrics computed: Shannon entropy, KL divergence, JS divergence, Gini, Zipf R-squared, Heaps' beta, Chao1, ACE, accumulation rate, rolling variance
- [x] `CuringDetector.is_converged()` checks metric-based convergence (JSD, entropy delta, type accumulation rate) before heuristic fallback
- [x] `CuringDetector.is_plateau()` checks metric plateau (JSD, entropy delta, coverage delta) without requiring type accumulation rate = 0
- [x] `is_cured()` heuristic fallback preserved for backward compatibility
- [x] New config fields: `jsd_convergence_threshold` (default 0.01), `entropy_delta_threshold` (default 0.05)
- [x] `plateau_entropy_delta` (default 0.1) - looser entropy threshold for plateau detection
- [x] Curing check order: `is_converged()` -> `is_plateau()` -> `is_cured()` -> `is_force_required()` (safety net)
- [x] `max_fluid_documents` is the sole safety net with WARN-level logging
- [x] **Metrics tracked post-cure** - cured-phase loop records JSD, Chao1 coverage, and entropy delta for each document using the same `StabilityMetrics` tracker
- [x] **Post-cure drift detection** - `CuringDetector.check_drift(remap_rate)` tracks remap rate per document. When rate exceeds `drift_remap_threshold` (default 0.3) for `drift_window` (default 3) consecutive docs, drift is signaled. Warning-only by default, opt-in re-curing via `re_cure_on_drift`
- [x] `ExtractionMetadata.remap_count` tracks entities force-remapped during type enforcement
- [x] Drift config: `drift_remap_threshold` (0.3), `drift_window` (3), `re_cure_on_drift` (false)
- [x] **Generative curing advisory** - `generative_curing` config (default false). When enabled, LLM replaces metric-based curing checks after `min_documents`. LLM always receives full metrics snapshot as per-document timeline. LLM failure falls through to metric-based checks (`is_converged`, `is_plateau`, `is_cured`). Safety net (`max_fluid_documents`) overrides LLM advisory. Re-cure: LLM replaces `re_cure_on_drift` boolean when enabled, falls back to boolean on LLM failure
- [x] **Graph query tool** - two-phase structured output: first LLM call returns `CureProbe` with optional `needs_query=True`. If metrics are ambiguous (JSD 0.02-0.08 or Chao1 0.5-0.75) and accumulator available, executes `query_fluid()` against in-memory FluidAccumulator, then second call with enriched context produces `CureDecision`. For LLM escalation in type resolution, `query_graph()` executes against Neo4j when top-2 posterior gap < 0.15. Three query types: `entity_counts`, `relationship_patterns`, `entity_search`. Max `generative_max_tool_calls` (default 2) per decision
- [x] **Early stopping patience** - `CuringDetector` tracks consecutive LLM "cure" votes per document via `record_llm_vote()` / `patience_exceeded()`. Threshold is `generative_patience` (default 0.4) as fraction of `max_fluid_documents` with minimum 3. At default settings: 0.4 * 20 = 8 consecutive document cure votes to auto-trigger. Counter resets on "don't cure" vote. Check order updated: patience check after LLM decision, before metric fallback
- [x] Config: `generative_patience` = 0.4 (fraction of max_fluid_documents), `generative_max_tool_calls` = 2
- [ ] **Proposed composite curing mechanism** (design lines 999-1007) - described as future work, not implemented. Would use weighted metric composite instead of three-condition heuristic

## Type Exemplars and Bayesian Resolution (Section 5.8)

- [x] Extraction prompt injects exemplar hints via `_build_entity_types_block()`: `"- Component: desc (e.g., Humidifier, Tubing) (seen 42x)"`
- [x] `ExemplarIndex` wraps FAISS IndexFlatIP over L2-normalized 1024-dim Titan v2 embeddings
- [x] Index built at curing time in `cli.py._build_exemplar_index()` from frozen exemplars
- [x] `BayesianTypeResolver` computes posterior from prior (type frequencies) * exemplar likelihood (FAISS cosine) * relationship likelihood (name-matching heuristic)
- [x] Pipeline step 4b conditionally routes through `_resolve_types_bayesian()` when `bayesian_resolution=true` and exemplar index available
- [x] Cold-start fallback: no index -> `_enforce_ontology_types()` (Levenshtein)
- [x] `bayesian_resolution` default = false (opt-in)
- [x] `type_resolution_top_k` default = 3
- [x] `type_resolution_entropy_threshold` default = 0.8
- [x] **Co-occurrence pattern** `P(co_entities | type)` - `_cooccurrence_likelihood()` counts same-chunk entities matching candidate type, range [1.0, 2.0]. Chunk-entity index built in `_resolve_types_bayesian()` before the entity loop
- [x] **Description semantics** `P(description | type)` - `_description_likelihood()` computes bag-of-words overlap between entity description and type exemplar descriptions, range [1.0, 2.0]. `TypeExemplar` model extended with `description` field, populated in `buffer._update_exemplars()`
- [x] **LLM escalation for high-entropy cases** - `_llm_resolve()` makes sync instructor+litellm call when entropy exceeds threshold and `llm_escalation=true`. Falls back to argmax on exception or invalid type. Disabled by default via `extract.llm_escalation`

## Curing Data Flow

- [x] Fluid phase: extract -> accumulate -> buffer.accumulate_from_result -> metrics.record -> detector.record -> check curing
- [x] Curing event: prune low-frequency -> snapshot -> cluster_types -> apply_type_mapping -> normalize_entity_ids -> consolidate -> load
- [x] Consolidation order: enforce types -> normalize IDs -> deduplicate -> resolve entities -> rewire relationships
- [x] Cured phase: per-document ingest_document -> resolve_against_graph -> load_doc_chunks + load_extraction(skip_doc_chunks=True)
- [x] **Cured-phase cross-document resolution** - `resolve_against_graph()` queries Neo4j for existing entities with same normalized name but different types, remaps incoming entities to match existing graph types and IDs, and rewires relationships
- [x] **Cured-phase document-chunk linkage** - `load_doc_chunks()` loads Document + Chunk nodes first, then `load_extraction(skip_doc_chunks=True)` loads entities + relationships only, preserving per-document Document-Chunk structure

## Unstructured Pipeline (Section 6)

- [x] Pipeline: parse -> chunk -> extract -> dedup -> resolve -> load
- [x] Type enforcement runs BEFORE ID normalization (fixed in v10)
- [x] ID generation: `sha1("{normalized_type}:{normalized_name}")[:12]`
- [x] Entity deduplication by (type, id) tuple with merge strategy
- [x] Relationship deduplication by (source, target, type) tuple
- [x] Entity resolution within type blocks (Levenshtein + optional embeddings)
- [x] Cross-type resolution with dynamic frequency-based priority and description similarity gate
- [x] `_description_similarity()` Jaccard similarity on lowercased word sets, excluding stop words
- [x] `cross_type_description_threshold` (default 0.3) gates cross-type merges - empty descriptions default to no merge
- [x] `resolve_against_graph()` applies description similarity gate before remapping entity types
- [x] Static fallback priority: Specification(8) > Component(7) > Feature(6) > WorkMode(5) > Product(4) > MedicalCondition(3) > Standard(2) > Organization(1)
- [x] Step 4b supports conditional Bayesian resolution (when enabled) or Levenshtein fallback
- [x] Relationship rewiring after cross-type merges
- [x] Embedding generation via Amazon Titan Text Embeddings v2
- [x] Dual-threshold gate: name_sim >= 0.65 AND cosine >= 0.80
- [x] Fallback: name Levenshtein >= 0.85 when no embeddings

## Config Defaults

- [x] `resolution_threshold` = 0.85
- [x] `name_threshold` = 0.65
- [x] `embedding_threshold` = 0.80
- [x] `min_documents` = 3
- [x] `max_fluid_documents` = 20

- [x] `coverage_delta_threshold` = 0.05
- [x] `stability_window` = 3
- [x] `metrics_variance_window` = 5
- [x] `enforcement_threshold` = 0.5
- [x] `max_type_exemplars` = 5
- [x] `type_resolution_top_k` = 3
- [x] `type_resolution_entropy_threshold` = 0.8
- [x] `bayesian_resolution` = false
- [x] `plateau_entropy_delta` = 0.1
- [x] `drift_remap_threshold` = 0.3
- [x] `drift_window` = 3
- [x] `re_cure_on_drift` = false
- [x] `generative_curing` = false
- [x] `generative_patience` = 5
- [x] `generative_max_tool_calls` = 2
- [x] `cross_type_description_threshold` = 0.3

## Known Gaps (prioritized)

1. **Composite curing mechanism** - design lines 999-1007 describe a weighted metric composite for curing detection, replacing the three-condition heuristic. Not yet implemented, current system uses `is_converged()` (metric-based) with `is_plateau()` (metric plateau) and `is_cured()` (heuristic fallback)
2. **Full OWL reasoning** - `owlready2` sync_reasoner and RDF export are not implemented. Cypher-based subclass propagation covers the transitive case but does not handle full OWL semantics (disjointness, property restrictions, cardinality constraints)

## Resolved Gaps

- **Cured-phase cross-document resolution** - resolved via `resolve_against_graph()` in `loader.py`, which queries Neo4j for existing entities and remaps types/IDs before loading
- **Post-cure metric tracking** - resolved by continuing `StabilityMetrics.record()` and `CuringDetector.record()` calls in the cured-phase loop
- **Progression-based curing signal** - resolved via `CuringDetector.is_converged()` using JSD, entropy delta, and type accumulation rate thresholds
- **Bayesian co-occurrence likelihood** - resolved via `_cooccurrence_likelihood()` using chunk-entity index for same-chunk type matching
- **Bayesian description semantics** - resolved via `_description_likelihood()` with bag-of-words overlap against type exemplar descriptions (exemplars now carry `description` field)
- **LLM escalation for high-entropy** - resolved via `_llm_resolve()` using sync instructor+litellm call, opt-in via `extract.llm_escalation`
- **Schema signal extraction** - resolved via standalone `extract_schema_signals()` in `schema_signals.py`, opt-in via `extract.schema_signal_extraction`
- **OWL subclass propagation** - resolved via Cypher-based `run_subclass_propagation()` in `loading/reasoning.py`, opt-in via `ontology_buffer.post_load_reasoning`
- **max_fluid_entities removed** - entity count was a blunt failsafe replaced by signal-driven curing (plateau detection, metric convergence). `max_fluid_documents` remains as the sole safety net

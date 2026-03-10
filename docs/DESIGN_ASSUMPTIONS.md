# Design Assumptions Checklist

Tracks alignment between `docs/DESIGN.md` and the actual implementation. Each item is a verifiable fact from the design document checked against code.

Last verified: 2026-03-10 (v0.1.11, post v12 implementation)

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
- [ ] **Schema signal extraction** - design section 5.4 describes a lightweight first-pass signal extraction as a separate step; implementation integrates signals into the main extraction pipeline without a standalone function

## Post-Load Reasoning (Section 5.6)

- [ ] **OWL reasoning not implemented** - design describes `owlready2` sync_reasoner, RDF export, Cypher-based subclass propagation. Config has `post_load_reasoning: false` but no code executes this. Disabled by default, no implementation present

## Schema Curing (Section 5.8)

- [x] Curing disabled by default (`curing.enabled = false`)
- [x] CLI flags: `--fluid` / `--no-fluid` and `--cure` for force-cure
- [x] Three-condition detection: min_documents, coverage delta convergence, type stability window
- [x] Failsafe: `max_fluid_documents` (default 20)
- [x] Failsafe: `max_fluid_entities` (default 150)
- [ ] **Design prose says max_fluid_entities default 50,000** (line 939) but config example and code use 150 - prose is wrong, implementation is correct
- [x] Two-layer type normalization: deterministic (always-on) + LLM clustering (at curing time)
- [x] `normalize_type_name()` splits on spaces, underscores, hyphens, camelCase boundaries -> PascalCase
- [x] Type clustering via single LLM call with instructor + litellm structured output
- [x] Enforcement threshold prunes low-frequency types before clustering (default 0.5%)
- [x] All 11 stability metrics computed: Shannon entropy, KL divergence, JS divergence, Gini, Zipf R-squared, Heaps' beta, Chao1, ACE, accumulation rate, rolling variance
- [x] `CuringDetector.is_converged()` checks metric-based convergence (JSD, entropy delta, type accumulation rate) before heuristic fallback
- [x] `is_cured()` heuristic fallback preserved for backward compatibility
- [x] New config fields: `jsd_convergence_threshold` (default 0.01), `entropy_delta_threshold` (default 0.05)
- [x] **Metrics tracked post-cure** - cured-phase loop records JSD, Chao1 coverage, and entropy delta for each document using the same `StabilityMetrics` tracker
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
- [ ] **Co-occurrence pattern** `P(co_entities | type)` - designed in DESIGN.md evidence source 3, deferred to future iteration
- [ ] **Description semantics** `P(description | type)` - designed in DESIGN.md evidence source 4, deferred to future iteration
- [ ] **LLM escalation for high-entropy cases** - designed as agent reasoning fallback, current implementation uses argmax regardless of entropy

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
- [x] Cross-type resolution with dynamic frequency-based priority
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
- [x] `max_fluid_entities` = 150
- [x] `coverage_delta_threshold` = 0.05
- [x] `stability_window` = 3
- [x] `metrics_variance_window` = 5
- [x] `enforcement_threshold` = 0.5
- [x] `max_type_exemplars` = 5
- [x] `type_resolution_top_k` = 3
- [x] `type_resolution_entropy_threshold` = 0.8
- [x] `bayesian_resolution` = false

## Known Gaps (prioritized)

1. **Bayesian evidence sources incomplete** - co-occurrence pattern and description semantics likelihoods designed but deferred. Current resolver uses only prior + exemplar similarity + relationship context. Adding these would improve resolution accuracy for entities where name similarity alone is insufficient
2. **LLM escalation for ambiguous types** - design describes agent reasoning for high-entropy posterior cases. Implementation falls back to argmax. Low priority since most entities resolve confidently via prior alone
3. **Schema signal extraction** - design describes lightweight first-pass, implementation skips this and does full extraction. Minor impact since full extraction subsumes signal extraction
4. **OWL reasoning** - designed but disabled and unimplemented. Low priority since OWL import works for ontology seeding
5. **max_fluid_entities prose** - design text says 50,000 but should say 150. Documentation fix only

## Resolved Gaps

- **Cured-phase cross-document resolution** - resolved via `resolve_against_graph()` in `loader.py`, which queries Neo4j for existing entities and remaps types/IDs before loading
- **Post-cure metric tracking** - resolved by continuing `StabilityMetrics.record()` and `CuringDetector.record()` calls in the cured-phase loop
- **Progression-based curing signal** - resolved via `CuringDetector.is_converged()` using JSD, entropy delta, and type accumulation rate thresholds

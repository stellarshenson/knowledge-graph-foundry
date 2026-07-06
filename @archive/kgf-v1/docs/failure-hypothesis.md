# Failure Hypothesis Analysis

## Historical Context

| Version | Score | Key Failures | Fix Applied |
|---------|-------|-------------|-------------|
| v08 | 88 | Baseline (8 curated types) | - |
| v09 | 81 | Type proliferation (31 types) | First fluid mode |
| v10-v13 | 76 | Singleton types, bad merges | Surface normalization, clustering, merge validation |
| v14-v15 | 73 | Double enforcement, 12 singletons | Min-score 0.7 on type enforcement |
| v17 | 72 | HAS_SPECIFICATION=0, SUPPORTS_MODE=1 | Clustering prompt hardening |
| v18 | 82 | Cross-type duplicates=56 | Intent-driven discovery model |
| v19 | 84 | Cross-type duplicates=39 | Bayesian cross-type dedup, SUPPORTS_MODE fix |
| v20 | 88 | Cross-type duplicates=52 | Expanded judge context (no pipeline changes) |
| v21 | 88 | Cross-type duplicates=48 | H5f deferred cross-type dedup (minimal impact) |
| v23 | 83 | Hierarchy completely inert, 0 merges | H5g hierarchy + intent/guide (hierarchy non-functional) |

## Resolved Hypotheses

### H1: Double Type Enforcement (FIXED in v15)

Type clustering (LLM-assisted) ran at curing time, then `_enforce_ontology_types()` ran AGAIN inside `accumulator.consolidate()` and overwrote those decisions. Fix: `skip_type_enforcement=True` during consolidation when clustering has already run.

### H2: Cross-Type Resolution Ignores Embeddings (FIXED in v15)

Added embedding cosine similarity as secondary gate in `_resolve_cross_type()`. When description Jaccard < 0.3 AND both entities have embeddings AND cosine >= 0.75, merge proceeds.

### H3: Specification Entities Lack Structured Properties (PARTIALLY ADDRESSED in v18)

Regex post-parser rejected. Intent prompt improved spec extraction - generative spec score rose from 2/5 to 4/5 in v18. Some specs still lack numeric values.

### H4: No Domain Compass (FIXED in v18)

Five structural changes: intent prompt, emerge threshold=1, relationship types use emerge threshold, removed pre-clustering pruning, Chao1 floor=0.5. Deterministic jumped from 87% to 95%.

---

## Active Hypotheses (v19 Failures)

### H5: Cross-Type Entity Duplication (56 -> 39 duplicates)

**Status**: Partially addressed in v19 - still primary bottleneck

**Evidence from graph**: 20 distinct entity names appear with multiple types. Dominant patterns:
- **Accessory vs Component** (7/20): humidifier, tubing, power cord, SD card, heated tube, headgear, filters. These physical parts are legitimately both components (inside the device) and accessories (sold separately)
- **Feature vs Interface vs Setting** (5/20): AHI (3 types), mask fit (3 types), ramp button (3 types), modem (3 types), supplemental oxygen (3 types). UI-adjacent concepts where the type boundary is genuinely ambiguous
- **Feature vs Section** (2/20): limited warranty, device alert

**Root cause analysis**: Five pipeline gaps allow cross-type duplicates through:

1. **Dedup key includes type** - `dedup.py` uses `(type.lower(), id.lower())` as dedup key. Entity IDs encode type in hash input: `{type}:{name}`. Same entity with different types produces different IDs, so dedup treats them as distinct
2. **Description gate too conservative** - `_resolve_cross_type()` requires Jaccard >= 0.3 on filtered words. "AHI" as Specification ("Apnea Hypopnea Index severity measure") vs Interface ("screen displaying nightly AHI value") has ~0% word overlap despite being the same real-world concept
3. **Embedding fallback requires embeddings** - The cosine fallback (>= 0.75) only triggers when both entities have embeddings. In consolidation during curing, entities from earlier docs may lack embeddings if `use_embeddings` wasn't active for those docs
4. **No cross-type awareness in type clustering** - `cluster_types()` operates on type NAMES only. It merges `RegulatoryStandard -> Standard` but cannot detect that "humidifier" appears as both Component and Accessory
5. **Cured-phase `resolve_against_graph()` only remaps incoming entities** - Does not retroactively clean duplicates already in the graph from the curing flush

**Industry approaches**:

- **Neo4j graphrag-python**: Uses post-write `SinglePropertyExactMatchResolver` that groups by label then merges within same label. Explicitly does NOT merge across labels. Also offers `SpaCySemanticMatchResolver` and `FuzzyMatchResolver`. Their architecture accepts cross-type duplicates as a design tradeoff
- **Graphiti (Zep)**: Uses entropy-gated fuzzy matching with hybrid search (embedding + text overlap) for entity dedup. Constrains edge dedup to same entity pairs. Their temporal KG approach handles updates rather than bulk construction
- **Microsoft GraphRAG**: Uses community detection (Leiden algorithm) to cluster entities post-extraction, then generates community summaries. Cross-type entities naturally cluster together if they share relationships

**Proposed fix strategies** (ordered by complexity):

**H5a - Name-identity merge override** (REJECTED as too simplistic): When normalized entity names are identical, always merge regardless of description similarity. While this addresses all 20 current groups, it only handles exact matches and provides no infrastructure for harder cases like "CPAP humidifier" vs "heated humidifier" or "AirSense 10" vs "AirSense 10 AutoSet" where names are similar but not identical.

**H5b - Post-curing graph consolidation**: After the curing flush loads entities to Neo4j, run a Cypher-based consolidation pass that identifies same-name different-type nodes and merges them using `apoc.refactor.mergeNodes()` or equivalent Cypher. This catches duplicates that the in-memory pipeline missed. Neo4j's own resolver follows this pattern (post-write resolution).

**H5c - Type coercion in extraction prompt**: Add explicit instructions to the constrained prompt: "If an entity was previously extracted as type X, always use type X for that entity regardless of the current context." Pass a lookup of known entity-to-type mappings from the buffer. This prevents cross-type creation at the source.

**H5d - Community detection consolidation**: Apply Louvain/Leiden community detection on the loaded graph to find entity clusters that should be merged. Entities sharing many relationships and similar names but different types would cluster together. This is the GraphRAG approach but adds a GDS dependency.

**H5e - Bayesian posterior for cross-type resolution** (IMPLEMENTED in v19): Replaced the binary description-similarity gate in `_resolve_cross_type()` with a multi-signal Bayesian posterior `P(same_entity | evidence)`. Four evidence signals combine via odds form:

- **Name identity prior** - identical normalized names get prior=0.8, fuzzy matches get prior=0.2
- **Description similarity LR** - Jaccard on filtered words, floored at 0.3 (never fully vetoes)
- **Embedding cosine LR** - Titan v2 cosine similarity when available (strong signal)
- **Source chunk co-occurrence LR** - shared chunks boost merge (1.5), no overlap is neutral (0.9)

Merge threshold: `cross_type_merge_threshold=0.6` (configurable in ExtractConfig). Same logic applied in `resolve_against_graph()` for cured-phase Neo4j resolution with case-insensitive `toLower()` query.

**v19 results**: Cross-type duplicates dropped from 56 to 39 (30% reduction). 34 Bayesian merges approved, 99 blocked. The remaining 39 duplicates have posteriors below 0.6 - entities with identical names but divergent descriptions, no embeddings from the graph side, and no shared source chunks. The Bayesian model successfully merges all cases where description similarity or co-occurrence provides supporting evidence, but cannot resolve purely name-based matches where descriptions are semantically unrelated (e.g., "Filter" as Component="physical air filter" vs Feature="data smoothing algorithm").

**Remaining gap analysis**: The 39 surviving duplicates fall into two categories: (1) genuinely ambiguous entities where the type boundary is real (e.g., "humidifier" IS both a component and an accessory in different contexts - 15-20 entities), and (2) entities that should merge but lack sufficient evidence signals in the current model (no shared chunks, no embeddings in graph-side resolution, very different descriptions - 19-24 entities). Category 2 could be addressed by H5b (post-curing graph consolidation) or H5c (type coercion in extraction prompt) as next steps.

### H6: SUPPORTS_MODE Benchmark Check (FIXED in v19)

**Status**: Resolved - was a benchmark bug, not an extraction failure

**Root cause**: The benchmark query filtered on `toLower(b.type) = 'mode'` but the ontology has no `Mode` entity type. Modes are extracted as `Feature` or `Setting` entities (e.g., "CPAP Mode" as Feature, "standby mode" as Setting). The graph contains 36 SUPPORTS_MODE relationships created via APOC as native Neo4j relationship types (`type(r)` returns them correctly, `r.type` property is null since APOC creates typed relationships natively, not RELATES_TO with a type property).

**Fix**: Changed the benchmark query to match entities with "mode" in their name and type in `['feature', 'setting']`, with an expanded relationship type list including HAS_FEATURE and HAS_SETTING. Deterministic score improved from 60/63 to 61/63.

### H7: Case Normalization Gaps (PARTIALLY FIXED in v19)

**Status**: Addressed in `resolve_against_graph()`, folded into H5e

**Fix applied**: `resolve_against_graph()` now queries Neo4j with `toLower(e.name) IN $names` using pre-normalized lowercase names, preventing case-sensitive mismatches between "Headgear" in the graph and "headgear" in extraction. The Bayesian posterior in `_resolve_cross_type()` uses `normalize_entity_name()` which lowercases, so in-memory cross-type resolution was already case-insensitive. The remaining case-sensitivity gaps are in dedup key generation (`dedup.py` uses `entity.id.lower()` which already lowercases) and entity ID hashing (which uses normalized names). No further action needed - case normalization is consistent across all comparison points.

### H8: Generative Query Answerability Disconnect (FIXED in v20)

**Status**: Resolved - was a benchmark measurement problem, not a graph quality problem

**Root cause**: The generative judge's context window was too narrow. The single query returned `a.name, type(r), b.name, b.type, left(b.description, 60)` which truncated descriptions at 60 chars and didn't include `b.value`, `b.unit`, or other spec properties. The LLM judge correctly reported it couldn't see specific pressure ranges, weights, or dimensions even though they existed in the graph. Deterministic scored 9/10 (data exists) while generative scored 2/5 (judge can't see it).

**Fix applied**: Replaced single-query judge with three-query approach in `tests/benchmark_multidoc.py`: (1) product/org outgoing relationships with 200-char descriptions and LIMIT 300, (2) dedicated specification detail query returning `value`, `unit` properties for all Specification entities, (3) mode and standard coverage query for Feature/Setting entities with "mode" in name plus Standard entities with compliance links. Also enriched cross_doc_resolution prompt with 120-char entity descriptions. Increased JSON truncation from 8000 to 12000 chars, max_tokens from 200 to 300.

**v20 results**: query_answerability jumped from 2/5 to 4/5. Generative average rose from 3.6/5.0 to 4.0/5.0. Hybrid score: 84 -> 88. Zero pipeline changes - purely benchmark query expansion. This confirms the v19 diagnosis that the 84 ceiling was a measurement artifact.

## Priority Matrix (v19 -> v20)

| Hypothesis | Impact | Complexity | Priority | Status |
|-----------|--------|-----------|----------|--------|
| H5e (Bayesian cross-type) | +2 actual | High | Done | 56->39 dupes, +2 hybrid |
| H6 (SUPPORTS_MODE check) | +1 actual | Low | Done | Benchmark bug fixed |
| H7 (case normalization) | folded | Low | Done | toLower() in graph query |
| H8 (generative context) | +4 actual | Medium | Done | Judge 2/5->4/5, hybrid +4 |
| H5 residual (52 dupes) | +2-4 est | Medium | 1 | H5b/H5c as next steps |

**v19 outcome**: H5e delivered +2 (82 -> 84), not the +5-8 estimated. The Bayesian model merges all evidence-supported pairs but cannot resolve the remaining duplicates where descriptions diverge and no co-occurrence or embedding evidence exists. The gap between estimated (+5-8) and actual (+2) reflects that ~20 of the remaining duplicates are genuinely ambiguous (the entity IS both a component and an accessory) rather than resolution failures.

**v20 outcome**: H8 delivered +4 (84 -> 88), matching the +3-5 estimate. The multi-query judge approach with full spec properties and 200-char descriptions gave the LLM judge adequate context. query_answerability jumped 2/5 -> 4/5 with zero pipeline changes - confirming this was purely a benchmark measurement problem. Cross-type duplicates at 52 this run (variance from non-deterministic extraction). All other generative scores held steady (manufacturer 5/5, product 4/5, cross_doc 3/5, spec 4/5).

## Priority Matrix (v23 -> v24)

| Hypothesis | Impact | Complexity | Priority | Status |
|-----------|--------|-----------|----------|--------|
| H5g fix (self-evolving buffer) | +3-5 est | Medium | 1 | Implementing - hierarchy was inert in v23 |
| H9 (cross_doc generative) | +1-2 est | Low | 2 | Will improve as duplicates drop |
| H10 (SleepStyle modes) | +1 est | Low | 3 | Extraction or linking gap |
| H5g-D (synonym resolution) | +1-2 est | High | 4 | 36 tubing variants, 38 filter variants |

**v23 outcome**: H5g delivered +0 from hierarchy (83% hybrid, -5 from v20). The hierarchy was completely inert - zero hierarchy merges, zero hierarchy entries in flushed ontology, all 133 cross-type decisions via Bayesian fallback. Root causes: post-ingestion-only evolution timing, document-count threshold, auto-merge bypassing the Bayesian model. The v24 fix targets all three root causes with the self-evolving buffer model.

## Priority Matrix (v20 -> v21)

| Hypothesis | Impact | Complexity | Priority | Status |
|-----------|--------|-----------|----------|--------|
| H5f (deferred cross-type dedup) | +2-4 est | Medium | 1 | Implementing |
| H9 (cross_doc generative) | +1-2 est | Low | 2 | Prompt tuning |
| H10 (SleepStyle modes) | +1 est | Low | 3 | Extraction or linking gap |

### H9: Cross-Doc Resolution Generative Stuck at 3/5

**Status**: Active - minor bottleneck

**Evidence**: cross_doc_resolution scores 5/6 (83%) deterministic but 3/5 generative. The judge sees duplicate counts with descriptions and correctly notes "fundamental CPAP components like tubing, filters, headgear still appear duplicated". However, many of these are genuinely multi-typed (Component + Accessory) rather than resolution failures.

**Root cause**: The judge cannot distinguish genuine type ambiguity from resolution failures even with descriptions. A "humidifier" as Component ("internal heating element for moisture delivery") and as Accessory ("replaceable water chamber sold separately") are genuinely different aspects of the same physical object.

**Proposed fix**: Either improve the prompt to explicitly instruct the judge that Component/Accessory overlap is expected for physical parts, or address H5 residual to reduce the duplicate count below the judge's concern threshold.

### H10: SleepStyle Modes Not Linked

**Status**: Active - minor deterministic failure

**Evidence**: The deterministic check "What modes does SleepStyle support?" fails. SleepStyle 200 supports CPAP mode but the extraction may not create a mode Feature/Setting entity linked to the SleepStyle product.

**Root cause**: The SleepStyle manual describes operating modes within general operating instructions rather than as a dedicated "modes" section. The extraction LLM may not recognize these as distinct mode entities worth extracting, or may extract them without linking to the product.

### v21 Cross-Type Duplicate Analysis (Graph Query Evidence)

47 duplicate groups producing 97 total nodes (50 excess). Only 1 within-type duplicate exists (`standby state` as Setting x2), confirming within-type resolution works well. The problem is entirely cross-type.

**Duplicate breakdown by type pair pattern**:

| Pattern | Count | Examples |
|---------|-------|---------|
| Component/Accessory | 21 | filter, humidifier, mask, headgear, sd card, tubing, heated tube, modem |
| Feature/Setting | 8 | ramp, auto on, auto off, reslex, time setting, humidity setting |
| Setting/Specification | 4 | ahi, ramp time, altitude, therapy pressure |
| Component/Interface | 3 | display, ramp key, control dial |
| Component/Specification | 3 | air outlet, power supply, 80w power supply |
| Feature/Specification | 3 | flex pressure relief, supplemental oxygen, humidity |
| Triple+ (3 types) | 2 | accessories (Component/Section/Accessory), mask fit (Interface/Feature/Setting) |
| Other pairs | 3 | ramp button (Feature/Component), apnea (MedicalCondition/Feature), periodic breathing (MedicalCondition/Interface) |

**Semantic analysis of descriptions** reveals three categories:

1. **Same concept, different perspective** (mergeable - ~25 groups): Both descriptions refer to the same physical thing viewed from different angles. Example: `humidifier` as Component ("Integrated humidifier component with maximum fill level of 290 mL") vs Accessory ("Optional accessory with usage tracking"). These should be one entity

2. **Same name, genuinely different aspects** (ambiguous - ~15 groups): Descriptions capture meaningfully different facets. Example: `ahi` as Specification ("Apnea/Hypopnea Index - measurement specification"), Interface ("Screen displaying nightly AHI value"), Setting ("The average AHI in the selected period"). These might warrant separate entities or a multi-faceted entity

3. **Same name, clearly same thing** (resolution failure - ~7 groups): `ramp` as Feature ("gradually increases pressure") vs Setting ("displays ramp starting pressure") - these describe the same ramp feature from documentation vs UI perspectives

**Topology signal analysis (Component/Accessory pairs)**:

Relationship target Jaccard overlap ranges from 0% to 29%. Highest: `sd card` (29%), `integrated heated humidifier` (29%), `flexible tubing` (25%), `humidifier` (21%). Lowest: `heated tube` (0%), `circuit tubing` (0%), `breathing circuit` (0%). The topology signal is weak because Component variants connect to internal parts (heater plate, water tank) while Accessory variants connect to products (HAS_ACCESSORY). They share product targets but diverge on component-level neighbors

**Name variant proliferation in Component/Accessory**: The tubing concept alone has 36 entity nodes across both types: `tube`, `tubing`, `heated tube`, `heated tubing`, `breathing tube`, `circuit tubing`, `flexible tubing`, `air tubing`, `connecting tubing`, `delivery tubes`, `standard tube`, `SlimLine tubing`, `ClimateLineAir heated tube`, plus size variants (12mm, 15mm, 19mm, 22mm). Similarly, `filter` has 38 nodes. This is a within-type synonym problem compounding the cross-type problem

### H5f: Deferred Cross-Type Dedup with Evidence Accumulation (v21)

**Status**: Implemented - minimal impact

**Approach**: Instead of making a permanent merge/block decision at the first encounter, pairs with posteriors in the ambiguous zone (0.4-0.6) are deferred to a buffer. Evidence accumulates across documents - co-occurrence, relationship target overlap (topology signal), and descriptions. At curing time, the buffer resolves all deferred pairs with the full evidence picture. Pairs still ambiguous after accumulation can be escalated to the LLM.

**Three-zone logic** replaces the binary threshold:
- posterior >= 0.6 -> merge immediately (unchanged)
- 0.4 <= posterior < 0.6 -> defer to buffer (NEW)
- posterior < 0.4 -> block immediately (unchanged)

**New evidence dimension - topology signal**: Jaccard overlap of relationship targets between the two entity type variants. Entities sharing many relationship neighbors are likely the same entity viewed from different perspectives.

**Configuration**: `deferred_dedup: true` (default), `deferred_dedup_ambiguous_lower: 0.4`, `deferred_dedup_llm_escalation: false`.

**Implementation**: `kg_builder_cli/extraction/deferred_dedup.py` (DeferredPair, DeferredDedupBuffer, MergeDecision), integrated into `resolution.py` and `accumulator.py`.

**v21 results**: Cross-type duplicates 52 -> 48 (only 4 fewer). The deferred buffer infrastructure works but most ambiguous pairs remain below 0.6 even after evidence accumulation. The topology signal (relationship target overlap) rarely fires because entity variants with different types tend to have different relationship neighborhoods - a Component connects to other Components while an Accessory connects to Products. Co-occurrence boost is similarly weak because same-name cross-type entities are typically extracted from different chunks.

**Post-mortem**: The hypothesis assumed that evidence accumulation would push ambiguous pairs above the merge threshold. In practice, the evidence signals (topology, co-occurrence, description convergence) are too weak for most cross-type pairs because the type difference genuinely manifests in different relationship patterns and descriptions. The 0.4-0.6 ambiguous zone contains mostly legitimately ambiguous entities (the entity IS both types) rather than resolution failures that more evidence would resolve. H5f adds robustness for corpora where the same entity is described consistently across documents, but for the CPAP benchmark where type ambiguity is real, the buffer accumulates evidence that confirms the ambiguity rather than resolving it.

**Conclusion**: The deferred dedup infrastructure is sound but the cross-type duplicate problem is fundamentally ontological, not evidential. Next approaches should target the ontology itself (type merging, type hierarchy) or accept multi-type entities as a valid graph pattern rather than trying to force single-type resolution.

## Priority Matrix (v21 -> v22)

| Hypothesis | Impact | Complexity | Priority | Status |
|-----------|--------|-----------|----------|--------|
| H5f (deferred cross-type dedup) | +0 actual | Medium | Done | 52->48 dupes, no hybrid change |
| H5g (ontology-enriched resolution) | +4-8 est | Medium | 1 | Hierarchy + resolution intent/guide + multi-label + exemplars |
| H9 (cross_doc generative) | +1-2 est | Low | 4 | Will improve automatically as duplicates drop |
| H5g-D (synonym resolution) | +1-2 est | High | 5 | 36 tubing variants, 38 filter variants need consolidation |
| H10 (SleepStyle modes) | +1 est | Low | 6 | Extraction or linking gap |

**v21 outcome**: H5f delivered +0 (88 -> 88), well below the +2-4 estimate. The deferred buffer resolved only 4 additional pairs. Graph query analysis revealed the problem is structural: 47 duplicate groups with 50 excess nodes, dominated by Component/Accessory (21 groups) and Feature/Setting (8 groups) where the type boundary reflects genuine dual roles rather than resolution failures. Additionally, within-type synonym proliferation (36 tubing nodes, 38 filter nodes) compounds the problem. The fix requires ontology-level changes (type hierarchy, multi-facet entities) not stronger resolution algorithms.

### H5g: Ontology-Enriched Type Resolution (v22-v24)

**Status**: Partially implemented (v22-v23), hierarchy fix in v24

**Design philosophy**: One enriched ontology, not two. The approach draws from OntoType's coarse-to-fine entity typing via type hierarchy (Komarlu et al., KDD 2024), AFET's hierarchical partial-label embedding for multi-type entities (Ren et al., EMNLP 2016), and ontology-grounded type disambiguation under Wikidata (Feng et al., KDD Workshop 2024). Instead of a separate resolution rules engine, we enrich the ontology with three layers: hierarchy for structural dedup, prose guidance for extraction-time disambiguation, and multi-labels for legitimate dual-role entities. The hierarchy is a dedup resolution strategy, not general extraction guidance - it materializes inside resolution machinery and gets flushed to ontology YAML for the next run. See `references/ontology/` for full paper summaries.

**Problem decomposition**: The 47 duplicate groups break into three categories addressed by a unified approach:

**Layer 1 - Type hierarchy** (structural, targets 29 groups: 21 Component/Accessory + 8 Feature/Setting):

New `type_hierarchy` section in ontology YAML defines parent-child subsumption: `Part` -> `[Component, Accessory]`, `Behavior` -> `[Feature, Setting]`. The hierarchy is NOT injected into extraction prompts - it lives exclusively in the resolution machinery. In `_resolve_cross_type()`, entities with same name under shared parent auto-merge (skip Bayesian) using frequency-based type priority. In fluid mode (no ontology seed), hierarchy starts empty and is discovered from data via `evolve_type_hierarchy()` when cross-type patterns meet conservative thresholds (>= 3 documents). Implementation: `TypeHierarchyEntry` model in `types/ontology.py`, `shared_parent()` on buffer, hierarchy check in `_resolve_cross_type()`.

**Layer 2 - Resolution intent + resolution guide** (prose guidance, targets ~7 inconsistent groups + prevents recurrence):

Two-layer prose guidance in ontology YAML. `resolution_intent` is the user-authored immutable prior describing type assignment rules. `resolution_guide` is the system-evolved section that accumulates learned disambiguation rules across runs when `resolution_guide_evolution` is enabled (default true). Both are injected into extraction prompts, capped at `max_resolution_intent_tokens`. The intent captures domain expertise; the guide captures lessons from data. The original intent is never modified by the system.

**Layer 3 - Multi-facet entities** (multi-label, targets 10 groups: Setting/Specification, Feature/Specification):

Entities appearing as both a configurable parameter and a measured value (e.g., `ramp time` as Setting and Specification) carry multiple type labels via `entity.labels`. Loader uses `apoc.create.addLabels(n, row.labels)` for multi-label Neo4j nodes. For cross-type pairs where both types are under different hierarchy parents, both labels are preserved rather than merged.

**Exemplar injection**: `type_exemplars` section in ontology YAML provides concrete disambiguation examples per type, auto-flushed from accumulated extraction patterns and user-curated between runs.

**Combined expected impact**: Layers 1+2+3 address all 47 groups. Layer 1 eliminates sibling-type duplicates through hierarchy. Layer 2 prevents type inconsistencies at extraction time. Layer 3 preserves legitimate multi-facet entities as multi-label nodes. Target: cross-type duplicates < 15, hybrid score 90+.

**Implementation files**: `types/ontology.py` (TypeHierarchyEntry, OntologyState extensions), `types/extraction.py` (Entity.labels), `ontology/buffer.py` (load/save hierarchy+intent+guide+exemplars, evolve_type_hierarchy, evolve_resolution_guide, cross_type_stats), `extraction/prompts.py` (resolution_guidance_block for intent+guide prose), `extraction/resolution.py` (hierarchy safety net, CrossTypeStat reporting), `loading/loader.py` (multi-label APOC), `types/config.py` (hierarchy_resolution, resolution_guide_evolution).

**v23 post-mortem - hierarchy completely inert**: v23 benchmark scored 83% hybrid (60/63 deterministic, 3.6/5.0 generative) - a 5-point drop from v20 (88%). Log forensics revealed that H5g hierarchy resolution was completely inert: zero hierarchy merges occurred across 10 documents, the flushed ontology contained 0 hierarchy entries, and all 133 cross-type decisions went through Bayesian fallback with none through the hierarchy path. Three root causes identified:

1. **Evolution timing**: `evolve_type_hierarchy()` only ran once post-ingestion (`cli.py:115`), never per-document. The hierarchy didn't exist during resolution because cross-type stats accumulate during ingestion but evolution never triggered mid-ingestion
2. **Document-based threshold**: `GUIDE_EVOLUTION_MIN_DOCUMENTS=3` counted distinct source documents, not encounter frequency. For the CPAP corpus structure, this threshold was never reached during the post-ingestion-only call because the function was called after all documents were already processed
3. **Hierarchy bypassed the model**: The original design auto-merged siblings without Bayesian evaluation. Even if the hierarchy had materialized, sibling types would have auto-merged regardless of description divergence - no evidence gate

**v24 fix - self-evolving buffer with frequency threshold**: Replace post-ingestion evolution with a self-evolving buffer where `record_cross_type_stats()` triggers `_maybe_evolve()` after each stats recording. Replace `GUIDE_EVOLUTION_MIN_DOCUMENTS` with `GUIDE_EVOLUTION_MIN_ENCOUNTERS` (encounter frequency, not document count). Replace hierarchy auto-merge with hierarchy-boosted Bayesian prior (0.95 for siblings under shared parent). The model decides all merges - hierarchy is evidence, not an override.

**Strategy D - Within-type synonym resolution** (deferred, compounds all categories):

The tubing concept has 36 nodes and filter has 38 nodes across Component/Accessory. Even after cross-type merging, name variants (`heated tube`, `heated tubing`, `Heated Tubing`, `15H tubing`) remain as separate within-type entities. Current Levenshtein resolution catches `tube`/`Tube` but not semantic synonyms like `circuit tubing`/`connecting tubing`. Options: (1) embedding-based clustering within type groups post-extraction, (2) LLM-assisted synonym detection during curing consolidation, (3) stricter normalization rules for common variant patterns (plurals, adjective prefixes). Deferred to a later iteration.

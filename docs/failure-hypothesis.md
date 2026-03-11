# Failure Hypothesis Analysis

## Historical Context

| Version | Score | Key Failures | Fix Applied |
|---------|-------|-------------|-------------|
| v08 | 88% | Baseline (8 curated types) | - |
| v09 | 81% | Type proliferation (31 types) | First fluid mode |
| v10-v13 | 76% | Singleton types, bad merges | Surface normalization, clustering, merge validation |
| v14-v15 | 73% | Double enforcement, 12 singletons | Min-score 0.7 on type enforcement |
| v17 | 72% | HAS_SPECIFICATION=0, SUPPORTS_MODE=1 | Clustering prompt hardening |
| v18 | 82% | Cross-type duplicates=56 | Intent-driven discovery model |

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

## Active Hypotheses (v18 Failures)

### H5: Cross-Type Entity Duplication (56 duplicates)

**Status**: Active - primary bottleneck for v19

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

**H5e - Bayesian duplicate candidates buffer** (SELECTED): Build a duplicate candidates buffer that accumulates cross-type evidence across documents during the fluid phase, then resolves at curing time using Bayesian posterior scoring. This extends the existing `BayesianTypeResolver` pattern (already in `kg_builder_cli/extraction/type_resolver.py`) from type assignment to entity identity.

The buffer tracks candidate pairs `(entity_a, entity_b)` where normalized names match or are similar. For each pair, it accumulates evidence signals across documents:

- **Name similarity** - normalized Levenshtein or exact match (strongest signal for identical names)
- **Embedding cosine** - semantic similarity from Titan v2 embeddings (catches fuzzy matches like "heated humidifier" vs "humidifier")
- **Shared relationship patterns** - if both entities participate in similar relationship types (HAS_COMPONENT, HAS_FEATURE) with overlapping neighbours
- **Cross-document frequency** - entities appearing in more documents with the same name strengthen the merge case
- **Description semantics** - bag-of-words and embedding overlap on descriptions

The posterior `P(same_entity | evidence)` determines the resolution path. High confidence (above threshold) triggers automatic merge with type selection via frequency-based priority. Low confidence defers to LLM escalation or keeps entities separate. This approach solves the immediate 20 exact-match groups AND provides infrastructure for future fuzzy duplicate detection.

Key design insight: the buffer doesn't need to resolve immediately. It accumulates evidence during fluid phase and resolves as a batch operation during curing, when the full picture is available. This is structurally similar to how `FluidAccumulator` defers loading until curing.

### H6: SUPPORTS_MODE Benchmark Check (Possible False Negative)

**Status**: Needs investigation

**Evidence**: The graph actually contains 25 SUPPORTS_MODE relationships. The benchmark check reports 0. The deterministic check may be using wrong Cypher or looking for a specific pattern that doesn't match the actual relationship structure.

**Action**: Review the benchmark query for SUPPORTS_MODE to determine if it's a real extraction failure or a benchmark bug.

### H7: Case Normalization Gaps

**Status**: Active - contributes to cross-type duplicates

**Evidence**: "Headgear" vs "headgear", "Mask Fit" vs "Mask fit", "Ramp Button" vs "Ramp button", "Supplemental oxygen" vs "supplemental oxygen" survive as separate nodes. The `normalize_entity_name()` function exists but case-insensitive matching may not be applied at all comparison points.

**Action**: Audit all name comparison points to ensure case-insensitive normalization.

### H8: Generative Query Answerability Disconnect (2/5)

**Status**: Active - secondary bottleneck

**Evidence**: The deterministic query_answerability scores 9/10 (90%), but the generative judge gives 2/5 claiming "no feature comparisons, pressure ranges, mode specifications, component lists, compliance standards, or technical specifications like weight/dimensions/sound levels in the provided relationships." This suggests the LLM judge receives a limited view of the graph (relationship sample) that doesn't represent the full graph content.

**Action**: Review the Cypher queries used to populate the generative judge's context. The graph has rich spec data (deterministic confirms pressure, weight, sound, dimension specs pass) but the judge doesn't see it.

## Priority Matrix

| Hypothesis | Impact | Complexity | Priority |
|-----------|--------|-----------|----------|
| H5e (Bayesian duplicate buffer) | +5-8% | High | 1 |
| H6 (SUPPORTS_MODE check) | +1-2% | Low | 2 |
| H8 (generative context) | +3-5% | Medium | 3 |
| H7 (case normalization) | +1-2% | Low | 4 (folded into H5e) |

H5e subsumes H5a (exact matches are trivially high-confidence pairs in the Bayesian model) and H7 (case normalization becomes part of the candidate detection phase). H5b and H5c remain as fallback strategies if H5e proves insufficient.

Combined expected: 82% -> 92-98% hybrid score.

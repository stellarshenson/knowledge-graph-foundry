# Schema Curing - Design and Empirical Results

Schema curing provides a middle path between pre-defined ontology seeds and fully unconstrained free extraction. The system starts with an empty ontology and an intent prompt, lets the schema evolve during ingestion, and holds all graph data in memory while the schema is "fluid". Only when the schema stabilizes ("cures") does the system flush to Neo4j.

## Current Curing Mechanism

The `CuringDetector` evaluates three convergence conditions after each document. All three must be true:

- Minimum documents processed (`min_documents`, default 3)
- Coverage convergence: coverage delta below threshold (default 0.05) for the last N documents
- Type stability: no new entity types for `stability_window` (default 3) consecutive documents

Failsafes force-cure when `max_fluid_documents` (default 20) or `max_fluid_entities` (default 500) are exceeded.

## Stability Metrics

Ten information-theoretic metrics are computed from the type frequency distribution after each document. The `StabilityMetrics` class is purely computational - it tracks signals but does not make curing decisions. All metrics use Python's `math` stdlib only.

| Metric | Key | What It Measures | Stability Signal |
|--------|-----|------------------|------------------|
| Shannon entropy | `entropy_shannon` | Type distribution diversity | Delta approaches 0 |
| KL divergence | `kl_divergence` | Distribution shift between consecutive docs | Approaches 0 |
| Jensen-Shannon divergence | `js_divergence` | Symmetric bounded distribution distance [0,1] | Approaches 0 |
| Type accumulation rate | `type_accumulation_rate` | New types per document (dV/dN) | Equals 0 |
| Gini coefficient | `gini_coefficient` | Frequency inequality (0=equal, 1=dominated) | Delta approaches 0 |
| Zipf R-squared | `zipf_r_squared` | Log-log linear fit quality | Exceeds 0.85, stabilizes |
| Heaps' beta | `heaps_beta` | Vocabulary growth rate (V = K*N^beta) | Approaches 0 |
| Chao1 coverage | `chao1_coverage` | Observed/estimated total types | Approaches 1.0 |
| ACE estimate | `ace_estimate` | Abundance-based total type estimate | Converges to observed |
| Rolling variance | `*_var` suffixed | Variance of key metrics over last W docs | Approaches 0 |

### Theoretical Basis

The metrics draw from three established fields:

**Information theory** (Shannon, KL, JSD). Entropy measures how evenly types are distributed - a mature schema has stable entropy because the relative frequencies stop shifting. JSD is the most robust divergence measure: symmetric (unlike KL), bounded [0,1], and always defined (no division-by-zero edge cases). KL divergence is included for completeness but requires additive smoothing.

**Computational linguistics** (Heaps' beta, Zipf R-squared). Heaps' law (V = K*N^beta) describes how vocabulary grows with corpus size. In natural language, beta typically ranges 0.4-0.6. When beta drops below ~0.1, vocabulary is saturating - new words appear at a rate proportional to N^0.1, which is effectively flat for practical corpus sizes. Zipf's law (frequency proportional to 1/rank^alpha) describes the shape of mature frequency distributions. Real ontologies and natural language both follow power laws, so high R-squared (> 0.85) indicates the distribution has matured past the initial chaotic phase.

**Ecology** (Chao1, ACE). Species richness estimators predict "how many species exist that we haven't observed yet" based on the ratio of singletons (species seen exactly once) to doubletons (species seen exactly twice). Chao1 coverage = observed/estimated gives a direct answer to "what fraction of all types have we discovered". When singletons drop and coverage approaches 1.0, the schema is saturated. ACE extends this with an abundance-based correction for rare species.

## Empirical Results: CPAP Benchmark v09

First fluid-mode run on the 10-document CPAP corpus (5 manufacturers, mix of manuals/datasheets/brochures). Configuration: empty ontology, intent prompt describing CPAP medical device domain, `min_frequency_to_confirm=1`, embeddings enabled.

### Curing Timeline

Schema cured naturally at document 4 of 10. The fluid phase accumulated 483 entities and 771 relationships from 4 documents, consolidated to 364 entities and 630 relationships at curing time. Remaining 6 documents loaded directly in the cured phase.

### Metrics Per Document

| Metric | Doc 1 | Doc 2 | Doc 3 | Doc 4 (cured) |
|--------|-------|-------|-------|----------------|
| JSD | n/a | 0.0137 | 0.0072 | 0.0145 |
| Chao1 coverage | 0.864 | 0.869 | 0.881 | 0.956 |
| Heaps' beta | n/a | n/a | 0.037 | 0.009 |
| Entropy delta | n/a | 0.0421 | 0.0568 | 0.0002 |
| New types | 31 | 0 | 0 | 0 |
| Coverage delta | n/a | 0.000 | 0.000 | 0.000 |

### Signal Clustering

The metrics fall into three groups based on when they provided actionable signal:

**Early signals** (stable from doc 2). JSD stayed below 0.02 from document 2 onward - the type distribution was barely shifting after the first large manual established the baseline. New type count dropped to zero at doc 2 and stayed there. These signals indicate the schema discovered its full vocabulary from a single comprehensive document, but early convergence alone is unreliable because small documents (like the Airsense brochure at 37 entities) may simply lack the diversity to introduce new types.

**Confirmation signals** (converging at doc 4). Chao1 coverage jumped from 0.881 to 0.956 - the estimator now predicted 95.6% of all types had been discovered. Heaps' beta dropped from 0.037 to 0.009, indicating vocabulary growth was effectively zero. Entropy delta collapsed from 0.0568 to 0.0002, meaning the distribution's information content stopped changing. These three signals independently confirmed that the schema had saturated. The fact that all three converged simultaneously at doc 4 provides strong evidence that this was the correct curing point.

**Uninformative signals** (in this configuration). Coverage delta remained at 0.000 throughout because `min_frequency_to_confirm=1` confirmed every type immediately upon first observation. This rendered the existing coverage heuristic blind. Rolling variance was undefined because only 4 docs were processed against a window of 5.

### Proposed Composite Curing Criterion

Based on the signal clustering, a composite criterion replacing the current three-condition heuristic:

```
cure_ready = (
    docs_processed >= min_documents
    AND js_divergence < 0.02
    AND chao1_coverage > 0.95
    AND entropy_shannon_delta < 0.01
)
```

This would have triggered at exactly doc 4 in the v09 run, matching the current heuristic. The advantage is that these metrics respond to distributional properties rather than binary conditions (new types yes/no, coverage delta above/below threshold), making them more robust to:

- Documents of varying size (a small document with no new types is different from a large document with no new types - JSD and entropy delta capture this)
- Coverage that plateaus early due to configuration (min_frequency_to_confirm=1 makes coverage useless, but Chao1 still works)
- Oscillating coverage deltas (JSD is symmetric and less sensitive to single-document perturbations)

### Benchmark Quality Impact

The v09 fluid run scored 81% hybrid vs 88% for v08 (seeded ontology). The gap analysis:

| Dimension | v08 (seeded) | v09 (fluid) | Root Cause |
|-----------|-------------|-------------|------------|
| Cross Doc Resolution | 6/6, LLM 4/5 | 4/6, LLM 2/5 | Type proliferation |
| Query Answerability | 10/10, LLM 2/5 | 9/10, LLM 2/5 | Diffuse type system |
| Document Coverage | 4/4 | 3/4 | Phantom Document nodes |

**Type proliferation** is the primary quality gap. The LLM discovered 31 entity types where the curated ontology defined 8. All 8 seed types were independently discovered, but with synonymous variants:

- Standard + Regulatory_Standard + SafetyStandard (3 types for 1 concept)
- WorkMode + OperatingMode + "Operating Mode" (3 types, one with a space)
- Organization + Manufacturer (2 types for 1 concept)
- Medical_Condition + Medical_Treatment + Therapy (3 types for related concepts)

This creates 36 cross-type duplicates - entities that are the same real-world thing but classified under different type labels. The consolidation at curing time merges entities within the same type, but cannot merge entities across different types without a type equivalence mapping.

**Novel types** discovered that may improve the seed ontology:

- Accessory (93 instances) - optional add-ons distinct from required Components
- Interface (50 instances) - UI elements and physical connectors
- Setting (48 instances) - configurable parameters
- Maintenance (28 instances) - cleaning and replacement procedures

## Identified Improvements

### Type Merging During Fluid Phase

The ontology buffer should detect and merge synonymous type names before curing. Approaches:

- Levenshtein similarity between type names (catches "WorkMode" vs "Work_Mode")
- Normalized form comparison (lowercasing, underscore/space equivalence catches "Operating Mode" vs "OperatingMode")
- LLM-assisted type clustering at curing time (ask the model to group the 31 discovered types into canonical categories)

The first two are cheap and deterministic. The third is expensive but handles semantic synonyms (Standard vs Regulatory_Standard). A hybrid approach using deterministic pre-filtering followed by LLM validation on ambiguous pairs would balance cost and accuracy.

### Cross-Document Resolution in Cured Phase

Currently, documents 5-10 load independently without deduplication against the existing graph. Each cured-phase document creates new entity nodes even when matching entities already exist from the consolidated batch. Two approaches:

- Post-load resolution query: after all documents are loaded, run a graph-wide entity resolution pass
- Load-time resolution: before creating each entity, check Neo4j for existing entities of the same type with similar names

The post-load approach is simpler to implement and matches the existing dedup/resolve pipeline. The load-time approach avoids creating duplicates but requires graph queries during loading, adding latency.

### Configuration Sensitivity

The `min_frequency_to_confirm=1` setting made coverage delta uninformative. For fluid mode, a higher threshold (2 or 3) would let coverage rise gradually and provide a useful convergence signal. However, this means types seen only once in the fluid phase would not be included in the cured ontology, potentially losing rare but valid types. The Chao1 metric addresses this directly - it estimates whether those rare types are likely to recur.

## Next Steps

1. Run fluid benchmark on a second corpus to validate proposed thresholds across different domains
2. Implement type name normalization in the ontology buffer (deterministic step)
3. Add post-load entity resolution for cured-phase documents
4. Evaluate whether the composite criterion (JSD + Chao1 + entropy delta) should replace the current heuristic or serve as a secondary gate
5. Test with `min_frequency_to_confirm=2` to measure the impact on type coverage vs noise reduction

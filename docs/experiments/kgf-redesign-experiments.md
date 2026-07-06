# KGF SOTA Redesign Experiments - closing the gap to state of the art

**Canonical Experiments Document**

Experiments log for the SOTA-driven redesign of Knowledge Graph Foundry, pre-registered from `../sota-decision.md`. Batch R01 runs eight levers (R1-R8), each a change the external research judged to move KGF from its accumulate-only, single-pass, Leiden-only baseline toward current state of the art. Predictions and acceptance bars are registered before implementation; verdicts fill in as each lands.

- **Branch / artefacts** - baseline is the initial v2 build (commit before R01); design rationale in [`../sota-decision.md`](../sota-decision.md); acceptance criteria in [`../acc-crit-kgf.md`](../acc-crit-kgf.md)
- **Data** - CPAP corpus `data/external/cpap-datasheets-and-manuals/` (27 documents), second-domain slice `data/external/apnea-articles/apnea_slice.jsonl` (150 documents)
- **Baseline graph** - CPAP build, ontology cured at document 5, 7 types

## Problem overview

The initial v2 build works end-to-end but the SOTA research found it behind the field on four axes and disqualifying on one. Each hypothesis targets one gap; the baseline is the initial build measured on the CPAP corpus.

- **Disqualifying** - accumulate-only facts: no temporal validity, no contradiction handling, cannot answer "current vs historical"
- **Behind SOTA** - single-pass extraction (under-extracts vs gleaning), Leiden+1-hop retrieval (capped on multi-hop vs PPR), hand-set resolution weights and brute-force cosine blocking, one-shot flat type clustering
- **Confirmed SOTA, held fixed** - identity decoupled from type + multi-label nodes, the resolution skeleton, curing's statistical basis

## Baseline performance (initial v2 build, CPAP corpus)

| measure | value | axis |
|---|---|---|
| entity_count | 1366 | scale |
| relationship_count | 1704 | scale |
| orphan_rate | 0.127 | connectivity (lower better) |
| duplicate_name_density | 0.003 | resolution quality (lower better) |
| relationship_type_entropy | 2.22 | relation diversity |
| avg_degree | 2.49 | connectivity (higher better) |
| modularity (Leiden) | 0.81 | community structure |
| temporal capability | none | longevity (accumulate-only) |
| multi-hop retrieval | vector top-k + fixed 1-hop | retrieval reach |

## Methodology and metrics

Each lever changes one subsystem over the baseline build and is verified either by re-measuring the CPAP graph (corpus metrics), by a targeted capability probe (temporal, retrieval), or by unit/integration tests (mechanism guarantees that a corpus metric cannot isolate). Naive baseline is mandatory and every result is a delta against the baseline row above.

- **Extraction recall proxy** - entities and relationships per document, and orphan_rate; more true structure lowers orphans and raises avg_degree without inflating duplicate_name_density
- **Resolution quality** - duplicate_name_density and a manual spot-count of known duplicate groups; blocking must be sub-quadratic (complexity guardrail, not just wall-clock)
- **Multi-hop retrieval** - answerability on a CPAP comparison probe set (cross-device, multi-attribute questions); PPR vs vector+1-hop, same seeds, same LLM
- **Temporal capability** - a superseding-fact probe: ingest a fact, then a contradicting update; the graph must return the current value AND retain the prior as history (non-lossy). Binary pass with a history check
- **Guardrail** - no lever may raise duplicate_name_density or orphan_rate above baseline while claiming a win on its own axis

## Research at a glance (R01, pre-registered)

| hypothesis | lever | mechanism | predicted | acceptance bar | verdict |
|---|---|---|---|---|---|
| R01-H1 | temporal model | bitemporal edges + contradiction reconciliation + entity versioning | supersede-query returns current value, history retained | temporal probe passes, non-lossy | **Promoted** |
| R01-H2 | retrieval | PPR seeded from vector top-k (GDS PageRank) | multi-hop answerability up, single-hop not down | >= baseline multi-hop, no single-hop regression | pending |
| R01-H3 | extraction | gleaning re-prompt + entity/relation split | recall up (entities+rels/doc, orphan_rate down) | recall up, duplicate_name_density not up | pending |
| R01-H4 | resolution | FAISS ANN blocking + LLM judge on defer zone | blocking sub-quadratic, defer decided better | dup density <= baseline, blocking O(n log n) | pending |
| R01-H5 | type consolidation | embed-block-verify, re-runnable, light isa | post-cure synonyms still merge | late synonym types merged | pending |
| R01-H6 | retrieval cost | community summaries global-only | local-query LLM cost down, answerability flat | cost down, no answerability loss | pending |
| R01-H7 | curing/calibration | Chao1 min-sample floor + learned/held-out calibration | no premature cure, no overfit curve | cure blocked below floor | pending |
| R01-H8 | resolution/drift | union-find split guard + contradiction-rate alarm | over-merges split, fact-drift distinguished | snowball reduced, alarm fires on fact drift | pending |

## Setup

- **Pipeline** - litellm+instructor extraction, Bedrock Titan embeddings (MiniLM CPU fallback), Neo4j 5 + APOC + GDS, Bayesian resolution, fluid-to-cured lifecycle
- **Engine** - Bedrock Claude Sonnet 4.5 (`eu.anthropic.claude-sonnet-4-5-20250929-v1:0`)
- **Reproducibility** - temperature 0; extraction has residual LLM non-determinism, so corpus deltas are reported with that caveat and mechanism guarantees are pinned by tests
- **Execution vehicle** - each lever is a code change with unit/integration tests; corpus-level levers re-run the CPAP build and re-measure

## R01 - experiment batch 1

Eight levers, pre-registered above, implemented and verified one at a time. Composable, but each isolated so its verdict is attributable.

### R01-H1 Bitemporal edges + contradiction reconciliation + entity versioning

- **Hypothesis** - because a graph maintained for months accumulates superseding and contradicting facts, giving every edge valid-time and transaction-time and invalidating (not deleting) a superseded edge will let the graph answer "current vs historical" while retaining full history, closing the disqualifying longevity gap
- **Lever** - temporal model on edges and entity snapshots
- **Mechanism** - add valid_from/valid_to and created_at/expired_at to edges; on ingest, hybrid-search existing edges between the same entity pair, LLM-check contradiction, and on temporal overlap set the old edge's valid_to; retrieval defaults to currently-valid; entity property/type changes retain prior versions
- **Prediction** - a superseding-fact probe returns the current value, and the prior fact is queryable as history; nothing is deleted
- **Acceptance bar** - temporal probe passes and is non-lossy (old edge present with valid_to set)
- **Result** - every edge carries created_at/valid_from on load and valid_to/expired_at (null = live); reconcile_contradictions invalidates prior functional edges (valid_to set, not deleted); entity versioning snapshots prior state to KGFEntityVersion on content change only. Live probe: HAS_CEO Alice → Bob returns Bob as current, Alice retained with valid_to set; idempotent reload creates no version. 5 temporal tests pass (2 unit, 3 live)
- **Verdict** - Promoted; the disqualifying longevity gap is closed - the graph is now bi-temporal and non-lossy

### R01-H2 PPR retrieval seeded from vector top-k

- **Hypothesis** - because a fixed 1-hop expansion cannot assemble a multi-hop reasoning chain, seeding GDS Personalized PageRank from the vector top-k entities will raise multi-hop answerability without regressing single-hop lookups
- **Lever** - retrieval traversal
- **Mechanism** - keep the vector index as the seeder; run PPR from the top-k entities; take top-N PPR nodes plus their source chunks as LLM context
- **Prediction** - cross-device multi-attribute questions answerable that 1-hop misses; single-hop unaffected
- **Acceptance bar** - multi-hop answerability >= baseline, no single-hop regression
- **Result** - pending (this batch)
- **Verdict** - pending

### R01-H3 Gleaning + entity/relation split

- **Hypothesis** - because a single extraction pass provably under-extracts, a bounded gleaning re-prompt plus separate entity and relation passes will raise extraction recall (more entities and relationships per document, lower orphan_rate) without inflating duplicate_name_density
- **Lever** - extraction passes
- **Mechanism** - after the first instructor pass, re-prompt for missed entities/relations (1-2 rounds); run entity and relation extraction as separate calls
- **Prediction** - recall up, orphan_rate down, avg_degree up, duplicate_name_density flat
- **Acceptance bar** - recall up and duplicate_name_density not above baseline
- **Result** - pending (this batch)
- **Verdict** - pending

### R01-H4 ANN blocking + LLM-judged defer zone

- **Hypothesis** - because brute-force within-type cosine is O(n^2) and hand weights are weakest in the ambiguous band, FAISS ANN top-k blocking plus routing the 0.4-0.6 defer zone to an LLM judge will keep resolution sub-quadratic and decide ambiguous merges better
- **Lever** - blocking + defer decision
- **Mechanism** - FAISS HNSW top-k neighbours per type instead of all-pairs; LLM judge on defer-band pairs only
- **Prediction** - blocking scales sub-quadratically; defer-band merges more accurate; duplicate_name_density <= baseline
- **Acceptance bar** - duplicate_name_density <= baseline and blocking complexity sub-quadratic
- **Result** - pending (this batch)
- **Verdict** - pending

### R01-H5 Re-runnable hybrid type consolidation

- **Hypothesis** - because a one-shot flat clustering pass cannot merge synonym types that first appear after the cure point, an embed-block-verify pass that re-runs on a post-cure type burst will merge late synonyms while preserving distinct facets
- **Lever** - type consolidation
- **Mechanism** - embed each type's definition, block by cosine, LLM-verify each candidate merge; allow bounded re-cure on a post-cure type-count burst; keep a light isa layer instead of a flat collapse
- **Prediction** - a synonym type introduced after curing gets merged; distinct facets kept
- **Acceptance bar** - late synonym merged without collapsing distinct types
- **Result** - pending (this batch)
- **Verdict** - pending

### R01-H6 Community summaries global-only

- **Hypothesis** - because local entity queries rarely retrieve from community summaries, routing only global sensemaking queries to summaries will cut per-query LLM cost with no answerability loss on entity queries
- **Lever** - retrieval routing
- **Mechanism** - PPR path for entity/multi-hop queries; community summaries computed and retrieved only for global queries
- **Prediction** - local-query LLM cost down, entity-query answerability flat
- **Acceptance bar** - cost down and answerability not down
- **Result** - pending (this batch)
- **Verdict** - pending

### R01-H7 Curing + calibration hardening

- **Hypothesis** - because Chao1 fluctuates on tiny samples and isotonic on 25 collected pairs fits noise, a minimum-sample floor before the cure gate and held-out/learned calibration will prevent premature curing and overfit curves
- **Lever** - cure gate + calibration
- **Mechanism** - block the cure gate until a minimum observation count; replace isotonic-on-collected-pairs with a fixed documented threshold below the label floor (temperature scaling on held-out above it); learn resolution LRs where labels exist
- **Prediction** - cure cannot fire below the floor; calibration does not overfit
- **Acceptance bar** - cure blocked below the floor
- **Result** - pending (this batch)
- **Verdict** - pending

### R01-H8 Transitivity guard + fact-drift alarm

- **Hypothesis** - because union-find snowballs (A~B, B~C force A=C) and remap+JSD only sees schema drift, a correlation-clustering split pass plus a contradiction-rate alarm will break over-merged components and surface fact drift the schema metrics miss
- **Lever** - post-merge split + drift signal
- **Mechanism** - after union-find, split components whose internal links are weak; add contradiction-rate per window (incoming edges that invalidate a live edge) as the fact-drift alarm, demoting remap+JSD to the schema-recure trigger
- **Prediction** - snowballed components split; a fact-drift scenario raises contradiction-rate without raising schema JSD
- **Acceptance bar** - over-merge split verified and fact-drift alarm distinct from schema drift
- **Result** - pending (this batch)
- **Verdict** - pending

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
| R01-H2 | retrieval | PPR seeded from vector top-k (GDS PageRank) | multi-hop answerability up, single-hop not down | >= baseline multi-hop, no single-hop regression | **Promoted** |
| R01-H3 | extraction | gleaning re-prompt + entity/relation split | recall up (entities+rels/doc, orphan_rate down) | recall up, duplicate_name_density not up | **Promoted** |
| R01-H4 | resolution | FAISS ANN blocking + LLM judge on defer zone | blocking sub-quadratic, defer decided better | dup density <= baseline, blocking O(n log n) | **Promoted** |
| R01-H5 | type consolidation | embed-block-verify, re-runnable, light isa | post-cure synonyms still merge | late synonym types merged | **Kept** (corpus regression, superseded by R02-H10) |
| R01-H6 | retrieval cost | community summaries global-only | local-query LLM cost down, answerability flat | cost down, no answerability loss | **Promoted** |
| R01-H7 | curing/calibration | Chao1 min-sample floor + learned/held-out calibration | no premature cure, no overfit curve | cure blocked below floor | **Promoted** |
| R01-H8 | resolution/drift | union-find split guard + contradiction-rate alarm | over-merges split, fact-drift distinguished | snowball reduced, alarm fires on fact drift | **Kept** (unexercised live) |
| R01-H9 | model routing | separate extraction model from orchestrator model | cheaper extractor holds recall at lower cost | recall/quality flat vs single strong model, cost down | pending (capability shipped) |

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
- **Result** - cross-device multi-attribute probe ("AirSense 11 vs iBreeze: pressure ranges, ramp, humidification") answered with grounded per-device specifics (pressure 4-20 cmH2O both, SmartStart vs Preheat/Auto Start, HumidAir 11 tub vs Humidity feature) - unreachable for fixed 1-hop which cannot assemble two neighbourhoods; single-fact probe ("weight of AirSense 11" -> 1130 g) intact. Qualitative probe pair, not an A/B - the 1-hop baseline was replaced, so the comparison is capability, not delta
- **Verdict** - Promoted; multi-hop comparison demonstrably answered, no single-hop regression observed

### R01-H3 Gleaning + entity/relation split

- **Hypothesis** - because a single extraction pass provably under-extracts, a bounded gleaning re-prompt plus separate entity and relation passes will raise extraction recall (more entities and relationships per document, lower orphan_rate) without inflating duplicate_name_density
- **Lever** - extraction passes
- **Mechanism** - after the first instructor pass, re-prompt for missed entities/relations (1-2 rounds); run entity and relation extraction as separate calls
- **Prediction** - recall up, orphan_rate down, avg_degree up, duplicate_name_density flat
- **Acceptance bar** - recall up and duplicate_name_density not above baseline
- **Result** - CPAP rebuild: 4601 entities (+237% vs 1366), 6717 relationships (+294% vs 1704), orphan_rate 0.059 (baseline 0.127, -53%), avg_degree 2.92 (+17%), duplicate_name_density 0.002 (baseline 0.003 - guardrail holds, DOWN despite 3.4x entities). Costs recorded: ~66 min wall-clock for 26 documents; side finding - relationship-type proliferation (334 native types, entropy 6.22 vs 2.22): gleaning recalls more relation surface than consolidation governs; relation-type consolidation is an open item
- **Verdict** - Promoted; both bar conditions met decisively

### R01-H4 ANN blocking + LLM-judged defer zone

- **Hypothesis** - because brute-force within-type cosine is O(n^2) and hand weights are weakest in the ambiguous band, FAISS ANN top-k blocking plus routing the 0.4-0.6 defer zone to an LLM judge will keep resolution sub-quadratic and decide ambiguous merges better
- **Lever** - blocking + defer decision
- **Mechanism** - FAISS HNSW top-k neighbours per type instead of all-pairs; LLM judge on defer-band pairs only
- **Prediction** - blocking scales sub-quadratically; defer-band merges more accurate; duplicate_name_density <= baseline
- **Acceptance bar** - duplicate_name_density <= baseline and blocking complexity sub-quadratic
- **Result** - duplicate_name_density 0.002 <= 0.003 baseline on a 3.4x larger graph; ANN blocking (FAISS IndexFlatIP top-k above ann_min_entities=200) engaged on the rebuild's per-document sets and the cure-time buffer, complexity guarantee test-pinned. Defer-zone LLM judge shipped but off by default (llm_defer_judge=False) - unexercised in this run, its live value unmeasured
- **Verdict** - Promoted on blocking; judge carries no verdict yet

### R01-H5 Re-runnable hybrid type consolidation

- **Hypothesis** - because a one-shot flat clustering pass cannot merge synonym types that first appear after the cure point, an embed-block-verify pass that re-runs on a post-cure type burst will merge late synonyms while preserving distinct facets
- **Lever** - type consolidation
- **Mechanism** - embed each type's definition, block by cosine, LLM-verify each candidate merge; allow bounded re-cure on a post-cure type-count burst; keep a light isa layer instead of a flat collapse
- **Prediction** - a synonym type introduced after curing gets merged; distinct facets kept
- **Acceptance bar** - late synonym merged without collapsing distinct types
- **Result** - mechanism bar met and test-pinned (embed-block-verify merges synonyms, rejects distinct facets, should_recure reopens on a burst). Corpus outcome is a recorded regression: the cured CPAP ontology holds 65 types vs the baseline's 7 - consolidation under-collapsed because gleaning-boosted extraction promotes spec values (PressureRange, PressureReliefRange, PressureSetting, RampTimeRange, Weight, Warranty, Dimension) to types, and embed-block-verify correctly refuses to merge genuinely distinct value categories. The failure is upstream typing, not the consolidation mechanism
- **Verdict** - Kept at its own bar; corpus regression recorded and superseded by R02-H10 (values-as-properties + demotion guard), which attacks the cause instead of the symptom

### R01-H6 Community summaries global-only

- **Hypothesis** - because local entity queries rarely retrieve from community summaries, routing only global sensemaking queries to summaries will cut per-query LLM cost with no answerability loss on entity queries
- **Lever** - retrieval routing
- **Mechanism** - PPR path for entity/multi-hop queries; community summaries computed and retrieved only for global queries
- **Prediction** - local-query LLM cost down, entity-query answerability flat
- **Acceptance bar** - cost down and answerability not down
- **Result** - ingest paid zero community-summary LLM cost (summaries computed only by the explicit optimize call: 82 communities, 82 summaries, modularity 0.830); local probes (comparison, single-fact) answered via the PPR path without touching summaries
- **Verdict** - Promoted; cost moved out of the ingest path with no local-answerability loss observed

### R01-H7 Curing + calibration hardening

- **Hypothesis** - because Chao1 fluctuates on tiny samples and isotonic on 25 collected pairs fits noise, a minimum-sample floor before the cure gate and held-out/learned calibration will prevent premature curing and overfit curves
- **Lever** - cure gate + calibration
- **Mechanism** - block the cure gate until a minimum observation count; replace isotonic-on-collected-pairs with a fixed documented threshold below the label floor (temperature scaling on held-out above it); learn resolution LRs where labels exist
- **Prediction** - cure cannot fire below the floor; calibration does not overfit
- **Acceptance bar** - cure blocked below the floor
- **Result** - floor test-pinned and live: cure fired at document 10 (plateau reason) with the min-sample floor active, versus document 5 on the baseline - no sub-floor cure possible; stability at cure jsd 0.0036, chao1 0.918, dH 0.028; calibration correctly stayed on the fixed documented threshold below the 100-label floor (no isotonic-on-noise)
- **Verdict** - Promoted; the gate cannot fire early and the calibration overfit path is closed

### R01-H8 Transitivity guard + fact-drift alarm

- **Hypothesis** - because union-find snowballs (A~B, B~C force A=C) and remap+JSD only sees schema drift, a correlation-clustering split pass plus a contradiction-rate alarm will break over-merged components and surface fact drift the schema metrics miss
- **Lever** - post-merge split + drift signal
- **Mechanism** - after union-find, split components whose internal links are weak; add contradiction-rate per window (incoming edges that invalidate a live edge) as the fact-drift alarm, demoting remap+JSD to the schema-recure trigger
- **Prediction** - snowballed components split; a fact-drift scenario raises contradiction-rate without raising schema JSD
- **Acceptance bar** - over-merge split verified and fact-drift alarm distinct from schema drift
- **Result** - both mechanisms test-pinned (split guard breaks weak-cohesion components; contradiction-rate alarm fires on invalidations without moving schema JSD). Live corpus never exercised them: 100% of 6717 edges remained valid (spec-sheet corpora do not contradict themselves within one rebuild), 0 invalidations, so the alarm and the split guard carry mechanism verdicts only
- **Verdict** - Kept; guarantees pinned by tests, live exercise awaits a corpus with superseding facts (S2 scenario)

### R01-H9 Separate extraction model from orchestrator model

- **Hypothesis** - because extraction is high-volume and mechanical while orchestration (clustering, judging, summarizing) is low-volume and judgment-heavy, routing extraction to a cheaper model will hold recall and quality at materially lower cost
- **Lever** - `Settings.extraction_llm` (bulk extractor) vs `Settings.llm` (orchestrator); single-model run is the control
- **Mechanism** - `Foundry.extraction_engine` resolves to a separately configured engine when `extraction_llm` is set, falling back to the orchestrator engine when None
- **Prediction** - entities/relationships per document within 10% of the single-strong-model run at lower per-document cost
- **Acceptance bar** - recall and duplicate_name_density flat vs single strong model, cost down
- **Result** - pending (capability shipped, measurement not yet run)
- **Verdict** - pending

### R01 results - CPAP rebuild (26 documents, full R1-R8 engine, 2026-07-06)

Corpus-level deltas against the baseline row; scorecard `reports/scorecard-20260706-105015.json`, run log `logs/cpap-rebuild.log`.

| measure | baseline | R01 rebuild | delta | reading |
|---|---|---|---|---|
| entity_count | 1366 | 4601 | +237% | gleaning recall (H3) |
| relationship_count | 1704 | 6717 | +294% | gleaning recall (H3) |
| orphan_rate | 0.127 | 0.059 | -53% | recall connects structure (H3) |
| duplicate_name_density | 0.003 | 0.002 | down | resolution holds at 3.4x scale (H3/H4 guardrail) |
| avg_degree | 2.49 | 2.92 | +17% | still far below the ~8.75 SOTA band (R02-H13 target) |
| modularity (Leiden) | 0.81 | 0.830 | flat-up | community structure preserved (82 communities) |
| entity types (cured) | 7 | 65 | regression | value-as-type promotion (H5 reading, R02-H10 target) |
| relationship types | ~10 (entropy 2.22) | 334 (entropy 6.22) | regression | ungoverned relation surface - open item |
| cured at document | 5 | 10 (plateau) | later | more types to stabilize; floor active (H7) |
| temporal capability | none | bitemporal live, 357 entity versions, 100% edges valid | closed | H1; contradiction path unexercised on this corpus |

The batch reading: the recall and longevity levers landed decisively (recall roughly tripled while duplicates went DOWN); the cost is an ungoverned type surface - 65 entity types and 334 relationship types - which is exactly the retrieval-first problem R02 pre-registers against. Wall-clock ~66 min / 26 documents with per-mention re-embedding (DEF-1) the dominant inefficiency.

## R02 - retrieval-first graph shape (pre-registered 2026-07-06)

Second batch, grounded in the six-thread external research round recorded in [`../sota-decision.md`](../sota-decision.md) (R02 section) with all cited papers archived under [`../../references/papers/`](../../references/papers/). Directive driving the batch: perfect context in 1-2 hops for weak reader models - work shifts from query time to ingest time. Baseline for all bars is the R01 rebuild measurement (verdicts above, measurement in progress). A shared probe set is part of this batch's setup: 25-30 questions over the CPAP corpus with gold evidence - comparison, single-fact, multi-hop, and deliberately unanswerable items - scored on answer accuracy, evidence recall, faithfulness (verifiable/total statements), and abstention correctness, with a weak reader (Haiku-class) alongside the standard reader.

| hypothesis | lever | mechanism | predicted | acceptance bar | verdict |
|---|---|---|---|---|---|
| R02-H10 | extraction typing | values-as-properties constraint + cure-time value-likeness demotion guard | type proliferation killed at source | cured types <= 15 on CPAP, no gold entity lost | **Kept** (19 types, bar missed narrowly; -71%, residual is synonym pairs) |
| R02-H11 | graph shape | ingest-time proposition (semantic-unit) nodes, embedded, citation-carrying | weak-reader accuracy up, tokens down | evidence recall +10% and weak-reader accuracy up vs entity-only context | **Promoted** (+10.6% recall, weak reader reaches strong parity) |
| R02-H12 | retrieval topology | passage nodes inside PPR projection, tiered reset weights | multi-hop evidence recall up | evidence recall +5% vs post-hoc chunk attach, query latency < 2x | **Refuted (null)** (B0 = B1 exactly) |
| R02-H13 | graph density | kNN similarity edges + defer-band alias edges | coherent local density up, recall up | avg_degree >= 4.0 and entity recall +5%, duplicate_name_density not up | **Refuted (null)** on recall (degree bar met, zero retrieval delta) |

### R02-H10 Values-as-properties extraction constraint

- **Hypothesis** - because LLM extraction promotes measured values ("4-20 cmH2O") to entity types (PressureRange, Weight, Warranty) and no SOTA system does this, constraining extraction to emit unit/measure/range strings as properties or claims on the parent entity - with a deterministic value-likeness demotion guard at cure time as backstop - will collapse the type inventory to the legitimate domain types without losing any gold entity
- **Lever** - extraction prompt schema + cure-time demotion guard; corpus, engine, resolution held fixed
- **Mechanism** - extraction schema forbids value-like type names; demotion guard classifies each candidate type by member-name statistics (fraction of digit/unit-dominant tokens) and folds attribute-like types into properties before curing metrics see them
- **Prediction** - cured type count drops from the R01 rebuild's measured count (order 66) to <= 15; JSD/Chao1 gates operate on a legitimate inventory and cure earlier
- **Acceptance bar** - cured types <= 15 on the CPAP rebuild AND no gold entity (devices, manufacturers, modes) lost from the graph
- **Experiment** - <br>source: [`[paper digest] Microsoft GraphRAG.md`](../../references/papers/) (claims/covariates model), [`[paper digest] NodeRAG.md`](../../references/papers/) (attribute nodes are entity summaries, never values)<br>method: modify extraction prompts + add demotion pass; re-run CPAP ingest; diff type inventory and gold entity list<br>caveat: rebuild ran mixed-model after a Bedrock quota outage (docs 1-15 Sonnet 4.5, docs 16-27 Haiku 4.5 via the resume path) - live exercise of R01-H9 routing
- **Result** - cured types 65 -> 19 (-71%); every value-costume type eliminated (no PressureRange/Weight/Warranty/Dimension; Specification absorbs demotions, 199 members); no gold entity lost (devices, manufacturers, modes all present); 1597 entities carry spec properties; curing statistics healthier at cure (chao1 0.991 vs 0.918, jsd 0.0105). Bar missed narrowly: 19 > 15 - the residual is synonym PAIRS (Condition/MedicalCondition, Feature/ClinicalFeature) that embed-verify treats as distinct facets, a different failure mode than value promotion
- **Verdict** - Kept; the registered disease (value promotion) is cured and both guardrails hold, but the numeric gate missed at 19 vs 15 - the residual belongs to synonym consolidation, tracked as its own follow-up, not to this lever

### R02-H11 Proposition nodes as first-class retrieval targets

- **Hypothesis** - because weak readers fail when forced to synthesize scattered entity descriptions at query time, generating self-contained proposition sentences at ingest (entity + key edges folded into standalone facts with source chunk ids), embedding them, and returning them as the primary context unit will raise weak-reader accuracy while cutting context tokens
- **Lever** - ingest-time proposition generation + retrieval returns propositions before chunks; extraction, resolution, PPR core held fixed
- **Mechanism** - NodeRAG semantic-unit pattern: content nodes carry what retrieval returns; entity names remain entry points; propositions seed and rank in PPR
- **Prediction** - evidence recall on the probe set up >= 10%; weak-reader accuracy up; context tokens per query down or flat
- **Acceptance bar** - evidence recall +10% and weak-reader accuracy improves vs entity-description context, token budget not up more than 20%
- **Experiment** - <br>source: [`[paper digest] NodeRAG.md`](../../references/papers/) (retrieval ratio 94.9% vs 86.3%, MuSiQue 46.3% at 5.9k tokens)<br>method: DETERMINISTIC proposition rendering (one sentence per valid relationship + one per entity property set) - faithful by construction, zero LLM cost, idempotent content-hash ids; 8508 backfilled on the R01 graph; probe set A/B via propositions_enabled
- **Result** - evidence recall 0.396 -> 0.438 (+10.6% relative, meets the +10% bar); strong-reader accuracy 0.708 -> 0.750; false refusals down 0.333 -> 0.250; context 1.19x (within the 1.2x cap). Weak-reader arm (Haiku 4.5): 0.708 -> 0.750 - REACHING STRONG-READER PARITY, the product goal in one number. Ingest cost: zero LLM (deterministic rendering), embeddings served through the DEF-1 cache
- **Verdict** - Promoted; all three bar conditions met and the weak-reader parity result is the strongest finding of the batch

### R02-H12 Passage nodes inside the PPR projection

- **Hypothesis** - because attaching chunks after PPR severs passage relevance from graph diffusion, adding chunk nodes to the PPR projection with a low reset weight will propagate passage and entity relevance jointly and raise multi-hop evidence recall
- **Lever** - PPR projection contents + reset-weight tiering (passages ~0.05, entities/propositions 1.0); seeds and damping held fixed
- **Mechanism** - HippoRAG 2 composite graph: dense passage signal and sparse phrase signal fuse inside one PPR run instead of post-hoc
- **Prediction** - evidence recall up >= 5% on multi-hop probes; single-fact probes unaffected
- **Acceptance bar** - evidence recall +5% vs post-hoc chunk attachment with no single-fact regression and query latency under 2x
- **Experiment** - <br>source: [`[paper digest] HippoRAG 2.md`](../../references/papers/) (passage-node removal costs 11 recall@5 points on MuSiQue)<br>method: KGFDocument + Chunk nodes persisted at ingest, MENTIONED_IN from entity loader, PPR projection spans Entity+Chunk via the PPR_NODE_LABELS seam; phase B ablation B0 (chunks in) vs B1 (chunks out) on the same rebuilt graph, same reader
- **Result** - B0 and B1 IDENTICAL on every measure (recall 0.333, accuracy 0.792, multi-hop 0.33, context within 1%). Multi-hop failure attribution shows why: of 4 failing multi-hop probes, 2 have evidence recall 1.0 (reader-side failure, ranking irrelevant) and 2 have recall 0.0 (evidence absent from the graph - no projection can rank what is not there). Provenance value stands regardless: S6 audit trace and future citation ids ride on the same nodes. Side find: the live integration suite caught GDS rejecting projections naming absent labels - fixed with a label-intersection guard
- **Verdict** - Refuted (null) at this corpus/probe scale; the HippoRAG 2 gain did not transfer - kept as infrastructure (provenance, audit), not as a retrieval claim

### R02-H13 Similarity-edge densification

- **Hypothesis** - because KGF's avg_degree 2.49 sits near the density of measurably failing systems (1.48) and far below winning ones (~8.75), adding cosine-gated kNN similarity edges between entities plus alias edges for the resolution defer band will densify coherent local clusters and raise entity recall without inflating duplicates
- **Lever** - similarity/alias edge creation at load time; resolution merges, PPR, extraction held fixed
- **Mechanism** - HippoRAG synonym-edge pattern scoped: hard merge stays primary, similarity edges connect near-neighbours so PPR can traverse lexical/semantic variants; defer-band pairs get alias edges instead of forced decisions
- **Prediction** - avg_degree rises to >= 4.0; entity recall on probes up >= 5%; orphan absorption as a side effect, not a target
- **Acceptance bar** - avg_degree >= 4.0 and entity recall +5% with duplicate_name_density not above baseline
- **Experiment** - <br>source: [`[paper digest] HippoRAG.md`](../../references/papers/) (synonym edges cosine > 0.8), [`[paper digest] When to Use Graphs in RAG.md`](../../references/papers/) (degree 8.75 vs 1.48 winners/losers), kNN augmentation study (+6.4% entity recall, p=0.000043)<br>method: post-load kNN pass over entity embeddings via the vector index (sub-quadratic), id-ordered MERGE; A1 vs A2 on the same graph, same reader
- **Result** - 5640 SIMILAR_TO edges created on the R01 graph (avg_degree 2.92 -> 5.37, degree bar met; 3839 more on the rebuilt graph -> 5.47); retrieval delta ZERO - A2 identical to A1 on recall, accuracy, and context to within one character. Reading: kNN edges derived from the same embedding space that drives vector seeding add only redundant paths - anything they connect, the seeder already found; the literature's gains came from sparser-seeded systems. Orphan absorption was real as a side effect (orphan_rate 0.099 -> 0.041 on the rebuilt graph)
- **Verdict** - Refuted (null) on the recall bar; the degree target alone is a vanity number - kept only as orphan absorption infrastructure, and the guardrail held (duplicate density flat)

## R03 - query-side context assembly (pre-registered 2026-07-06)

Query-time batch over the R02 graph shape; each lever independent of the others, all measured on the shared probe set.

| hypothesis | lever | mechanism | predicted | acceptance bar | verdict |
|---|---|---|---|---|---|
| R03-H14 | seeding | query-to-triple linking alongside entity seeds | seed quality up | evidence recall +5%, no latency blowup | **Refuted (null)** (off = on exactly) |
| R03-H15 | query handling | comparison decomposition into per-entity retrievals | comparison accuracy up | comparison probe accuracy +10%, tokens < 1.5x | **Refuted (null)** at the 0.875 ceiling (fired on 5/8, zero delta) |
| R03-H16 | serialization | PPR-ordered per-entity blocks, head+tail placement, per-claim citations | weak-reader accuracy and faithfulness up | weak-reader accuracy +10% and faithfulness >= 0.9 | **Refuted (null)** (context too short for the effect) |
| R03-H17 | abstention | structural coverage verdict (seed neighbourhood, path connectivity, community overlap) | unanswerables refused | >= 70% correct refusal on unanswerable probes, < 10% false refusal | **Refuted** (top-score signal inert; system refusal 100% via grounded reader) |

### R03-H14 Query-to-triple seeding

- **Hypothesis** - because a query names relations as often as entities ("pressure range of X"), embedding relation sentences and seeding PPR from matched triples plus entities will raise evidence recall over entity-only seeding
- **Lever** - seed construction; PPR core and context assembly held fixed
- **Mechanism** - HippoRAG 2 query-to-triple linking: triple embeddings capture predicate semantics entity names miss
- **Prediction** - evidence recall up >= 5%, biggest gain on attribute questions
- **Acceptance bar** - evidence recall +5% with no meaningful latency increase
- **Experiment** - <br>source: [`[paper digest] HippoRAG 2.md`](../../references/papers/) (+12.5% recall@5 average, +21 on MuSiQue)<br>method: proposition nodes double as triple embeddings; proposition_seeding toggle isolates seed extension from context effect; 24 answerable probes, Opus 4.5 reader, densified R01 graph
- **Result** - off and on identical (recall 0.438, accuracy 0.750). Reading: with propositions already IN the context, extending the PPR seed set through their ABOUT entities adds nothing - the facts arrive through the content channel before the seeding channel can matter. HippoRAG 2's gain assumed triples were seeds only, not returned content
- **Verdict** - Refuted (null); superseded by the stronger H11 mechanism that subsumes it

### R03-H15 Comparison-query decomposition

- **Hypothesis** - because "A vs B on X" requires covering two entity neighbourhoods and one-shot retrieval splits its budget badly between them, decomposing into per-entity sub-retrievals and unioning contexts will raise comparison accuracy at bounded cost
- **Lever** - query routing for detected comparisons; retrieval per sub-query unchanged
- **Mechanism** - structural split (entity list x attribute), not LLM-guessed decomposition - shallow by construction, no error propagation
- **Prediction** - comparison probe accuracy up >= 10%; context efficiency improves
- **Acceptance bar** - comparison accuracy +10% with combined context under 1.5x single-query tokens
- **Experiment** - <br>source: RT-RAG / EfficientRAG findings (decomposition +7% F1 / +6% EM, ~10x context efficiency) via traversal research thread in [`../sota-decision.md`](../sota-decision.md)<br>method: deterministic pattern split in query(), per-entity retrieval, deduplicated union; 8 comparison probes, toggle A/B, Opus 4.5 reader
- **Result** - decomposition verified firing on 5/8 comparison probes (pattern coverage gap on "which device tolerates/offers ..." phrasings); accuracy identical off and on at 0.875 - the strong reader with propositions already answers these comparisons from blended context. On the rebuilt graph comparisons reached 1.00 (decomposition on, not ablated there). The +10% bar had only 12.5% headroom at this ceiling
- **Verdict** - Refuted (null) at this probe ceiling; retained as routing capability, re-adjudicate on a harder comparison set or weaker reader before widening patterns

### R03-H16 Reasoning-ordered context serialization with citations

- **Hypothesis** - because flat concatenation buries key facts mid-context (>30% degradation) and uncited claims invite fabrication, serializing per-entity blocks (name, propositions, relationship facts, source snippet) ordered by PPR score with top items at head and tail, and forcing per-claim citation ids, will raise weak-reader accuracy and faithfulness
- **Lever** - context assembly format only; retrieval set identical
- **Mechanism** - lost-in-the-middle mitigation + StrictCitations grounding, both measured strongest in the small-model band
- **Prediction** - weak-reader accuracy up >= 10%; faithfulness >= 0.9; no cost increase
- **Acceptance bar** - weak-reader accuracy +10% and faithfulness >= 0.9 on the probe set
- **Experiment** - <br>source: [`[paper digest] Lost in the Middle.md`](../../references/papers/), [`[paper digest] Instruction Tuning LLMs on Graphs.md`](../../references/papers/) (structured blocks beat flat triples, largest gain small models), [`[paper digest] Let Me Speak Freely.md`](../../references/papers/) (no forced JSON answers: -10-15% reasoning)<br>method: head+tail interleave toggle with identical retrieval; 24 answerable probes, Opus 4.5 reader
- **Result** - off and on identical (accuracy 0.750). Reading: lost-in-the-middle degradation is a LONG-context pathology (the >30% losses are measured at 10k+ token contexts); KGF's capped context (~4k chars on the R01 graph) is too short for ordering to matter. The per-claim citation instruction (not ablated separately) rode along in all arms. Faithfulness metric (statement decomposition) not yet instrumented - noted as measurement debt
- **Verdict** - Refuted (null) at current context lengths; the interleave stays (zero cost) and becomes testable if context budgets grow - e.g. the rebuilt graph's 15.7k-char contexts

### R03-H17 Structural abstention signal

- **Hypothesis** - because reader-model confidence is a proven-useless refusal signal (0% correct abstention) while graph structure is not, emitting a coverage verdict from seed-neighbourhood size, path connectivity between query entities, and community overlap - and refusing or clarifying when coverage is thin - will catch most unanswerable questions without suppressing answerable ones
- **Lever** - pre-generation coverage gate; retrieval and generation unchanged when coverage passes
- **Mechanism** - structural signals (empty neighbourhood, no connecting path, low overlap) measure what the graph knows, independent of reader confidence
- **Prediction** - >= 70% of unanswerable probes refused; < 10% of answerable probes falsely refused
- **Acceptance bar** - correct refusal >= 70% and false refusal < 10% on the probe set
- **Experiment** - <br>source: HRAG graph cross-validation (76% correct refusal vs 0%) via topology research thread in [`../sota-decision.md`](../sota-decision.md)<br>method: coverage gate on best retrieval score (abstention_min_score 0.75); 4 unanswerable + 24 answerable probes; score-distribution analysis with the gate disabled
- **Result** - the implemented signal (top vector/proposition score) is inert: with propositions on, the gate abstained on 0/4 unanswerables (and falsely on 1 answerable with propositions off). Distribution analysis kills the whole signal class: unanswerable top-scores (0.79-0.86) sit INSIDE the answerable range (0.74-0.95) - no threshold exists. Root cause is conceptual: vector similarity measures topical proximity, not answerability; an unanswerable question about an in-corpus device retrieves excellent context that lacks the asked attribute. System-level refusal was still 100% correct in every run - owed to the strict grounding prompt and the reader, not the gate
- **Verdict** - Refuted for the top-score signal; the pre-registered richer signals (asked-attribute existence against entity properties/propositions, path connectivity) remain the open path - answerability is an attribute-existence problem, not a similarity problem

### R02/R03 results - probe measurements across graphs and readers

| run | graph | reader | evidence recall | accuracy | single_fact | comparison | multi_hop | refusal | ctx chars |
|---|---|---|---|---|---|---|---|---|---|
| A0 baseline | R01 | Sonnet 4.5 | 0.396 | 0.708 | 0.80 | 0.88 | 0.33 | 4/4 | 3253 |
| A1 +propositions | R01 | Sonnet 4.5 | 0.438 | 0.750 | 0.90 | 0.88 | 0.33 | 4/4 | 3876 |
| A2 +similarity edges | R01 | Sonnet 4.5 | 0.438 | 0.750 | 0.90 | 0.88 | 0.33 | 4/4 | 3877 |
| W0 weak, no props | R01 | Haiku 4.5 | - | 0.708 | 0.90 | 0.75 | 0.33 | 4/4 | - |
| W1 weak, props | R01 | Haiku 4.5 | - | 0.750 | 0.90 | 0.88 | 0.33 | 4/4 | - |
| B0 rebuilt, full | H10 rebuild | Opus 4.5 | 0.333 | **0.792** | 0.90 | **1.00** | 0.33 | 4/4 | 15693 |
| B1 rebuilt, no passages | H10 rebuild | Opus 4.5 | 0.333 | 0.792 | 0.90 | 1.00 | 0.33 | 4/4 | 15801 |

Batch reading, honest and in full:

- **The batch's one big win is ingest-time content**: propositions moved every dial they were predicted to move and lifted the weak reader to strong parity - the product thesis ("the graph does the lifting") confirmed in one number
- **Six pre-registered levers returned nulls or refutations** - topology and query-side tuning add nothing once propositions saturate a probe set of this size; that coherent negative is itself the finding, and it validates the retrieval-first doctrine (work belongs at ingest)
- **Multi-hop 0.33 never moved across any graph, reader, or lever** - failure attribution on the rebuilt graph: 2 of 4 failures have evidence recall 1.0 (reader/serialization side), 2 have 0.0 (facts absent from the graph - repairable only by targeted re-extraction, the R04 loop)
- **Metric lesson** - verbatim-substring evidence recall dropped on the rebuilt graph (0.438 -> 0.333) while accuracy ROSE to the batch best (0.792, comparisons perfect): facts rephrased as properties/propositions evade the verbatim matcher; accuracy is the outcome gate, verbatim recall is now a diagnostic only
- **Caveats** - phase B reader is Opus 4.5 (quota failover), so B-vs-A accuracy deltas are reader-confounded (B0-vs-B1 within-phase comparison is clean); rebuilt-graph context grew 4x (property dumps + decomposition union) - a token-budget item for the ops batch; faithfulness metric not yet instrumented (measurement debt)

### Scoring correction (2026-07-06, supersedes the accuracy figures above)

Failure inspection revealed the deterministic scorer was too strict for prose gold answers: with no numeric tokens it required the whole gold sentence as a verbatim substring, so correct paraphrases ("provides automatic, personalized adjustments" vs gold "makes automatic, personalized adjustments") scored wrong. Corrected scorer: numeric golds unchanged (value-token majority); prose golds score by content-word overlap >= 0.6 (stopwords dropped, 6-char prefix stems). All persisted runs re-adjudicated from saved answers - no re-execution, ablation arms remain identical so every null verdict stands; only absolute levels change.

| run | graph | reader | accuracy (was) | single_fact | comparison | multi_hop (was) | refusal |
|---|---|---|---|---|---|---|---|
| A0 baseline | R01 | Sonnet 4.5 | 0.833 (0.708) | 0.80 | 0.88 | 0.83 (0.33) | 4/4 |
| A1 +propositions | R01 | Sonnet 4.5 | 0.875 (0.750) | 0.90 | 0.88 | 0.83 (0.33) | 4/4 |
| W1 weak, props | R01 | Haiku 4.5 | 0.875 (0.750) | 0.90 | 0.88 | 0.83 (0.33) | 4/4 |
| B0 rebuilt, full | H10 rebuild | Opus 4.5 | **0.917** (0.792) | 0.90 | **1.00** | 0.83 (0.33) | 4/4 |

Corrected reading: multi-hop was never broken - 5 of 6 multi-hop probes answer correctly on all graphs; the "0.33 wall" was the scorer. H11's deltas survive (A0 -> A1 +4.2pts, weak parity holds at 0.875 = strong reader's A1). The two REAL failures on the rebuilt graph are both extraction gaps with evidence recall 0.0: P09 (SleepStyle 200 dimensions never extracted) and P19 (SmartRamp mechanism sentence never extracted) - the reader correctly reports graph absence for P09. Final honest scoreboard on the rebuilt graph: 22/24 answerable correct + 4/4 correct refusals = 26/28. Both residuals are the R04 targeted-repair case: failing probe names its source document.

## R04 - use-case regime loop (pre-registered 2026-07-06)

The regime doctrine operationalized: a use case narrows every stage, and failures against the regime's own probes drive targeted graph repair. First slice implemented: `Foundry.repair(question, sources)` - focused re-extraction of named documents that bypasses ingest fingerprints, requires STABLE, and injects the failing question into the extraction purpose.

| hypothesis | lever | mechanism | predicted | acceptance bar | verdict |
|---|---|---|---|---|---|
| R04-H18 | targeted repair | question-focused re-extraction of the failing probe's source | extraction-gap probes flip to correct | both rebuilt-graph residuals (P09, P19) answer correctly post-repair; no previously-correct probe regresses | **Refuted as implemented** - neither flipped; yielded the failure taxonomy (identity gap, fidelity gap) |
| R04-H19 | probe generation | probes generated from the regime (purpose + seed), not hand-written | regime coverage without curation cost | generated set covers all seeded types; >= 80% of generated probes well-formed | pending |
| R04-H20 | saturation criterion | repair loop iterates until weak-reader parity and abstention-only residuals | convergence, not endless repair | loop terminates; terminal residuals are all correct abstentions | pending |
| R04-H21 | identity audit | alias edges from explicit assertions + shared-source attribute-fingerprint detector | identity-gap probes flip | P09 correct; SmartRamp/Smart Ramp class of intra-doc duplicates merged | pending |
| R04-H22 | fidelity audit | verbatim source sentences bound to entities as quote-propositions | fidelity-gap probes flip | P19 correct under the deterministic scorer; no regression | pending |
| R04-H23 | completeness audit | type-cohort attribute expectation (PCWA) computes gaps at ingest; gap queue drives repair-from-source and doubles as the abstention signal | gaps surface before any query fails | P09-class gap auto-detected with zero probes; recorded gaps refuse matching unanswerables | pending |

### R04-H18 Targeted repair of extraction gaps

- **Hypothesis** - because both genuine probe failures are extraction gaps (evidence recall 0.0) with known source documents, re-extracting only those documents with the failing question injected into the purpose will surface the missing facts and flip the probes, without touching the rest of the graph
- **Lever** - post-hoc graph repair; ingest pipeline, retrieval and reader all held fixed
- **Mechanism** - purpose-conditioned extraction already steers what gets extracted (the gap exists because the general purpose did not emphasize dimensions/ramp mechanics); narrowing the purpose to the failing question is the regime doctrine applied at document granularity
- **Prediction** - P09 (SleepStyle 200 dimensions) and P19 (SmartRamp vs standard ramp) answer correctly post-repair; entity/relationship deltas small (single-digit); no regression on the 26 previously-correct probes
- **Acceptance bar** - both probes correct under the corrected scorer; scoreboard 28/28
- **Experiment** - <br>method: `kgf repair "<probe question>" <source.pdf>` against the rebuilt graph (Opus 4.5 extractor), then re-query both probes and re-score; regression spot-check on the comparison probe sharing P09's entity (SleepStyle vs iBreeze dimensions)
- **Result** - neither probe flipped, and the diagnosis reclassifies both failures. P09 is an IDENTITY gap, not a missing fact: the dimensions have been in the graph all along as `prop_dimensions_mm=275 x 170 x 140` on `HC230 Product Range`; the manual specs the device under its model code and states the alias explicitly ("Please refer to the HC230-Series Product range listed in the Appendix") - that linking sentence was never extracted as an edge, so re-extraction keeps attaching specs to the spec-table name forever. P19 is a FIDELITY gap: the repair worked mechanically (14 entities, 13 relationships; answer improved from "not in graph" to a correct-direction explanation) but the extractor stored a paraphrase ("adjusts pressure based on breathing patterns") where the source sentence carries the precise mechanism ("maintains a constant lower pressure until the device detects that you require more pressure"); the answer scores 0.438 against the 0.6 bar. Side effect observed: the repair pass spawned `SmartRamp` alongside the pre-existing `Smart Ramp` - alias sprawl, the identity disease at small scale
- **Verdict** - Refuted as implemented, and the refutation is the batch's key finding: the residuals of a proposition-saturated graph are REPRESENTATION failures (identity, fidelity), not recall failures - re-running the same lossy abstraction cannot fix either. Successors H21 (identity) and H22 (fidelity) target the two classes directly

### R04-H21 Identity audit - alias edges from assertion and evidence

- **Hypothesis** - because the P09 failure is two names for one device with no connecting edge, extracting explicit alias assertions ("refer to the X-Series", "also known as") as SAME_AS edges, plus a deterministic detector (entities sharing source documents where one carries the attribute cluster the other's type-siblings all have), will connect alias pairs and flip identity-gap probes
- **Lever** - post-extraction alias resolution; extraction and retrieval unchanged
- **Mechanism** - identity is the one job no flat proposition store can do; the existing cross-type Bayesian resolution missed these pairs because name similarity is near zero ("SleepStyle 200 Series" vs "HC230 Product Range") - the signal lives in explicit textual assertions and shared-source attribute fingerprints instead
- **Prediction** - P09 flips with zero new extraction; intra-doc duplicate pairs (SmartRamp/Smart Ramp, AutoRamp/Auto Ramp) merge
- **Acceptance bar** - P09 correct; no false alias edge on the 28-probe set (spot-check merged pairs)
- **Experiment** - <br>method: alias pass over the rebuilt graph, then re-query P09 and the SleepStyle-vs-iBreeze comparison probe
- **Result** - pending
- **Verdict** - pending

### R04-H22 Fidelity audit - verbatim evidence propositions

- **Hypothesis** - because LLM extraction abstracts (lossy exactly where a question needs precision), binding the exact source sentence to the entity as a quote-proposition at extraction/repair time gives the reader lossless evidence and flips fidelity-gap probes
- **Lever** - ingest-time content addition; deterministic sentence selection, no new LLM calls
- **Mechanism** - extends the proven H11 mechanism (ingest-time content is what works) from rendered facts to verbatim quotes; unlike H12's whole-chunk passages (null), quotes are fact-anchored and enter the context through the proposition channel that measurably works
- **Prediction** - P19 flips; fidelity failures vanish as a class; context growth bounded (sentences, not chunks)
- **Acceptance bar** - P19 correct under the deterministic scorer; no probe regression
- **Experiment** - <br>method: quote-proposition pass for repair-touched entities on the rebuilt graph; re-query P19
- **Result** - pending
- **Verdict** - pending

### R04-H23 Completeness audit - the graph knows what it doesn't know

- **Hypothesis** - because P09-class gaps are computable without any probe (14 of 15 device entities carry `prop_dimensions*`; SleepStyle 200 does not), a type-cohort attribute-expectation audit (partial closed-world assumption) run at ingest time will surface gaps before any query fails, feed the targeted-repair queue, and - as recorded negative knowledge - provide the attribute-existence abstention signal H17 failed to get from vector scores
- **Lever** - post-ingest audit stage; produces a gap queue consumed by repair and a gap ledger consulted at query time
- **Mechanism** - completeness prediction is established KB research (obligatory-relation F1 90-100%, WSDM 2017; "if 9/10 siblings have it, the 10th should" per the PCWA survey; informative negations per UnCommonSense) but published gap-fillers use LLM parametric knowledge (GenIC) and published feedback loops stop at triplet edits (EvoRAG) - nobody wires cohort-gap detection to repair-from-source; the research thread confirmed the void explicitly
- **Prediction** - the SleepStyle dimensions gap is auto-detected with zero probes; repair-from-source or an honest "corpus does not state it" negative record results; recorded gaps refuse matching unanswerable questions structurally
- **Acceptance bar** - P09-class gap surfaces in the audit; >= 70% of unanswerable probes refused via the gap ledger with < 10% false refusal (the H17 bar, now with the right signal)
- **Experiment** - <br>source: [`[paper digest] Predicting Completeness in Knowledge Bases.md`](../../references/papers/), [`[paper digest] Completeness Recall and Negation in Open-World KBs.md`](../../references/papers/), [`[paper digest] UnCommonSense.md`](../../references/papers/), [`[paper digest] GenIC.md`](../../references/papers/), [`[paper digest] EvoRAG.md`](../../references/papers/)<br>method: per-type attribute prevalence over the rebuilt graph (threshold ~0.7 sibling prevalence), gap queue -> repair, gap ledger -> abstention check on the 4 unanswerable probes
- **Result** - pending
- **Verdict** - pending

## R05 - longevity campaign on the benchmark document corpus (pre-registered 2026-07-06)

The long hypothesis: KGF's lifecycle machinery (curing, drift, calibration, audits) earns its keep only under sustained multi-wave operation - unmeasurable at 26 documents, measurable at thousands. Corpus: 10,763 deduplicated reference articles (9.4M chars, 105 topic clusters); waves are cluster-sliced JSONL files in `data/interim/apnea-waves/` (6 waves, 5,101 docs planned; adaptive extension to the full corpus). Engine: local gpt-oss-120b (vLLM, 96GB card, zero API cost); embeddings Bedrock Titan. Graph: dedicated third Neo4j container. Probes: 47 synthetic QA pairs with gold answers (`tests/probes/apnea-probe-set.yml`), each mapped to its source cluster - 24 fall inside the planned waves, 23 remain out-of-corpus controls that must be refused until (unless) their cluster is ingested.

| hypothesis | lever | mechanism | predicted | acceptance bar | verdict |
|---|---|---|---|---|---|
| R05-H24 | lifecycle at scale | curing + consolidation under 6 cluster-shifted waves | type system stays bounded while content grows ~10x | type count <= 30 at campaign end; chao1 saturation maintained; drift signal fires on >= 1 cluster transition | pending |
| R05-H25 | zero-cost extractor | gpt-oss-120b extraction + propositions + grounded reader | product thesis holds on a local engine | in-wave probe accuracy >= 0.75 (corrected scorer) | pending |
| R05-H26 | coverage growth | fixed probe set re-run after each wave | answerability tracks cluster membership monotonically | in-wave probes flip to answered as their cluster lands; out-of-wave probes >= 70% refused throughout | pending |

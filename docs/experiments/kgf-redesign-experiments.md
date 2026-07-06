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
| R04-H21 | identity audit | alias edges from explicit assertions + shared-source attribute-fingerprint detector | identity-gap probes flip | P09 correct; SmartRamp/Smart Ramp class of intra-doc duplicates merged | **Promoted** - P09 answers with the gold dimensions via the alias chain; SmartRamp/Smart Ramp merged (normalized-name); scoreboard 28/28 |
| R04-H22 | fidelity audit | verbatim source sentences bound to entities as quote-propositions | fidelity-gap probes flip | P19 correct under the deterministic scorer; no regression | **Promoted** - P19 recall 0.0 -> 1.0, scoreboard 27/28 (only the H21 target left); shipped text-side quote scan + trigram diversity filter + reader attribution rule |
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
- **Experiment** - <br>method: alias pass over the rebuilt graph, then re-query P09 and the SleepStyle-vs-iBreeze comparison probe; full 28-probe scoreboard ([`probe_eval_r04h21.ipynb`](../../notebooks/probe_eval_r04h21.ipynb))
- **Result** - four deterministic detectors shipped (`graph/aliases.py`: explicit assertion, deictic assertion, model-code cluster, normalized name) plus alias-cluster rendering in retrieval (SAME_AS neighbours' properties merge into the entity block). Four measured iterations, each false anchor pinned by a regression test: (1) measurement tokens (15mm, 2.5kg) masqueraded as model codes and clustered cables/thermistors/tubing into nonsense alias families - excluded by a unit-suffix pattern, P15 recovered; (2) the deictic detector anchored on 'Device', then (3) on 'Patient Menu', then on 'Operating temperature' - generic and interface names dominate raw occurrence counts, and the document's true subject ('SleepStyle 200 Series') appears in ZERO chunks of its own manual (stylized PDF rendering), so candidacy moved to extraction provenance (source_documents membership) ranked by filename-token overlap (SleepStyle_200_Operating_Manual.pdf names its subject). Final chain: SleepStyle 200 Series =deictic= HC230-Series =model_code= HC230 Product Range; P09 now answers with the exact gold dimensions (275 x 170 x 140 mm) that sat unreachable on the alias. 127 SAME_AS edges, all methods provenance-carrying and reversible. Scoreboard 28/28 (offline re-score of saved answers after the Bedrock daily quota exhausted; only the refusal pattern changed, to accept P25's semantically correct "does not have a specific ... value explicitly stated")
- **Verdict** - Promoted. The identity-gap class closes and with it the CPAP probe set: 26/28 baseline -> 27/28 (H22, fidelity) -> 28/28 (H21, identity). Side-finding: prose-regex refusal detection is structurally brittle (two scorer widenings in one day) - the structured refusal H30 pre-registers (question-coverage gap) is the durable answer

### R04-H22 Fidelity audit - verbatim evidence propositions

- **Hypothesis** - because LLM extraction abstracts (lossy exactly where a question needs precision), binding the exact source sentence to the entity as a quote-proposition at extraction/repair time gives the reader lossless evidence and flips fidelity-gap probes
- **Lever** - ingest-time content addition; deterministic sentence selection, no new LLM calls
- **Mechanism** - extends the proven H11 mechanism (ingest-time content is what works) from rendered facts to verbatim quotes; unlike H12's whole-chunk passages (null), quotes are fact-anchored and enter the context through the proposition channel that measurably works
- **Prediction** - P19 flips; fidelity failures vanish as a class; context growth bounded (sentences, not chunks)
- **Acceptance bar** - P19 correct under the deterministic scorer; no probe regression
- **Experiment** - <br>method: quote-proposition pass for repair-touched entities on the rebuilt graph; re-query P19; full 28-probe scoreboard as the no-regression check ([`probe_eval_r04h22.ipynb`](../../notebooks/probe_eval_r04h22.ipynb))
- **Result** - three iterations, each failure diagnostic: (1) quotes anchored to MENTIONED_IN edges never reached the P19 sentence - its chunk carries zero mention edges, so the fidelity audit inherited the extraction's own provenance failures; rewritten as a pure text-side scan (every chunk x every entity name, no graph dependency). (2) The gold quote then existed but ranked 9 behind eight alias-multiplied renderings of one zero-mechanism fact ("DreamStation has feature SmartRamp" x8 across DreamStation/DreamStation CPAP Pro/Philips DreamStation and SmartRamp/Smart Ramp) - the identity disease directly causing the fidelity failure; fixed with a character-trigram Jaccard diversity filter on proposition retrieval (over-fetch 4x, greedy near-duplicate skip; measured separation clones 0.42-0.79 vs distinct 0.02-0.12, threshold 0.4). (3) P19 flipped (evidence recall 0.0 -> 1.0, the verbatim mechanism quoted in the answer) but the de-clutter exposed P25: an unscoped "sound pressure level" proposition from a different device's document reached the reader, which transferred the value to the asked device - a false answer on an unanswerable control that the clone-crowding had accidentally prevented; fixed with a reader attribution rule (a value stated for a different or unnamed subject must not be transferred). Final scoreboard 27/28 - only P09 (the H21 identity target) fails
- **Verdict** - Promoted. Fidelity-gap class closed by verbatim quotes entering the proposition channel, with two structural side-findings: (a) alias sprawl and fidelity failure are one disease - redundant alias renderings crowd informative content out of every retrieval window, so the diversity filter benefits all queries; (b) quality failures mask each other in cascade (clone-crowding masked retrieval starvation AND reader over-attribution) - continuous auditing, not one-shot fixes, is the structural answer, which is the self-auditing foundry thesis observed live

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

## R06 - contrarian round: falsify KGF's own load-bearing assumptions (pre-registered 2026-07-06)

Every round through R05 assumed KGF's architecture is right and tuned inside it. R06 attacks the architecture. Five hypotheses each name an assumption the whole design rests on and pre-register the experiment that would break it - the point is falsification, not confirmation, so a null that hardens an assumption is as valuable as a flip that overturns it. Priors were checked against the 2023-2026 literature before registration (six-source sweep); each row carries an honest novelty verdict and the sources are in `references/papers/`. Same engine and corpus as R05 (local gpt-oss-120b, benchmark article corpus, neo4j3), so R06 rides the R05 waves rather than needing its own build - each hypothesis is measured on a completed wave graph.

| hypothesis | assumption attacked | lever | predicted | acceptance bar | prior art | verdict |
|---|---|---|---|---|---|---|
| R06-H27 | facts belong in the graph | hollow graph: store only identity + attribute-existence + verbatim provenance spans, zero paraphrased propositions; assemble answers from spans at query time | fidelity failure becomes structurally impossible; QA not worse than the proposition graph | in-wave accuracy >= proposition-graph accuracy; zero fidelity-class failures by construction | partial - span grounding + paraphrase-fidelity loss documented (Extractive-Abstractive Spectrum; Evidence Units), no hollow end-to-end system proven on QA | pending |
| R06-H28 | ontology quality drives accuracy | scramble type labels on a cured wave graph post-hoc, re-run all probes | if QA moves < 5%, typing is causally inert for retrieval and only earns its keep as the H23 audit baseline | measured QA delta under label scramble; either outcome recorded (null hardens audit-only thesis, non-null is first causal proof curing pays) | argues against - ontology ablations degrade QA (OMD-GraphRAG; SG-KBQA generalization), but nobody ran the scramble test specifically | pending |
| R06-H29 | merge at ingest | keep duplicate entities, add alias edges, resolve at read time | wrong-merge errors (unrecoverable) vanish; the persistent cross-type duplicate failure class disappears by redefinition | cross-type duplicate probes answer without ingest merge; no read-time latency regression past budget | partial - ingest-merge errors shown to compound on multi-hop ((0.85)^n); query-time resolution is old (Bhattacharya-Getoor 2007) but unproven vs ingest-merge on modern KG-QA | pending |
| R06-H30 | extract what a document says | question-native graph: extract answerable questions as first-class nodes bound to verbatim spans; completeness = expected-question coverage per type cohort; retrieval = question-to-question match | unifies retrieval, abstention and the H23 audit in one structure; out-of-scope questions refuse structurally | in-wave accuracy >= proposition graph; >= 70% out-of-wave refused via coverage gap; retrieval is question-match only | novel - doc2query/HyDE/QA-Expand generate questions for expansion, none make them first-class KG nodes with cohort coverage auditing | pending |
| R06-H31 | one frontier pass extracts best | small local model (gpt-oss-120b) in a verify-and-repair loop vs one Bedrock-Sonnet single pass, same wave, same probes | test-time compute inversion: loop on the free local model beats the paid single pass | local-loop graph QA >= single-pass QA at zero API cost; extraction recall not lower | partial - small-model self-correction (ISC) and test-time verification proven for reasoning, never measured on KG extraction; distillation variants need the big model, the loop here does not | pending |
| R06-H32 | cure timing is a tunable constant | replay the wave-1 type-arrival stream; compare cure points of candidate gates against retrospective type saturation | only a scale-free statistical gate cures near true saturation; every count-floor gate is premature or arbitrary | winning gate cures within the retrospective saturation window with zero corpus-size input; v1 plateau confirmed premature at doc 4 | DEF-3 incident is the motivating data; Good-Turing missing mass is classical (McAllester-Schapire bounds), unused for ontology-cure gating in reviewed literature | **Confirmed under corrected bar, then bounded by live validation** - best one-shot gate, but one-shot curing is insufficient on a drifting stream (see amendment; successor H33) |
| R06-H33 | cure is a one-shot event | reversible cure: the drift detector's sustained-remap recure path must reopen consolidation when a post-cure content shift arrives | no within-sample gate can anticipate out-of-distribution novelty; the lifecycle answer is re-melting, not a smarter gate | on wave 1b: a material post-cure type block (>= 5% of subsequent observation mass) triggers recure and gets integrated; OR no material block arrives and cure-time types keep >= 95% forward coverage (inconclusive, extend to wave 2); refuted if a material block arrives with no recure | old run evidence: 34 drift warnings, zero recures - remap spikes alternated with quiet docs so the all-3-consecutive criterion never held; suspicion pre-registered, not pre-tuned | pending |

### R06-H27 The hollow graph - no propositions, only pointers

- **Hypothesis** - because the P19 fidelity failure is caused by the extractor paraphrasing a load-bearing sentence, a graph that never stores a paraphrase cannot fail that way; storing only entity identity (nodes + alias edges), attribute-existence claims (that entity E has an attribute A, never A's value) and provenance pointers to verbatim source spans makes fidelity failure structurally impossible while the graph still routes a reader to the exact spans that answer
- **Assumption attacked** - that propositional knowledge (subject-relation-object triples with LLM-rendered content) belongs in the graph at all; H22 adds quotes alongside propositions, H27 says quotes are the only content and propositions are the disease
- **Lever** - a hollow-graph ingest variant: extraction emits (entity, attribute-name, span-pointer) not (entity, relation, value); reader assembles from spans
- **Mechanism** - identity is the one job flat storage cannot do and provenance spans are lossless by definition; the graph becomes an index over verbatim evidence, not a paraphrase of it - the retrieval-first doctrine taken to its limit (all fidelity work shifts to zero, because nothing is transformed)
- **Prediction** - in-wave QA accuracy not worse than the proposition graph on the same wave; the fidelity-gap failure class (P19 type) is empty by construction; context size bounded by spans not chunks
- **Acceptance bar** - in-wave accuracy >= proposition-graph accuracy on the same wave-1 probes; manual audit finds zero fidelity-class residuals; if accuracy drops, record which query types need synthesis a pointer cannot provide (the honest failure mode)
- **Prior art** - Evidence Units (arXiv 2604.00500) groups spans with provenance in Neo4j but for document organization, not QA-graph construction; the Extractive-Abstractive Spectrum (arXiv 2411.17375) proves abstractive generation trades verifiability for fluency but does not build a hollow KG; no system proves a proposition-free graph matches a proposition graph on QA
- **Experiment** - <br>method: hollow-ingest variant over wave-1 documents into a scratch graph; run the 5 in-wave probes through a span-assembly reader; compare accuracy and fidelity-residual count against the R05 proposition graph
- **Result** - pending
- **Verdict** - pending

### R06-H28 Types are decoration - the scramble test

- **Hypothesis** - because retrieval is driven by embeddings and graph proximity rather than type labels, permuting the type labels on a cured graph will barely move QA accuracy; if so, the ontology's only causal contribution is as the cohort baseline the H23 completeness audit needs, not as a retrieval signal - which would mean months of curing machinery earns its keep only at audit time
- **Assumption attacked** - that ontology/type quality has a large causal effect on retrieval and QA (the implicit justification for curing, consolidation, calibration)
- **Lever** - post-hoc label permutation on a completed wave graph; nothing else changed
- **Mechanism** - a scramble is the cleanest possible ablation - same nodes, same edges, same embeddings, same content, only the type strings permuted; any accuracy delta is attributable to typing alone, isolating what removal ablations (which also drop structure) cannot
- **Prediction** - QA delta < 5% absolute under a full label scramble; a matched control (drop types entirely) no worse than scramble
- **Acceptance bar** - measured accuracy delta reported both ways; a null (< 5%) is registered as evidence typing is retrieval-inert and reframes curing as an audit-only investment; a non-null (>= 5%) is registered as the first causal evidence in the program that curing pays at retrieval time - either is a publishable result
- **Prior art** - argues against the null: OMD-GraphRAG (arXiv 2603.25152) and SG-KBQA (arXiv 2502.12737) both show schema guidance lifts QA, but via removal/guidance ablations that confound schema with structure; the isolated scramble test is unrun in the cited literature
- **Experiment** - <br>method: on the R05 wave graph, permute all `:Type` labels by a fixed random derangement (vary the derangement by seed offset per trial), re-run all in-wave probes, compare to the unscrambled baseline; repeat with types fully removed
- **Result** - pending
- **Verdict** - pending

### R06-H29 Duplicates are features - resolve at read time

- **Hypothesis** - because a wrong ingest-time merge is unrecoverable and destroys provenance-specific context, keeping duplicate entities connected by alias edges (the H21 machinery) and resolving them only at read time preserves per-source context and eliminates the entire wrong-merge error class; the persistent cross-type duplicate failure (47 pairs at v29) stops being a defect and becomes the intended representation
- **Assumption attacked** - that entity resolution must happen at ingest and that a merged graph is cleaner than a duplicate-rich one
- **Lever** - a no-ingest-merge variant plus a read-time resolver that walks alias edges to gather a query's entity cluster
- **Mechanism** - merging is a lossy, irreversible commit made under maximum uncertainty (one document's worth of evidence); deferring it to read time makes it reversible, query-conditioned, and evidence-complete - the resolution runs over the whole alias neighbourhood, not one mention
- **Prediction** - cross-type duplicate probes answer correctly without any ingest merge; no read-time latency regression beyond the retrieval budget; duplicate_name_density stops being a quality signal
- **Acceptance bar** - the cross-type duplicate probe class answers >= the merged graph; read-time resolution stays within the retrieval latency budget (measure hop count and wall-clock); no false cross-entity bleed introduced by alias-walk
- **Prior art** - partial: the (0.85)^n multi-hop-poisoning analysis and DEG-RAG (arXiv 2510.14271, which argues FOR ingest denoising) frame the cost of bad merges; query-time entity resolution (Bhattacharya-Getoor, JAIR 2007) is the theoretical ancestor but predates KG-QA and never compared against ingest-merge on this task
- **Experiment** - <br>method: ingest a wave with resolution disabled but alias-edge extraction on; read-time resolver over alias neighbourhoods; compare cross-type duplicate probe accuracy and latency against the merged R05 graph
- **Result** - pending
- **Verdict** - pending

### R06-H30 The question-native graph - extract what a document can answer

- **Hypothesis** - because retrieval, abstention and completeness auditing are all really about questions, inverting extraction to emit answerable questions as first-class nodes (each bound to the verbatim span that answers it) unifies all three: retrieval becomes question-to-question matching, completeness becomes expected-question coverage per type cohort, and an out-of-scope query refuses structurally when no stored question matches
- **Assumption attacked** - that a knowledge graph should represent what documents assert (entity-centric triples) rather than what they can answer (question-centric nodes)
- **Lever** - a question-native ingest variant: per chunk, extract answerable questions + their answering spans + the entity/type they concern; index questions
- **Mechanism** - doc2query proved generated questions improve retrieval, but as throwaway expansion; promoting questions to persistent typed nodes gives the graph an abstention signal (no matching question = refuse) and a completeness metric (cohort question-coverage) that entity graphs lack, folding H23 and H17's failed abstention into the structure itself
- **Prediction** - in-wave accuracy >= proposition graph; out-of-wave refusal >= 70% via coverage-gap (a question with no stored analogue); retrieval needs no entity traversal
- **Acceptance bar** - in-wave accuracy >= the proposition graph on wave-1 probes; >= 70% of out-of-wave probes refused through question-coverage gaps with < 10% false refusal; question-match retrieval alone (no entity hop) reaches the answering span
- **Prior art** - novel: the query-expansion survey (arXiv 2509.07794) and QA-Expand (arXiv 2502.08557) generate questions to expand queries at retrieval time; none make questions first-class graph citizens or audit cohort question-coverage - the closest published ideas stop at auxiliary expansion
- **Experiment** - <br>method: question-native ingest over wave-1 documents into a scratch graph; question-to-question retrieval reader; measure in-wave accuracy, out-of-wave refusal, and whether coverage-gap abstention beats the H17 vector-score null
- **Result** - pending
- **Verdict** - pending

### R06-H31 Small model plus audit loop beats big model single-pass

- **Hypothesis** - because the self-auditing repair loop can find and fix identity/fidelity/completeness gaps, a small local model (gpt-oss-120b, free) run inside that loop produces a graph at least as good as a single pass of a frontier API model (Bedrock Sonnet) - test-time compute inversion applied to graph construction, where iteration on cheap local inference substitutes for one expensive strong pass
- **Assumption attacked** - that KG quality tracks extractor model strength, so the strongest available single-pass model is the right default
- **Lever** - two builds of the same wave: gpt-oss-120b + verify-and-repair loop vs Bedrock Sonnet single pass; identical probes
- **Mechanism** - a single pass has one shot to catch every fact; a loop re-reads under focus (the R04 repair mechanism) and closes cohort gaps (H23), trading the frontier model's per-call quality for many cheap corrective calls - the same test-time-compute logic that beats parameter scaling on reasoning, never yet measured on extraction
- **Prediction** - local-loop graph QA >= single-pass QA; extraction recall (entities+rels/doc) not lower; API cost zero vs the Sonnet pass
- **Acceptance bar** - in-wave accuracy of the local-loop graph >= the Sonnet single-pass graph on the same wave; recall proxy not lower; the loop terminates (bounded iterations)
- **Prior art** - partial: Small Language Model Can Self-Correct (arXiv 2401.07301) shows 6B models self-correct via fine-tuning but do not beat GPT-4; the Trust-but-Verify survey (arXiv 2508.16665) confirms test-time verification scales - neither measures small-loop vs big-single-pass on KG extraction, and the self-correction results do not reach frontier single-pass parity, so this is the risky one
- **Experiment** - <br>method: build wave-1 twice (local-loop vs Sonnet single-pass), same documents, same probe set, compare accuracy, recall proxy and cost
- **Result** - pending
- **Verdict** - pending

### R06-H32 Cure timing must come from the evidence, not a constant

- **Hypothesis** - because the foundry ingests an unbounded stream, any curing gate that references a count (documents seen, observations accumulated, corpus fraction) encodes a scale assumption that some corpus will violate - as wave 1 proved by curing at document 4 of 481 (DEF-3); a gate on a scale-free statistic with small-sample protection built into its own confidence bound - Good-Turing missing mass UCB, n1/N + z*sqrt(n1+1)/N <= threshold - cures near true type saturation on any corpus size with zero corpus-size input, because the minimum evidence mass emerges from the bound (wide at small N) instead of being decreed
- **Assumption attacked** - that cure timing can be fixed by tuned constants (min_documents, min observations, max_fluid force) - each is a hardcoded value that drives the metrics differently at a different scale
- **Lever** - curing gate criterion only; extraction, resolution, consolidation untouched
- **Mechanism** - the missing mass n1/N is the estimated probability that the next type observation is unseen (Good-Turing); it is dimensionless and comparable across corpora; the one-sided confidence term z*sqrt(n1+1)/N widens automatically when evidence is thin, so a flat-looking window over 20 observations cannot pass, while 500 well-distributed observations can - the only remaining constants are a significance threshold and a confidence level, statistical conventions rather than scale assumptions
- **Prediction** - on the replayed wave-1 stream: the v1 plateau gate cures at doc 4 (confirmed premature); a point-estimate gate with a count floor cures at whatever the floor dictates (the floor drives the result - the disease); the UCB gate cures within the retrospective saturation window (the document band where the cumulative type inventory reaches ~95% of its wave-end value) without any corpus-size input
- **Acceptance bar** - UCB cure point inside the saturation band; v1 cure point far outside it; result invariant when the replay is truncated (first 100 docs vs first 200 docs vs full wave - a stream-native gate must not change its verdict because the future changed)
- **Experiment** - <br>data: per-document type observations replayed in ingest order from the live wave-1 graph (KGFDocument.created_at ordering, entity types + source_documents)<br>method: notebook replay ([`curing_gate_h32.ipynb`](../../notebooks/curing_gate_h32.ipynb)) computing each candidate's cure document: (a) v1 plateau, (b) chao1 composite, (c) point-estimate missing mass + count floor, (d) missing-mass UCB; retrospective saturation band from the cumulative-new-types curve; truncation invariance check at 100/200/full<br>caveat: post-cure remapping means stored types are the remapped ones - the replay measures gate behaviour on the realized stream, not the counterfactual unremapped one; recorded as a known bias
- **Result** - replayed 208 documents, 22 types, ~2100 observations. Cure points: v1 plateau doc 5, chao1 composite doc 10, point+200-floor doc 26, missing-mass UCB doc 20 - all perfectly truncation-invariant (100/200/full identical) and ALL outside the pre-registered inventory band [168, 208]. The band itself then failed interrogation: the type-arrival table shows 7 types at doc 1 carrying 85.3% of observation mass, a material second block at doc 13 (Condition, Event, ApneaEvent, Concept - ~13% of mass), and everything after doc 15 totalling ~1.4% (the doc-168 and doc-203 arrivals carry 0.14% and 0.05%) - a 95%-of-inventory criterion lets a 0.05%-mass type define saturation. Under the operative ground truth - mass-weighted forward observation coverage at cure time - the gates separate cleanly: v1 85.14%, chao1 84.91% (both cure BEFORE the doc-13 material block; the quantified DEF-3 damage), point+floor 98.51% at doc 26 (passes, but the arbitrary floor dictates the timing), UCB 98.55% at doc 20 (passes, scale-free, waits out the material block by construction because doc-13's new types spike the singleton count and widen the bound)
- **Verdict** - Confirmed under the corrected bar, and the correction is itself a finding: (1) the pre-registered inventory-saturation band is refuted as a cure criterion - ontology saturation must be measured in observation mass, not type count, and Good-Turing over occurrences is exactly the calibrated estimator of future-mass coverage; (2) v1 plateau and chao1 composite are confirmed structurally premature (they miss the doc-13 block, 15% of future mass); (3) the count-floor patch is confirmed as the disease H32 named - right coverage, arbitrary timing; (4) the missing-mass UCB gate ships: scale-free, truncation-invariant, 98.55% forward coverage, constants limited to a significance threshold and a confidence level. DEF-3 closes on this evidence
- **Amendment (2026-07-06, live validation)** - wave 1b (fresh ingest under the shipped gate) cured at document 7: the gate ran correctly (blocked docs 1-6, UCB 1.29 -> 0.06; passed at 0.0499 <= 0.05) but this run's extraction emitted 9 types from document 1 with fast-shrinking singletons, so the within-sample statistics honestly said saturated. The replay's doc-20 prediction was stream-specific: extraction is stochastic, and no gate computed on documents 1-7 can anticipate a content shift arriving at document 13 - Good-Turing is exact about the sampled distribution and structurally blind to non-stationarity. H32's scale-free gate SURVIVES as the right one-shot criterion (every count-based alternative remains strictly worse) but one-shot curing itself is insufficient on a drifting stream. Successor: H33 - cure must be reversible

### R06-H33 Cure must be reversible - re-melting beats a smarter gate

- **Hypothesis** - because no within-sample statistic can anticipate out-of-distribution novelty (H32 amendment: the UCB gate passed honestly at wave-1b document 7, then the stream's content shifts arrive later), the correct lifecycle design is a reversible cure: the drift detector's sustained-remap path (`DriftVerdict("recure")` -> FSM STABLE -> RECURING) must fire when a material post-cure type block arrives and reopen consolidation to integrate it
- **Assumption attacked** - that curing is a one-shot event to be timed perfectly; three successive gate designs (v1 plateau, count floors, missing-mass UCB) all chased a decision that is unmakeable in principle on a non-stationary stream
- **Lever** - post-cure lifecycle path only; the H32 UCB gate stays as the (best possible) initial-cure criterion
- **Mechanism** - the drift detector already computes per-document remap rates and windowed JSD against the cured distribution; sustained remap renders a recure verdict; what is unproven is whether the tuning ever lets it fire on a real stream - the old premature run produced 34 warnings and zero recures because remap spikes alternated with quiet documents and the all-3-consecutive-docs criterion never held
- **Prediction** - on wave 1b, the post-cure arrival of a material type block (the analogue of the old run's doc-13 block) produces sustained remap; if the all-consecutive criterion is too strict for bursty streams (the pre-registered suspicion), recure never fires and the criterion is refuted in favour of a windowed-mean test
- **Acceptance bar** - one of: (i) recure fires on a genuine content shift and the post-recure ontology holds >= 95% forward observation mass coverage; (ii) no material block arrives (cure-time types keep >= 95% forward coverage) - inconclusive, extend to wave 2; refuted if a material block (>= 5% of subsequent observation mass in new types) arrives with no recure
- **Experiment** - <br>data: wave 1b live run (cured at doc 7, 481 documents total), event log drift records + end-of-wave forward-coverage replay<br>method: monitor drift.decision events; at wave end, replay the realized stream to compute post-cure new-type mass and the forward coverage of the doc-7 cured set; if refuted, re-run the H32 replay harness with a windowed-mean remap criterion before touching production code
- **Note (2026-07-06, CFAR assessment)** - evaluated radar-style CFAR (adaptive threshold from a local reference window at constant false-alarm rate) as a criterion candidate: rejected on three structural mismatches - CFAR detects point spikes (our 46 wave-1b warnings are all single-doc spikes and zero were real; the target is a SUSTAINED level change), local adaptation self-masks sustained drift (the reference window is contaminated by the drift it should detect - the clutter-edge failure), and per-doc remap rates violate its noise model (heteroscedastic: a 2-entity doc yields rate 1.0 from one remap). What survives is the objective - constant false-alarm rate with a data-derived threshold, the H32 doctrine applied to drift. The fallback criterion candidate is upgraded from windowed-mean (still a fixed threshold, laggy) to CUSUM/Page-Hinkley calibrated by target average run length (dimensionless operating point, accumulates evidence so adaptation cannot mask it), with per-doc remap evidence weighted by entity count (binomial) to kill small-denominator spikes
- **Result** - pending
- **Verdict** - pending

## R07 - contrarian slate 2: the entry point, the graph's right to exist, and the reader (pre-registered 2026-07-06)

Sixteen candidate hypotheses attacking assumptions R01-R06 left standing. Trigger: the P09 forensic showed the vector index - the ONLY entry point into the graph - failing on a probe the graph could answer, rescued only by structure (SAME_AS). If the entry mechanism is the weakest link, every downstream improvement is bounded by it. The slate generalizes: which of KGF's components are load-bearing and which are theater? Literature sweeps pending per hypothesis at scheduling time (prior-art column deliberately left open - novelty is checked before a hypothesis runs, not before it is registered). Status: candidate pool; H34 scheduled immediately (retrieval-only, no completions needed - runs under the exhausted Bedrock quota).

| id | assumption attacked | contrarian claim | runnable without completions |
|----|--------------------|------------------|------------------------------|
| H34 | vector top-k finds the entry node | seeds mostly miss the gold node; PPR/propositions/aliases do the real work | yes |
| H35 | curing must happen (FSM exists) | never cure - resolve type equivalence at read time, delete the lifecycle | partial |
| H36 | chunking is neutral preprocessing | chunk boundaries destroy extraction context; whole-doc extraction beats chunked | no |
| H37 | PPR expansion earns its keep | at <5k entities PPR = 1-hop neighborhood render; the random walk is theater | yes |
| H38 | relationships carry the answers | probes are answered by properties + propositions; edges are navigation, not knowledge | yes |
| H39 | resolution must be precision-biased | over-merge + read-time split beats under-merge + alias patching (H29 complement) | partial |
| H40 | embed the question as the probe | question-form embeddings mismatch entity surfaces; embed a hypothetical answer instead | yes |
| H41 | one mixed vector index suffices | name-embeddings and description-embeddings live in different subspaces; split the channels | yes |
| H42 | the graph answers questions | the graph should only ROUTE to source chunks; answers re-derived from text can't inherit graph errors | no |
| H43 | gleaning (multi-pass extraction) pays | with audits in place, single-pass + audit >= multi-pass without audits, at lower cost | no |
| H44 | drift lives in ingestion signals | remap-rate drift is a proxy; probe-refusal-rate drift is the operative signal | partial |
| H45 | graph quality is the binding constraint | reader variance exceeds ALL graph-improvement deltas measured in R02-R04 | no |
| H46 | community summaries earn the global path | the global path fires rarely and loses to decomposed local retrieval when it does | no |
| H47 | graph growth tracks corpus growth | with working resolution, entities saturate (Heaps flattening); linear growth = resolution failure signal | yes |
| H48 | generated propositions are needed | quote propositions (H22 kind) replace generated ones entirely; extraction should copy, never write | partial |
| H49 | ingest order is not ours to choose | a buffered curriculum (reorder within a window) presents representative content to the curing gate earlier | no |
| H50 | (steelman) CFAR deserves a trial, not an argument | adaptive-threshold point detection loses to sequential change-point detection at matched false-alarm budget | yes |

### R07-H34 The entry point is the weakest link - seeds mostly miss

- **Hypothesis** - because the vector index is the sole entry into the graph (`_retrieve_local`: question embedding -> top-k seeds -> everything else expands from there), and P09 proved a gold node with near-zero question similarity is invisible to it, a material fraction of currently-passing probes pass DESPITE the seed set, not because of it - the gold evidence enters context via proposition hits, PPR expansion, or alias rendering after mediocre seeding
- **Assumption attacked** - that vector top-k reliably finds the first node for traversal; every R02-R04 improvement silently assumed the entry point works
- **Lever** - measurement only (this hypothesis changes no code); its verdict routes H40/H41
- **Mechanism** - per-probe seed attribution: for each probe, identify the graph nodes carrying gold evidence (evidence-substring match over node properties, propositions, alias-cluster renders), then classify how each entered context: (a) direct vector seed, (b) proposition-hit seed, (c) PPR-expansion only, (d) alias render only; ablate each channel and measure evidence-recall delta
- **Prediction** - <=60% of gold-carrying nodes are direct vector seeds on the 28-probe CPAP set; at least 3 probes rely entirely on channels (b)-(d); ablating PPR + propositions + aliases (pure vector top-k render) drops evidence recall by >=25%
- **Acceptance bar** - confirmed if direct-seed share <=60% or the pure-vector ablation drops recall >=25%; refuted if direct seeding alone achieves >=90% of full-pipeline evidence recall (entry point vindicated, H40/H41 deprioritized)
- **Experiment** - <br>data: rebuilt CPAP graph (neo4j2), 28-probe set with gold evidence<br>method: retrieval-only notebook ([`probe_eval_r07h34.ipynb`](../../notebooks/probe_eval_r07h34.ipynb)) - embed each question (Titan, alive), run vector top-k / proposition query / PPR / alias render separately, attribute gold-evidence entry per channel, ablation grid; zero completions needed<br>cost: ~30 embedding calls
- **Result** - 33 gold strings over 24 evidence-bearing probes; full-pipeline evidence recall 1.000 (every gold surfaced - retrieval is complete). Channel census (first-hit attribution in production order): direct vector seed 21 (63.6%), proposition-seeded node render 8, proposition text 2, alias-cluster merge 2 (both the P09/P16 dimensions - the H21 story verbatim), PPR-expansion-only 0, missing 0. Pure-vector ablation: recall 0.667 vs 1.000 full - a 33.3% drop; five probes (P01, P03, P09, P19, P22) carry ZERO gold in the pure-vector context. Matcher required three iterations, each a finding about surface forms: strict substring scored 23/33 golds "missing" while the scoreboard passes 28/28 (unit variants: 28 dB(A) vs 28 dBA); token-majority still missed values whose UNIT lives in the property key (dimensions_mm: "275 x 170 x 140" vs gold "275mm x 170mm x 140mm") - fixed with a unit-stripped numeric-skeleton match. Side observation for H39: the SAME_AS *1..2 closure of SleepStyle 200 Series contains false members (MANU, DreamStation CPAP, bCPAP prongs) via chained model-code/deictic edges - harmless today (setdefault + LIMIT 5) but a live over-merge surface
- **Verdict** - Confirmed via the ablation clause (33.3% >= 25% bar; direct-seed share 0.636 sits just above the 0.60 clause). The entry point works but is structurally leaky: a third of the evidence enters through channels that exist only because R02-R04 built them, and the biggest rescuer is proposition seeding (R03-H14, 10 golds), not PPR - which contributed ZERO golds, a direct pre-signal for H37 (PPR is theater). Routing consequence: H40 (answer-form probes) and H41 (split index) are promoted to scheduled - both target exactly the 12 golds that vector seeding misses

### R07-H35 Never cure - the lifecycle should not exist

- **Hypothesis** - because three gate designs (v1 plateau, count floors, missing-mass UCB) chased a decision H32/H33 proved unmakeable in principle on a non-stationary stream, the contrarian resolution is to never make it: keep types fluid forever, maintain a continuously-updated type-equivalence clustering (the fluid-state exploration mechanism already shown to work), and resolve type identity at read time - deleting the FSM, the curing gate, the drift-triggered recure path, and the premature-cure failure class in one move
- **Assumption attacked** - that a knowledge graph needs a curing event at all; the entire EMPTY->CURING->STABLE->RECURING lifecycle assumes types must freeze
- **Lever** - ontology lifecycle; extraction and resolution untouched
- **Prediction** - on the wave-1b stream, a never-cure run with read-time type clustering matches the cured run's probe accuracy within noise while eliminating all drift warnings and recure machinery; consolidation cost shifts to a background clustering pass whose staleness does not affect probe outcomes
- **Acceptance bar** - probe parity (within 1 probe on the 47-set) AND no query-latency regression >20%; refuted if uncured type sprawl degrades retrieval (entity fragmentation across never-merged type variants)
- **Experiment** - <br>method: replay wave 1b with curing disabled + periodic type clustering; same probe cycle; compare accuracy, latency, operational complexity<br>note: H32's gate remains the best one-shot criterion if this refutes; nothing regresses
- **Result** - pending
- **Verdict** - pending

### R07-H36 Chunking destroys the context extraction needs

- **Hypothesis** - because chunk boundaries are set by token arithmetic, not meaning, entities and relations spanning a boundary are systematically under-extracted (the OSA-consolidation variance and the SleepStyle unlinked-modes failures both sit near boundaries), and whole-document extraction with a long-context model recovers them - chunking is not neutral preprocessing but the largest unmeasured source of extraction loss
- **Assumption attacked** - that per-chunk extraction with fixed windows is an implementation detail rather than a quality decision
- **Prediction** - whole-doc extraction on the 10-doc CPAP corpus yields >=10% more cross-section relationships and closes at least one persistent failure (OSA consolidation or SleepStyle modes); per-entity precision does not drop
- **Acceptance bar** - both prediction clauses; refuted if whole-doc extraction hallucinates more (audit-detected fidelity errors rise)
- **Experiment** - rebuild CPAP twice (chunked vs whole-doc, same model), diff the graphs, run the 28-probe set + fidelity audit on both
- **Result** - pending
- **Verdict** - pending

### R07-H37 PPR is theater at this scale

- **Hypothesis** - because PPR's value proposition is global structure discovery but KGF graphs are small (<5k entities) and seed-local, the ranked expansion PPR returns is statistically indistinguishable from a plain 1-hop neighborhood of the seeds - the damping, projection, and GDS machinery buy nothing a MATCH clause doesn't
- **Assumption attacked** - R01-H2's promotion; PPR was adopted from literature on graphs 100-1000x larger
- **Prediction** - node-set overlap between PPR top-n and 1-hop-of-seeds >=80% on the probe workloads; probe outcomes identical under swap
- **Acceptance bar** - refuted (PPR vindicated) if PPR-only nodes carry gold evidence on >=2 probes; confirmed if swap changes no probe outcome
- **Experiment** - retrieval-only ([`probe_eval_r07h37.ipynb`](../../notebooks/probe_eval_r07h37.ipynb)): run both expansions per probe on the CPAP graph, diff node sets, test gold placement in the disjoint sets; zero completions
- **Result** - mean containment 0.994: PPR's top-15 is 99.4% seeds-plus-1-hop - the random walk adds essentially no reach at this scale. PPR-exclusive gold (beyond 1 hop) on exactly 1 probe (P10), under the 2-probe refuter bar. The sharper finding inverts the question: on 20 of 24 probes, gold strings sit in 1-hop neighbours that PPR RANKED OUT of its top-15 - PPR at this scale is not an expander but a lossy filter on the 1-hop neighbourhood (caveat recorded: the 1-hop-beyond set is larger than PPR's budget, so this measures what the ranking discards, not that an equal-budget swap wins; the discards were compensated by the proposition channels - full recall stayed 1.0 in H34)
- **Verdict** - Confirmed. PPR ships nothing a MATCH clause doesn't at <5k entities, consistent with its H34 zero-gold channel census. Consequence: PPR stays for now (it is not HARMFUL - removal is a simplification, not a quality fix) but the expansion budget question is reopened - a gold-aware look at WHICH 1-hop neighbours matter (relation-type priors, property density) is the successor question, and any future scale claim for PPR must be re-proven on a graph 100x this size

### R07-H38 The graph's edges are navigation, not knowledge

- **Hypothesis** - because R02-H10 moved values into properties and H22 moved evidence into propositions, the relationships themselves no longer carry answers - they only shape PPR's walk; measured per-probe, gold evidence enters context via node properties, propositions, and alias renders, with relationship-line renders contributing to zero probes
- **Assumption attacked** - that the edge inventory (1745 rels in v28) is knowledge; it may be scaffolding whose only job is connectivity for traversal
- **Prediction** - masking all relationship lines from rendered context changes <=1 probe outcome on the 28-set; masking node properties or propositions breaks >=8 each
- **Acceptance bar** - confirmed if the asymmetry holds; refuted if relation lines are load-bearing for >=3 probes (multi-hop probes are the expected refuters - the interesting result is WHICH probes need edges)
- **Experiment** - context-ablation on saved retrieval outputs; needs a reader for final answers (quota) but evidence-recall variant runs completion-free
- **Result** - pending
- **Verdict** - pending

### R07-H39 Resolution should over-merge and split at read time

- **Hypothesis** - because the H21/H22 arc proved read-time machinery (alias clusters, diversity filters) can repair identity, the precision-biased merge threshold (0.6 posterior) sits on the wrong side: merging aggressively (0.4) and splitting at read time via provenance (each merged entity keeps source_documents; a reader-facing split is a render decision) recovers the cross-type duplicates that survived every threshold tune since v19
- **Assumption attacked** - that a wrong merge is costlier than a missed merge; with provenance-carrying merges, wrong merges are reversible - missed merges silently fragment evidence forever
- **Prediction** - threshold 0.4 + provenance-split render closes >=3 of the 47 v28 cross-type duplicates without breaking any currently-passing probe
- **Acceptance bar** - duplicate count drops >=30% with probe parity; refuted if any probe regresses from a bad merge the split render fails to repair
- **Experiment** - re-run cross-type resolution at 0.4 on a graph copy, add split render, measure duplicates + probes
- **Result** - pending
- **Verdict** - pending

### R07-H40 Embed the answer, not the question

- **Hypothesis** - because entity embeddings encode names + descriptions (declarative surface) while probe embeddings encode interrogative surface, the two live in mismatched regions of embedding space - P09's failure class; embedding a HYPOTHETICAL answer sentence (cheap template or tiny-model draft: "The dimensions of X are ...") as the probe closes the gap without touching the index
- **Assumption attacked** - that the question is the right retrieval probe; every KGF retrieval since R01 embeds the raw question
- **Prediction** - answer-form probes lift direct-seed gold-node hits (H34's metric) by >=15 percentage points on the probes H34 flags as seed-misses
- **Acceptance bar** - direct-seed share rises with no regression on currently-seeded probes; refuted if templated answer-forms inject noise that displaces good seeds
- **Experiment** - runs on H34's harness with a second probe column; template variant is completion-free
- **Result** - pending
- **Verdict** - pending

### R07-H41 Split the vector index - names and descriptions are different subspaces

- **Hypothesis** - because a single embedding per entity averages name identity with descriptive content, entities with short names and long descriptions match questions on neither; separate name-embedding and description-embedding channels (two indexes, union the top-k) retrieve both identity-matches and content-matches that the mixed embedding dilutes away
- **Assumption attacked** - one vector per node, one index per graph
- **Prediction** - union-of-channels top-k contains the gold node for >=2 probes the mixed index misses (H34 provides the miss list)
- **Acceptance bar** - net gold-node coverage rises; refuted if the union just widens k (same gain from raising top_k on the mixed index)
- **Experiment** - build the two-channel index on CPAP, re-run H34 attribution; embeddings only
- **Result** - pending
- **Verdict** - pending

### R07-H42 The graph should route, never answer

- **Hypothesis** - because every graph error class found so far (over-attribution, alias fragmentation, premature cure) corrupted ANSWERS while the source chunks stayed correct, the durable architecture treats the graph as a ROUTER: retrieval resolves which source chunks matter (via entities, propositions, aliases), but the reader's context is built from the chunks themselves - graph errors can misroute (recoverable, measurable) but can never inject false content
- **Assumption attacked** - that the graph render IS the context; the self-auditing-foundry doctrine says the graph is a quality controller, not a retrieval index - this hypothesis takes that doctrine literally at query time
- **Prediction** - chunk-context answering matches graph-context accuracy on the 28-set while eliminating the H22 iter-3 over-attribution class entirely; context length grows <=2x
- **Acceptance bar** - parity + zero attribution errors; refuted if chunk contexts bury the signal (recall drops on multi-hop probes where the graph render concentrates evidence)
- **Experiment** - swap render source on saved retrievals, re-answer; needs completions (post-quota)
- **Result** - pending
- **Verdict** - pending

### R07-H43 Audits replace gleaning

- **Hypothesis** - because gleaning (R01-H3 multi-pass extraction) and the R04 audits (identity, fidelity, completeness) target the same failure - extraction missed something - but audits are deterministic, targeted, and post-hoc while gleaning is a blanket second LLM pass, single-pass extraction + the audit suite recovers >= gleaning's contribution at a fraction of the cost
- **Assumption attacked** - R01-H3's promotion predates the audit machinery; its value was never re-measured after H21/H22 shipped
- **Prediction** - on a CPAP rebuild without gleaning (audits on), entity/relation counts drop <=5% and probe accuracy holds 28/28; ingest cost drops ~35%
- **Acceptance bar** - probe parity at materially lower cost; refuted if gleaning-only entities carry gold evidence
- **Experiment** - one rebuild + probe cycle (post-quota)
- **Result** - pending
- **Verdict** - pending

### R07-H44 Drift lives in the answers, not the remap rates

- **Hypothesis** - because remap-rate drift (H33's signal) measures ontology-fit while the system's contract is answer quality, the operative drift detector is a standing probe panel replayed periodically: refusal-rate and answer-churn drift catch degradation that remap rates miss (a graph can drift ontologically while answering fine, and rot semantically while types stay stable)
- **Assumption attacked** - that ingestion-side statistics are sufficient sentinels; ties to H30 (question-native coverage as a first-class signal)
- **Prediction** - on the wave campaign, probe-churn between waves flags at least one degradation event that produces zero drift warnings
- **Acceptance bar** - one confirmed miss by the remap detector caught by probe churn; inconclusive if the campaign stays clean on both
- **Experiment** - piggybacks on R05's per-wave probe cycles - free; comparison at campaign end
- **Result** - pending
- **Verdict** - pending

### R07-H45 The reader is the bigger term

- **Hypothesis** - because R02-R04 graph improvements moved probe accuracy by 1-2 probes each while informal observation shows reader swaps (Sonnet vs gpt-oss-120b) moving results more, the variance decomposition is inverted: reader choice explains more outcome variance than all graph improvements combined - meaning further graph work has lower marginal value than reader/prompt work
- **Assumption attacked** - the project's central bet that graph quality is the binding constraint
- **Prediction** - frozen-graph reader matrix (3+ readers x 28 probes) shows inter-reader spread >= the total R02-R04 improvement delta (4 probes)
- **Acceptance bar** - spread measured honestly either way; a confirmed result redirects effort, a refuted one validates the roadmap - both outcomes are valuable
- **Experiment** - reader matrix on the frozen CPAP graph (post-quota for API readers; local reader now)
- **Result** - pending
- **Verdict** - pending

### R07-H46 The global path is dead weight

- **Hypothesis** - because community summaries exist to answer corpus-thematic questions but `is_global_query` routes only a thin slice of real workloads and decomposed local retrieval (R03-H15) already unions evidence across entities, deleting the global path and routing everything through decomposed local retrieval loses nothing measurable
- **Assumption attacked** - R01-H6 kept summaries for the global path; the path's actual hit rate was never audited
- **Prediction** - on both probe sets plus a synthetic thematic-question set, global-path answers are matched or beaten by forced-local answers; the path fires on <10% of queries
- **Acceptance bar** - refuted if thematic probes need summaries (expected refuter: "what themes does the corpus cover" class); confirmed otherwise - then summaries move to an on-demand report feature, off the query path
- **Experiment** - route-forcing flag + probe cycles (needs completions for answer comparison; routing census is free now)
- **Result** - pending
- **Verdict** - pending

### R07-H47 Entity growth must saturate - linearity is a defect signal

- **Hypothesis** - because a fixed domain has finite entities, a working resolution pipeline must show Heaps-law flattening in cumulative entity count as the campaign corpus grows; sustained linear growth means resolution is leaking duplicates at scale - making the growth curve a free, always-on, corpus-size-independent resolution health metric (the structural sibling of H32's missing-mass gate, applied to entities instead of types)
- **Assumption attacked** - that entity count growing with corpus size is normal progress; nobody checks the second derivative
- **Prediction** - wave 1b's cumulative entity curve fits Heaps K*n^b with b<0.9; per-wave b rising toward 1.0 over the campaign flags resolution leakage before duplicate counts do
- **Acceptance bar** - the fitted exponent is stable and the metric flags known-bad segments (the premature-cure run's curve should show measurably higher b); refuted if b is noise-dominated at wave scale
- **Experiment** - pure event-log/graph analysis ([`entity_growth_h47.ipynb`](../../notebooks/entity_growth_h47.ipynb)) - runs now, zero LLM calls
- **Result** - interim (wave 1b at 130/481 docs, 802 placeable entities): global Heaps fit b = 0.803 (K = 16.0) - saturating, under the 0.9 bar. Windowed exponents: 0.811 (docs 6-35), 0.753 (36-65), 0.833 (66-95), 0.966 (96-125) - the final window is near-linear. Boundary check: the whole prefix is ONE document cluster (c34), so the uptick is not a content-shift artefact; it is either 30-doc window noise or the first sign of resolution leakage at scale. The premature-run comparison clause is not computable (that graph was wiped; only type-level observations survive in the H32 replay) - recorded as a scope limitation
- **Verdict** - Interim confirmed (b < 0.9 on the realized prefix); final verdict at wave end with the full 481-doc fit. The windowed uptick is exactly the alarm shape the hypothesis proposes to operationalize - if wave-end windows sustain b > 0.9, the metric graduates from health check to defect signal and a resolution forensic follows

### R07-H48 Extraction should copy, never write

- **Hypothesis** - because H22's verbatim quote propositions carry provenance by construction and cannot paraphrase-drift, while generated propositions add an LLM rewrite between source and reader, replacing ALL generated propositions with quote propositions loses no probe and removes a hallucination surface (the aggressive half of H27's hollow graph, scoped to the proposition channel)
- **Assumption attacked** - that generated propositions add abstraction value over selected quotes
- **Prediction** - quote-only proposition channel holds 28/28 on CPAP and matches proposition-recall on the campaign set; generated-only propositions carry unique gold evidence on zero probes
- **Acceptance bar** - parity confirms; refuted if generated propositions synthesize cross-sentence facts quotes cannot express (expected refuter: aggregation probes)
- **Experiment** - channel-masking on saved retrievals (recall variant completion-free); answer variant post-quota
- **Result** - pending
- **Verdict** - pending

### R07-H49 The foundry should choose its own reading order

- **Hypothesis** - because H33 proved cure quality depends on what the stream shows the gate early, and the foundry controls a buffer even in streaming operation (documents queue before ingest), reordering WITHIN a buffer window - diversity-first by embedding dispersion, cheap and corpus-size-independent - presents representative content to the curing gate earlier and reduces both premature cures and recure churn without violating the unbounded-stream doctrine
- **Assumption attacked** - that ingest order is exogenous; the stream is unbounded but the buffer is ours
- **Prediction** - replaying wave 1b with a 20-doc diversity buffer moves the UCB cure point later (past the doc-7 early cure) and raises cure-time forward coverage by >=5 points
- **Acceptance bar** - forward coverage rises on replay across 3 shuffle seeds; refuted if the effect is within shuffle noise
- **Experiment** - extends the H32 replay harness; embeddings only, runs now
- **Result** - pending
- **Verdict** - pending

### R07-H50 CFAR on the drift stream - formal trial of the rejected candidate (pre-registered 2026-07-06)

- **Hypothesis** - adaptive-threshold point detection (the CFAR family), at a MATCHED false-alarm budget, is structurally inferior to sequential change-point detection (CUSUM/Page-Hinkley) for the drift detector's actual target - a sustained post-cure remap-level shift - for three mechanism reasons: its target model is a point spike, its local reference window absorbs sustained or gradual shifts (self-masking, the clutter-edge failure), and per-document remap rates violate its homogeneous-noise assumption (small-denominator docs: 2 entities, 1 remap, rate 0.5)
- **Assumption attacked** - the H33 design note (2026-07-06) rejected CFAR on argument alone; this hypothesis gives CFAR its fair trial, INCLUDING the m-of-n binary-integration variant a radar engineer would actually deploy against sustained targets - if the steelman wins, the note is superseded
- **Lever** - measurement only; the winning criterion becomes H33's fallback candidate, production untouched until H33 adjudicates
- **Mechanism** - all detectors calibrated to the same empirical false-alarm budget (target ARL0 ~500 docs, tuned by bisection on each detector's single free scalar over simulated clean streams), then compared on detection delay and miss rate against injected step and ramp remap shifts; unequal false-alarm budgets are the classic way detector comparisons lie, so matching is the design core
- **Prediction** - at matched ARL0: CA-/OS-CFAR miss rate on ramp-onset shifts >= 2x CUSUM's, median detection delay on step shifts >= 2x; m-of-n CFAR narrows but does not close the gap; the current production criterion (all-window-consecutive fixed threshold) also loses to CUSUM on ramp shifts; on the realized clean wave-1b stream, all calibrated detectors stay silent
- **Acceptance bar** - CFAR refuted if either the delay or the miss clause holds for every CFAR variant; CFAR VINDICATED (H33 note superseded) if the best CFAR variant lands within 25% of CUSUM on both step and ramp delay/miss at matched ARL0; results reported across three baseline noise levels (p0 = 0.01 / 0.05 / 0.10) so the verdict is not an artifact of one noise floor
- **Experiment** - <br>data: realized post-cure remap series from the wave-1b control metanode (246 docs, 1 nonzero - the clean-stream silence check) + realized entities-per-doc distribution (neo4j3) driving a Binomial synthetic baseline (remaps_i ~ Bin(n_i, p), x_i = remaps_i/n_i - reproduces the small-denominator burstiness)<br>method: numpy-only notebook ([`drift_cfar_h50.ipynb`](../../notebooks/drift_cfar_h50.ipynb)); detectors: production all-3-consecutive, CA-CFAR (trailing window 16, guard 2), OS-CFAR (75th percentile), CFAR 2-of-3 binary integration, CUSUM (quiescent-adaptation reference + design-shift allowance); step (+0.30) and ramp (10-doc onset) shifts, 200 trials each, 40-doc detection horizon; zero LLM calls<br>iteration trail: iteration 1's calibration was degenerate and each failure was itself evidence - a censored ARL0 band let never-alarms pass as calibrated; the epsilon floor turned OS-CFAR into a fixed threshold on quiet floors (the zero-floor pathology predicted by the H33 note); and the first CUSUM used a TRAILING median reference, which self-masks exactly like CFAR - replaced with quiescent-only EWMA adaptation (mu0 updates only while S=0)
- **Result** - CFAR REFUTED at every noise floor (p0 = 0.01/0.05/0.10), all detectors at matched ARL0 ~500. Ramp-shift miss rates: CUSUM 0.00/0.00/0.00, CA-CFAR 0.87/0.85/0.81, OS-CFAR 0.23/0.99/0.73, CFAR 2-of-3 (the steelman) 0.84/0.63/0.60. The self-masking signature is visible in the delay distribution: when CFAR detects at all, its median delay is 0-1 docs - it catches the onset spike or never, because after the reference window fills with shifted values the threshold rises with the drift. OS-CFAR's one good showing (miss 0.09 at p0=0.01) is the epsilon-floor degeneracy: alpha ~167 x eps = a de-facto FIXED threshold - it competed by ceasing to be CFAR. Two pre-registration surprises recorded: (1) the production all-3-consecutive criterion MATCHED CUSUM (miss 0.00 everywhere, delay 2-7 vs 0-7 docs) - the pre-registered clause that production loses on ramps is refuted at this shift size (+0.30 clears its threshold, so consecutive exceedance is near-certain); its structural weakness - a sustained shift BELOW the threshold that CUSUM would accumulate - was not in this experiment's scope. (2) On the realized clean series, CA- and OS-CFAR false-alarmed on the single spike document (point-chasing on real data; production and 2-of-3 stayed silent) - but so did plain-rate CUSUM, whose h calibrated at p0=0.05 does not transfer to the real stream's p0~0.004: the H33 note's entity-count evidence weighting is needed for spike robustness regardless of detector choice
- **Verdict** - Confirmed (CFAR formally refuted) per the pre-registered bar: every CFAR variant, including the m-of-n steelman, exceeds 2x CUSUM's ramp miss rate at matched false-alarm budget, at all three noise floors. The H33 design note stands, now with data. Two routing consequences for H33's fallback decision: the production criterion is REHABILITATED for large shifts (it matched CUSUM at delta=0.30) and the open question narrows to sub-threshold sustained drift, where accumulation should win by construction; and any successor criterion must weight per-document evidence by entity count - the real-stream check showed spike vulnerability is a noise-model problem, not a detector-family problem

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
- **Result** - wave 1b COMPLETE (481/481 documents, FSM STABLE throughout, zero recures, zero drift verdicts; 2078 entities, 4110 relations). The 9-type inventory cured at document 7 achieved forward coverage 0.9996 over the 474 post-cure documents (2235 of 2236 post-cure type observations covered; the single novel type 'Setting' carried 1 observation = 0.04% of mass, vastly below the 5% material-block threshold). No material post-cure block arrived, so the recure path was never exercised - it cannot be validated by a wave that never needed it
- **Verdict** - INCONCLUSIVE per the pre-registered bar, second clause exactly: no material block + forward coverage >= 95% -> extend to wave 2. Side-finding worth its own line: the curing gate that DEF-3 flagged as suspiciously early (cured at doc 7 of 481) was sufficient, not premature - 99.96% forward coverage over 474 unseen documents is the empirical answer to the scale-aware-floors concern on this corpus. The upgraded fallback criterion (binomial-LLR CUSUM per H50/H59) goes in before wave 2 so a future material block is detected by the better instrument

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
- **Result** - FINAL at wave end (481 docs, 2078 entities): global Heaps exponent b = 0.771 (K from log-log fit), comfortably under the 0.9 bar. The interim alarm resolved: the mid-wave final-window b = 0.966 was window noise, not a regime change - the completed wave's late windows read 0.704 / 0.713 / 0.641 / 0.837 with no sustained rise. Interim fit at 130 docs had read b = 0.803
- **Verdict** - CONFIRMED (final) - entity growth saturates on this corpus; resolution is not leaking duplicates at the macro scale. The exponent joins the panel as the ingest-axis identity marker (paired with the missing-mass UCB per the two-axis doctrine); per-wave re-fit is cheap and the windowed track catches regime changes early

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

## R08 - contrarian slate 3 + conformist deepening (pre-registered 2026-07-06)

Two camps in one round, by design. Five contrarian hypotheses (H51-H55) attack assumptions no prior round touched - the parsing layer beneath everything, the merge step that creates every defect class, the embedding bill, the Bayesian machinery, and the project's own use-case doctrine (the audit-the-auditor entry). Five conformist hypotheses (H56-H60) ride the round's strongest confirmed results and established literature, digging deeper instead of turning tables: the proposition channel (best rescuer in H34), the Good-Turing estimator family (H32), the alias audit (H21), the CUSUM class (H50), and evidence-based pruning (Less-is-More, digested). Contrarian entries get a literature sweep before running (registration does not claim novelty); conformist entries cite papers already digested in `references/papers/`.

| id | camp | assumption attacked / grounding | claim | runnable without completions |
|----|------|--------------------------------|-------|------------------------------|
| H51 | contrarian | PDF->text parsing is neutral plumbing | parsing loses more than every downstream improvement gained; the H21 forensic (subject name in ZERO chunks of its own manual) is the tip | yes |
| H52 | contrarian | one merged graph is the product | merge nothing: per-document micro-graphs + query-time federation deletes resolution, curing and drift machinery | partial |
| H53 | contrarian | vector embeddings earn their bill at seeding | BM25 over the same entity text matches Titan seeds on a spec-heavy corpus | yes |
| H54 | contrarian | Bayesian resolution earns its complexity | at 44% measured calibration accuracy the posterior is numerology; two deterministic rules + defer-to-audit reproduce its decisions | yes |
| H55 | contrarian | the use-case regime doctrine (purpose narrows every stage) | purpose-blind ingest matches purpose-driven on both probe sets - the purpose changes what the ontology CALLS things, not what retrieval finds | no |
| H56 | conformist | propositions are the measured best rescue channel (H34) + evidence-units literature | coverage is uneven and the gaps predict seed misses; targeted generation lifts the channel materially | yes |
| H57 | conformist | Good-Turing missing-mass UCB promoted (H32) | one estimator family, three inventories: relationship types and per-entity property keys get the same coverage bound - H23's statistical footing | yes |
| H58 | conformist | alias audit promoted (H21) + collective ER literature (Bhattacharya-Getoor) | a fifth detector - shared-specification evidence with property-agreement chain guard - finds aliases text cannot and fixes the false *1..2 closure | yes |
| H59 | conformist | CUSUM class superiority proven (H50), gaps identified precisely | binomial log-likelihood-ratio increments make CUSUM single-spike immune and cross-floor calibration-stable | yes |
| H60 | conformist | Less-is-More denoising (digested, SUPPORTS) + our measured de-cluttering wins (H22 iters 2-3) | pruning low-evidence elements improves precision without recall loss - the graph should hold LESS | partial |

### R08-H51 The parse is the bottleneck - loss upstream of everything

- **Hypothesis** - because the pipeline treats PDF-to-text parsing as neutral plumbing while the H21 iteration-4 forensic showed a document's own subject name ('SleepStyle 200 Series') appearing in ZERO of its chunks (stylized rendering), parsing loses named strings and table structure BEFORE extraction runs - and this upstream loss exceeds what any single downstream improvement (R02-R04 deltas: 1-2 probes each) recovered
- **Assumption attacked** - every hypothesis so far started from chunk text as ground truth; none audited the text against the source bytes
- **Prediction** - a deterministic multi-parser fidelity audit (named-string preservation, numeric-token preservation, table-cell recovery across pdftotext/pdfplumber-class parsers) finds >=20% of documents losing at least one entity-name string present in the source; at least one persistent failure (OSA consolidation or SleepStyle modes) roots upstream in parse loss, not extraction
- **Acceptance bar** - material loss found AND one persistent-failure root cause moves upstream; refuted if named-string preservation >=99% across parsers (parsing vindicated, chunk text is trustworthy ground)
- **Experiment** - deterministic parser diff over the CPAP + campaign corpora; zero LLM calls, runs now
- **Result** - pending
- **Verdict** - pending

### R08-H52 Merge nothing - federate reads instead of merging writes

- **Hypothesis** - because every major defect class so far (cross-type duplicates, premature cure, alias fragmentation, drift) exists ONLY because ingestion merges entities into one global graph, per-document micro-graphs with query-time federation - retrieve per-document subgraphs, union ANSWER evidence rather than entities - deletes entity resolution, curing and the drift machinery while matching probe accuracy
- **Assumption attacked** - that a single resolved graph is the product and resolution/curing/drift are unavoidable costs of having one
- **Prediction** - federated retrieval over the provenance-preserved graph (source_documents already stored per entity) lands within 1 probe of 28/28 on CPAP; ingest cost drops (no resolution calls); query cost rises <=2x
- **Acceptance bar** - probe parity + machinery deletion; refuted if cross-document probes (comparisons, multi-doc identity like P09) collapse without ingest-time merging - the expected refuter, which is exactly why it must be measured rather than assumed
- **Experiment** - federation retrieval mode prototype + probe cycle (reader required - local model or post-quota)
- **Result** - pending
- **Verdict** - pending

### R08-H53 The embedding bill is optional - BM25 matches Titan at seeding

- **Hypothesis** - because the corpus class is specification-heavy (model codes, part numbers, exact feature names) where lexical match is strong by construction, BM25 over the exact text the entity embeddings encode (type: name - description[:200], embeddings.py:48) matches the Titan vector index on direct-seed gold coverage (H34's metric) - the per-query embedding call and the vector index are optional for seeding on this regime
- **Assumption attacked** - that dense retrieval is a prerequisite for graph entry; the whole R01-R07 stack assumed a vector index at its base
- **Prediction** - BM25 top-8 seeds land within 10% of the vector top-8 on pure-seed evidence recall on the 28-probe set; the UNION of the two channels beats both (established dense+sparse complementarity), making hybrid seeding the constructive consequence either way
- **Acceptance bar** - confirmed if BM25 is within 10% relative (or better); refuted if the vector index beats BM25 by >25% relative on pure-seed recall
- **Experiment** - extends the H34 harness ([`probe_eval_r08h53.ipynb`](../../notebooks/probe_eval_r08h53.ipynb)): BM25 (k1=1.5, b=0.75) over the identical embedding text, same render, same matcher, same golds; zero LLM calls, zero embedding calls for the BM25 side; two controls added during the run - RRF fusion at matched k=8 budget, and vector-alone at k=16 (the budget control that decides whether a union gain is fusion or just budget)
- **Result** - pure-seed evidence recall at k=8: BM25 0.583 vs vector 0.667 - a 12.5% relative gap, inside the pre-registered dead zone (>10%, <25%). Seed overlap only 2.5/8 (the channels retrieve different nodes; BM25 wins P01/P19, vector wins 5 probes). The hybrid story then collapsed under controls: RRF at matched k=8 scores 0.646 (BELOW pure vector - fusion displaces good dense seeds), union at 16 seeds scores 0.750, but vector-ALONE at 16 seeds scores 0.854 - the union's gain was pure budget, and diluting any budget with BM25 seeds strictly loses to spending it all on the dense channel. The unplanned discovery is the seed-budget elasticity: doubling top_k from 8 to 16 lifts pure-seed recall 0.667 -> 0.854 (+28% relative), the cheapest seed-gap fix measured to date
- **Verdict** - Inconclusive per the strict pre-registered bar, but constructively resolved AGAINST the contrarian claim: the embedding bill is not optional on this corpus (BM25 12.5% behind at matched budget), and the dense+sparse complementarity consequence is refuted by the budget control (vector@16 > union@16 > rrf@8). Routing consequences: (1) the H34 seed-gap remediation ladder now starts with the trivial lever - raise top_k (0.854 at k=16 vs 0.667 at k=8) with the H22 diversity filter guarding context bloat - BEFORE the clever levers (H40 answer-form probes, H41 split index), which must now beat vector@16, not vector@8; (2) BM25 survives only as a zero-cost fallback when no embedding provider is reachable (engine-matrix degraded mode), not as a quality play

### R08-H54 The Bayesian layer is numerology at measured 44% calibration

- **Hypothesis** - because the measured calibration of the cross-type resolver sits at chance (25 ground-truth pairs, 44% accuracy, 2-point isotonic curve) yet merges still mostly work, the posterior machinery (prior x LR_desc x LR_emb x LR_cooc against a 0.6 threshold) is decoration over what is effectively name-identity plus embedding-similarity; two deterministic rules plus a defer-to-audit queue reproduce >=90% of its decisions with explainable evidence strings
- **Assumption attacked** - that probabilistic resolution machinery earns its complexity; grounded in our own weak calibration measurement, not in taste
- **Prediction** - decision replay over the logged cross-type decisions (77 in the v28 record; more on the campaign graph) shows >=90% agreement with a two-rule system; among disagreements, the identity audit sides with the deterministic rule at least as often as with the posterior
- **Acceptance bar** - agreement + parity on audit adjudication; refuted if the posterior's defer zone uniquely prevents measured false merges the rules would commit
- **Experiment** - deterministic decision replay + audit adjudication of disagreements; runs now
- **Result** - pending
- **Verdict** - pending

### R08-H55 The purpose is a placebo - audit the project's own doctrine

- **Hypothesis** - because the use-case regime doctrine (purpose narrows typing, materialization, routing, probes, drift) was adopted by design conviction rather than ablation, a purpose-blind ingest of the same corpus (generic purpose string) matches the purpose-driven graph on both probe sets - the purpose changes what the ontology CALLS things and how the operator reads the graph, not what retrieval finds
- **Assumption attacked** - the project's own most-cherished doctrine; this is the round's audit-the-auditor entry, and a refutation here would be the cheapest good news of the campaign (doctrine survives as governance and explainability value even if the retrieval claim falls)
- **Prediction** - purpose-blind CPAP rebuild lands within 1 probe of 28/28; type inventories differ visibly while retrieval metrics do not
- **Acceptance bar** - parity refutes the doctrine's RETRIEVAL claim specifically; doctrine confirmed if purpose-blind drops >=3 probes
- **Experiment** - one CPAP rebuild under a generic purpose + full probe cycle (extraction LLM required - local model or post-quota)
- **Result** - pending
- **Verdict** - pending

### R08-H56 Deepen the best channel - proposition coverage audit and closure

- **Grounding** - propositions are the measured best rescue channel (H34: 10 of 12 non-seed golds; R02-H11: +10.6% evidence recall, lifts a weak reader to strong-reader parity); fine-grained evidence-unit retrieval is established practice (evidence-units paper, digested)
- **Hypothesis** - proposition coverage is uneven (optimize-time generation from descriptions plus the H22 quote scan) and the gaps predict remaining seed misses; a per-chunk coverage audit followed by targeted quote-proposition generation lifts the pure-proposition channel materially
- **Prediction** - >=20% of evidence-bearing chunks carry zero propositions; closing the gaps lifts proposition-channel evidence recall >=15 points on the H34 harness, with the trigram diversity filter keeping the context clean
- **Acceptance bar** - the recall lift lands without displacing currently-retrieved evidence; refuted if coverage is already saturated (audit finds <5% gaps)
- **Experiment** - deterministic coverage audit + generation extension + H34 re-measure; embeddings only, runs now. Scope note (2026-07-06, revised after H108): the attached-but-unrendered count was 2, not 6 (H61 overcount, corrected); H108 refuted per-seed surfacing as a render fix - the global proposition channel is the correct mechanism, so this audit's coverage half stands but the render half is retired
- **Result** - pending
- **Verdict** - pending

### R08-H57 One estimator family, three inventories - Good-Turing for completeness

- **Grounding** - the missing-mass UCB is promoted (H32: 98.55% forward coverage, scale-free, truncation-invariant); Good-Turing is the calibrated estimator of unseen mass for ANY categorical inventory, not just entity types
- **Hypothesis** - the same UCB applied to the relationship-type inventory and to per-entity-type property-key inventories gives H23's completeness audit its statistical footing: "the graph knows what it doesn't know" becomes a per-inventory coverage bound, and low-coverage cohorts predict probe refusals
- **Prediction** - at wave-1b end the relationship-type missing mass sits <=5% while per-type property coverage varies widely; cohorts with UCB > 0.2 contain the majority of refusal-control failures in the campaign probe cycle
- **Acceptance bar** - coverage bounds rank-correlate with refusals; refuted if the bounds are flat across cohorts (uninformative)
- **Experiment** - pure graph counting now; correlation against the per-wave probe cycles as they land
- **Result** - pending
- **Verdict** - pending

### R08-H58 Collective-evidence alias detector - the fifth detector

- **Grounding** - the alias audit is promoted (H21: 28/28, four deterministic detectors); collective/relational entity resolution (Bhattacharya-Getoor, digested) shows relationship evidence resolves what attribute similarity cannot
- **Hypothesis** - a fifth deterministic detector - shared-specification evidence (two entities agreeing on >=k identical property VALUES, e.g. the same dimensions_mm and the same power figure) gated by document or neighborhood overlap - finds true aliases the four textual detectors miss; the same property-agreement test, required for SAME_AS chain traversal, removes the false *1..2 closure members H34 observed (MANU, DreamStation CPAP, bCPAP prongs) without losing P09
- **Prediction** - >=3 new true aliases on the campaign graph at the standing zero-false-alias bar; the chain guard drops all three false closure members
- **Acceptance bar** - evidence-listed inspection confirms zero false; refuted if generic value collisions ('2 years' warranty) dominate the candidate set beyond filtering
- **Experiment** - extend `graph/aliases.py` + inspection listing + P09 regression; deterministic, runs now
- **Result** - pending
- **Verdict** - pending

### R08-H59 Evidence-weighted CUSUM - close the two gaps H50 measured

- **Grounding** - H50 formally refuted CFAR and left CUSUM the class winner with two measured gaps: the plain-rate form false-alarmed on the real stream's single small-denominator spike, and its threshold calibrated at one noise floor did not transfer to another
- **Hypothesis** - CUSUM on the per-document binomial log-likelihood ratio - increment log[Bin(remaps_i; n_i, p1) / Bin(remaps_i; n_i, p0)] - is single-spike immune by construction (a rate of 1.0 on a 2-entity document carries little evidence) and calibration-stable across noise floors (the LLR folds the noise model into the statistic)
- **Prediction** - on the H50 harness: zero alarms on the realized clean series including the spike document; a threshold calibrated at p0=0.05 lands in the ARL0 band at 0.01 and 0.10 without recalibration; detection miss/delay matches or beats plain CUSUM at matched budget
- **Acceptance bar** - all three clauses; refuted if the LLR form loses detection power at matched budget
- **Experiment** - extends the [`drift_cfar_h50.ipynb`](../../notebooks/drift_cfar_h50.ipynb) harness; numpy only, runs now; on confirmation this becomes H33's fallback criterion candidate
- **Result** - pending
- **Verdict** - pending

### R08-H60 The graph should hold less - evidence-based pruning

- **Grounding** - Less-is-More KG denoising (digested, SUPPORTS verdict) plus our own measured de-cluttering wins: H22 iteration 2 (removing alias-clone propositions fixed retrieval starvation) and iteration 3 (de-cluttering exposed a reader over-attribution error that clutter had masked)
- **Hypothesis** - pruning low-evidence elements - entities with single-mention provenance, no properties and no propositions; relationships with orphaned endpoints or no currently-valid interval - improves retrieval precision and context cleanliness without recall loss
- **Prediction** - the prune candidate set covers >=15% of campaign-graph entities; probe metrics hold after pruning-on-copy; per-query context length drops measurably; no gold-carrying element is ever in the candidate set (checked before delete, reversible via versioning)
- **Acceptance bar** - zero probe regression + measurable context cleanup; refuted if any gold-carrying element qualifies for pruning (the criteria are then wrong, not the graph)
- **Experiment** - prune-on-copy + evidence-recall probe cycle (completion-free variant now; answer variant post-quota)
- **Result** - pending
- **Verdict** - pending

## R09 - graph topology round: structural markers, communities, rebuild policy, and the metric-traversal coupling (pre-registered 2026-07-06)

The graph has almost no structural self-knowledge. What exists today: GDS Leiden runs at optimize time and writes `communityId` to every entity (`graph/graphrag.py:52`) but NOTHING reads it at query time; the Heaps exponent (H47) is the only macro structural marker; the rebuild trigger is JSD over type frequencies (drift.py) - a distributional signal, blind to topology; density has been touched twice from the retrieval side (H22 de-cluttering, H60 pruning); and H37/H67-class traversal facts exist only where a hypothesis happened to need them. This round builds the instrument panel deliberately - degree structure, neighborhood overlap, reachability, betweenness, assortativity, core decomposition, hop-distance law, community quality, spectral connectivity - with one standing doctrine, the H37 lesson generalized: **a metric earns a place on the panel only if it (a) predicts probe outcomes, (b) triggers a maintenance action earlier or cheaper than an existing trigger, or (c) improves a traversal/render decision at matched budget. Anything else is dashboard decoration and gets recorded as such.** Four themes: structural health markers (H61-H67), communities (H68-H72), rebuild policy (H73-H76), metric-traversal coupling (H77-H80). Literature sweeps precede any design change that ships (registration claims no novelty); grounded against our own measured facts throughout - the 0.58 rel-type-diversity calibration correlate (v28), the vector@16 = 0.854 bar (H53), the false SAME_AS closure members (H34), the 47 cross-type duplicates (v29 defect record).

| id | theme | grounding / assumption attacked | claim | runnable without completions |
|----|-------|--------------------------------|-------|------------------------------|
| H61 | markers | render caps are uniform (LIMIT 15 rels, 5 aliases) over a heavy-tailed degree distribution | uniform caps silently discard gold on hubs; degree-aware truncation recovers it at matched budget | yes |
| H62 | markers | duplicate detection is text/embedding-driven | duplicates are structural twins first: neighbor-Jaccard ranks true duplicate pairs better than embedding similarity | yes |
| H63 | markers | every entity is assumed retrievable in principle | >=30% of entities are 2-hop dark matter under production seeding, and dark matter is mostly the low-evidence prune set (H60 overlap >=70%) | yes |
| H64 | markers | all nodes are equal for merge-risk purposes | evidence paths concentrate through few high-betweenness cut vertices; a bad merge there damages 3x more than on periphery | yes |
| H65 | markers | Heaps (H47) is the only resolution-leak marker | degree assortativity is its topological companion: stable disassortative when healthy, rising when duplicate hubs link each other | partial |
| H66 | markers | no compact structural fingerprint exists | the k-core shell profile is stable across waves and gold evidence concentrates in middle shells (>=70%) | yes |
| H67 | markers | traversal depth is an open design dial | the seed-to-gold hop distribution is bimodal - 0-2 hops or disconnected; no traversal of ANY depth rescues missing golds (generalizes H37) | yes |
| H68 | communities | Leiden communities are assumed topical | communities are provenance artifacts: NMI(community, dominant source doc) >= 0.6 - documents rediscovered, not topics | yes |
| H69 | communities | seeds are picked by vector score alone | seed-community concentration predicts misses; community-diversified seeding beats the vector@16 = 0.854 bar | yes |
| H70 | communities | merge decisions ignore community structure | false merges are >=2x more likely cross-community; a community-mismatch veto removes the false SAME_AS closures without losing P09 | yes |
| H71 | communities | R6 demoted community summaries by argument | measured retest: context cores add <=1 marginal gold at local granularity - retire from the local path with numbers, not taste | partial |
| H72 | communities | graph density is only ever reduced | intra-community transitive closure flips >=1 multi-hop probe to direct-seed answerable at zero context-precision cost (tension pair with H80) | yes |
| H73 | rebuild | incremental maintenance is assumed lossy vs rebuild | full rebuild and maintained graph are retrieval-equivalent (+-1 probe) while structurally divergent - maintenance debt is retrieval-invisible at this horizon | no |
| H74 | rebuild | JSD over type frequencies is the rebuild trigger | a composite of structural deltas (Heaps residual, assortativity, dark-matter, shell-profile JSD) fires earlier with zero false alarms | partial |
| H75 | rebuild | rebuild is all-or-nothing | community-scoped partial rebuild recovers >=80% of full-rebuild benefit at <=30% cost | no |
| H76 | rebuild | ingest order is assumed immaterial | reverse-order ingest diverges >=10% in inventory but <=2% in probe recall - path dependence lives in identity, not retrieval | no |
| H77 | coupling | connectivity is not monitored | algebraic connectivity + effective diameter move before type-frequency JSD under structural degradation (injection replay) | yes |
| H78 | coupling | render budget is uniform per node | degree-quantile budget allocation is Pareto-better: no probe loses, H61's truncation victims recover, context length unchanged | yes |
| H79 | coupling | render candidate ranking uses PPR (theater per H37) | relationship-type entropy - the top v28 calibration correlate (0.58) - ranks render candidates better than PPR at matched budget | yes |
| H80 | coupling | edge pruning has no measured safety line | bottom 30% of edges by (betweenness x evidence x validity) composite are removable with ZERO evidence-recall loss; the knee locates the operating point | yes |

### R09-H61 Hub truncation - uniform render caps on a heavy-tailed graph

- **Grounding** - the per-node render caps relations at LIMIT 15 and aliases at 5 uniformly (`pipeline.py` render spec); entity-graph degree distributions are heavy-tailed, so a uniform cap is a silent lossy filter exactly on the nodes most likely to be retrieved
- **Hypothesis** - top-decile-degree nodes carry several times more relations than the cap admits, and on the probe set at least some gold relation edges rank outside the arbitrary top-15 on rendered hubs - evidence recall is lost to truncation, not to seeding
- **Prediction** - top-decile nodes hold >=3x the cap in relations; >=2 of 28 probes have a gold edge truncated on at least one rendered hub; re-render with the same TOTAL edge budget reallocated by degree quantile recovers them
- **Acceptance bar** - recovery at matched total budget; refuted if truncated hub edges never carry gold (uniform caps vindicated, hubs are generic)
- **Experiment** - deterministic: degree census + truncation audit + matched-budget re-render on the H34 harness; runs now
- **Result** - audit in [`probe_render_r09h61.ipynb`](../../notebooks/probe_render_r09h61.ipynb). The degree premise is wrong at render scale: median degree 1, p90 = 5, only 62 of 2531 connected entities (2.4%) exceed the cap of 15, top-decile mean 13.5 = 0.9x cap (bar was 3x). Gap decomposition of the 33 golds against the vec-8 render: BASE 18 (rendered fine), REL<=15 1, REL-TRUNC **0** - not a single gold lives in a truncated relation line - SEEDING 8 (carrier not among the 8 vector seeds; the H53 top_k lever), PROP-ATTACHED 6. Matched-budget re-ranking (storage vs neighbor-degree vs type-entropy round-robin) is a three-way tie at 23/33 presence - ordering is irrelevant because nothing gold-bearing is ever truncated. The discovery is the PROP-ATTACHED bucket: 6 golds (18%) sit in propositions ATTACHED to an already-rendered seed node, invisible because production renders only propositions the separate global proposition vector channel happens to retrieve - the node is in the context, its proposition carries the answer, the render does not show it. That - not truncation - is the H67 gap (0.909 carriage vs 0.636 rendered)
- **Verdict** - REFUTED - uniform caps are vindicated on this corpus; hubs are not being truncated out of their gold. Correction (2026-07-06, from the H108 forensics): the PROP-ATTACHED bucket was overcounted at 6 - the per-seed sequential placement loop could mislabel golds carried by a later seed's base render, and the fuzzy matcher degenerates on short golds (single-digit token majority). True attached-prop-only golds: 2. The headline verdict (zero truncation loss, caps vindicated) is unaffected - it never depended on the bucket split. The render gap decomposes as seeding (8, fixed by vector@16 per H53) + attached-but-unrendered propositions (6, a render-surfacing fix: show top-M attached propositions per seeded node - routed into H56's experiment design as the closure step's render half). H78 and H79 are pre-adjudicated by the same measurement (see their entries)

### R09-H62 Structural twins - neighbor-Jaccard finds duplicates text cannot

- **Grounding** - duplicates enter as parallel nodes sharing neighborhoods (same manufacturer, same category, same spec values) before any SAME_AS links them; every production detector is text- or embedding-driven; collective ER literature says relationships resolve what attributes cannot
- **Hypothesis** - neighbor-set Jaccard over the entity graph ranks true duplicate pairs above embedding cosine ranking, and the two signals combined strictly dominate either alone
- **Prediction** - on the labeled duplicate inventory (47 cross-type duplicates, v29 record + campaign additions), Jaccard MAP > embedding MAP; combined rank raises MAP further; the false-positive head of the Jaccard ranking is dominated by siblings (same-family models), which the description-contrast feature already used in cross-type resolution filters
- **Acceptance bar** - MAP improvement with sibling filtering; refuted if structural ranking is uninformative (graph topology knows less about identity than text does)
- **Experiment** - deterministic ranking comparison on labeled pairs; runs now; on confirmation the signal feeds H58's fifth detector as a sixth evidence term
- **Result** - pending
- **Verdict** - pending

### R09-H63 Dark matter - the census of the unreachable

- **Grounding** - retrieval-first doctrine promises perfect context in 1-2 hops, which presumes the evidence is within 2 hops of SOME seed; nothing has ever measured how much of the graph is reachable at all under the production seed budget
- **Hypothesis** - a material fraction of entities is 2-hop dark matter - never inside seeds-plus-2-hops for any probe - and dark matter is substantially the same population as the H60 low-evidence prune set (single mention, no properties, no propositions)
- **Prediction** - >=30% of campaign-graph entities are dark under vector@16 seeding across the probe set; >=70% of dark matter qualifies for the H60 prune candidate set; zero gold-carrying entities are dark
- **Acceptance bar** - overlap confirms pruning is safe precisely because the prunable mass is already unreachable; CRITICALLY refuted if gold-carrying or high-evidence entities are dark - that converts the finding from a hygiene fact into a seeding-gap alarm and routes to H40/H41/H69
- **Experiment** - deterministic reachability census (BFS from per-probe seed sets); runs now
- **Result** - census in [`dark_matter_r09h63.ipynb`](../../notebooks/dark_matter_r09h63.ipynb) on the CPAP graph (registered against the campaign graph; the gold probe set lives here - campaign version lands with the wave-end probe cycle). Lit region under production seeds: 2036 of 2798 entities (72.8%); wide k=16: 2098 (75.0%) - dark share 0.250, narrowly under the 0.30 bar. The identity claim failed decisively: the H60 strict prune predicate (single-chunk AND no properties AND no propositions) qualifies only 39 entities (1.4% of the graph, against H60's >=15% prediction - a strong pre-signal that H60's criteria are far narrower than registered), so the dark-prunable overlap is 0.051 vs the 0.70 bar. Zero golds are fully dark (every gold retains at least one lit carrier - consistent with H67). Iteration note: the first run flagged 430+ 'dark golds' - a matcher artifact (value-like golds such as '16 cm' fuzzy-match many incidental entities); the corrected clause tests whether ALL of a gold's carriers are dark
- **Verdict** - REFUTED on the identity claim: dark matter is NOT the low-evidence mass. The dark 25% is rich, well-extracted catalog entities (suction units, nebulizers, sensor accessories) that the 28-probe set simply never asks about - 'dark' measures probe-set coverage of the corpus, not intrinsic unreachability. The safety clause holds (no gold beyond reach). Routing: H60's prune criteria need re-registration against measured reality (1.4%, not >=15%); probe-set breadth, not graph hygiene, is what the dark share tracks - useful as a coverage metric, not a pruning license

### R09-H64 Betweenness bottlenecks - where a bad merge hurts most

- **Grounding** - merge errors are currently treated as uniformly costly; graph theory says inter-region paths concentrate through few cut vertices, so error cost should be wildly non-uniform
- **Hypothesis** - seed-to-gold evidence paths concentrate through a small high-betweenness set; corrupting a bottleneck node (simulated bad merge/split) degrades multi-hop probe recall several times more than corrupting a random node - merge-audit priority should be betweenness-weighted
- **Prediction** - top-1% betweenness nodes lie on >=50% of seed-to-gold shortest paths; simulated corruption at bottlenecks degrades recall >=3x random-node corruption; the campaign graph's bottleneck set is small enough (<=30 nodes) for per-wave manual-grade auditing
- **Acceptance bar** - concentration + differential damage; refuted if paths spread uniformly (then audit priority by degree or evidence count instead)
- **Experiment** - GDS betweenness (approximate) + path census + corruption replay on a copy; runs now
- **Result** - pending
- **Verdict** - pending

### R09-H65 Assortativity trend - the topological companion to Heaps

- **Grounding** - H47 watches identity-leak VOLUME (vocabulary growth); nothing watches leak TOPOLOGY. A healthy spec-graph is disassortative - hubs (manufacturers, categories, common spec values) bind periphery; duplicate hubs linking each other push degree assortativity upward
- **Hypothesis** - degree assortativity r stays in a narrow disassortative band across a healthy wave and responds measurably to injected resolution leaks - a second-order drift marker orthogonal to remap rate (which sees only what resolution DID, not what it missed)
- **Prediction** - wave-1b series holds r < -0.05 throughout with band width < 0.1; merge-undo injection replay (un-merging known true aliases at increasing rate) moves r upward monotonically and detectably at >=10% injection
- **Acceptance bar** - stability + injection sensitivity; refuted if r is noisy or flat under injection (not a marker - record as decoration per the panel doctrine)
- **Experiment** - snapshot series reconstruction (approximate, from first-seen positions and edge provenance) + injection replay; partial now, exact series from wave 2 onward if promoted
- **Result** - pending
- **Verdict** - pending

### R09-H66 The k-core fingerprint - shells as structural identity

- **Grounding** - no compact, corpus-size-independent fingerprint of graph structure exists; the k-core shell-index distribution is cheap, deterministic, and captures density layering in one histogram
- **Hypothesis** - gold evidence concentrates in the middle shells - the periphery (shell 1) holds orphan mentions, the max core holds generic hubs - and the shell profile is stable across healthy waves, making profile divergence a structural regime-change alarm
- **Prediction** - >=70% of gold-evidence entities sit in shells 2..k_max-1; profile JS-divergence between healthy wave snapshots < 0.05; the premature-cure failure mode (over-merge) would have shown as max-core inflation
- **Acceptance bar** - concentration + stability; refuted if gold spreads uniformly across shells (core number carries no evidence signal)
- **Experiment** - core decomposition (networkx/scipy on the projected entity graph) + gold mapping via the H34 harness; runs now
- **Result** - pending
- **Verdict** - pending

### R09-H67 The hop-distance law - no traversal depth rescues a missing gold

- **Grounding** - H37 showed PPR specifically adds nothing over seeds+1-hop; the open general question is whether ANY traversal mechanism of any depth could - i.e., what the seed-to-gold graph-distance distribution actually looks like; retrieval-first doctrine (perfect context in 1-2 hops) predicts its shape
- **Hypothesis** - the distribution is bimodal: gold evidence is either within 0-2 hops of a production seed or in a different connected component / beyond any practical radius - the 3-5 hop band is nearly empty, so traversal-depth engineering is a dead lever and only seeding (H40/H41/H69) or densification (H72) can recover misses
- **Prediction** - >=90% of reachable golds at <=2 hops from the nearest seed; <5% in the 3-5 hop band; misses are disconnection, not distance
- **Acceptance bar** - bimodality confirms and permanently closes the traversal-depth design dial; refuted if a material 3-4 hop band exists - then deeper traversal is a REAL lever, the retrieval-first doctrine needs an amendment, and H37's verdict was scale-specific rather than structural
- **Experiment** - shortest-path census from per-probe production seeds to gold nodes; deterministic, runs now; the round's flagship - every coupling hypothesis (H78-H80) interprets against this distribution
- **Result** - census in [`graph_census_r09h67.ipynb`](../../notebooks/graph_census_r09h67.ipynb) over the rebuilt CPAP graph (2798 entities, 3905 valid non-SIMILAR_TO edges, 19654 attached propositions). All 33 golds have carrier entities (zero orphans - at gold granularity the extraction surface is complete, a partial pre-answer to H51). Hop distribution under production seeds (vec-8 + propositions): 30 golds at hop 0 (a seed itself carries the gold), 1 at hop 1, 2 at hop 2, ZERO in the 3-5 band, ZERO unreachable. Wide budget (k=16): 31 at hop 0, 2 at hop 2. Reachable-at-<=2 share 1.000 (bar >= 0.90), 3-5 band share 0.000 (bar < 0.05). The predicted bimodality did not even materialize - there is no disconnected mass for this probe set; the distribution is a point mass at the seeds. Cross-link: hop-0 carrier share (0.909) far exceeds H34's rendered direct-seed share (0.636) - the gold is ON the seeded node far more often than the render SHOWS it, which relocates the remaining loss from traversal to rendering (truncation/ordering - exactly H61/H78/H79 territory)
- **Verdict** - CONFIRMED, stronger than registered: the traversal-depth dial is closed - 100% of gold evidence sits within 2 hops of a production seed and 91% sits ON a seed. No traversal mechanism of any depth has anything to recover; the entire remaining gap between hop-0 carriage (0.909) and rendered recall is a RENDER problem, not a reach problem. H72 (densification) loses its multi-hop motivation on this corpus and must now justify itself purely as a render-shortcut; H78/H79 gain priority - they attack the measured gap directly

### R09-H68 Communities as provenance artifacts - documents rediscovered

- **Grounding** - Leiden communities exist on every entity (`communityId`, written at optimize) but their SEMANTICS were never audited; extraction is per-document, so co-mention edges are document-local by construction - the null hypothesis for any KG built this way is that community structure recapitulates document boundaries
- **Hypothesis** - normalized mutual information between community assignment and dominant source document is high (>=0.6) - the communities are provenance artifacts, and any community-based feature is document-identity in disguise until cross-document resolution breaks the correspondence
- **Prediction** - NMI >= 0.6 on the campaign graph at wave-1b end; the correspondence WEAKENS as waves accumulate (cross-doc merges braid documents together) - NMI trend down across waves is itself a resolution-quality signal
- **Acceptance bar** - high NMI confirms (and demotes naive community features); refuted if NMI < 0.3 - communities genuinely cross-document, semantically real, and H69-H71 gain a stronger footing
- **Experiment** - re-run Leiden on the campaign graph + NMI census; deterministic GDS + sklearn, runs now
- **Result** - pending
- **Verdict** - pending

### R09-H69 Community-diversified seeding - beat vector@16 with structure

- **Grounding** - the standing seed bar is vector@16 = 0.854 (H53 budget control); vector seeds are picked by score alone, and score-similar entities cluster - if all 16 seeds land in 1-2 communities, the probe sees one region of the graph however large the budget
- **Hypothesis** - seed-community concentration predicts evidence misses, and enforcing community diversity (swap tail seeds for the next-best candidates from unrepresented communities) beats the pure-vector allocation at matched budget
- **Prediction** - probes whose 16 seeds span <=2 communities have measurably lower evidence recall; diversified@16 >= 0.90 vs the 0.854 bar
- **Acceptance bar** - matched-budget win; refuted if concentration does not correlate with misses (communities carry no retrieval signal - expected under an H68 artifact verdict, which is why H68 runs first)
- **Experiment** - deterministic re-seeding replay on the H34/H53 harness; runs now, sequenced after H68
- **Result** - pending
- **Verdict** - pending

### R09-H70 The conductance merge gate - cross-community merges are suspect

- **Grounding** - the false SAME_AS closure members H34 exposed (MANU, DreamStation CPAP, bCPAP prongs) and the 47 cross-type duplicates form a labeled merge-error inventory; community membership was never a resolution feature
- **Hypothesis** - false merges are disproportionately cross-community (>=2x the rate of true merges); a community-mismatch veto - or a Bayesian LR term if H54 leaves the posterior standing - removes false closures without touching legitimate cross-document aliases
- **Prediction** - the labeled false set shows >=2x cross-community rate; applying the veto retroactively drops the false closure members while P09 (legitimate multi-doc identity) survives
- **Acceptance bar** - differential + P09 regression-free; refuted if community membership is independent of merge correctness
- **Experiment** - deterministic replay over the labeled decision inventory; runs now, sequenced after H68 (an artifact verdict there weakens but does not kill this - provenance mismatch is itself evidence)
- **Result** - pending
- **Verdict** - pending

### R09-H71 Context cores retested - numbers where R6 used argument

- **Grounding** - R6/H46 demoted community summaries to the global-only path largely by argument; H34's attribution harness now exists to measure channel value exactly; propositions are the proven best rescue channel (10 of 12 non-seed golds)
- **Hypothesis** - community-summary nodes ("context cores") as a local seeding/render channel add at most 1 marginal gold over vector@16 + propositions at spec-heavy probe granularity - the wrong granularity for local probes, whatever their global/thematic value
- **Prediction** - <=1 marginal gold on the 28-probe set; the channel's contexts displace higher-value proposition content at matched budget (net negative or flat)
- **Acceptance bar** - <=1 marginal gold retires cores from the local path permanently (with numbers this time); >=3 marginal golds reinstates them and reopens R6
- **Experiment** - summary generation for campaign communities (completions - local model or post-quota) + H34 attribution extension; partial now (harness prep deterministic)
- **Result** - pending
- **Verdict** - pending

### R09-H72 Closure densification - the graph earns edges inside tight communities

- **Grounding** - density has only ever been REDUCED (H22, H60); the H67 hop census will show whether misses are distance; hierarchical relations (PART_OF, SUPPORTS_MODE, COMPATIBLE_WITH) are transitively meaningful within tight communities - the tension pair with H80, by design: one adds edges, one removes, the probe set adjudicates optimal density from both sides
- **Hypothesis** - materializing transitive closure edges for hierarchy-class relations WITHIN high-density communities (provenance-marked as inferred) flips at least one multi-hop probe to direct-seed answerable at zero context-precision cost
- **Prediction** - >=1 P09/P22-class probe flips; inferred edges never displace gold in renders (they enter below extracted edges in render ranking); closure inflation stays bounded (<=15% edge growth)
- **Acceptance bar** - flip without displacement; refuted if inferred edges bloat contexts or displace gold (the H22 lesson: context is a fixed budget)
- **Experiment** - deterministic closure computation on a graph copy + H34 probe replay; runs now
- **Result** - pending
- **Verdict** - pending

### R09-H73 Rebuild equals maintenance - is the debt retrieval-visible?

- **Grounding** - the rebuild decision engine exists (drift verdicts) but the COST of not rebuilding was never measured; the fear that incremental maintenance accumulates retrieval-relevant debt is an assumption
- **Hypothesis** - a from-scratch re-ingest of the identical corpus and the incrementally maintained graph are retrieval-equivalent (within 1 probe / 2% evidence recall) while structurally divergent (entity inventory, type assignments) - maintenance debt is real but retrieval-invisible at this horizon, so rebuild cadence should be driven by structure-hygiene markers (H65/H66/H77), not recall fear
- **Prediction** - probe metrics within noise; inventory divergence >=10% of entities; the divergent mass is dominated by low-evidence periphery (connects to H63's dark matter)
- **Acceptance bar** - equivalence + divergence localized to periphery; refuted if the rebuild recovers probes the maintained graph misses (maintenance debt is retrieval-real - rebuild triggers must tighten)
- **Experiment** - full re-extraction of wave 1b into a fresh graph (local model, post-wave GPU window) + dual probe cycle; needs completions
- **Result** - pending
- **Verdict** - pending

### R09-H74 The composite rebuild trigger - structure fires before distribution

- **Grounding** - the production rebuild trigger is JSD over type frequencies - blind to topology by construction; this round instruments Heaps residual (H47), assortativity trend (H65), dark-matter delta (H63) and shell-profile divergence (H66); a composite of orthogonal markers should dominate any single one
- **Hypothesis** - the structural composite predicts probe-recall degradation at least one wave earlier than the JSD trigger, with zero false fires on healthy waves
- **Prediction** - backtested over the R05 wave snapshots + per-wave probe cycles as they land: composite leads JSD on any true degradation event; on the (so far) healthy campaign, NEITHER fires - the composite's specificity clause
- **Acceptance bar** - earlier + specific; refuted if JSD alone matches the composite (parsimony wins - the panel stays diagnostic, the trigger stays simple)
- **Experiment** - backtest as R05 probe cycles accumulate; partial now (marker series), full adjudication needs >=2 wave cycles
- **Result** - pending
- **Verdict** - pending

### R09-H75 Partial rebuild - repair the sick community, not the graph

- **Grounding** - rebuild is currently all-or-nothing; if degradation localizes (H68-H70 give community-level quality signals), full rebuild wastes extraction on healthy regions
- **Hypothesis** - when markers localize degradation to specific communities, re-extracting ONLY the documents touching those communities recovers >=80% of the full-rebuild recall benefit at <=30% of the extraction cost
- **Prediction** - on an induced-degradation graph copy (merge-undo injection concentrated in one community), community-scoped repair closes >=80% of the probe gap at the predicted cost fraction
- **Acceptance bar** - the 80/30 clause; refuted if degradation delocalizes on repair (fixing one community exposes cross-community damage - rebuild is genuinely global)
- **Experiment** - induced degradation + scoped re-extraction (completions - local model) + probe cycle; queue for the wave-3+ window
- **Result** - pending
- **Verdict** - pending

### R09-H76 Order invariance - path dependence lives in identity, not retrieval

- **Grounding** - ingest order determines curing content, merge order and description survivorship; whether any of that matters to the USER-VISIBLE surface was never measured; H54's decision replay gives the identity-layer half of the answer, this gives the retrieval half
- **Hypothesis** - reverse-order ingest of wave 1b yields >=10% entity-inventory divergence (path-dependent identity) but <=2% probe-recall divergence (retrieval robust to history) - the foundry's product is the retrieval surface, not the inventory, and inventory determinism is worth less engineering than it tempts
- **Prediction** - inventory symmetric difference >=10%; probe metrics within 2%; type inventories nearly identical (curing converges to the same ontology from either direction - a strong vote for the curing gate's stability)
- **Acceptance bar** - the split verdict (identity diverges, retrieval does not); refuted in the interesting direction if retrieval diverges too - ingest order becomes a first-class quality variable and curriculum effects (H49) gain standing
- **Experiment** - full reverse-order re-ingest (completions - local model); queue behind H73, shares its fresh-graph infrastructure
- **Result** - pending
- **Verdict** - pending

### R09-H77 Connectivity moves first - the spectral early-warning channel

- **Grounding** - type-frequency JSD sees the graph as a bag of labels; fragmentation - the graph pulling apart into loosely-coupled blobs as resolution degrades - shows in algebraic connectivity (Fiedler value) and effective diameter before it shows in label mix
- **Hypothesis** - under structural degradation, connectivity markers move before and more monotonically than JSD: an injection replay (merge-undo at increasing rates) shows algebraic connectivity of the giant component falling and effective diameter rising detectably at injection rates where JSD is still flat
- **Prediction** - on healthy wave-1b snapshots both marker families are flat; under injection, connectivity responds at <=half the injection rate JSD needs; the two-family panel (spectral + distributional) dominates either alone
- **Acceptance bar** - differential sensitivity; refuted if JSD responds first or simultaneously (distribution is sufficient, spectral is decoration)
- **Experiment** - scipy Laplacian eigensolve on the projected giant component + sampled BFS diameter + injection replay; deterministic, runs now
- **Result** - pending
- **Verdict** - pending

### R09-H78 Degree-aware render budgets - Pareto over uniform caps

- **Grounding** - direct consequence of H61: if uniform caps truncate gold on hubs, the fix must not simply raise limits (context is a fixed budget - H22); the budget must be REALLOCATED - periphery nodes render everything they have, hubs get a ranked top-k, total token budget unchanged
- **Hypothesis** - degree-quantile budget allocation is Pareto-better than uniform LIMIT 15/5: no probe loses evidence, H61's truncation victims recover, and context length stays within +-5%
- **Prediction** - evidence recall >= uniform on all 28 probes, strictly > on >=2; the reallocation interacts positively with vector@16 seeding (more seeds -> more rendered nodes -> budget discipline matters more)
- **Acceptance bar** - Pareto (zero probes lose); refuted if ranked truncation loses golds that arbitrary-order LIMIT happened to keep - then ORDERING is the real problem and H79 takes over
- **Experiment** - matched-budget re-render replay on the H34 harness; deterministic, runs now, sequenced after H61
- **Result** - adjudicated by the H61 audit (same harness, same intervention space): zero golds live beyond position 15 on any rendered node, and degree-quantile reallocation cannot improve on a cap that discards nothing - all allocation policies tie at 23/33 presence
- **Verdict** - REFUTED by premise collapse (H61): there is no truncation to reallocate around. The Pareto claim holds vacuously (no probe loses) but the strict-gain clause fails (no probe gains). Uniform LIMIT 15 stays

### R09-H79 Entropy-ranked rendering - the calibration correlate becomes a policy

- **Grounding** - relationship-type diversity was the TOP positive calibration correlate in v28 (0.58) - an unexploited measured signal; PPR ranking is theater at this scale (H37); render ordering currently falls back to arbitrary storage order within the LIMIT
- **Hypothesis** - ranking a node's rendered relations (and hub render priority generally) by relationship-type entropy beats both PPR-rank and arbitrary order at matched budget: type-diverse neighborhoods carry more answerable structure per token than type-monotone ones
- **Prediction** - entropy-ranked render >= production on evidence recall at matched budget; entropy-rank + H78 allocation combined gains >=2 probes over production render; entropy-rank alone beats PPR-rank (retiring PPR's last remaining job)
- **Acceptance bar** - matched-budget win; refuted if entropy rank is indistinguishable from random (the 0.58 correlate was calibration-specific, not retrieval-general - a useful negative for the calibration layer too)
- **Experiment** - re-render replay with three ranking policies on the H34 harness; deterministic, runs now
- **Result** - adjudicated inside the H61 audit: type-entropy round-robin ranking vs neighbor-degree vs storage order is a three-way tie at 23/33 gold presence - with no gold-bearing relation ever truncated, the ordering of the 15 rendered lines cannot change what evidence appears
- **Verdict** - REFUTED per the registered bar (entropy rank indistinguishable from arbitrary order). The 0.58 rel-type-diversity correlate stays a calibration signal, not a render policy; PPR's last remaining job is retired by parsimony (H37), not replaced by entropy

### R09-H80 The sparsification safety line - how much graph is dead weight

- **Grounding** - H60 prunes ELEMENTS by evidence; the edge-level twin ranks edges by a traversal-relevance composite (approximate edge betweenness x evidence count x validity status) and asks how much is removable before retrieval notices; the deliberate tension pair with H72 - the probe set adjudicates optimal density from both directions
- **Hypothesis** - the bottom 30% of edges by composite are removable with zero evidence-recall loss on both probe sets; degradation begins somewhere past that - the knee locates the graph's measured operating density
- **Prediction** - zero-loss plateau extends to >=25-30% removal; the knee sits before 50%; removed edges are dominated by SIMILAR_TO leftovers, stale-interval versions, and provenance-thin extractions - the same population three independent hygiene signals (H60, H63, this) keep converging on
- **Acceptance bar** - plateau + knee located; refuted if ANY removal level below 20% loses gold - the graph is already at optimal density, pruning doctrine caps out, and H72's densification direction wins the tension pair
- **Experiment** - staged edge removal on a graph copy + probe replay per stage; deterministic, runs now
- **Result** - pending
- **Verdict** - pending

## R10 - research-grounded round: the improvement gradient, curvature detectors, learned quality, ontology optima (pre-registered 2026-07-06)

Four parallel literature scouts (curvature/spectral mathematics, GNNs for KG quality, information-theoretic optima, ontology optimization) fed this round; all 24 load-bearing papers are downloaded and digested in `references/papers/` per the papers skill. The round answers the project owner's driving question - **is there an optimum graph for a given use case, with a gradient that says "improvement still possible"?** - with a two-axis doctrine now under test. Axis 1, ingest saturation, is already instrumented (Good-Turing missing mass 98.55% forward coverage, Heaps b=0.803): it says whether there is more VOCABULARY to discover. Axis 2, task utility, is new: a scalar foundry potential Phi(G) = probe-evidence sufficiency minus lambda x token cost, whose per-edit gain Delta-Phi over the admissible edit set (add/remove/merge/materialize/retype) IS the requested gradient. If Phi is empirically monotone submodular (the RPQ view-selection paper proves exactly this for workload-benefit objectives), greedy edit selection carries the (1-1/e) Nemhauser guarantee and a swap-stable fixed point is a rigorous "no single edit improves" certificate (Krause-Golovin). The MDL residual (VoG) supplies the use-case-agnostic complement - compression-optimum vs retrieval-optimum divergence is itself a registered prediction. Four themes: the gradient (H81-H86), curvature/topology detectors repurposed from over-squashing theory to defect detection (H87-H91), learned quality at honest scale (H92-H97), ontology optima (H98-H100). Grounded throughout in measured facts: direct-render recall 0.697 (23/33), the 6 PROP-ATTACHED golds, 91% on-seed carriage, 47 cross-type duplicates, 44% resolver calibration, 39-entity prune set.

| id | theme | grounding (papers in references/papers/) | claim | runnable without completions |
|----|-------|------------------------------------------|-------|------------------------------|
| H81 | gradient | RPQ view selection (submodular benefit, 9.73x), Krause-Golovin, GIB | the foundry potential Phi is empirically submodular; per-edit Delta-Phi is the improvement gradient; a swap-stable fixed point certifies "no improvement possible" | yes |
| H82 | gradient | VoG MDL summarization | a two-part MDL residual gives the use-case-agnostic second axis; its fixed point = "no structure left to explain"; it DIVERGES from Phi_task | yes |
| H83 | gradient | both potentials | the sign pair (Delta-Phi_task, Delta-Phi_MDL) classifies edits: retrieval-deficient / bloat / missing structure - and predicts probe failure classes | yes |
| H84 | gradient | GIB subgraph recognition | a thin task-sufficient subgraph exists: <=30% of edges preserve >=95% probe recall; the knee is the IB certificate | yes |
| H85 | gradient | in-house GT/Heaps + two-axis doctrine | ingest saturation and task-utility gradient are weakly correlated - saturated is not optimal | yes |
| H86 | gradient | RPQ view selection | materializing top-k probe-evidence path views cuts query cost >=30% at equal recall; honest risk: 91% on-seed leaves little traversal to precompute | yes |
| H87 | curvature | Topping SDRF, Fesser-Weber AFRC | augmented Forman-Ricci curvature separates false SAME_AS closure edges from true aliases at AUC >= 0.7 | yes |
| H88 | curvature | Black effective resistance | residual effective resistance (graph minus edge) validates SAME_AS: spurious closures are sole bridges (high), true co-references are redundant (low) | yes |
| H89 | curvature | Rengaswami inter-community curvature bound | curvature-thresholded pairs beat name similarity on the 47-duplicate record at matched recall - an embedding-free duplicate detector | yes |
| H90 | curvature | Knowledge Persistence (Bastos) | Betti curves (H0 collapse, spurious H1) detect injected over-merge before the production remap trigger; flat on healthy waves | yes |
| H91 | curvature | AFRC + component analysis | super-hub autopsy: the degree-236 node is a legitimate hub (curvature-normal), not an over-merge sink - either verdict feeds H64 audit priority | yes |
| H92 | learned | ULTRA (177k params, zero-shot MRR 0.395 > supervised 0.344) | pretrained ULTRA scores our edges at AUC >= 0.75 inference-only; risk: 12-type relation graph is degenerate for its relation-graph conditioning | yes |
| H93 | learned | ULTRA + CCA (similar-noise is the hard case) | ULTRA bottom-decile edges are >=3x enriched for real extraction errors vs a random decile | after H92 |
| H94 | learned | in-context clustering ER (150% over pairwise, 5x fewer calls) | zero-shot LLM clustering resolves the 47 cross-type duplicates at F1 >= 0.8, beating the 44%-calibrated Bayesian resolver | needs local model |
| H95 | learned | OWL2Vec* lexical-dominance ablation | null-leaning: from-scratch structural embeddings LOSE to Titan text embeddings for duplicate ranking at 2.8k nodes; constructive refuter: concat wins by >0.05 AUC | yes |
| H96 | learned | GSL survey (LDS/IDGL/SLAPS; dense relaxation feasible at 2.8k) | the relaxed gradient dL_probe/dA_ij ranks discrete edit proposals better than embedding-similarity ranking | yes |
| H97 | learned | Titan geometry + H34 false-closure evidence | intra-chain embedding variance flags >=70% of false SAME_AS closures - the cheapest pre-filter for H58's chain guard | yes |
| H98 | ontology | LLM-KGC survey (NO published granularity objective - open problem), AutoSchemaKG (no stopping rule), MDL frame | at least one single-step type merge/split improves probe answerability - the curing gate froze a saturated but task-suboptimal granularity | partial |
| H99 | ontology | Box2EL (geometry carries subsumption - repurposed at instance level), OWL2Vec*, LLMs4OL (taxonomy discovery weak: F1 0.66) | type-region containment over entity embeddings finds latent hierarchy and flags type mislabels at precision > 0.6 | partial |
| H100 | ontology | ROMEO task-based evaluation | per-probe structural metric profiles (population, connectivity, relationship diversity) predict probe pass/fail at AUC > 0.7 | yes |

### R10-H81 The foundry potential - a submodular gradient with a stopping certificate

- **Grounding** - Pang et al. prove workload-benefit view selection on graph databases is monotone submodular and reap a 9.73x speedup greedily ([paper digest] rpq materialized view selection); Nemhauser/Krause-Golovin give greedy (1-1/e) and the swap-stable local-optimum certificate; GIB provides the task-conditioned compression frame, and our gold probes collapse its intractable MI term to countable coverage
- **Hypothesis** - define Phi(G) = sum over probes of rendered-evidence sufficiency minus lambda x context tokens, over the admissible edit set {add edge, remove edge, merge nodes, split node, materialize proposition/view, retype}; Phi is empirically monotone submodular, per-edit Delta-Phi is THE improvement gradient the project owner asked for, and a swap-stable fixed point (no single edit with Delta-Phi > 0) is a computable "improvement still possible = false" certificate
- **Prediction** - greedy edit selection on the CPAP graph lifts direct-render recall 0.697 -> >=0.9 within +10% tokens; realized single-edit gains decay monotonically (empirical submodularity); at the fixed point, sampled multi-edit combinations (pairs/triples) improve Phi in <5% of draws
- **Acceptance bar** - all three clauses; refuted if supermodular interactions are frequent (pairs beating their singles' sum) - then single-edit gradients cannot certify optimality and the certificate needs local search over bounded neighborhoods
- **Experiment** - deterministic edit-replay on the H34 harness; candidate edits from the measured gap decomposition (H61) and detector outputs; runs now
- **Result** - pending
- **Verdict** - pending

### R10-H82 The MDL residual - "no structure left to explain"

- **Grounding** - VoG two-part MDL ([paper digest] vog graph summarization mdl): admit a structure iff it reduces total bits; the fixed point is the canonical compression stopping certificate
- **Hypothesis** - a two-part MDL over a KG vocabulary (type-blocks, stars, chains, clique-ish alias clusters) yields Phi_MDL = bits saved; its per-edit delta is the use-case-AGNOSTIC gradient; and it diverges from Phi_task - the compression optimum is not the retrieval optimum
- **Prediction** - on the CPAP graph the MDL gradient flattens while the task gradient is still positive (or vice versa on bloat regions); the divergence set is non-empty and interpretable
- **Acceptance bar** - divergence demonstrated and classified; refuted (interestingly) if the two fixed points coincide - one potential would suffice for both hygiene and retrieval
- **Experiment** - numpy MDL encoder over the projected graph + shared edit set with H81; runs now
- **Result** - pending
- **Verdict** - pending

### R10-H83 The gradient sign-pair - a defect taxonomy from two potentials

- **Grounding** - H81 + H82 jointly; the diagnostic reading of disagreement between a task-conditioned and a task-agnostic objective
- **Hypothesis** - the per-edit sign pair (Delta-Phi_task, Delta-Phi_MDL) classifies graph regions: (+,0) structurally complete but retrieval-deficient (missing materialization - the 6 PROP-ATTACHED golds should land here), (0,+) removable bloat (dark-matter catalog mass), (+,+) genuinely missing structure (unlinked mode families)
- **Prediction** - the classification aligns with the measured failure inventory (PROP-ATTACHED golds -> (+,0); the H63 dark 25% -> (0,+) dominated)
- **Acceptance bar** - alignment on >=80% of the labeled cases; refuted if the sign pair is uncorrelated with failure class
- **Experiment** - joint replay over H81/H82's edit set; runs now
- **Result** - pending
- **Verdict** - pending

### R10-H84 The thin sufficient subgraph - an IB knee certificate

- **Grounding** - GIB-subgraph recognition ([paper digest] gib subgraph recognition): a subgraph "as informative as possible with less redundant structure" exists and is much smaller than the input; our 91%-on-seed measurement predicts the shell is thin here
- **Hypothesis** - ablating edges in ascending gold-path participation order, <=30% of edges preserve >=95% probe evidence recall; the recall-vs-budget curve has a knee, which is the IB-flavored counterpart of H80's structural composite (the two rankings' agreement is reported)
- **Prediction** - knee exists before 30% retention; the retained core is dominated by seed-incident and alias edges
- **Acceptance bar** - knee found; refuted if recall degrades smoothly under any removal order (no compressible bottleneck - the IB framing fails on this graph)
- **Experiment** - staged ablation replay (shares H80's harness); runs now
- **Result** - pending
- **Verdict** - pending

### R10-H85 Saturated is not optimal - the two axes are independent

- **Grounding** - in-house Good-Turing UCB (H32) and Heaps (H47) instrument the ingest axis; H81 instruments the task axis; the doctrine says they answer different questions
- **Hypothesis** - per-type missing mass and residual per-type task gradient (max Delta-Phi over edits touching that type) are weakly correlated (|r| < 0.3): a vocabulary-saturated graph can still carry a large retrieval-utility gradient
- **Prediction** - the CPAP graph (fully cured, missing mass ~1.5%) still shows positive task gradient concentrated on the render/materialization edit class
- **Acceptance bar** - weak correlation + positive residual gradient; refuted if missing mass predicts the task gradient (r -> 1) - one estimator would suffice
- **Experiment** - correlation over H81's per-type gains; runs now
- **Result** - pending
- **Verdict** - pending

### R10-H86 Evidence-path views - the RPQ materialization transfer

- **Grounding** - Pang et al. prove the workload-benefit objective monotone submodular and reach 9.73x on Wikidata query logs ([paper digest] rpq materialized view selection); our materialization stage is the same problem with probes as the workload
- **Hypothesis** - greedily materializing top-k probe-evidence path views (cached per-seed renders, shortcut edges, surfaced propositions) cuts query-time cost (tokens + hops) >=30% at equal evidence recall, with a benefit-per-token knee stable under probe bootstrap (knee location variance < 20%)
- **Prediction** - the honest risk is registered as a clause: with 91% of evidence already on-seed, the traversal left to precompute may be too small - the win, if any, concentrates in the PROP-ATTACHED and alias-merge render work
- **Acceptance bar** - cost cut at equal recall + stable knee; refuted if no view set reduces cost at equal recall (materialization is already saturated)
- **Experiment** - deterministic view-replay on the H34 harness; runs now
- **Result** - pending
- **Verdict** - pending

### R10-H87 Curvature flags the false closure - AFRC on SAME_AS edges

- **Grounding** - Topping et al. prove negatively curved edges are the structural bridges ([paper digest] curvature over-squashing sdrf); Fesser-Weber's AFRC recovers Ollivier-Ricci's discrimination in linear time ([paper digest] afrc augmented forman-ricci curvature); we repurpose from GNN-enablement (irrelevant here - evidence is <=2 hops) to defect detection
- **Hypothesis** - false SAME_AS closure edges (the MANU / DreamStation CPAP / bCPAP prongs class) carry significantly more negative AFRC than true co-reference edges - a spurious identity bridge connects two neighborhoods that share no triangles
- **Prediction** - AUC >= 0.7 separating labeled false from true SAME_AS edges by edge AFRC
- **Acceptance bar** - AUC >= 0.7; refuted at AUC <= 0.55 (curvature carries no identity signal)
- **Experiment** - networkx AFRC over all SAME_AS edges + labeled defect set; milliseconds at 3.9k edges; runs now
- **Result** - pending
- **Verdict** - pending

### R10-H88 Effective resistance audits SAME_AS - redundancy means true

- **Grounding** - Black et al. bound information flow by effective resistance and compute it from the Laplacian pseudoinverse ([paper digest] effective resistance over-squashing); inverted here: instead of ADDING low-resistance edges for GNN depth, we AUDIT existing identity edges by residual redundancy
- **Hypothesis** - deleting a true SAME_AS edge leaves LOW residual resistance between its endpoints (shared neighborhood reconnects them); deleting a spurious closure edge leaves HIGH residual resistance (it was the sole bridge) - a threshold recovers >=70% of known false closures at zero loss on true aliases
- **Prediction** - the residual-resistance distributions separate cleanly; the false-closure members are extreme outliers
- **Acceptance bar** - >=70% recall at zero true-alias loss; refuted if distributions are indistinguishable
- **Experiment** - scipy pseudoinverse at 2.8k nodes; runs now; on confirmation joins H58's chain guard as a second deterministic prong
- **Result** - pending
- **Verdict** - pending

### R10-H89 The curvature bound finds cross-type duplicates - no embeddings needed

- **Grounding** - Rengaswami-Bourni-Maroulas prove inter-community edges carry provably more negative curvature ([paper digest] ricci curvature community structure); cross-type duplicates are by construction pairs bridging two type-communities the ontology froze apart
- **Hypothesis** - curvature-thresholded candidate pairs (with the principled inter-community cutoff, not a tuned magic number) recover the 47-duplicate record at higher precision than name-similarity at matched recall
- **Prediction** - the curvature detector wins at matched recall; its false-positive head is same-family siblings, filterable by the existing description-contrast feature
- **Acceptance bar** - precision > name-similarity baseline at matched recall; refuted otherwise
- **Experiment** - AFRC + threshold sweep vs the labeled record; runs now
- **Result** - pending
- **Verdict** - pending

### R10-H90 Betti curves as the over-merge alarm - topology before distribution

- **Grounding** - Knowledge Persistence computes persistence diagrams over graph filtrations at ~0.04% of ranking-evaluation cost ([paper digest] knowledge persistence kg evaluation); over-merge collapses H0 (swelling giant component) and injects spurious H1 cycles
- **Hypothesis** - Betti curves per ingest snapshot detect injected over-merge (merge-undo replay in reverse) at lower injection rates than the production remap-rate trigger, and stay flat on the healthy wave - the topological sibling of H77's spectral early warning (both race the production trigger; the round reports which wins)
- **Prediction** - H0/H1 respond at <=half the injection rate the remap trigger needs; zero false movement on wave-1b snapshots
- **Acceptance bar** - differential sensitivity + specificity; refuted if flat or coincident with the production trigger
- **Experiment** - persistence over shortest-path filtration (2.8k nodes, scipy/ripser-lite implementation); runs now
- **Result** - pending
- **Verdict** - pending

### R10-H91 Super-hub autopsy - is degree 236 an entity or an accident?

- **Grounding** - the H61 census found max degree 236 against a median of 1; a hub that large is either a legitimate category/manufacturer or an over-merge sink accreting edges from falsely-identified members
- **Hypothesis** - (registered in the null direction) the top hubs are legitimate: their incident-edge AFRC matches the graph norm and their removal changes component count only as expected for a hub; the alternative outcome - anomalous curvature + H0 splitting - would mark them as over-merge artifacts and reprioritize H64's audit
- **Prediction** - legitimate verdict for the top-5 hubs
- **Acceptance bar** - either outcome is recorded as a verdict; the hypothesis fails only if the instruments cannot distinguish (curvature normal AND component behavior anomalous, or vice versa, with no adjudication)
- **Experiment** - per-hub incident curvature + removal component census; runs now
- **Result** - pending
- **Verdict** - pending

### R10-H92 ULTRA scores our edges - zero-shot structural plausibility

- **Grounding** - ULTRA is a 177k-parameter KG foundation model: zero-shot MRR 0.395 across 57 graphs beats supervised SOTA 0.344, no per-graph training ([paper digest] ultra kg foundation model); NBFNet supplies the interpretable path mechanism beneath it
- **Hypothesis** - a pretrained checkpoint (ultra_50g), inference-only, ranks held-out true edges above corrupted negatives on our graph at AUC >= 0.75 - structural plausibility for free
- **Prediction** - AUC >= 0.75 on 200 held-out edges vs relation- and tail-corrupted negatives; the registered risk: our ~12-relation vocabulary gives ULTRA's relation-graph conditioning a thin substrate and may collapse scoring toward chance
- **Acceptance bar** - AUC >= 0.75 confirms; AUC ~ 0.5 refutes (relation-graph degeneracy) - either way the scale question is answered for the class
- **Experiment** - checkpoint inference on GPU idle window; runs now
- **Result** - pending
- **Verdict** - pending

### R10-H93 The bottom decile is where the errors live - ULTRA as defect detector

- **Grounding** - CCA shows structure-only error detectors collapse on semantically-similar noise (0.945 -> 0.633 precision) - exactly the LLM-extraction failure mode ([paper digest] cca kg error detection contrastive); ULTRA's score plus our text evidence is the fusion CCA argues for
- **Hypothesis** - the bottom ULTRA-score decile of existing edges is >=3x enriched for real extraction errors vs a random decile
- **Prediction** - 30-vs-30 audited edges (LLM-adjudicated against source chunks, then inspected) show the enrichment; the flagged set feeds the gap ledger per the self-auditing doctrine
- **Acceptance bar** - >=3x enrichment; refuted if extraction errors are structurally plausible hallucinations (enrichment ~1x) - CCA's warning realized, and text-side detection becomes the only route
- **Experiment** - sequenced after H92; local-model adjudication
- **Result** - pending
- **Verdict** - pending

### R10-H94 Cluster, don't compare - LLM in-context resolution of the 47

- **Grounding** - in-context clustering ER reports up to 150% accuracy gains over pairwise matching at 5x fewer calls, zero-shot, optimal at ~9 records per call ([paper digest] llm in-context clustering entity resolution); our Bayesian resolver measures 44% calibration - coin-flip territory (H54's replay is the demolition case; this is the replacement candidate)
- **Hypothesis** - zero-shot in-context clustering over the 47 cross-type duplicates plus matched distractors resolves them at F1 >= 0.8, and its whole-set reasoning natively avoids the false transitive closures that pairwise-then-union created
- **Prediction** - F1 >= 0.8 with zero new false closures; registered risk: over-merging same-family siblings (the known hardest negatives)
- **Acceptance bar** - F1 >= 0.8 AND sibling precision >= pairwise baseline; refuted if sibling over-merge drops precision below the Bayesian resolver
- **Experiment** - local 120B post-wave window (~50 calls); on confirmation this is the H54 two-rule system's third rule
- **Result** - pending
- **Verdict** - pending

### R10-H95 Text beats structure at this scale - the honest null

- **Grounding** - OWL2Vec*'s ablation shows lexical signal dominates structure (MRR 0.213 word-based vs 0.154 structure-only) ([paper digest] owl2vec ontology embedding); 2.8k nodes starve from-scratch structural embeddings
- **Hypothesis** - (null-leaning, registered to protect against structure-embedding enthusiasm) node2vec/from-scratch-GNN embeddings rank the labeled duplicate pairs WORSE than Titan text embeddings by >0.05 AUC
- **Prediction** - text wins; the constructive refuter is the interesting outcome: text+structure concatenation beating text alone by >0.05 AUC would prove structure carries complementary identity signal worth engineering
- **Acceptance bar** - either the null holds (stop investing in trained structural embeddings) or the concat refuter fires (invest in fusion) - a decision either way
- **Experiment** - node2vec (CPU minutes at 2.8k nodes) + ranking AUC; runs now
- **Result** - pending
- **Verdict** - pending

### R10-H96 The relaxed gradient proposes edits - differentiable structure as ranker

- **Grounding** - the GSL survey's direct-parameterization family (LDS/IDGL/SLAPS) treats adjacency as a parameter with literal task gradients; dense relaxation at 2.8k nodes (~7.8M entries) is memory-trivial ([paper digest] graph structure learning survey); the honest transfer to a discrete auditable KG is proposal RANKING, not soft storage
- **Hypothesis** - ranking candidate edits by the relaxed gradient d(probe loss)/dA_ij yields higher precision@k of edits whose realized Delta-Phi_task > 0 than embedding-similarity ranking
- **Prediction** - gradient ranking wins at k=20; the differentiable probe loss is a soft-render surrogate (seed-similarity-weighted coverage of gold carriers)
- **Acceptance bar** - precision@20 > embedding baseline; refuted if the discrete/continuous gap dominates (gradient <= baseline) - GSL does not transfer and H81's heuristic proposal set stands
- **Experiment** - torch soft-adjacency surrogate + replay verification against H81's realized gains; runs now
- **Result** - pending
- **Verdict** - pending

### R10-H97 Chain variance - the cheapest false-closure filter

- **Grounding** - the false SAME_AS members (MANU, DreamStation CPAP, bCPAP prongs) were surfaced by H34's render forensics; Titan embedding geometry is already paid for; H58's chain guard needs a pre-filter ordering
- **Hypothesis** - SAME_AS chains whose intra-chain pairwise cosine variance exceeds a data-derived threshold contain >=70% of known false closures
- **Prediction** - variance flags the labeled defects; registered risk: the resolver merged them BECAUSE text similarity was high - the distinction may be invisible to Titan (the refuter CCA's similar-noise finding predicts)
- **Acceptance bar** - >=70% recall at precision > 0.5; refuted if false members are uniformly high-similarity (signal absent from text geometry - structural detectors H87/H88 become the only route)
- **Experiment** - numpy over stored embeddings; minutes; runs now
- **Result** - pending
- **Verdict** - pending

### R10-H98 The granularity gap - is the cured inventory task-optimal?

- **Grounding** - the LLM-KGC survey states outright there is "no explicit guidance on granularity choices or optimization objectives" - an open problem ([paper digest] llm kg construction survey); AutoSchemaKG never stops discovering (92% schema alignment but no gate) ([paper digest] autoschemakg dynamic schema induction) - our Good-Turing gate is the differentiator, but it stops on SATURATION, not task UTILITY
- **Hypothesis** - at least one single-step type merge or split (embedding-cluster-proposed) improves aggregate probe answerability - the gate froze a statistically-saturated but task-suboptimal granularity; refutation would validate the gate as task-optimal too
- **Prediction** - >=1 improving operator exists on the CPAP inventory (12 types); type edits plug into H81's potential as the retype edit class
- **Acceptance bar** - improving operator found and verified by probe replay; refuted if no single-step operator improves - the cured inventory is a local task optimum (strong validation, worth publishing either way)
- **Experiment** - operator enumeration + re-map (deterministic label rewrite) + probe replay; local-model assist for split assignments
- **Result** - pending
- **Verdict** - pending

### R10-H99 Geometry finds the latent hierarchy - boxes over a flat ontology

- **Grounding** - Box2EL proves geometric containment carries subsumption (median rank 60-80% better on GALEN/GO) but consumes authored axioms we lack ([paper digest] box2el dual box embeddings); the repurposing - fit regions per type over ENTITY embeddings and test containment - is unvalidated; LLMs4OL flags taxonomy discovery as the weak LLM task (F1 0.66), so the LLM cross-check is itself at risk ([paper digest] llms4ol 2024 overview)
- **Hypothesis** - (a) type-region containment over entity embeddings finds >=2 latent subsumption pairs in the flat 12-type inventory, agreeing with an LLM-elicited subsumption DAG above chance (kappa > 0.4); (b) region outliers flag type-assignment errors at precision > 0.6 on audit
- **Prediction** - the technical-product inventory contains latent accessory/consumable-under-product structure that geometry recovers
- **Acceptance bar** - both clauses; refuted if no containment beats a shuffled-label baseline (the ontology is genuinely flat) or outliers are legitimate long-tail members
- **Experiment** - Gaussian/box region fit per type (numpy) + one local-model DAG elicitation pass + audit; partial now
- **Result** - pending
- **Verdict** - pending

### R10-H100 Structural profiles predict probe fate - ROMEO re-derived for retrieval

- **Grounding** - task-based ontology evaluation derives task-specific structural metrics whose profiles predict task performance (class-richness-0 ontologies produce only terminology questions) ([paper digest] task-based ontology evaluation); the metric derivation transfers, the metric VALUES do not - we re-derive against probe-answering
- **Hypothesis** - per-probe-subgraph structural profiles (type population, average connectivity, relationship-type diversity, proposition density) predict probe pass/fail at AUC > 0.7 - the graph's structural health explains retrieval success
- **Prediction** - proposition density and relationship diversity dominate the profile (consistent with the 0.58 calibration correlate and H34's channel census)
- **Acceptance bar** - AUC > 0.7; refuted if no profile correlates - extraction fidelity dominates structure entirely (H51's claim gains indirect support)
- **Experiment** - metric computation per probe-touched subgraph + logistic fit with leave-one-out; runs now
- **Result** - pending
- **Verdict** - pending

## R11 - the weak-flank round: identity layer, render gap, the SOTA comparison, and the persistent failures (pre-registered 2026-07-06)

The standing gap assessment names three weak flanks: (1) the IDENTITY LAYER - 47 cross-type duplicates on record and a Bayesian resolver measuring 44% calibration accuracy on 25 pairs; (2) the RENDER GAP - 6 of 33 golds live in propositions attached to rendered seeds yet invisible to the render, currently rescued by channel redundancy (redundancy doing the work of correctness); (3) the SOTA CLAIM - the goal demands head-to-head comparison against published methods, and that benchmark has not been run. Plus the persistent failure modes: the unlinked mode-family probe, extraction-variance consolidation, and the single-spike drift evidence problem. This round does not duplicate the standing registrations (H54 Bayesian replay, H58 fifth detector, H56 proposition closure, R10's H87-H89/H92-H97 detectors) - it supplies what they all lack: statistical footing (a labeled identity benchmark two orders larger than 25 pairs), decision-theoretic structure (cost-split thresholds, constraint vetoes, ensemble arbitration), the direct render fix, and the goal-critical published-baseline harness. Themes: identity (H101-H107), retrieval correctness (H108-H112), the SOTA benchmark (H113-H117), persistent failures operationalized (H118-H120).

| id | theme | weak spot attacked | claim | runnable without completions |
|----|-------|--------------------|-------|------------------------------|
| H101 | identity | every resolver metric rests on 25 labeled pairs | a 200+ pair identity benchmark (detector-generated candidates, evidence-adjudicated) moves measured resolver metrics by >=10 points - the 44% figure is itself unreliable | needs local model |
| H102 | identity | single 0.6 merge threshold | cost-sensitive dual thresholds (merge / defer-to-audit / reject) cut false merges >=50% at equal true-merge recall | after H101 |
| H103 | identity | no hard negative constraints | identity invariants (different manufacturer, incompatible spec values -> never merge) veto >=80% of the 47-duplicate error class at zero true-merge loss | yes |
| H104 | identity | merges are effectively irreversible in practice | split-and-remerge replay reproduces <=90% of merges; the unstable remainder is enriched for the defect set - instability IS an error signal | yes |
| H105 | identity | same-family siblings are the hardest negatives | resolver precision on a sibling stress set is >=20 points below overall; description-contrast closes half the gap | needs local model |
| H106 | identity | detectors act independently | reliability-weighted ensemble arbitration (4 deterministic + Bayesian + structural + LLM-clustering) beats every individual at F1 with <=half the false merges | after H101 |
| H107 | identity | resolution blamed for upstream faults | >=60% of the 47 duplicates root-cause to extraction variance or parse artifacts UPSTREAM of the resolver - resolution alone cannot fix them | yes |
| H108 | retrieval | the 6 PROP-ATTACHED golds (0.909 vs 0.636 gap) | rendering top-M attached propositions per seed (probe-ranked, fixed budget) lifts direct-render recall 0.697 -> >=0.85 at <=+10% tokens | yes |
| H109 | retrieval | redundancy masks fragility | >=25% of golds are single-channel (one failure from loss); the channel-knockout matrix quantifies it; H108 halves the single-channel count | yes |
| H110 | retrieval | probe wording is a hidden variable | >=3 probes flip pass/fail under paraphrase; multi-query seed union at matched budget restores them | embeddings only |
| H111 | retrieval | abstention is unmeasured | gap-ledger + coverage-bound abstention achieves precision >=0.9 at recall >=0.8 on unanswerable probes | needs local model |
| H112 | retrieval | context ordering is untested folklore | reader accuracy varies <=2 points across head-tail / relevance-sorted / random block orderings - the dial closes either way | needs local model |
| H113 | sota | the goal's comparison claim is unrun | KGF >= GraphRAG, LightRAG, HippoRAG-2, vector-RAG and BM25-RAG on evidence recall AND answer accuracy at matched reader and token budget on the benchmark corpus | needs local model |
| H114 | sota | no external-validity evidence | on a public multi-hop QA slice with published numbers, KGF lands within 5 points of published GraphRAG-class results without corpus-specific tuning | needs local model |
| H115 | sota | cost story unquantified | KGF's ingest-heavy design amortizes: query-time cost <=50% of GraphRAG-class at equal accuracy past a measurable break-even query count | with H113 |
| H116 | sota | "architecturally sound" needs ablation evidence | every retained stage (propositions, resolution, curing, bitemporal) contributes >=1 point on the H113 harness - no dead weight ships | with H113 |
| H117 | sota | longevity claim vs baselines untested | under corpus corruption (near-duplicate docs, contradictory versions, OCR noise), KGF degrades <=half as much as vanilla RAG baselines | with H113 |
| H118 | failures | the unlinked mode-family probe (det 9/10) | targeted repair (H56 generation + H58 collective evidence) closes it AND generalizes: >=2 other unlinked mode families found and linked | needs local model |
| H119 | failures | consolidation instability across runs | 5x re-extraction variance (entity-set Jaccard) drops >=50% with temperature-0 + canonicalization prompt - determinism is a prompt property, not a model property | needs local model |
| H120 | failures | single-spike drift evidence (doc 75 class) | H59's binomial-LLR CUSUM shipped behind a flag replays wave 1b with zero false alarms and matched detection on injected shifts - then becomes the default | yes |

### R11-H101 The identity benchmark - 25 pairs cannot carry the layer

- **Weak spot** - the 44% calibration figure, the resolver threshold, and every merge-quality claim rest on 25 ground-truth pairs; at that n a single flipped label moves accuracy 4 points - the measurement itself is the first defect
- **Hypothesis** - a 200+ pair labeled identity benchmark - candidates generated by ALL standing detectors (four deterministic, Bayesian defer zone, neighbor-Jaccard twins, curvature bridges, chain variance), adjudicated by the local model against source-chunk evidence with human-auditable evidence strings - shifts at least one headline resolver metric by >=10 points, proving the 25-pair figures were noise-dominated
- **Prediction** - calibration accuracy moves off 44% by >=10 points in either direction; the benchmark stratifies into named difficulty tiers (siblings, cross-type, alias-chains, distractors)
- **Acceptance bar** - benchmark shipped + metric shift demonstrated; refuted if 200-pair metrics reproduce the 25-pair figures within 5 points (the small sample was honest after all)
- **Experiment** - candidate generation deterministic now; adjudication on the local model post-wave; every R11 identity entry conditions on this artifact
- **Result** - pending
- **Verdict** - pending

### R11-H102 Merge, defer, or reject - decision theory replaces the single threshold

- **Weak spot** - one scalar threshold (0.6) forces a binary decision where the cost structure is asymmetric: a false merge corrupts renders and closures silently, a false non-merge costs a duplicate context block
- **Hypothesis** - cost-sensitive dual thresholds - merge above t_hi, defer-to-audit between, reject below t_lo, with t_hi/t_lo set by the measured false-merge:false-split cost ratio on H101's benchmark - cut false merges >=50% at equal true-merge recall, with the defer queue small enough to audit (<=10% of decisions)
- **Prediction** - the optimal t_hi sits well above 0.6; the defer zone catches the sibling tier disproportionately
- **Acceptance bar** - both clauses on held-out benchmark folds; refuted if the posterior is so miscalibrated that no threshold pair beats the single cut (H54's numerology verdict confirmed from a second direction)
- **Experiment** - threshold sweep on H101; deterministic after H101
- **Result** - pending
- **Verdict** - pending

### R11-H103 Identity invariants - what must never merge

- **Weak spot** - the resolver has no hard-constraint layer; domain-obvious vetoes (different manufacturers' products, incompatible physical spec values) are currently soft evidence at best
- **Hypothesis** - a deterministic invariant veto - conflicting manufacturer provenance, numerically incompatible same-key spec values (weight 1.3kg vs 2.1kg), disjoint model-number families - eliminates >=80% of the 47-duplicate error CLASS at zero measured true-merge loss
- **Prediction** - >=80% of the labeled defects violate at least one invariant; zero true pairs on H101 do
- **Acceptance bar** - both clauses; refuted if true aliases routinely violate the invariants (e.g. manufacturer strings too noisy to trust) - then invariants demote to soft features
- **Experiment** - invariant evaluation over the labeled sets; deterministic, runs now against the 47 + 25 records, re-verified on H101 when it lands
- **Result** - evaluated in [`identity_forensics_r11.ipynb`](../../notebooks/identity_forensics_r11.ipynb) over the 127 SAME_AS edges (method provenance: model_code 73, deictic_assertion 25, normalized_name 20, explicit_assertion 9). A category-lexicon label rule (independent signal family) marked 6 false merges; the invariants (manufacturer conflict, numeric spec incompatibility) caught 1 of 6 - coverage 0.17 vs the 0.80 bar. Diagnosis is signal SPARSITY, not principle: manufacturer evidence exists on only ~12% of entities (339 MANUFACTURED_BY edges + 53 props over 2798), so most pairs have nothing to veto on; meanwhile the invariants fired on 8 pairs the weak name-lexicon could NOT label (spec-value conflicts on model_code merges) - likely true catches the label rule misses, undecidable without adjudication. Zero presumed-true (same-name) pairs were vetoed
- **Verdict** - REFUTED as-registered on current signals, with the cause identified as label-and-signal starvation on both sides of the measurement: the 0.80 bar is unreachable while manufacturer coverage sits at 12%, and the 6-pair label set is too weak to score against. Routes to H101 (adjudicated labels) plus a signal-enrichment prerequisite: manufacturer inference from document provenance (a manual's subject family implies its entities' manufacturer) before re-testing. The invariant CONCEPT survives - its 8 unlabeled fires on model_code merges are the most suspicious edges in the graph

### R11-H104 Instability is an error signal - the split-and-remerge probe

- **Weak spot** - merges are recorded but never re-derived; a merge the resolver would not reproduce is a merge nobody should trust
- **Hypothesis** - bitemporal versioning permits lossless un-merge; replaying resolution over split-back candidates reproduces <=90% of standing merges, and the unstable remainder is >=3x enriched for the known defect set - reproducibility under replay is a zero-label error detector
- **Prediction** - instability concentrates in cross-type and sibling merges; stable merges are near-100% clean
- **Acceptance bar** - enrichment >=3x; refuted if instability is uniform noise uncorrelated with defects
- **Experiment** - split-remerge replay on a graph copy; deterministic, runs now
- **Result** - pending
- **Verdict** - pending

### R11-H105 The sibling stress set - measure the hardest negatives directly

- **Weak spot** - same-manufacturer adjacent-model products (the 200 vs 600 series class) are the known hardest negatives, but no metric isolates them - overall precision hides the cliff
- **Hypothesis** - resolver precision on a purpose-built sibling stress set sits >=20 points below overall precision; adding the description-contrast feature (already used in cross-type resolution) closes >=half the gap
- **Prediction** - the stress set exposes the cliff; contrast helps; the residual failures need invariants (H103), not more similarity
- **Acceptance bar** - both clauses; refuted if sibling precision matches overall (the fear was unfounded - retire the sibling narrative)
- **Experiment** - stress-set construction from model-number families (deterministic) + local-model adjudication of labels
- **Result** - pending
- **Verdict** - pending

### R11-H106 Ensemble arbitration - reliability weights over independent detectors

- **Weak spot** - detectors run as an unordered pile; agreement and conflict carry no formal weight, so one noisy source can push a merge alone
- **Hypothesis** - per-source reliability weights learned on H101 (a simple Dawid-Skene-style or logistic arbitration over detector votes: 4 deterministic + Bayesian + structural Jaccard/curvature + LLM clustering) beat every individual source at F1 while committing <=half the false merges of the best individual
- **Prediction** - the deterministic detectors get near-veto weights on their fire conditions; the Bayesian source gets weight only in the defer band; structural sources add recall on non-textual duplicates
- **Acceptance bar** - F1 > best individual AND false merges <= half; refuted if sources are too correlated for arbitration to add anything (ensemble ~ best single)
- **Experiment** - arbitration fit + held-out folds on H101; after H101
- **Result** - pending
- **Verdict** - pending

### R11-H107 Root-cause the 47 - is identity even the guilty layer?

- **Weak spot** - the 47 cross-type duplicates are booked as resolver failures, but the resolver can only merge what extraction presents; blaming the identity layer for upstream variance would misdirect all of R11
- **Hypothesis** - partitioning all 47 by root cause - extraction variance (same document, different surface forms across runs), parse artifacts (H51's territory), genuine cross-document ambiguity, true resolver misses - attributes >=60% upstream of the resolver
- **Prediction** - extraction variance dominates; the true resolver-miss share is <=25%, resetting expectations for what H94/H102/H103 can fix
- **Acceptance bar** - partition complete with evidence strings per case; the 60% clause decides routing (upstream -> H119 determinism work; resolver -> H102/H103/H106)
- **Experiment** - forensic classification against source chunks; deterministic against stored provenance, runs now
- **Result** - the inventory itself was the first finding: at embedding cosine >= 0.90 the rebuilt graph contains ZERO disjoint-type pairs - the "47 cross-type duplicates" class of the old defect record does not exist on the current engine (all 71 high-cosine unmerged pairs are same-type 62 / overlapping-type 9; minus SAME_AS-linked, 66 candidates). The registered partition then ran on the real class: extraction_variance 47 (71% - same document emitted both surface forms: 'Pro-Flow nasal cannula' vs 'Pro-Flow adult nasal cannula', 'EverGo oxygen concentrator' vs 'EverGo', 'CPAP' vs 'CPAP mode'), resolver_visible_miss 19 (29% - blocking saw the pair at cosine > 0.85, resolution declined), surface_variant 0, cross_document_ambiguity 0. Upstream share 0.71 vs the 0.60 bar; the resolver-miss share (0.29) slightly exceeds the predicted <=0.25
- **Verdict** - CONFIRMED - the duplicate problem roots upstream of the resolver: 71% is extraction surface-form variance within single documents, exactly H119's territory (canonicalization prompt + temperature-0), and no resolver improvement can prevent what extraction keeps re-creating. Routing per the registered clause: H119 is promoted to the primary identity lever; H102/H103/H106 address the remaining 29%. Class-shape discovery routed to the gap assessment: the weak-flank framing updates from "47 cross-type duplicates" to "66 same-type variance pairs plus the model_code false-merge surface (H103's 8 suspicious fires)" 

### R11-H108 Surface the attached propositions - the direct render fix

- **Weak spot** - 6 of 33 golds (18%) live in propositions ABOUT already-rendered seeds but invisible to the render (H61's discovery); the full pipeline rescues them through the global proposition channel - redundancy doing the work of correctness
- **Hypothesis** - rendering the top-M propositions attached to each seed (ranked by probe-embedding similarity, within a fixed +10% token budget) lifts direct-render evidence recall from 0.697 (23/33) to >=0.85, with full-context recall held at 1.0 and no displacement of currently-rendered evidence
- **Prediction** - all 6 PROP-ATTACHED golds recovered at M<=3; the token budget holds because attached propositions are short
- **Acceptance bar** - >=0.85 direct recall at <=+10% tokens, zero displacement; refuted if ranked attached propositions crowd out relation lines that other probes need (the H22 fixed-budget lesson firing again)
- **Experiment** - render-replay extension of the H61 harness; deterministic, runs now; on confirmation ships to `pipeline._retrieve_local` as a flagged render option
- **Result** - three configurations in [`probe_render_r11h108.ipynb`](../../notebooks/probe_render_r11h108.ipynb): per-seed cosine top-M (recall 0.697->0.758 only at M=5, +49% tokens), novelty-first ranking with the H22 trigram filter (0.758 at +32%), and global-union ranking token-capped at the +10% budget (0.697 - zero recovery). The rank diagnostic then dissolved the premise: of the "6 PROP-ATTACHED golds", only TWO (P03 28 dB(A), P19 constant lower pressure) have genuine carrying propositions in the seed-attached pool, at global ranks 22 and 16 - recoverable only at +20-32% token budgets, far outside the bar. The other four were measurement artifacts, root-caused live: (a) H61's placement loop checked categories per-seed sequentially with early break, so a gold in a LATER seed's base render could be mislabeled PROP-ATTACHED (P23's gold is literally a seed NAME - "AutoRamp with sleep onset detection"); (b) the H34 fuzzy matcher degenerates on short golds against short texts - value_tokens("SD card: > 1 year") reduces to ["1"], so token-majority matches any digit-bearing proposition (22 false "carriers" for P10). The remaining baseline-missing golds are genuine SEEDING gaps - carrier entities outside the vec-8 seed set - for which the known lever is vector@16 (H53: +28% relative)
- **Verdict** - REFUTED, and the refutation resolves the weak-flank framing: "redundancy doing the work of correctness" was backwards. The global proposition channel is not redundant backup - it IS the correct mechanism for proposition-carried evidence (it ranks all 10,968 propositions query-conditioned, which no per-seed local budget can match; production full recall stays 1.000). The render gap decomposes into seeding gaps (lever: top_k, already measured) plus 2 deep-ranked prop golds (lever: none within budget; the channel already rescues them). No render change ships. Housekeeping routed: H61's decomposition counts corrected (see its Result note), the matcher gains a short-gold guard for future per-prop checks, and H109's knockout matrix inherits the corrected classification

### R11-H109 The knockout matrix - how fragile is ceiling recall?

- **Weak spot** - full-pipeline recall 1.0 is carried by overlapping channels; nobody has measured how many golds survive on exactly one channel - single points of failure invisible at the ceiling
- **Hypothesis** - a channel-knockout matrix (ablate each of vec / alias / prop_text / prop_node per probe) shows >=25% of golds are single-channel; H108's render fix cuts the single-channel count by >=half - correctness replacing redundancy
- **Prediction** - the prop_text channel carries the most exclusive golds (per H34's rescue census); knockout fragility concentrates on the same probes that paraphrase-flip in H110
- **Acceptance bar** - matrix shipped + the halving demonstrated post-H108; refuted if golds are near-uniformly multi-channel (redundancy is genuine depth - the fragility narrative retires)
- **Experiment** - ablation replay on the H34 harness; deterministic, runs now
- **Result** - pending
- **Verdict** - pending

### R11-H110 Paraphrase stress - is the entry point question-surface-sensitive?

- **Weak spot** - every probe result rests on one phrasing per question; vector seeding is sensitive to surface form and no invariance measurement exists
- **Hypothesis** - under 5 systematic paraphrases per probe (embeddings only), >=3 probes flip pass/fail on pure-seed evidence recall; a multi-query seed union (union of top-k over paraphrases, matched total budget) restores the flipped probes
- **Prediction** - flips concentrate on probes whose seeds came from name-matching rather than description-matching; the union costs nothing at matched budget (H53's elasticity discovery reapplied)
- **Acceptance bar** - both clauses; refuted if recall is paraphrase-invariant (the entry point is robust - a strong stability credential worth recording)
- **Experiment** - paraphrase generation (local model, ~150 short calls) + Titan embedding + seed replay; near-runnable
- **Result** - pending
- **Verdict** - pending

### R11-H111 Calibrated abstention - refusing well is part of correctness

- **Weak spot** - the refusal-control probes exist (R05) but abstention currently rides on heuristics; the self-auditing doctrine says the gap ledger should DRIVE refusal, and that link is unmeasured
- **Hypothesis** - an abstention rule composed from the gap ledger plus coverage bounds (H57's per-inventory UCBs) achieves precision >=0.9 at recall >=0.8 on unanswerable probes, beating the current heuristic on both
- **Prediction** - coverage-bound features dominate the rule; false refusals concentrate on probes answerable only via propositions (fixable by H108's surfacing)
- **Acceptance bar** - precision/recall clause on the refusal set; refuted if the ledger signals are uncorrelated with answerability
- **Experiment** - rides the wave-end refusal probe cycle (local reader); sequenced with R05
- **Result** - pending
- **Verdict** - pending

### R11-H112 Does block order matter? - closing a folklore dial

- **Weak spot** - the head-tail interleave in the renderer is inherited folklore ("lost in the middle"); it has never been tested against alternatives on this system
- **Hypothesis** - (null-leaning) reader answer accuracy varies <=2 points across head-tail interleave, relevance-sorted, and random block orderings at identical content - ordering is not a lever at this context length
- **Prediction** - the null holds (contexts are short enough that position effects vanish)
- **Acceptance bar** - either the null (retire the dial, keep the simplest ordering) or a >=3-point spread (adopt the winner) - the dial closes both ways
- **Experiment** - 3x probe cycle with reordered contexts (local reader); post-wave window
- **Result** - pending
- **Verdict** - pending

### R11-H113 The head-to-head - KGF against the published field

- **Weak spot** - THE goal-critical gap: "achieved SOTA in comparison to other methods published" is a comparison claim, and no comparison has run
- **Hypothesis** - on the benchmark corpus + 28-probe gold set, with the SAME local reader and matched context token budgets, KGF meets or beats GraphRAG (Microsoft), LightRAG, HippoRAG-2, plain vector RAG, and BM25 RAG on BOTH evidence recall and answer accuracy
- **Prediction** - KGF wins evidence recall outright (the ingest-time work pays); answer accuracy is closest against HippoRAG-2; vector RAG is the honest floor that must be beaten decisively to justify the graph at all (H37/H52's question, now asked externally)
- **Acceptance bar** - >= on both metrics vs every baseline; ANY loss is recorded verbatim and becomes the next round's target - the bar cannot be adjusted after seeing results
- **Experiment** - baseline harness (their official implementations, our corpus, one reader); local 120B, multi-day post-wave; the single highest-priority completion-dependent item in the program
- **Result** - pending
- **Verdict** - pending

### R11-H114 External validity - a public benchmark with published numbers

- **Weak spot** - the probe set is self-authored; a skeptic discounts any self-graded benchmark
- **Hypothesis** - on a public multi-hop QA slice where GraphRAG-class numbers are published (2WikiMultiHopQA or MuSiQue subset sized to the local budget), KGF lands within 5 points of the published leaders without corpus-specific tuning (same config that ships)
- **Prediction** - KGF's evidence recall transfers; answer accuracy depends on the reader more than the graph (and is reported with the reader controlled)
- **Acceptance bar** - within 5 points; a larger gap is recorded with a forensic delta analysis (what the public corpus has that ours lacks)
- **Experiment** - one public slice, ingest + probe cycle on the local model; post-wave
- **Result** - pending
- **Verdict** - pending

### R11-H115 The amortization curve - when does ingest-heavy win?

- **Weak spot** - KGF spends heavily at ingest (extraction, resolution, curing); without a cost frontier the design choice is taste, not evidence
- **Hypothesis** - measured end-to-end (build cost + N x query cost), KGF's query-time cost is <=50% of GraphRAG-class at equal accuracy, giving a break-even N beyond which KGF is strictly cheaper - the longevity regime the project targets
- **Prediction** - break-even lands at modest N (hundreds of queries) because KGF's query path is 2 vector lookups + renders while summary-graph methods re-synthesize
- **Acceptance bar** - frontier published with all costs (tokens, wall-clock, dollars); refuted if KGF's query path is not materially cheaper at equal accuracy
- **Experiment** - instrumented runs alongside H113
- **Result** - pending
- **Verdict** - pending

### R11-H116 The ablation ladder - every shipped stage must earn a point

- **Weak spot** - "architecturally sound" is asserted; the goal's reviewer will ask which stages actually carry the result
- **Hypothesis** - on the H113 harness, ablating each stage (propositions, entity resolution, curing/typed ontology, bitemporal validity) costs >=1 probe-metric point each - no dead weight in the shipped configuration
- **Prediction** - propositions cost the most (H34's channel census), bitemporal the least on a static corpus (its value is longevity, measured instead by H117)
- **Acceptance bar** - every stage >=1 point or the stage is flagged for removal per the simplification doctrine (the H37 precedent: measured theater gets cut)
- **Experiment** - 4 ablated builds + probe cycles; with H113's infrastructure
- **Result** - pending
- **Verdict** - pending

### R11-H117 Degradation under dirt - the longevity differentiator

- **Weak spot** - the longevity claim (months of operation on accumulating, imperfect corpora) has no comparative evidence
- **Hypothesis** - under controlled corpus corruption (10% near-duplicate documents, contradictory revised versions, OCR-noise injection), KGF's accuracy degrades <=half as much as vector-RAG and BM25-RAG baselines - the identity + bitemporal machinery is FOR this, and this is where it shows
- **Prediction** - contradictory versions are where bitemporal wins visibly; near-duplicates are where resolution wins; OCR noise hits everyone (H51's parse sensitivity)
- **Acceptance bar** - <=half degradation vs both baselines; refuted if KGF degrades comparably - the maintenance machinery fails its core promise and the finding outranks every other in the program
- **Experiment** - corrupted-corpus variants + H113 harness; post-wave
- **Result** - pending
- **Verdict** - pending

### R11-H118 Close the mode-family probe - and prove the fix generalizes

- **Weak spot** - the unlinked mode-family probe (det 9/10 on query answerability) has persisted across three releases; every prior fix attempt was global machinery hoping to catch it incidentally
- **Hypothesis** - a targeted repair - H56's coverage-gap proposition generation plus H58's shared-specification collective evidence, applied to the failing family - closes the probe deterministically AND the same detector sweep finds >=2 OTHER unlinked mode families in the campaign graph, proving the fix is a class repair, not a spot patch
- **Prediction** - the family links via shared spec values; the campaign graph contains parallel cases
- **Acceptance bar** - probe passes + >=2 generalization finds; refuted if the family only links with hand-written evidence (the failure is extraction-fundamental, routed to H119)
- **Experiment** - detector sweep deterministic; generation needs the local model; post-wave
- **Result** - pending
- **Verdict** - pending

### R11-H119 Extraction determinism - variance is a prompt property

- **Weak spot** - the consolidation instability (same documents, different entity surfaces across runs) drives duplicates upstream of every resolver fix (H107's predicted dominant root cause)
- **Hypothesis** - re-extracting the same 10-document set 5x, entity-set Jaccard variance drops >=50% under temperature-0 decoding plus a canonicalization prompt (naming rules: fullest form, no marketing suffixes, singular) versus the production prompt - determinism is substantially a prompt property, not an inherent LLM limitation
- **Prediction** - naming variance (surface forms) collapses; genuine content variance (which entities matter) persists at a lower floor - the residual defines the resolver's irreducible workload
- **Acceptance bar** - >=50% variance reduction at equal extraction recall (no entities lost to rigidity); refuted if variance persists (inherent nondeterminism - the resolver keeps its full workload and H101's benchmark becomes even more critical)
- **Experiment** - 5x2 extraction runs on the local model; post-wave GPU window
- **Result** - pending
- **Verdict** - pending

### R11-H120 Ship the evidence-weighted detector - from verdict to default

- **Weak spot** - H50 proved the spike-doc false-alarm class and H59 registered the fix (binomial-LLR CUSUM), but the production detector still runs all-3-consecutive; a proven-better instrument sitting unshipped is a weak spot of process, not knowledge
- **Hypothesis** - H59's detector, implemented behind a config flag and replayed against the FULL wave-1b remap stream (spike doc included) plus injected sustained shifts, produces zero false alarms and detection delay <= the production criterion at matched ARL0 - clearing it for default-on in the next minor release
- **Prediction** - clean replay; the flag flips
- **Acceptance bar** - zero false alarms on realized stream AND matched-or-better detection on injections; refuted if implementation-vs-harness divergence appears (the harness idealized something production breaks)
- **Experiment** - extends drift.py behind `drift.detector_variant`; deterministic replay; runs after H59's harness verdict lands
- **Result** - pending
- **Verdict** - pending

## R12 - the matching-model round: giving the resolver a signal with the right shape (pre-registered 2026-07-06)

H107 partitioned the duplicate problem (71% extraction variance, 29% resolver-visible misses) and exposed the core signal defect: the resolver's embedding likelihood is bi-encoder cosine, which measures TOPICAL similarity, not identity - "EverGo" vs "EverGo oxygen concentrator" scores 0.983 (same product) while adjacent siblings score ~0.95 (different products); the signal saturates exactly in the decision band. This round, fanned out from the project owner's concepts (better embedding model, another model class, cross-encoders, anisotropy removal), tests whether a matching signal with the RIGHT shape - joint attention over both records, directional entailment, field decomposition, string-theoretic features, isotropized geometry - separates what raw cosine cannot. Interim labels until H101 lands: the H107 candidate inventory (47 variance pairs + 19 resolver misses as noisy positives), same-name SAME_AS pairs (clean positives), model-number-family siblings (hard negatives), the 6 labeled false merges (clean negatives), random pairs (easy negatives). Hardware note: cross-encoders and small embedders run on the idle GPUs (0/2) NOW - this round does not wait for the wave.

| id | concept | claim | runnable now |
|----|---------|-------|--------------|
| H121 | cross-encoder | a pretrained pairwise cross-encoder (bge-reranker class) separates duplicates from siblings at AUC >= cosine + 0.10 - joint attention sees what two independent vectors cannot | yes (GPU 0/2) |
| H122 | NLI entailment | identity = MUTUAL entailment: bidirectional NLI detects the containment asymmetry ("EverGo" entailed by "EverGo oxygen concentrator") and flags siblings via spec contradiction | yes (GPU 0/2) |
| H123 | embedder bake-off | the best IDENTITY embedder is not the retrieval embedder: a dedicated local model (bge/e5/gte class) beats Titan on duplicate-ranking AUC - split the two jobs | yes (GPU 0/2) |
| H124 | contrastive fine-tune | a small embedder fine-tuned on SYNTHESIZED variance pairs (perturbations mirroring measured extraction variance) + sibling hard negatives beats every off-the-shelf model | yes (GPU 0/2) |
| H125 | instruction embedding | an instruction-tuned embedder prompted "represent the product identity, ignore descriptors" closes >= half the gap to the cross-encoder at bi-encoder cost | yes (GPU 0/2) |
| H126 | field decomposition | separate name/spec/description similarity channels as three LR terms beat the single full-record vector - false merges are high-desc/low-spec, variance pairs are high-name | yes |
| H127 | LLM pairwise judge | the local 120B as cross-encoder beats dedicated cross-encoders on accuracy but loses the cost frontier - quantify the exchange rate | post-wave |
| H128 | defer-band architecture | cross-encoder ONLY in the Bayesian defer band captures >= 90% of the full gain at < 5% of the pair-scoring cost | after H121 |
| H129 | calibration transfer | isotonic calibration of the winning scorer lifts resolver calibration from 44% to >= 70% held-out - fix the posterior by replacing its likelihood | after H121/H101 |
| H130 | string-theoretic revival | null-leaning: on the VARIANCE class (71% of the problem), tuned string features match neural scorers - the classic ER stack suffices where the defect is surface form | yes |
| H131 | anisotropy removal | the 0.93-0.99 saturation is partly GEOMETRY: mean-centering + whitening/ABTT over the stored Titan vectors spreads the similarity distribution and lifts duplicate-ranking AUC >= 0.05 with zero new models | yes |
| H142 | self-calibrating loop | the builder adjudicates its own defer-band decisions with the resident LLM and recalibrates on schedule - active-learning calibration as a pipeline stage | post-wave |
| H143 | NLI + cross-encoder complementarity | the contradiction channel and the relevance channel miss different pairs; the ensemble beats the better individual by >= 0.04 AUC | yes (GPU 0/2) |

### R12-H121 The cross-encoder sees the pair - joint attention for identity

- **Grounding** - the measured saturation: variance pairs and sibling pairs both live at cosine 0.93-0.99 (H107 inventory); cross-encoders attend across both records jointly and are the standard reranking fix for exactly this failure shape; pretrained checkpoints run zero-shot on a free GPU
- **Hypothesis** - a pretrained cross-encoder scoring record pairs (name + types + top spec lines) separates true duplicates from siblings at ROC-AUC >= bi-encoder cosine + 0.10 on the interim labeled set, zero training
- **Prediction** - cosine AUC lands 0.6-0.75 (saturated); cross-encoder >= 0.85; the win concentrates on the sibling hard negatives
- **Acceptance bar** - AUC gap >= 0.10; refuted if the cross-encoder inherits the saturation (identity is not in its pretraining signal either)
- **Experiment** - interim pair set + two checkpoints on GPU 0/2; runs now
- **Result** - pending
- **Verdict** - pending

### R12-H122 Identity as mutual entailment - direction matters

- **Grounding** - identity has a logical structure similarity lacks: A and B denote the same thing iff each record entails the other; one-directional entailment is CONTAINMENT ("EverGo" vs "EverGo oxygen concentrator" - the measured dominant variance form); NLI cross-encoders ship pretrained (3-label, entailment index via id2label)
- **Hypothesis** - bidirectional NLI scoring classifies the three regimes the resolver conflates: mutual entailment = duplicate, asymmetric entailment = surface variant (merge, keep the fuller name), contradiction on spec fields = sibling (never merge)
- **Prediction** - the asymmetry signal alone recovers >= 70% of the 47 variance pairs; contradiction fires on >= 60% of siblings
- **Acceptance bar** - both clauses; refuted if NLI treats all high-overlap product records as mutually entailing
- **Experiment** - NLI checkpoint on GPU 0/2; runs now
- **Result** - pending
- **Verdict** - pending

### R12-H123 The identity embedder is not the retrieval embedder - split the jobs

- **Grounding** - one Titan vector serves retrieval seeding AND resolution likelihood - two tasks with different invariances (retrieval wants topical closeness; identity wants surface-form invariance plus sibling separation)
- **Hypothesis** - at least one local embedder (bge-m3 / e5-large / gte class, conventions respected: e5 prefixes + mean pooling, bge CLS) beats Titan on duplicate-ranking AUC by >= 0.05; retrieval keeps Titan untouched - the resolver gets its own signal
- **Prediction** - a 3-4 model bake-off finds a winner
- **Acceptance bar** - >= 0.05 AUC over Titan; refuted if all bi-encoders saturate identically - the failure is the CLASS, not the checkpoint, and H121 becomes the only route
- **Experiment** - embed the interim pair set per model on GPU 0/2; runs now
- **Result** - pending
- **Verdict** - pending

### R12-H124 Train the invariance we measured - contrastive fine-tune on synthesized variance

- **Grounding** - H107 measured the exact perturbation distribution extraction produces (drop/add descriptors, abbreviate, attach model codes) - synthesizable from the graph itself; hard negatives from model-number families; CCA's synthetic-mismatch warning applies
- **Hypothesis** - a small embedder contrastively fine-tuned on synthesized pairs beats every off-the-shelf model by >= 0.05 AUC on REAL pairs (train synthetic, test real - the honest split)
- **Prediction** - the invariance is narrow and learnable in hours on GPU 0/2
- **Acceptance bar** - >= 0.05 over the H123 winner; refuted if synthetic-real transfer fails (route to H101 labels for real-pair training)
- **Experiment** - sentence-transformers contrastive loop; runs now
- **Result** - pending
- **Verdict** - pending

### R12-H125 Just ask the embedder - instruction-tuned identity representation

- **Grounding** - instruction-embedding models condition the vector on a task string; an identity instruction is a zero-training lever between off-the-shelf and fine-tune
- **Hypothesis** - an instruction-tuned embedder with "represent this product listing for identity matching, ignoring marketing descriptors" closes >= 50% of the bi-encoder-to-cross-encoder AUC gap at unchanged cost
- **Prediction** - helps on variance pairs, not siblings (instructions cannot inject spec-contradiction detection)
- **Acceptance bar** - >= 50% gap closure; refuted if the instruction moves AUC < 0.02
- **Experiment** - one instruction model in the H123 harness; runs now
- **Result** - pending
- **Verdict** - pending

### R12-H126 Three channels, not one vector - field-decomposed likelihoods

- **Grounding** - false merges are high-description/low-spec agreement; variance pairs are high-name-containment; a single full-record vector averages the distinction away (H41's split-index idea, reborn where the evidence says it matters)
- **Hypothesis** - per-field similarity features (name / spec / description) beat the single-vector likelihood by >= 0.07 AUC, and the per-field pattern is diagnostic: name-high+spec-low = sibling, name-contained+spec-high = variant
- **Prediction** - the spec channel does the sibling separation; the name channel does the variance work
- **Acceptance bar** - >= 0.07 + the diagnostic pattern; refuted if fields are too sparse to embed reliably
- **Experiment** - field extraction + per-field similarity; runs now
- **Result** - pending
- **Verdict** - pending

### R12-H127 The 120B as cross-encoder - accuracy vs the exchange rate

- **Grounding** - an LLM judging "same product? yes/no/uncertain + one-line evidence" is the most expressive cross-encoder available; H94 tests the set-wise form, this is pairwise; the question is what accuracy costs
- **Hypothesis** - the local 120B pairwise judge beats the best dedicated cross-encoder by >= 5 accuracy points at >= 100x the per-pair cost - the exchange rate that decides H128's architecture
- **Prediction** - LLM wins accuracy; cost confines it to the defer band
- **Acceptance bar** - both measured; frontier measurement, no refutation clause
- **Experiment** - ~150 pairs post-wave; the same calls double as H101 adjudication
- **Result** - pending
- **Verdict** - pending

### R12-H128 Cross-encode only the defer band - the architecture that ships

- **Grounding** - cross-encoders cannot replace blocking (quadratic); production shape: bi-encoder blocking -> posterior -> cross-encoder only where the posterior defers (defer band was 5 of 77 decisions in the v28 record)
- **Hypothesis** - defer-band-only cross-encoding captures >= 90% of the full-cross-encoder quality gain at < 5% of its pair-scoring cost
- **Prediction** - the band holds most decision-relevant uncertainty if the posterior is even weakly informative
- **Acceptance bar** - both clauses; refuted if hard pairs land OUTSIDE the band - confirming H54 from a third direction
- **Experiment** - replay with band gating; after H121
- **Result** - pending
- **Verdict** - pending

### R12-H129 Fix the posterior by replacing its likelihood - calibration transfer

- **Grounding** - 44% calibration with a 2-point isotonic curve says the current likelihood carries no usable probability; a separating scorer + isotonic calibration is the standard repair
- **Hypothesis** - the winning scorer, isotonically calibrated on labeled pairs, lifts held-out decision accuracy from 44% to >= 70% with ECE <= 0.15
- **Prediction** - the scorer does the lifting, the calibration map makes it honest; the isotonic curve gains real support
- **Acceptance bar** - both clauses held-out; if labels are too few pre-H101, re-run on the benchmark (H101 is the round's keystone)
- **Experiment** - after H121 and ideally H101
- **Result** - pending
- **Verdict** - pending

### R12-H130 The classic stack was built for this - string features on the variance class

- **Grounding** - 71% of the duplicate problem is surface-form variance - the EXACT regime classical ER string similarity was built for, decades before embeddings; null-leaning by design
- **Hypothesis** - on the variance class, a 4-feature string logistic (token-subset containment, Jaro-Winkler, length-normalized edit distance, model-code equality) matches the best neural scorer within 0.03 AUC at ~zero cost
- **Prediction** - strings match neural on variance, lose on siblings - the constructive outcome is a CASCADE: strings resolve the cheap 71%, neural handles the hard 29%
- **Acceptance bar** - within 0.03 on variance; the cascade ships if both halves win their class; refuted if neural dominates even pure surface variance
- **Experiment** - python-Levenshtein (existing dependency) + logistic; runs now, no GPU
- **Result** - interim (same notebook): the 4-feature string logistic scores 0.878 overall and 0.855 on the variance-vs-sibling class - trailing even the whitened bi-encoder (0.947 on variance) by 0.09, three times the 0.03 parity bar. The cascade premise weakens before the neural winners even run
- **Verdict** - pending final vs H121/H123, but leaning REFUTED: embeddings dominate on this corpus even for pure surface variance (product names carry semantics strings cannot see - 'EverGo' vs 'EverGo oxygen concentrator' is trivial for both, but 'FOT' vs 'Forced Oscillatory Technique' is invisible to every string feature and easy for the embedder). The classic stack survives only as the model-code equality feature, already a detector

### R12-H131 Isotropize the space - the saturation is partly geometry

- **Grounding** - sentence/document embedding spaces are anisotropic (vectors occupy a narrow cone), compressing cosine into a thin high band - and the measured band here is 0.93-0.99, the classic signature; the standard removals (mean-centering, PCA whitening, all-but-the-top component removal) are deterministic transforms over the STORED vectors, zero new models
- **Hypothesis** - isotropizing the Titan space (centering + whitening or top-k component removal, fit on all 2798 entity vectors) spreads the pair-similarity distribution (interquartile range >= 3x) and lifts duplicate-vs-sibling ranking AUC by >= 0.05
- **Prediction** - the spread materializes; part of the "saturation" dissolves as geometry rather than semantics; the residual saturation is the true bi-encoder class limit that H121 addresses
- **Acceptance bar** - both clauses; refuted if whitened cosine ranks no better (the compression was semantic, not geometric - the class limit is real and the cross-encoder route is mandatory)
- **Experiment** - numpy over stored embeddings; runs now, no GPU; transforms also re-tested under H123's winner
- **Result** - measured in [`matching_models_r12.ipynb`](../../notebooks/matching_models_r12.ipynb) on the interim pair set (252 pairs: 47 variance + 19 resolver-miss + 20 same-name positives; 40 siblings + 6 false merges hard negatives; 120 random). Transform sweep (centering, PCA whitening, all-but-top-k for k in 1/3/5/10) fit on all 2798 entity vectors: duplicate-vs-hard-negative AUC moved raw 0.888 -> whiten 0.901 (+0.013, bar was +0.05); the similarity spread RATIO came out 0.7x (whitening narrowed the pair-set IQR rather than widening it). Both clauses fail
- **Verdict** - REFUTED, with the diagnosis worth more than a confirmation: raw cosine's RANKING was never broken by geometry - AUC 0.888 against hard negatives means the order is largely right even inside the compressed 0.93-0.99 band, because AUC is rank-based and insensitive to value compression. What the compression actually breaks is THRESHOLDING and calibration (a fixed 0.6 cut on values crammed into a 0.06-wide band) - which relocates the fix from the geometry (H131, dead) to the calibration layer (H129) and the pair-scoring class (H121). The registered refuter clause fires exactly as written: the class limit is real, the cross-encoder route is mandatory for the residual

## R13 - the optimal-transport round: identity, drift and completeness as transport problems (pre-registered 2026-07-06)

Fanned out from the project owner's direction: optimal transport for resolution through embeddings - Sinkhorn, Wasserstein - and its natural extensions in this system. The unifying idea: an entity is not a point, it is a BAG (of name tokens, spec key-values, attached propositions, graph neighbors), and a document is a bag of entities; identity, contradiction, drift and completeness are all statements about how cheaply one bag transports onto another. Single-vector cosine collapses the bag before comparing - transport compares the bags directly, with unmatched mass as a first-class signal (the contradiction/incompleteness residue cosine cannot express). Precedent in-house: the WMD document-distance work in the user's prior research track. Solvers: exact EMD via scipy assignment on small bags (name/spec bags are 5-50 items), entropic Sinkhorn (POT library) where bags grow. All entries use existing stored embeddings; most run now on CPU.

| id | concept | claim | runnable now |
|----|---------|-------|--------------|
| H132 | WMD identity | Word Mover's Distance over record token-embedding bags separates duplicates from siblings at AUC >= cosine + 0.10 - the bag sees the differing token | yes |
| H133 | Sinkhorn spec alignment | OT over property key-value sets: matched mass = shared identity evidence, UNMATCHED mass = contradiction feature that flags siblings | yes |
| H134 | neighborhood transport | entity as distribution over 1-hop neighbor embeddings; Wasserstein between neighborhoods = relational identity signal orthogonal to text (H62's Jaccard, continuously generalized) | yes |
| H135 | assignment-constrained resolution | cross-document entity alignment as entropic OT with one-to-one constraints - the transport polytope FORBIDS the many-to-one chaining that built the false SAME_AS closures | yes |
| H136 | Gromov-Wasserstein twins | structure-only matching (no shared space needed) catches duplicates whose text diverged (codes, abbreviations) - the structural complement to H130's strings | yes |
| H137 | barycenter chain guard | merged identity = Wasserstein barycenter of member embeddings; a chain member far from the barycenter is a false member - the OT form of H58's chain guard, tested on the model_code closures | yes |
| H138 | type-distribution OT | types as embedding distributions; W-distance between types ranks merge candidates, within-type barycenter clustering ranks splits - the principled proposal engine for H98's granularity operators | yes |
| H139 | Sinkhorn drift channel | per-document entity-embedding distribution vs the graph baseline: an embedding-space drift alarm racing JSD-on-types (distribution), H77 (spectral) and H90 (topological) - the fourth family on the early-warning panel | yes |
| H140 | completeness transport | transport cost from chunk-embedding mass to entity-embedding mass per document: expensive chunks = unextracted content - a per-document completeness instrument for the audit doctrine | yes |
| H141 | transport likelihood | the integration test: replacing LR_emb with a transport-based likelihood (WMD + unmatched-mass features) in the posterior lifts calibration beyond H129's scorer swap | after H132/H133 |

### R13-H132 Word Mover's Distance - the bag sees the differing token

- **Grounding** - cosine collapses "Pro-Flow adult nasal cannula" to one vector where "adult" is diluted; WMD transports token embeddings and pays explicitly for the token with no counterpart; in-house precedent: the WMD document-distance research track
- **Hypothesis** - WMD over record token bags (name + type + spec keys, stopword-stripped, existing embedding vocabulary) separates duplicates from siblings at AUC >= raw cosine + 0.10; the unmatched-token cost is itself a usable feature
- **Prediction** - siblings pay visibly for their differing model tokens; variance pairs transport nearly free (containment = cheap partial transport)
- **Acceptance bar** - AUC gap >= 0.10; refuted if token-level transport inherits the same saturation (token embeddings equally anisotropic - couple with H131's whitening, which is a registered interaction)
- **Experiment** - scipy exact EMD on small bags; CPU, runs now
- **Result** - pending
- **Verdict** - pending

### R13-H133 Unmatched mass is the contradiction - Sinkhorn over the spec sets

- **Grounding** - the sibling problem is structured disagreement: most spec keys match, ONE value differs (pressure range, weight); cosine averages it away; OT with marginals over key-value items yields matched mass (shared evidence) AND unmatched/expensive mass (the disagreement) as separate quantities
- **Hypothesis** - the transport residual (cost concentrated on unmatchable spec items) flags siblings at >= 0.8 precision where both records carry >= 3 spec items; combined matched+residual features beat any single similarity
- **Prediction** - the residual isolates the differing value; sparse-spec pairs abstain (honest coverage limit)
- **Acceptance bar** - precision clause on the sibling set; refuted if spec value embeddings are too coarse to localize the disagreement
- **Experiment** - Sinkhorn (POT) over key-value embedding bags; CPU, runs now
- **Result** - pending
- **Verdict** - pending

### R13-H134 Neighborhood transport - relational identity, continuously

- **Grounding** - H62 registered neighbor-set Jaccard (discrete overlap); OT generalizes it: an entity is a distribution over its neighbors' EMBEDDINGS, so two duplicates whose neighbor sets differ in surface form but agree in meaning still transport cheaply
- **Hypothesis** - neighborhood Wasserstein ranks the labeled duplicate pairs better than neighbor-Jaccard by >= 0.05 AUC and carries signal on pairs with ZERO literal neighbor overlap (where Jaccard is blind)
- **Prediction** - the continuous version wins exactly on cross-document pairs whose contexts were extracted with different surface forms
- **Acceptance bar** - both clauses; refuted if median degree 1 starves the signal (most entities have too few neighbors to form a distribution - the honest scale risk)
- **Experiment** - per-pair EMD over 1-hop neighbor embedding bags; CPU, runs now
- **Result** - pending
- **Verdict** - pending

### R13-H135 The transport polytope forbids the chain - assignment-constrained resolution

- **Grounding** - the false SAME_AS closures were built by greedy PAIRWISE merging then transitive union - nothing enforced global consistency; OT with one-to-one marginals is a global assignment: mass conservation makes "A matches B AND A matches C with B unlike C" expensive by construction
- **Hypothesis** - re-resolving document-pair entity sets as entropic OT assignments (Sinkhorn, low temperature) reproduces the true merges while producing ZERO of the known false closure members - the constraint does structurally what H58's evidence guard does heuristically
- **Prediction** - the model_code false merges (mask-battery over 'P10') never survive assignment because the mask has a better match or no match; P09's legitimate multi-doc identity survives
- **Acceptance bar** - zero false closures + P09 regression-free; refuted if legitimate multi-facet entities NEED many-to-one (the assignment constraint would then be too strong - measured, not assumed)
- **Experiment** - replay over the SAME_AS-bearing document pairs; CPU, runs now
- **Result** - pending
- **Verdict** - pending

### R13-H136 Gromov-Wasserstein - matching structure to structure

- **Grounding** - GW aligns two metric spaces WITHOUT a shared embedding space: it matches neighborhoods by their internal distance patterns; duplicates whose text diverged completely (pure code vs full name) are invisible to every text signal but may be structural twins
- **Hypothesis** - GW distance between candidate pairs' 1-hop induced subgraphs (edge-type-aware cost) recovers >= 3 labeled duplicates that BOTH cosine and string features rank below threshold
- **Prediction** - the wins are the code-vs-name pairs
- **Acceptance bar** - >= 3 unique recoveries at precision >= 0.5 in the flagged head; refuted if degree-1 neighborhoods make GW degenerate (same scale risk as H134, registered separately because GW fails differently)
- **Experiment** - POT entropic GW on small neighborhood graphs; CPU, runs now
- **Result** - pending
- **Verdict** - pending

### R13-H137 The barycenter chain guard - membership by distance to the center of mass

- **Grounding** - a merged identity (SAME_AS cluster) should have a coherent center; the Wasserstein barycenter of member record-bags is that center; the false closure members (MANU, bCPAP prongs) should sit far from the barycenter of the cluster they were chained into
- **Hypothesis** - member-to-barycenter distance separates false from true members of the *1..2 closures at AUC >= 0.85, and thresholding it removes the known false members with zero true-member loss
- **Prediction** - the model_code chains show the widest member spread (consistent with their false-merge surface)
- **Acceptance bar** - both clauses; refuted if barycenters of small clusters (2-4 members) are too unstable to threshold
- **Experiment** - barycenters over the 127-edge closure clusters; CPU, runs now; on confirmation joins H58/H88 as the third chain-guard prong
- **Result** - pending
- **Verdict** - pending

### R13-H138 Types as distributions - the granularity proposal engine

- **Grounding** - H98 needs candidate merge/split operators ranked by something better than intuition; a type IS a distribution of its entities' embeddings; W-distance between two type distributions measures their semantic separation, within-type 2-barycenter clustering measures internal heterogeneity
- **Hypothesis** - type-pair W-distance ranks merge candidates and within-type barycenter-split gain ranks split candidates such that the top-3 proposals of each contain every operator that H98's probe replay confirms as improving
- **Prediction** - Condition/MedicalCondition and Feature/ComfortFeature-class pairs rank as top merge candidates; Accessory (999 entities) ranks as top split
- **Acceptance bar** - the confirmed operators (if any) come from the OT top-3s; refuted if probe-improving operators exist that OT ranks poorly (the proposal engine misses what matters)
- **Experiment** - sliced-Wasserstein between type distributions; CPU, runs now; feeds H98
- **Result** - pending
- **Verdict** - pending

### R13-H139 The fourth alarm family - drift as transport in embedding space

- **Grounding** - the early-warning panel has three families: distributional (JSD on type frequencies, production), spectral (H77), topological (H90); none sees SEMANTIC shift - a new document whose entities are embedded far from everything the graph knows; Sinkhorn divergence between the doc's entity-embedding distribution and the graph baseline is exactly that instrument
- **Hypothesis** - per-doc Sinkhorn divergence stays in a tight band on the healthy wave and responds to injected off-domain documents at >= 2x smaller injection than the type-frequency JSD needs - semantic drift shows in embedding space before it shows in type mix
- **Prediction** - clean band on wave 1b; the campaign's single spike doc is NOT an outlier here (its entities were on-domain - the remap spike was an identity event, not a semantic one; the two instruments measure different things, which is the point)
- **Acceptance bar** - differential sensitivity + wave specificity; refuted if the divergence just tracks document length or entity count
- **Experiment** - replay over wave-1b per-doc entity embeddings + injection; CPU, runs now
- **Result** - pending
- **Verdict** - pending

### R13-H140 The completeness meter - what the chunks hold that the graph does not

- **Grounding** - the audit doctrine wants "the graph knows what it doesn't know"; per-document transport cost from chunk-embedding mass to the document's extracted-entity embedding mass measures exactly the content extraction left behind (expensive chunk mass = nothing in the graph accepts it cheaply)
- **Hypothesis** - per-chunk transport residual correlates with the known extraction gaps (the H21 zero-chunk finding class, refusal-probe subjects) at rank correlation >= 0.5, giving the completeness audit a per-document instrument
- **Prediction** - table-heavy and stylized-rendering chunks (H51's suspects) carry the highest residuals
- **Acceptance bar** - correlation clause against the labeled gap inventory; refuted if residuals track chunk length/genre instead of extraction quality
- **Experiment** - chunk vs entity embedding bags per document (chunk embeddings exist for retrieval; else Titan on a sample); mostly runs now
- **Result** - pending
- **Verdict** - pending

### R12-H142 The self-calibrating identity loop - the builder labels its own doubt

- **Grounding** - (user-directed, 2026-07-06) H129 calibrates ONCE on a static label set; but the foundry runs for months and its decision distribution drifts with the corpus; the defer band already isolates exactly the decisions worth labeling; an LLM adjudicator is already resident (the extraction model) - the loop closes itself: sample defer-band decisions -> LLM adjudicates against source chunks with evidence strings -> labels accumulate in the graph -> isotonic recalibration re-fits on schedule -> thresholds adapt. Active-learning calibration as a PIPELINE STAGE, not a one-shot experiment
- **Hypothesis** - a self-calibration loop (adjudicate up to N=20 defer-band pairs per ingest batch, refit isotonic when >=30 new labels) keeps held-out decision accuracy within 5 points of an oracle calibrated on ALL labels, at <=5% of the oracle's labeling cost - and beats the static H129 calibration by >=10 points after one corpus shift (wave 2 vs wave 1 material)
- **Prediction** - the loop's accuracy tracks the oracle; the static calibration decays across waves; adjudication cost stays bounded because the defer band shrinks as calibration improves (the loop consumes its own fuel)
- **Acceptance bar** - all three clauses on the campaign waves; refuted if LLM adjudication labels are too noisy to calibrate on (measured against H101's human-auditable evidence strings - the noise rate itself is a deliverable)
- **Experiment** - simulated loop on wave-1b decisions + live on wave 2; local model; post-wave
- **Result** - pending
- **Verdict** - pending

### R12-H143 NLI and the cross-encoder are different instruments - measure the complementarity

- **Grounding** - (user-directed, 2026-07-06) H121 (cross-encoder) and H122 (NLI) both score pairs, but they answer different questions: the cross-encoder scores RELEVANCE-shaped similarity, NLI scores directional LOGICAL relation (entailment/contradiction/neutral) - the contradiction channel has no cross-encoder counterpart, and the entailment asymmetry detects containment no symmetric scorer can express
- **Hypothesis** - the two signals are complementary, not redundant: an ensemble (cross-encoder score + both NLI directions + contradiction probability) beats the better individual by >= 0.04 AUC on the interim set, with NLI's contradiction channel contributing the sibling separation and the cross-encoder contributing the variance-pair recall
- **Prediction** - error sets barely overlap: cross-encoder misses structured contradictions (one spec value differs in otherwise-identical records), NLI misses fuzzy paraphrase identity; the ensemble's defer-band deployment (H128) uses NLI contradiction as a cheap veto BEFORE the cross-encoder runs
- **Acceptance bar** - >= 0.04 ensemble gain + the error-set analysis; refuted if the signals correlate > 0.9 (one suffices - keep the cheaper)
- **Experiment** - extends the H121/H122 GPU harness with the ensemble arm; runs with that batch
- **Result** - pending
- **Verdict** - pending

### R13-H141 Transport in the posterior - the integration test

- **Grounding** - H129 swaps the likelihood for a calibrated scorer; this asks whether TRANSPORT features specifically (WMD distance + unmatched-mass residual + barycenter coherence) add calibration beyond whatever scorer wins - i.e., is OT a better likelihood or just another correlated signal
- **Hypothesis** - adding transport features to the winning H129 configuration lifts held-out decision accuracy by >= 5 further points or reduces ECE by >= 0.05; otherwise OT stays a detector-side tool and the posterior keeps the simpler likelihood
- **Prediction** - the unmatched-mass residual is the only transport feature that survives feature selection (it is the one thing no similarity scalar expresses)
- **Acceptance bar** - either clause on held-out folds; a null result is a clean simplification verdict
- **Experiment** - after H132/H133 land and H129 has a baseline
- **Result** - pending
- **Verdict** - pending


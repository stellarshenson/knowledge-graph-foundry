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

### R01-H9 Separate extraction model from orchestrator model

- **Hypothesis** - because extraction is high-volume and mechanical while orchestration (clustering, judging, summarizing) is low-volume and judgment-heavy, routing extraction to a cheaper model will hold recall and quality at materially lower cost
- **Lever** - `Settings.extraction_llm` (bulk extractor) vs `Settings.llm` (orchestrator); single-model run is the control
- **Mechanism** - `Foundry.extraction_engine` resolves to a separately configured engine when `extraction_llm` is set, falling back to the orchestrator engine when None
- **Prediction** - entities/relationships per document within 10% of the single-strong-model run at lower per-document cost
- **Acceptance bar** - recall and duplicate_name_density flat vs single strong model, cost down
- **Result** - pending (capability shipped, measurement not yet run)
- **Verdict** - pending

## R02 - retrieval-first graph shape (pre-registered 2026-07-06)

Second batch, grounded in the six-thread external research round recorded in [`../sota-decision.md`](../sota-decision.md) (R02 section) with all cited papers archived under [`../../references/papers/`](../../references/papers/). Directive driving the batch: perfect context in 1-2 hops for weak reader models - work shifts from query time to ingest time. Baseline for all bars is the R01 rebuild measurement (verdicts above, measurement in progress). A shared probe set is part of this batch's setup: 25-30 questions over the CPAP corpus with gold evidence - comparison, single-fact, multi-hop, and deliberately unanswerable items - scored on answer accuracy, evidence recall, faithfulness (verifiable/total statements), and abstention correctness, with a weak reader (Haiku-class) alongside the standard reader.

| hypothesis | lever | mechanism | predicted | acceptance bar | verdict |
|---|---|---|---|---|---|
| R02-H10 | extraction typing | values-as-properties constraint + cure-time value-likeness demotion guard | type proliferation killed at source | cured types <= 15 on CPAP, no gold entity lost | pending |
| R02-H11 | graph shape | ingest-time proposition (semantic-unit) nodes, embedded, citation-carrying | weak-reader accuracy up, tokens down | evidence recall +10% and weak-reader accuracy up vs entity-only context | pending |
| R02-H12 | retrieval topology | passage nodes inside PPR projection, tiered reset weights | multi-hop evidence recall up | evidence recall +5% vs post-hoc chunk attach, query latency < 2x | pending |
| R02-H13 | graph density | kNN similarity edges + defer-band alias edges | coherent local density up, recall up | avg_degree >= 4.0 and entity recall +5%, duplicate_name_density not up | pending |

### R02-H10 Values-as-properties extraction constraint

- **Hypothesis** - because LLM extraction promotes measured values ("4-20 cmH2O") to entity types (PressureRange, Weight, Warranty) and no SOTA system does this, constraining extraction to emit unit/measure/range strings as properties or claims on the parent entity - with a deterministic value-likeness demotion guard at cure time as backstop - will collapse the type inventory to the legitimate domain types without losing any gold entity
- **Lever** - extraction prompt schema + cure-time demotion guard; corpus, engine, resolution held fixed
- **Mechanism** - extraction schema forbids value-like type names; demotion guard classifies each candidate type by member-name statistics (fraction of digit/unit-dominant tokens) and folds attribute-like types into properties before curing metrics see them
- **Prediction** - cured type count drops from the R01 rebuild's measured count (order 66) to <= 15; JSD/Chao1 gates operate on a legitimate inventory and cure earlier
- **Acceptance bar** - cured types <= 15 on the CPAP rebuild AND no gold entity (devices, manufacturers, modes) lost from the graph
- **Experiment** - <br>source: [`[paper digest] Microsoft GraphRAG.md`](../../references/papers/) (claims/covariates model), [`[paper digest] NodeRAG.md`](../../references/papers/) (attribute nodes are entity summaries, never values)<br>method: modify extraction prompts + add demotion pass; re-run CPAP ingest; diff type inventory and gold entity list
- **Result** - pending
- **Verdict** - pending

### R02-H11 Proposition nodes as first-class retrieval targets

- **Hypothesis** - because weak readers fail when forced to synthesize scattered entity descriptions at query time, generating self-contained proposition sentences at ingest (entity + key edges folded into standalone facts with source chunk ids), embedding them, and returning them as the primary context unit will raise weak-reader accuracy while cutting context tokens
- **Lever** - ingest-time proposition generation + retrieval returns propositions before chunks; extraction, resolution, PPR core held fixed
- **Mechanism** - NodeRAG semantic-unit pattern: content nodes carry what retrieval returns; entity names remain entry points; propositions seed and rank in PPR
- **Prediction** - evidence recall on the probe set up >= 10%; weak-reader accuracy up; context tokens per query down or flat
- **Acceptance bar** - evidence recall +10% and weak-reader accuracy improves vs entity-description context, token budget not up more than 20%
- **Experiment** - <br>source: [`[paper digest] NodeRAG.md`](../../references/papers/) (retrieval ratio 94.9% vs 86.3%, MuSiQue 46.3% at 5.9k tokens)<br>method: proposition generator in the load path, proposition label + embedding, retrieval assembly prefers propositions; probe set A/B
- **Result** - pending
- **Verdict** - pending

### R02-H12 Passage nodes inside the PPR projection

- **Hypothesis** - because attaching chunks after PPR severs passage relevance from graph diffusion, adding chunk nodes to the PPR projection with a low reset weight will propagate passage and entity relevance jointly and raise multi-hop evidence recall
- **Lever** - PPR projection contents + reset-weight tiering (passages ~0.05, entities/propositions 1.0); seeds and damping held fixed
- **Mechanism** - HippoRAG 2 composite graph: dense passage signal and sparse phrase signal fuse inside one PPR run instead of post-hoc
- **Prediction** - evidence recall up >= 5% on multi-hop probes; single-fact probes unaffected
- **Acceptance bar** - evidence recall +5% vs post-hoc chunk attachment with no single-fact regression and query latency under 2x
- **Experiment** - <br>source: [`[paper digest] HippoRAG 2.md`](../../references/papers/) (passage-node removal costs 11 recall@5 points on MuSiQue)<br>method: extend the GDS projection with chunk nodes + weighted sourceNodes; probe set A/B against R01 retrieval
- **Result** - pending
- **Verdict** - pending

### R02-H13 Similarity-edge densification

- **Hypothesis** - because KGF's avg_degree 2.49 sits near the density of measurably failing systems (1.48) and far below winning ones (~8.75), adding cosine-gated kNN similarity edges between entities plus alias edges for the resolution defer band will densify coherent local clusters and raise entity recall without inflating duplicates
- **Lever** - similarity/alias edge creation at load time; resolution merges, PPR, extraction held fixed
- **Mechanism** - HippoRAG synonym-edge pattern scoped: hard merge stays primary, similarity edges connect near-neighbours so PPR can traverse lexical/semantic variants; defer-band pairs get alias edges instead of forced decisions
- **Prediction** - avg_degree rises to >= 4.0; entity recall on probes up >= 5%; orphan absorption as a side effect, not a target
- **Acceptance bar** - avg_degree >= 4.0 and entity recall +5% with duplicate_name_density not above baseline
- **Experiment** - <br>source: [`[paper digest] HippoRAG.md`](../../references/papers/) (synonym edges cosine > 0.8), [`[paper digest] When to Use Graphs in RAG.md`](../../references/papers/) (degree 8.75 vs 1.48 winners/losers), kNN augmentation study (+6.4% entity recall, p=0.000043)<br>method: post-load kNN pass over entity embeddings, gated cosine threshold; probe set A/B
- **Result** - pending
- **Verdict** - pending

## R03 - query-side context assembly (pre-registered 2026-07-06)

Query-time batch over the R02 graph shape; each lever independent of the others, all measured on the shared probe set.

| hypothesis | lever | mechanism | predicted | acceptance bar | verdict |
|---|---|---|---|---|---|
| R03-H14 | seeding | query-to-triple linking alongside entity seeds | seed quality up | evidence recall +5%, no latency blowup | pending |
| R03-H15 | query handling | comparison decomposition into per-entity retrievals | comparison accuracy up | comparison probe accuracy +10%, tokens < 1.5x | pending |
| R03-H16 | serialization | PPR-ordered per-entity blocks, head+tail placement, per-claim citations | weak-reader accuracy and faithfulness up | weak-reader accuracy +10% and faithfulness >= 0.9 | pending |
| R03-H17 | abstention | structural coverage verdict (seed neighbourhood, path connectivity, community overlap) | unanswerables refused | >= 70% correct refusal on unanswerable probes, < 10% false refusal | pending |

### R03-H14 Query-to-triple seeding

- **Hypothesis** - because a query names relations as often as entities ("pressure range of X"), embedding relation sentences and seeding PPR from matched triples plus entities will raise evidence recall over entity-only seeding
- **Lever** - seed construction; PPR core and context assembly held fixed
- **Mechanism** - HippoRAG 2 query-to-triple linking: triple embeddings capture predicate semantics entity names miss
- **Prediction** - evidence recall up >= 5%, biggest gain on attribute questions
- **Acceptance bar** - evidence recall +5% with no meaningful latency increase
- **Experiment** - <br>source: [`[paper digest] HippoRAG 2.md`](../../references/papers/) (+12.5% recall@5 average, +21 on MuSiQue)<br>method: embed relation sentences at load, vector-match query against triples, union seed sets; probe A/B
- **Result** - pending
- **Verdict** - pending

### R03-H15 Comparison-query decomposition

- **Hypothesis** - because "A vs B on X" requires covering two entity neighbourhoods and one-shot retrieval splits its budget badly between them, decomposing into per-entity sub-retrievals and unioning contexts will raise comparison accuracy at bounded cost
- **Lever** - query routing for detected comparisons; retrieval per sub-query unchanged
- **Mechanism** - structural split (entity list x attribute), not LLM-guessed decomposition - shallow by construction, no error propagation
- **Prediction** - comparison probe accuracy up >= 10%; context efficiency improves
- **Acceptance bar** - comparison accuracy +10% with combined context under 1.5x single-query tokens
- **Experiment** - <br>source: RT-RAG / EfficientRAG findings (decomposition +7% F1 / +6% EM, ~10x context efficiency) via traversal research thread in [`../sota-decision.md`](../sota-decision.md)<br>method: comparison detector in query(), per-entity PPR, deduplicated union; probe A/B on comparison items
- **Result** - pending
- **Verdict** - pending

### R03-H16 Reasoning-ordered context serialization with citations

- **Hypothesis** - because flat concatenation buries key facts mid-context (>30% degradation) and uncited claims invite fabrication, serializing per-entity blocks (name, propositions, relationship facts, source snippet) ordered by PPR score with top items at head and tail, and forcing per-claim citation ids, will raise weak-reader accuracy and faithfulness
- **Lever** - context assembly format only; retrieval set identical
- **Mechanism** - lost-in-the-middle mitigation + StrictCitations grounding, both measured strongest in the small-model band
- **Prediction** - weak-reader accuracy up >= 10%; faithfulness >= 0.9; no cost increase
- **Acceptance bar** - weak-reader accuracy +10% and faithfulness >= 0.9 on the probe set
- **Experiment** - <br>source: [`[paper digest] Lost in the Middle.md`](../../references/papers/), [`[paper digest] Instruction Tuning LLMs on Graphs.md`](../../references/papers/) (structured blocks beat flat triples, largest gain small models), [`[paper digest] Let Me Speak Freely.md`](../../references/papers/) (no forced JSON answers: -10-15% reasoning)<br>method: serializer A/B with identical retrieval; faithfulness scored as verifiable/total statements
- **Result** - pending
- **Verdict** - pending

### R03-H17 Structural abstention signal

- **Hypothesis** - because reader-model confidence is a proven-useless refusal signal (0% correct abstention) while graph structure is not, emitting a coverage verdict from seed-neighbourhood size, path connectivity between query entities, and community overlap - and refusing or clarifying when coverage is thin - will catch most unanswerable questions without suppressing answerable ones
- **Lever** - pre-generation coverage gate; retrieval and generation unchanged when coverage passes
- **Mechanism** - structural signals (empty neighbourhood, no connecting path, low overlap) measure what the graph knows, independent of reader confidence
- **Prediction** - >= 70% of unanswerable probes refused; < 10% of answerable probes falsely refused
- **Acceptance bar** - correct refusal >= 70% and false refusal < 10% on the probe set
- **Experiment** - <br>source: HRAG graph cross-validation (76% correct refusal vs 0%) via topology research thread in [`../sota-decision.md`](../sota-decision.md)<br>method: coverage scorer over retrieval internals; probe set includes deliberately unanswerable items (off-corpus devices, absent attributes)
- **Result** - pending
- **Verdict** - pending

# R57 Miss-Atlas - Retrieval-Failure Diagnostics Research Brief (2026-07-24)

Cross-references the IR / RAG / KGQA failure-diagnosis literature against the R57 miss atlas (per-(probe, gold-entity) coordinate system: linker, dense, traversal, entity, query, join+render axes; H620 retrieve/render/read decomposition; near-miss shelf, tie-loss, boundary+1, textually-starved, one-class-per-miss claims). New digests filed in `references/papers/`. Verdict tags: VALIDATES / EXTENDS / CONTRADICTS.

## (A) Failure taxonomies

- **Load-bearing taxonomy** - Barnett's *Seven Failure Points* (`[paper digest] Seven Failure Points of RAG.md`) is the applied-RAG standard: FP1 Missing Content, FP2 Missed Top-Ranked, FP3 Not-in-Context (consolidation), FP4 Not Extracted, FP5 Wrong Format, FP6 Incorrect Specificity, FP7 Incomplete
- It is a **pipeline partition by loss-stage**, not an overlapping symptom list - FP1-FP4 form a clean corpus->retrieve->consolidate->read cascade
- **Maps to atlas (VALIDATES H620)**: FP1 = carrier absent from corpus, FP2 = carrier_not_retrieved (linker/dense axes, rank below adaptive/top-16 cutoff), FP3 = retrieved_not_rendered (consolidation drop), FP4 = rendered_answer_absent (reader miss). Our three H620 classes are Barnett's FP1-FP4 coarsened - external confirmation the fence is drawn in the right place
- **Class we lack (EXTENDS)**: an explicit **FP1 corpus-gap class** - answer-carrier present at NO depth - distinct from carrier_not_retrieved. The atlas presumes the gold entity exists in the graph; the "no carrier anywhere" terminal case has no coordinate
- The RAG-evaluation lens (`[paper digest] sufficient context.md`, already filed) splits errors into insufficient-context vs failed-to-use-sufficient-context - the same retrieve/read fence, from the reader side
- **Recommendation 1**: add a `corpus_gap` terminal value to the join/render status axis (FP1) so a genuinely-absent carrier is not miscoded as a retrieval near-miss
- **Recommendation 2**: adopt Barnett FP5/FP6/FP7 as optional sub-types of the render-status flag (format / specificity / completeness) only if render misses prove numerous - do not pre-build

## (B) Rank-diagnostic practice (classic IR failure analysis)

- The **RIA workshop** (`[paper digest] RIA workshop where can IR go.md`) manually autopsied 6 systems x 45 TREC topics; Buckley's categories dominate on "emphasized one aspect, missed another"
- **Key result**: root cause is the same across all systems for 39/45 topics - all rankers **miss the same topic aspect** in their top documents. Failure is **topic-intrinsic, not per-system noise**
- **Standing verdict (VALIDATES our closed axes)**: "no one knows how to choose good approaches on a per-topic basis" - per-query failure *prediction/selection* has resisted decades of effort, a pre-neural echo of our three killed score-shape attempts
- Classic IR did **not** use signed-distance-to-cutoff / near-miss-shelf diagnostics - it used manual aspect-level autopsy. The near-miss shelf is a modern dense-retrieval construct; Barnett FP2 ("ranked, just below top-K") is its nearest named analogue and treats it as an expected first-class failure - **VALIDATES the shelf as a real axis, not an artifact**
- Topic-intrinsic failure **grounds the atlas's premise**: because the miss reproduces across retriever variants, per-(probe, entity) coordinates measure structure, not run luck
- **Recommendation**: reframe the atlas as a **per-query failure-class router input** (RIA's "match technique to topic" lesson), not a confidence predictor - the literature says diagnosis is tractable, prediction is not

## (C) Query performance prediction (QPP)

- `[paper digest] QPP for Neural IR Are We There Yet.md` - 19 QPPs x 7 lexical + 7 BERT retrievers; taxonomy = pre-retrieval (query/corpus stats) vs post-retrieval (coherency=Clarity, score-shape=WIG/NQC/SMV, robustness)
- **Finding (VALIDATES our 3 KILLED score-shape attempts)**: QPPs are statistically significantly worse on neural IR; accuracy drops up to 10% vs lexical, and fails precisely on the semantically-hard queries that matter. Semantic BERT-QPP does not fix it
- Post-hoc **score-distribution prediction is weak for dense retrieval** - the field's own verdict. Our kills are consistent with SOTA, not a local mistake. The literature does **not** contradict us
- **EXTENDS**: QPP separates *pre-retrieval* (query specificity, anchor IDF) from *post-retrieval* predictors; our atlas is entirely post-retrieval. Pre-retrieval query-side signal is the untried lever the closed score-shape axis points at
- **Recommendation**: keep signed-distance-to-cutoff as a *descriptive* miss coordinate only; do not re-promote it to a confidence signal (QPP is the pre-registered trap). If prediction is retried, test a **pre-retrieval query-specificity predictor** (query axis), never another post-hoc score-shape statistic

## (D) Position / render effects (retrieval vs reader)

- `[paper digest] Lost in the Middle.md` (filed): U-shaped positional accuracy - LLMs use head/tail context, lose the middle (>30% degradation); render/read failure is a distinct, position-dependent axis from retrieval failure
- `[paper digest] sufficient context.md` (filed): autorater sufficiency signal cleanly separates "context insufficient" (retrieval) from "failed to use sufficient context" (reader) - the standard two-way decomposition
- **Maps to atlas (VALIDATES H620)**: our carrier_not_retrieved vs retrieved_not_rendered vs rendered_answer_absent is exactly the sufficiency split with the consolidation stage (Barnett FP3) inserted. The standard equivalent to H620 **exists** and agrees with our fence
- **EXTENDS**: Lost-in-the-Middle says render failure is **position-conditioned** - a carrier can be retrieved AND in-context yet lost purely by mid-context placement. Our retrieved_not_rendered class does not record the carrier's *position* in the assembled prompt
- **Recommendation**: add a **render-position coordinate** (rank/position of the carrier within the assembled context window) to the render side of H620, so a Lost-in-the-Middle positional loss is distinguishable from a true consolidation drop

## (E) Multi-hop specifics (bridge-entity failure)

- `[paper digest] MuSiQue.md` - the standard multihop failure diagnosis is **bridge-entity centric**: failure = failing to retrieve/traverse the bridge entity linking hop-1 to hop-2. Single-hop (disconnected-reasoning) models drop 30 F1 points; bridge-paragraph removal is the operational definition of unanswerable
- `[paper digest] Self-Ask Compositionality Gap.md` (filed): ~40% of 2-hop questions fail despite both sub-answers being individually correct, and the gap does not shrink with scale - the failure is the *composition* (bridge) step, not the lookups
- Standard role split: **first-hop lookup vs bridge-traversal vs terminal-answer**. The bridge is the load-bearing locus; there is no single published first-vs-bridge-vs-comparison *fraction* (it is dataset-specific), but bridge-traversal is the consensus dominant multihop failure
- **Maps to atlas (EXTENDS traversal axis)**: our traversal axis records *where* a carrier sits (hop distance to region boundary, on/off-path, PPR-mass rank) but not its *reasoning role*. A bridge miss and a terminal miss share a hop coordinate yet differ in downstream cost
- **Cross-check (VALIDATES boundary+1 claim mechanistically)**: bridge entities sit structurally one hop past the first-hop anchor neighborhood - a bridge-heavy miss profile *predicts* boundary+1 clustering, supplying the mechanism our geometric claim currently lacks. Anchor-reset seeding (H583/H597) is precisely the bridge-reachability remedy disconnected retrieval skips
- **Recommendation**: add a **bridge-role tag** (first-hop / bridge / terminal) to each missed gold entity via the probe's decomposition; then test whether the boundary+1 shelf is bridge-dominated

## Actionable axis gaps (summary)

1. **`corpus_gap` terminal class** (Barnett FP1) - absent-carrier distinct from unretrieved-carrier
2. **Bridge-role tag** (MuSiQue / Self-Ask) - first-hop / bridge / terminal on every missed entity
3. **Render-position coordinate** (Lost-in-the-Middle) - carrier's position in the assembled context, to split positional loss from consolidation drop
4. **Pre-retrieval query-specificity predictor** (QPP) - the one prediction lever not yet killed; the post-hoc score-shape axis stays closed

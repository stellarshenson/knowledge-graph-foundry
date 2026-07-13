# R42 Metrics Framework - Literature Brief (2026-07-11)

Grounding for a METRICS FRAMEWORK round. User directive (2026-07-11, verbatim intent): "research metrics that make it genuinely measurable and that we can track gradient with respect to hyperparameters and hypothesis." The problem: the 24-probe recall harness is saturated (composed frontier 0.9583 = 23-of-24, the last probe a parser loss) and binary-per-probe - one probe = 4.2 points of composite, run-to-run sigma 0.0290 (H351), so levers smaller than a whole probe are invisible and only cliffs register. Gradient here means finite-difference sensitivity on measured response curves with error bars, not backprop. The framework must compose with the two incoming high-resolution instruments: the R39-H389 coverage certificate (continuous 0-1 per-doc fact coverage, +-2% reproducibility clause) and the #59 benchmark's 1000-question sets.

Fences: R38 owns calibration certificates (H383-H388); R39 owns the coverage instrument itself (H389) and coverage-driven ingest (H390/H394); R35 owns the answerability gap ledger (H373); R31-H351 owns the N>=3 Welch gate form, already shipped. R42 claims the MEASUREMENT FRAMEWORK: the metric registry with priced noise floors, paired-design evaluation, response-curve tracing, and attribution - the layer that makes every other round's verdicts cheap and honest.

## 1. Measurement-science anatomy - the exact numbers

**Sample size vs detectable delta** (Adding Error Bars to Evals, arXiv 2411.00640 - the load-bearing source). Paired-design formula: n = (z_a/2 + z_b)^2 (w^2 + s_A^2/K_A + s_B^2/K_B) / d^2, where w^2 = Var(x_A) + Var(x_B) - 2Cov(x_A, x_B) is the paired per-question variance and K is answer resamples. At 80% power, alpha 0.05 (multiplier 7.85), typical paired variance w^2 = 1/9:

| Target delta | Questions needed (paired) |
|---|---|
| 0.05 | 349 |
| 0.03 | 969 - the paper's "new evals need >= 1,000 questions" headline |
| 0.02 | 2,180 |
| 0.01 | 8,721 |

- **At n = 1000 fixed** (the #59 sets): MDE = 2.80 sqrt(w^2/1000) = **2.95 points** at w^2 = 1/9; 4.4 points for binary EM at cross-arm correlation 0.5 (w^2 = 0.25); 6.3 points unpaired binary (w^2 = 0.5). Pairing is not optional - it is worth 1.4-2.1x in resolution for free
- **A 1-point delta is out of reach of 1000 questions** - it needs ~8,700 questions, or variance reduction: K-resampling (MDE 13.2% → 7.5% raising K 1 → 10 at n = 198), next-token-probability scoring instead of sampled answers, or tighter pairing
- **Clustered SEs**: questions sharing a source document are correlated; naive SEs are up to **3x too small** on real evals - the #59 sets generated from a shared corpus MUST cluster by document or every significance claim inflates
- **Paired differences**: Var(paired) = Var(unpaired) - 2Cov/n - the formal statement of "hypothesis A/Bs difference out shared variance"; run both arms on the SAME questions, report per-question deltas

**Which test** (Urbano et al., SIGIR 2019, arXiv 1905.11096, simulation with known null): the **paired t-test** maintains Type I exactly at alpha, is most powerful (especially small n), robust to non-normality; permutation near-identical; Wilcoxon, sign, and bootstrap-shift should be discontinued (bootstrap-shift biases toward small p-values). Type III errors (right rejection, wrong direction) reach **~2%** on shallow measures at 25-50 questions - small probe sets can produce confidently wrong-signed verdicts. This ratifies and generalizes the H351 Welch-CI form: one test form, everywhere.

**Judge reliability as instrument noise** (MT-Bench, arXiv 2306.05685): GPT-4 judge vs human majority **85%** agreement (non-tie), human-human ceiling **81%** - but agreement is delta-dependent, falling from ~100% on large gaps to **~70% on close pairs**, exactly KGF's operating regime. Position bias: only GPT-4 swap-consistent > 60%; few-shot raises consistency 65.0% → 77.5%. RAGAS (arXiv 2309.15217) puts numbers on reference-free metric constructions: statement-decomposition faithfulness agrees with humans **0.95**, answer relevance **0.78**, context relevance **0.70** - the construction (decompose to per-statement ratios) beats raw LLM scoring (0.72/0.52/0.63). A 0.70-agreement instrument has a ~30% flip rate and cannot gate small deltas.

**Pricing the judge instead of trusting it** (ARES, arXiv 2311.09476 + Prediction-Powered Inference, arXiv 2301.09633): fine-tuned lightweight judges + PPI rectification on **~150-300 human labels** yield system rankings at Kendall tau **0.91/0.97** (context/answer relevance), beating RAGAS by +0.065/+0.132 tau and a 1,350-annotation direct-sampling baseline by 0.08 tau with 78% fewer labels. Label floor is real: tau collapses to 0.44-0.67 at 50 labels. GPT-4 labels substituted for human cost 0.05-0.30 tau. PPI mechanism: measure the judge's bias on the labeled subset (the rectifier), subtract it, widen the CI by the rectifier's uncertainty - validity guaranteed regardless of judge quality, interval width scales with judge accuracy. This is the H351 doctrine applied to instrument error: never trust a band you have not measured.

**Differentiable surrogates** (reported per mission): a class of textual-gradient pipeline optimizers exists (DSPy-style prompt compilation, TextGrad-style LLM-feedback descent) that treats pipeline metrics as losses; none of them price metric variance - they descend on noisy point estimates. Not load-bearing for R42's measurement framework; papers deliberately not archived this round (no number used), archival owed by any future round that builds on them. KGF's "gradient" stays finite-difference on variance-priced response curves.

## 2. Current-instrument audit

What KGF measures today, resolution, and noise-floor status:

| Instrument | Measures | Resolution | Noise floor | Status |
|---|---|---|---|---|
| 24-probe recall harness (`notebooks/h158_measure.py` recall_at_k) | share of gold evidence in rendered context, mean of 24 probes | fractional per probe, but 1 probe = 4.2 pts of composite | run-mean sigma **0.0290 MEASURED** (H351); MDD 0.059 at N=3/arm, +0.03 needs ~12 runs/arm | **SATURATED** at 0.9583; gates only cliffs |
| Deterministic benchmark (63 checks) | binary graph-structure checks | 1 check = 1.6 pts | ~0 (deterministic) | healthy but coarse; 60/63 since v18 |
| SAME_AS precision proxy (298 adjudicated pairs) | resolver merge precision/recall vs labels | continuous | deterministic given event log, but label set DECAYED - only 14/68 true pairs still name-resolvable (H375) | decayed; needs re-adjudication |
| Never-extracted census | failed-probe gold entities absent from graph | integer count | ~0 (near-deterministic graph lookup - H351's model primary clause) | healthy; the exemplar low-variance mechanism check |
| Generative judge scores (v28-era, 5-axis) | 1-5 ordinal per quality axis | 20 pts per step | **UNKNOWN - never replicated**; MT-Bench predicts ~70% agreement in the close-pair regime | unpriced; unusable as gate |
| Calibration accuracy (25 ground-truth pairs) | resolver posterior calibration | 4 pts per pair | unknown; n = 25 is below every power threshold in Section 1 | starved |
| ECE/calibration machinery (R38, in flight) | escalation + abstention confidence | continuous | to be registered by R38 | incoming |
| Context growth / tokens per query | retrieval cost | continuous | ~0 (deterministic per config) | healthy - the one true continuous instrument shipped today (+27.8% static, +6.9% ladder, measured to 0.1%) |
| Throughput calibration cache (R30/DEF-12) | knee, tok/s, latency p50/p95 | continuous | window variance carried per entry | healthy; the registry pattern to copy |
| Coverage certificate (R39-H389) | per-doc fact coverage 0-1 | per-fact (~15 facts/doc → ~6.7%/doc, ~0.7% corpus-level at 10 docs) | +-2% reproducibility CLAUSE, to be measured N>=3 | incoming - first continuous ingest-side instrument |
| Answerability gap ledger (R35-H373) | unanswerable-but-grounded question count | integer, ranked | >= 50%-of-top-20 precision bar | incoming |

Summary: two instruments have measured noise floors (harness sigma 0.0290, throughput windows); the deterministic instruments have ~0 floors but 1.6-4.2-point resolution; every judge-derived score is unpriced. The composite has no attribution path - when 0.9583 moves, nothing says which component moved.

## 3. Proposed metric suite mapped to KGF components

Design rules applied throughout: continuous ratios over binary probes (RAGAS's decomposition move); paired per-question deltas with clustered SEs (Error Bars); paired t/Welch as the only test form (Urbano, H351); judge metrics only with PPI rectification (ARES); every metric enters a REGISTRY carrying its measured sigma, and acceptance bars are auto-priced off the registry (H351 generalized).

| Metric | Component | Range | Resolution | Cost per eval | Noise-floor source | Gradient exposed (knobs) |
|---|---|---|---|---|---|---|
| Extraction coverage (H389 certificate) | extraction + parsing | 0-1 per doc | per-fact, ~0.7% corpus-level | <= 25% of ingest (H389 bar) | +-2% clause, measured N>=3 re-audits | passes K, chunk size, prompt form, parser choice |
| Identity fragmentation rate | resolver | duplicate-pair density per 1k entities | per-pair | graph census + blocking, no LLM | ~0 given graph; sampling CI on adjudicated subset | merge threshold, blocking k, canonicalization |
| Retrieval recall@k, paired, on #59 1000-q sets | retrieval | 0-1 mean | 0.1%; MDE ~3 pts at n=1000, ~1 pt at n~8.7k | retrieval-only, no LLM, ~40x harness cost | clustered SE (cluster = source doc), measured | top_k, span length, seeds, escalation threshold, PPR on/off |
| Answer faithfulness, PPI-rectified judge | reader / end-to-end | 0-1 with CI | CI width = the floor, scales with judge quality | local judge all items (idle-card, H363 economics) + one-time 150-300 adjudications | PPI rectifier variance, reported per run | render form, reader prompt, context budget |
| Answerability closure rate (H373 ledger) | graph completeness | rate + integer backlog | per-question | 1 retrieval + present-check, no LLM | near-0 (deterministic check) | every ingest lever |
| Calibration ECE + Brier (R38) | escalation + resolver confidence | 0-1 | binned | offline replay | bootstrap CI over decision set (R38 registers) | escalation threshold, calibration curve |
| Tokens per answered query | cost | continuous | 0.1% | free telemetry | ~0 | every context lever |
| Run-to-run sigma (per metric, registered) | the framework itself | >= 0 | - | N>=3 config-identical replays, replay-cheap where possible | it IS the floor | extraction-form levers (DEF-11's target) |

**Attribution chain** (requirement 5): the metrics form a staged pipeline - extraction coverage → post-resolution coverage (facts surviving the resolver) → seed recall → render recall → answer faithfulness/EM - each stage measured on the SAME question/fact set. When the composite moves, walk the chain; the first stage whose delta exceeds its registered band owns the move. This is retrieval-vs-reader error attribution (the RAGAS/ARES triad) extended to the two KG-specific stages (extraction, identity) that RAG evaluation never has.

**Composition with incoming instruments**: H389's coverage score is the chain's first stage and inherits the registry's N>=3 sigma measurement (its +-2% clause becomes a measured floor, not a hope); the #59 1000-question sets are the chain's last two stages' substrate, run paired with per-question deltas and document-clustered SEs from day one.

## 4. Proven-novel open slots

- **S1 - Variance-priced hypothesis adjudication as a first-class framework.** The Error Bars paper prescribes the practice for model evals; RAGAS/ARES score systems but do not price experiment gates; no RAG/KG evaluation framework ships a metric registry where every metric carries a measured run-to-run sigma and acceptance bars are derived from it. KGF already lives the doctrine ad hoc (H351's gate form, R30's calibration cache with window variance) - making it the registry is unclaimed. Open
- **S2 - Component-attribution chain for KG pipelines.** Published RAG evaluation decomposes retrieval vs generation (the RAGAS/ARES triad); nothing published decomposes extraction / identity / retrieval / render for KG-RAG, and nothing runs all stages on a shared question set so deltas attribute. Open
- **S3 - Response-curve registry with MDE-aware step sizing.** Hyperparameter sweeps are ubiquitous; sweeps whose step size is chosen so adjacent points differ by more than the metric's measured band - so the traced curve is real, not noise - appear nowhere. Open
- **S4 - Coverage-certificate-derived metrics** (from R39's S1): the certificate as the extraction-stage member of a priced metric chain; R39 owns the instrument, R42 owns its registry integration and its use in attribution. Open by composition
- **S5 - PPI for graph-quality judging.** ARES applies PPI to query-level RAG triads only; nobody applies the rectifier pattern to fact-level graph audits (judge = graph-support test, gold = one-time human-verified miss sample). Directly upgrades H389's LLM support-test from trusted to priced. Open

## 5. Hypothesis candidates (placeholder numbering HX+1.., assigned after R40/R41 registration)

### HX+1 Metric registry with measured noise floors - the H351 rule generalized (conformist)

- **Mechanism** - every gate-eligible metric ships a registry entry: N>=3 config-identical replay sigma, resolution, cost, clustering structure; acceptance bars are AUTO-PRICED as one-sided Welch CIs against the registered floor; a bar citing an unregistered metric is a registration error
- **Grounding** - H351 (2-run bands false-fail 46-60% at true null; sigma 0.0290 measured once, for one metric); Error Bars Sections 2-5 (the arithmetic); R30 calibration cache (the registry pattern, already shipped for throughput)
- **Falsifiable prediction** - >= 3 currently-shipped metrics have noise floors LARGER than deltas cited in past acceptance bars (the judge 5-axis scores, the 25-pair calibration accuracy, and per-probe recall are the candidates); at least one historical verdict's margin sits inside its metric's measured band
- **Bar sketch** - registry populated for >= 6 metrics; replay-based floors for all offline-computable ones; one historical-verdict audit run and recorded (GAP-1 discipline: past verdicts stand, the audit prices the NEXT gates)
- **Composes with** - every subsequent hypothesis in every round; H389's +-2% clause becomes a registry entry

### HX+2 Paired per-question evaluation with document-clustered SEs on the #59 sets (conformist)

- **Mechanism** - A/B arms always run on the same 1000 questions; verdicts on per-question deltas via paired t-test; SEs clustered by source document; report MDE alongside every mean
- **Grounding** - Error Bars (paired variance = unpaired - 2Cov/n; clustered SEs up to 3x naive; MDE 2.95 pts at n=1000, w^2=1/9); Urbano (paired t maintains Type I, most powerful; Type III ~2% at small n)
- **Falsifiable prediction** - measured cross-arm per-question covariance on config-adjacent KGF pipelines is strongly positive (shared retrieval substrate), cutting SE >= 30% vs unpaired and making a 2-point delta decidable at n = 1000 where unpaired needs > 4 points
- **Bar sketch** - covariance and both SEs measured on one real A/B; paired MDE <= 0.7x unpaired MDE; clustered vs naive SE ratio reported; ships as the standard #59 verdict form
- **Composes with** - #59 harness (H368's gate consumes this form), HX+1 registry

### HX+3 PPI-rectified judge metrics - faithfulness and coverage support-tests with confidence intervals (follower)

- **Mechanism** - local judge (idle-card economics) scores ALL items (1000-question faithfulness; H389 fact support-tests); a one-time adjudicated sample of 150-300 items measures the judge's bias (the rectifier); every reported score is a PPI interval, never a point
- **Grounding** - ARES (tau 0.91/0.97 with 150-300 labels; collapse at 50; GPT-4 labels cost 0.05-0.30 tau - adjudication should be human or frontier-with-verification); PPI (validity regardless of judge quality); KGF already owns adjudicated seed sets (298 identity pairs, 63 checks, H389's one-time miss verification)
- **Falsifiable prediction** - PPI intervals on KGF's faithfulness metric are >= 30% narrower than classical intervals from the labeled sample alone; the unrectified judge's bias is nonzero and stable enough that the rectifier converges within 300 labels
- **Bar sketch** - CI width comparison at equal label budget; rectifier bias reported; REFUTED if the local judge's accuracy is so low the PPI interval is no narrower than classical (then only exact-match instruments ship, per HX+5)
- **Composes with** - H389 (S5), the faithfulness row of the suite, HX+1 registry

### HX+4 Component-attribution chain - the first stage past its band owns the move (conformist)

- **Mechanism** - the staged metrics (extraction coverage → post-resolution coverage → seed recall → render recall → answer score) computed on one shared question/fact set per run; a composite delta is attributed to the first stage whose own delta exceeds its registered band; ambiguous multi-stage moves flagged, never silently split
- **Grounding** - RAGAS/ARES triad (retrieval vs generation attribution exists at query level); KGF's stage instruments all exist or are registered (H389, fragmentation census, h158 seed/render decomposition, faithfulness judge); the R34 composed frontier already did this ONCE by hand (parity → +props → +window rung deltas)
- **Falsifiable prediction** - >= 80% of historically CONFIRMED levers, replayed through the chain, attribute to exactly one stage; the H366 window lever attributes to render recall, H367 to seed recall, blind
- **Bar sketch** - chain computed on >= 2 historical A/B pairs from cached artifacts; blind attribution matches the known mechanism; cost <= 1.2x of running the metrics separately (shared retrieval pass)
- **Composes with** - all suite rows; the R34 rung-decomposition pattern becomes machinery

### HX+5 The judge noise floor sits ABOVE the deltas we care about - only exact-match instruments can track gradients (contrarian)

- **Mechanism** - claim: for KGF's config-adjacent comparisons (1-3 point deltas), every LLM-judge continuous metric has replay sigma + bias drift exceeding the delta, so judge metrics can NEVER be primary gates regardless of PPI - rectification prices the noise but cannot shrink it below the effect; gradient tracking belongs exclusively to deterministic instruments (coverage certificate's present-checks, EM recall, censuses, token counts)
- **Grounding** - MT-Bench: judge-human agreement falls to ~70% on close pairs - the regime of every KGF sweep step; RAGAS context relevance 0.70; ARES tau measured on SYSTEM-level rankings with large gaps, not 1-point neighbors; KGF's own 5-axis judge scores were never replicated (Section 2)
- **Falsifiable prediction** - the same frozen graph judged 3x by the same local judge shows per-axis sigma >= 2 points (0-100 scale) while exact-match instruments replay at <= 0.5; on a 1-point-delta A/B pair the judge's paired CI includes zero but the deterministic chain's does not
- **Bar sketch** - frozen-graph replay triplet + one small-delta A/B; CONFIRMED → judge metrics demoted to supporting-evidence-only in the registry (a standing constraint on HX+3's scope); REFUTED if judge replay sigma < 1 point (then HX+3 promotes fully)
- **Composes with** - HX+1 (this is a registry population experiment), HX+3 (its adversary)

### HX+6 Retire the 24-probe harness as a gate - it is a smoke test (heretical)

- **Mechanism** - claim: post-R34 the harness has zero discriminative power between candidate configs and its gate role is theater; demote it to a regression smoke test (binary: frontier holds / regressed) and move ALL gating to the priced suite; stop spending N>=3 ingests to re-measure a saturated instrument
- **Grounding** - composed frontier 0.9583 with the last probe unreachable by retrieval (parser loss); sigma 0.0290 → MDD 0.059 at N=3 (H351) - larger than every remaining probe-level gain; Urbano Type III ~2% at n=24; Error Bars: 24 questions resolve ~19-point effects from question-sampling variance alone
- **Falsifiable prediction** - across N=5 replays each of >= 3 post-R34 configs known to differ (parity / +props / +window), the harness composite CANNOT separate at least one adjacent pair at the Welch gate, while the paired #59 form separates all three
- **Bar sketch** - the replay grid (cheap, cached retrieval); CONFIRMED → harness reclassified in the registry as smoke-only, gate budget reallocated; REFUTED if the harness separates all pairs (then saturation is priced but not disqualifying)
- **Composes with** - HX+2 (the replacement gate form), #59 harness

### HX+7 Variance is the objective - a sigma-halving lever outranks a recall lever (heretical)

- **Mechanism** - claim: at sigma 0.0290 the foundry is instrument-limited, not quality-limited - every future experiment's cost scales with sigma^2 (n ~ w^2/d^2), so halving run-to-run sigma halves every future MDE and quarters every future run budget; register sigma as a first-class KPI with its own response curve over extraction-form levers, and adjudicate at least one round where the winning lever is chosen by sigma reduction at flat recall
- **Grounding** - DEF-11 (variance sank R29's control arm); H351 (at sigma 0.029, +0.03 needs ~12 runs/arm - infeasible; at sigma 0.015 it needs ~3); H353 (JD 0.5483 naming churn, unioning did not stabilize it - the variance source is extraction FORM, unaddressed); Error Bars (n scales with w^2)
- **Falsifiable prediction** - >= 1 extraction-form lever (constrained decoding of entity names, canonical surface templates, sorted emission order) cuts run-mean recall sigma from 0.0290 to <= 0.0175 at recall within the non-regression band - paying for itself within 2 subsequent experiments' reduced run counts
- **Bar sketch** - N=4 replay ingests per arm (the sigma measurement needs its own power); sigma ratio <= 0.6 with recall non-regression; the cost accounting (runs saved per future round) reported; REFUTED if no lever moves sigma > 20% (then variance is engine-inherent and budgets must simply carry it)
- **Composes with** - HX+1 (registry), DEF-11's open half, every future round's budget

### HX+8 Finite-difference response curves - the sweep becomes a measured curve, not a scatter (follower)

- **Mechanism** - for each registered continuous knob (top_k, span length, escalation threshold ~0.765, merge threshold 0.6, chunk size), trace metric-vs-knob on cached/offline replay with error bars from the registry; step size chosen so adjacent points differ by >= 1 MDE (S3's rule); curvature and monotonicity recorded per knob; knobs whose response is a step function are flagged NOT-TUNABLE (cliff class) and excluded from gradient-style optimization
- **Grounding** - R34's M-sweep (M=0/1/2/4: 0.8542 → 0.9583 → flat → flat - a measured cliff-then-plateau, done once by hand); R37's threshold calibration (0.668 vs 0.765 - two operating points on one signal, found by sweep); Error Bars MDE arithmetic supplies the step-size rule; offline-replay economics make repeated evaluation ~free for retrieval-side knobs
- **Falsifiable prediction** - >= 2 retrieval-side knobs show smooth locally-monotone response (usable finite-difference gradient with sign stable across replays); >= 1 knob shows a cliff (adjacent-step delta > 5 MDE) proving the curve machinery correctly refuses gradient claims where none exist
- **Bar sketch** - >= 3 knobs traced at >= 5 points each, N>=3 replays per point where the metric is nondeterministic; per-knob verdict (tunable / cliff / flat) enters the registry; cost <= 1 GPU-day total on cached artifacts
- **Composes with** - HX+1 (bands), HX+2 (paired points), R37/R38 threshold machinery

| Candidate | Persona | Lever | Falsifiable prediction | Bar sketch |
|---|---|---|---|---|
| HX+1 | conformist | metric registry + auto-priced bars | >= 3 shipped metrics have floors above past bar deltas | >= 6 metrics registered, one historical audit |
| HX+2 | conformist | paired + doc-clustered #59 verdicts | pairing cuts SE >= 30%, 2-pt deltas decidable at n=1000 | paired MDE <= 0.7x unpaired, measured |
| HX+3 | follower | PPI-rectified judge metrics | CI >= 30% narrower at equal label budget | width comparison; REFUTED → judges demoted |
| HX+4 | conformist | staged attribution chain | >= 80% of confirmed levers attribute to one stage, blind | 2 historical A/Bs re-attributed correctly |
| HX+5 | contrarian | judge noise floor > target deltas | judge replay sigma >= 2 pts vs <= 0.5 exact-match | frozen-graph triplet + small-delta A/B |
| HX+6 | heretical | harness demoted to smoke test | harness cannot separate adjacent post-R34 configs at N=5 | replay grid; #59 form separates all |
| HX+7 | heretical | sigma reduction as the round objective | extraction-form lever: sigma 0.0290 → <= 0.0175 at flat recall | N=4/arm, ratio <= 0.6, cost accounting |
| HX+8 | follower | MDE-stepped response curves per knob | >= 2 smooth knobs + >= 1 detected cliff | 3 knobs x 5 points, verdicts to registry |

Sequencing: HX+1 first (the registry is the substrate every bar cites); HX+5 immediately after (it prices the judge class before HX+3 spends adjudication budget); HX+2 rides the #59 build; HX+4/HX+8 ride cached artifacts (offline); HX+6 is a cheap replay grid; HX+7 is the only full-ingest spender and queues behind the registry's sigma baseline. Defects: DEF-11's open variance half is HX+7's target.

## 6. Source register

New papers archived this round (PDF + digest in `references/papers/`, %PDF verified):

1. `[paper] Adding Error Bars to Evals, 2024-11.pdf` - sample-size formula, paired/clustered SEs, n~969 for d=0.03 (arXiv 2411.00640)
2. `[paper] Statistical Significance Testing in IR, 2019-05.pdf` - paired t-test wins, Type III ~2%, discontinue Wilcoxon/sign/bootstrap-shift (arXiv 1905.11096)
3. `[paper] RAGAS, 2023-09.pdf` - reference-free continuous RAG metrics, human agreement 0.95/0.78/0.70 (arXiv 2309.15217)
4. `[paper] ARES, 2023-11.pdf` - fine-tuned judges + PPI, tau 0.91/0.97 with 150-300 labels (arXiv 2311.09476)
5. `[paper] Prediction-Powered Inference, 2023-01.pdf` - the rectifier, valid CIs from predictions + small gold sets (arXiv 2301.09633)
6. `[paper] LLM-as-a-Judge MT-Bench, 2023-06.pdf` - judge-human agreement 85% vs 81% ceiling, ~70% on close pairs, position/verbosity bias (arXiv 2306.05685)

Already-archived digests cited: KGGen (MINE retention 29.8-66.1% - the per-fact adjudication → continuous retention score pattern), Completeness/Recall/Negation in Open-World KBs, Predicting Completeness in KBs (KB-level completeness estimation lineage), Platt vs Isotonic Calibration + Beta Calibration (R38's calibration substrate).

Internal grounding: `docs/experiments/kgf-redesign-experiments.md` (H351, H353, DEF-11, R34 composed frontier, H373, H389); `reports/experiments/adjudicated/r39-graph-construction-literature-brief-20260711.md` (MINE pattern, S1 open slot); `notebooks/h158_measure.py` (harness mechanics).

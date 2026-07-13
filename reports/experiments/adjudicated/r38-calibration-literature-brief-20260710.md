# R38 Literature Brief - Self-Calibration Mechanisms for the H382 Context-Escalation Gate

Date: 2026-07-10. Scope: published-literature solution options for calibrating, persisting, and re-calibrating the H382 gate threshold. All numbers below verified against the archived source PDFs in `references/papers/`; anything not verifiable is marked unverified.

## Problem Restated

The H382 gate is a scalar decision rule: escalate the render (rung 0 → rung 2) when the top-seed cosine signal falls below a threshold θ. Measured on 24 probes: gated policy recall 0.9583 at +6.9% context (escalation rate 25%), always-escalate 0.9583 at +27.8%, never-escalate 0.8958. Fitted θ ≈ 0.765 (2-fold cross-calibration, out-of-fold cuts 0.7650 / 0.7644). H157 established that calibration CONSTANTS do not transfer across corpus classes (isotonic transfer → ECE 0.2606 = 5.18x reference). The directive: ship an a-priori belief, calibrate per corpus, and persist the calibration information - plausibly in the graph - so future ingestions update rather than refit from scratch.

The literature maps onto four sub-problems: (1) setting θ with guarantees at tiny n, (2) combining a shipped prior with per-corpus evidence, (3) harvesting labels without humans, (4) surviving drift and persisting state across ingestions.

---

## 1. Distribution-Free and Small-Sample Threshold Setting

### Mechanism card - Split conformal quantile threshold

- **Name**: Split conformal prediction (Angelopoulos & Bates 2021, arXiv 2107.07511 - archived)
- **Mechanism**: θ = the ⌈(n+1)(1−α)⌉-th smallest of n held-out calibration scores; one sort, no fitting
- **Exact guarantee**: 1−α ≤ P(miss caught) ≤ 1−α + 1/(n+1), finite-n, both-sided; sole assumption is exchangeability of calibration and test points
- **Data requirements**: any n ≥ 1; achievable α levels are multiples of 1/(n+1) - at n = 24 the granularity is 1/25 = 0.04, so α ∈ {0.04, 0.08, 0.12, ...}
- **Update cost**: re-sort on new labels; O(n log n), trivially incremental
- **Drift behavior**: none - guarantee dies with exchangeability; this is the static, per-corpus-class fit
- **Fit verdict**: STRONG. It is the only mechanism that turns exactly our situation (scalar signal, n = 24 labeled outcomes) into an exact finite-sample guarantee. The H157 lesson is a corollary of its assumption: exchangeability holds within a corpus class, not across - so the calibration set must be per class

### Mechanism card - Conformal risk control (CRC)

- **Name**: Conformal Risk Control (Angelopoulos, Bates, Fisch, Lei, Schuster 2022, arXiv 2208.02814 - archived)
- **Mechanism**: generalize the coverage indicator to any loss monotone in the knob; pick λ̂ = inf{λ : (n/(n+1)) R̂_n(λ) + B/(n+1) ≤ α}
- **Exact guarantee**: Theorem 1: E[L_{n+1}(λ̂)] ≤ α for exchangeable, non-increasing, right-continuous losses bounded by B. Theorem 2: E[L_{n+1}(λ̂)] ≥ α − 2B/(n+1) (tight up to O(1/n))
- **Data requirements**: feasible iff α ≥ B/(n+1); binary miss loss (B = 1) at n = 24 → smallest certifiable α = 0.04. Degrades gracefully: infeasible α → λ_max (always escalate), never invalid
- **Update cost**: maintain the empirical risk step-curve R̂_n(λ) over the labeled outcome set; adding labels is an insertion + re-scan
- **Drift behavior**: none per se (same exchangeability basis); shift extensions via weighting exist in the paper
- **Fit verdict**: STRONG - the best-fitting single mechanism. Define L_i(θ) = 1{probe i unanswered under gated policy at threshold θ}; monotone provided rung 2 answers a superset of rung 0 (true on the probe set: gated matched always-escalate at 0.9583). Concrete check: with n = 24 and the 1 residual miss at θ ≈ 0.765, (24/25)(1/24) + 1/25 = 0.08 - the SHIPPED OPERATING POINT IS EXACTLY THE CRC SOLUTION AT α = 0.08. The mechanism certifies what H382 already measured, and gives the refit rule for every future corpus class

### Mechanism card - Adaptive conformal inference (ACI)

- **Name**: Adaptive Conformal Inference Under Distribution Shift (Gibbs & Candes, NeurIPS 2021, arXiv 2106.00170 - archived)
- **Mechanism**: make the working level a state: α_{t+1} = α_t + γ(α − err_t) after each observed outcome
- **Exact guarantee**: Proposition 4.1: with probability 1, for all T, |1/T Σ err_t − α| ≤ (max{α_1, 1−α_1} + γ)/(Tγ) - long-run empirical miss frequency → α under ARBITRARY distribution shift, no distributional assumptions at all
- **Data requirements**: a stream of labeled outcomes; the bound is asymptotic in T. At T = 24 outcomes and γ = 0.05 the slack is ≈ (0.92 + 0.05)/(24 × 0.05) ≈ 0.81 - vacuous. Needs hundreds of outcomes before the certificate bites
- **Update cost**: one addition per outcome; state = one float
- **Drift behavior**: its raison d'etre - coverage self-corrects through any shift; cost is that γ must match the unknown drift rate (paper used γ = 0.005), and miss bursts can push it to always-escalate (infinite-set analogue)
- **Fit verdict**: GOOD for steady state, wrong for cold start. The gate sees replay outcomes in trickles per ingestion; across many ingestions of one corpus class ACI keeps the miss rate pinned at α without ever refitting

### Mechanism card - DtACI (online conformal under arbitrary shift, successor to ACI)

- **Name**: Conformal Inference for Online Prediction with Arbitrary Distribution Shifts (Gibbs & Candes 2022, arXiv 2208.08401 - archived)
- **Mechanism**: run k ACI experts with step sizes γ_1 < ... < γ_k (ratio ≤ 2), select/average via exponential re-weighting with forgetting
- **Exact guarantee**: Theorem 3.1: dynamic-regret bound on pinball loss over EVERY interval of a chosen width against any comparator sequence (locally adaptive validity). Theorem 3.2: |1/T Σ E[err_t] − α| ≤ (1+2γ_max)/(Tγ_min) + terms in η_t, σ_t; with decaying η_t, σ_t the long-run miss frequency converges to α exactly
- **Data requirements**: same stream as ACI; no step-size tuning - adaptive to both size and type of shift
- **Update cost**: k parallel one-float updates + weight update; state = 2k floats
- **Drift behavior**: the strongest of the family - provably reacts on local windows, fixes ACI's γ-selection problem and AgACI/MVP's over-weighting of history
- **Fit verdict**: GOOD - the production form of Option S2 below if KGF wants continuous threshold adaptation without per-class tuning. Same asymptotic caveat as ACI

### Mechanism card - Conformal PID / quantile tracking

- **Name**: Conformal PID Control (Angelopoulos, Candes, Tibshirani, NeurIPS 2023, arXiv 2307.16895 - archived)
- **Mechanism**: control the THRESHOLD directly on the score scale: q_{t+1} = q_t + η(err_t − α) (P term); add saturated error integration (I term) and an optional score forecaster (D term)
- **Exact guarantee**: Proposition 1: P term alone achieves 1/T Σ err_t = α + o(1) for any score sequence bounded by an unknown constant. Theorem 1: P+I(+any D) achieves long-run coverage DETERMINISTICALLY with no assumptions on the scores
- **Data requirements**: outcome stream; asymptotic like ACI
- **Update cost**: 2-3 floats of state (threshold, integrator sum); one update per outcome
- **Drift behavior**: I-term is a built-in drift corrector; unlike ACI, never emits the infinite-set pathology - threshold moves by bounded steps on the cosine scale
- **Fit verdict**: GOOD, and architecturally the cleanest online variant for KGF because the state variable IS θ (a cosine value ~0.765), directly interpretable and persistable; the D slot can host a per-corpus prior model without endangering validity

**Section 1 bottom line**: split conformal / CRC answer "set θ from 24 labels with an exact guarantee" (α granularity 0.04); ACI → DtACI → conformal PID answer "keep θ honest online under drift" with long-run guarantees that need hundreds of outcomes to bind. They compose: conformal fit at ingestion time, controller between refits.

---

## 2. Combining an A-Priori Prior with Per-Corpus Evidence

### Mechanism card - Hierarchical Beta-Binomial threshold posterior

- **Name**: hierarchical / empirical Bayes conjugate updating (textbook conjugate analysis; no single canonical paper - not archived; the posterior-sampling use is covered by the archived Thompson Sampling tutorial, arXiv 1707.02038)
- **Mechanism**: discretize the signal into buckets (e.g., sketch quantiles); per bucket b and corpus class c, model the rung-0 miss probability p_{b,c} ~ Beta(α_b + m_{b,c}, β_b + k_{b,c}) where (α_b, β_b) are prior pseudo-counts pooled from previous corpora and (m, k) are the class's observed miss/hit counts; θ = the lowest bucket whose posterior miss probability exceeds tolerance
- **Guarantee/assumptions**: Bayesian credibility, not frequentist risk control - valid exactly insofar as the hierarchical model holds; empirical-Bayes shrinkage pulls sparse classes toward the cross-corpus mean (a soft version of shipping the prior)
- **Data requirements**: works from n = 0 (pure prior = the shipped 0.765 belief) upward; every label improves it
- **Update cost**: integer count increments; merging two ingestions = adding counts. The cheapest possible persistence
- **Drift behavior**: none intrinsic; add exponential decay on counts (discounting) to forget stale corpora - standard practice, no distribution-free guarantee
- **Fit verdict**: STRONG as the PRIOR LAYER, weak as the certificate. This is the most literal implementation of the directive "ship an a priori belief but be able to calibrate": prior pseudo-counts travel across corpus classes as structure, per-class counts dominate as evidence arrives. H157 says do not let the prior masquerade as the certificate - pair it with a conformal check

### Mechanism card - Platt scaling at tiny n

- **Name**: Platt scaling (Niculescu-Mizil & Caruana, ICML 2005 - archived)
- **Mechanism**: 2-parameter sigmoid P(miss|s) = 1/(1+exp(As+B)) fit on calibration outcomes, with regularized targets y+ = (N+ +1)/(N+ +2), y− = 1/(N− +2)
- **Guarantee/assumptions**: none distribution-free; empirically, at calibration sets below about 200-1000 cases Platt beats isotonic with ALL nine learning methods tested (the paper's learning-curve result)
- **Data requirements**: usable from a few tens of points; low variance because 2 parameters
- **Update cost**: small logistic fit; seconds
- **Drift behavior**: refit per class; sigmoid shape assumption (Gaussian per-class scores) can bias badly on skewed cosine scores
- **Fit verdict**: MODERATE - the standard citation for why H157's isotonic transfer failed (isotonic overfits below ~1000 points, and its constants are class-bound), and the fallback if a miss-probability CURVE is needed rather than a threshold

### Mechanism card - Isotonic regression (anti-recommendation at this n)

- **Name**: isotonic calibration (same archived ICML 2005 source; H157 in-house evidence)
- **Mechanism**: pool-adjacent-violators monotone step function
- **Guarantee/assumptions**: nonparametric consistency at large n only
- **Data requirements**: ~1000+ points before it beats Platt (archived learning curves)
- **Fit verdict**: REJECT at n = 24. KGF has already paid to learn this (H157: ECE 0.2606 = 5.18x on transfer); the literature agrees and adds the small-n overfitting mechanism

### Mechanism card - Beta calibration

- **Name**: Beta calibration (Kull, Silva Filho, Flach, AISTATS 2017 - archived)
- **Mechanism**: 3-parameter map µ(s; a, b, c) from Beta score distributions; fit = logistic regression on ln(s) and −ln(1−s)
- **Guarantee/assumptions**: parametric; family contains the identity (a = b = 1, c = 0) so it cannot uncalibrate an already-calibrated signal - the logistic family provably lacks this
- **Data requirements**: same regime as Platt (tens of points), one extra parameter
- **Update cost**: one small logistic fit
- **Drift behavior**: refit per class; prior transfer = initialize at parent-class (a, b, c)
- **Fit verdict**: GOOD if a probability curve is wanted: the gate signal is bounded in [0,1] and skewed, which is precisely where Platt's Gaussian-score assumption breaks and beta calibration was shown superior (Naive Bayes, AdaBoost experiments). For a pure threshold, conformal still dominates - no curve, no model bias

**Section 2 bottom line**: the prior/evidence combination splits cleanly into a Bayesian belief layer (hierarchical Beta-Binomial pseudo-counts - ships across corpora, updates by counting) and a guarantee layer (conformal/CRC - refit per class from the same labels). Curve-fitting (Platt/beta) is only needed if the gate ever consumes probabilities instead of a cut; isotonic is contraindicated at this n by both the literature and H157.

---

## 3. Harvesting Calibration Labels Without Humans

### Mechanism card - Replay outcome labels (cheapest-rung-that-succeeded)

- **Name**: Adaptive-RAG outcome-labeled supervision (Jeong et al., NAACL 2024 - already archived, see digest)
- **Mechanism**: run each probe at rung 0 and rung 2 during replay; label = the cheapest rung that answered correctly. Adaptive-RAG trained its whole complexity router from exactly such labels, no human annotation
- **Guarantee/assumptions**: labels are exact for the gate's own loss (they ARE the loss); requires a probe set with checkable answers and one always-escalate replay pass per calibration event
- **Data requirements**: n probes → n labels; cost = one rung-2 pass over the probe set (the +27.8% context cost, paid once per calibration, not per query)
- **Update cost**: re-run replay on new/changed probes only
- **Drift behavior**: replay can be re-run at any time - this is the refit trigger's payload
- **Fit verdict**: STRONG and already in hand - H382's 24 measured outcomes are exactly this label type. The literature precedent says such labels suffice to train a full router; KGF only needs them to place one scalar cut
- **Caution from the same literature**: Adaptive-RAG's labels also encoded dataset inductive biases (single-hop → B, multi-hop → C); the KGF analogue is to keep probe families balanced per corpus class, else the threshold calibrates to the probe mix, not the corpus

### Mechanism card - Self-supervised proxies

- **Name**: answer-delta and abstention proxies (mechanism generalized from archived Self-RAG (reflection/critique tokens) and FLARE (low-confidence token triggers) digests; no new paper archived)
- **Mechanism**: label without gold answers - (a) escalate-and-compare: did rung 2 CHANGE the answer materially vs rung 0? change → rung 0 was insufficient (positive label); (b) abstention/critique: reader declines or self-criticizes at rung 0 → insufficiency label; (c) FLARE-style: low generation confidence at rung 0 → insufficiency
- **Guarantee/assumptions**: proxy validity is an empirical question - answer-change ≠ answer-improvement; systematic proxy bias shifts the calibration target itself
- **Data requirements**: free at query time for (b)/(c); (a) costs a shadow escalation on a sampled fraction of live queries
- **Update cost**: none beyond logging
- **Drift behavior**: continuous label stream → feeds the online controllers (Section 1) between replay events
- **Fit verdict**: MODERATE - the only label source that scales beyond the probe set, but must be validated against replay labels before being trusted (a cheap in-house experiment: proxy-vs-replay agreement on the 24 probes). Treat as noisy-label augmentation, never as the certificate's basis

### Mechanism card - Bandit-style threshold tuning (Thompson sampling)

- **Name**: Thompson sampling / posterior-sampling bandit (Russo et al., FnTML 2018, arXiv 1707.02038 - archived)
- **Mechanism**: maintain Beta posteriors over miss-rate per candidate threshold (or per signal bucket); each ingestion, sample from the posterior and run the sampled threshold; update conjugate counts from harvested outcomes
- **Guarantee/assumptions**: regret bounds under the model prior - NOT risk control; exploratory choices can transiently raise misses
- **Data requirements**: works from zero data (prior-driven); learns fastest of all options per label because it picks informative operating points
- **Update cost**: count increments
- **Drift behavior**: none intrinsic; discounted counts as usual
- **Fit verdict**: WEAK-TO-MODERATE for KGF. Exploration below the certified threshold is a real recall loss on live queries; any use must be clamped to explore only ABOVE the conformal certificate (safe direction: escalating more than necessary costs context, not recall). Ranked last as a design driver; useful as an active-learning garnish on S1/S3

**Section 3 bottom line**: replay labels are the calibration currency and KGF already mints them; self-supervised proxies extend the stream between replays but need a one-time validity check; bandit exploration is only admissible on the cost side (over-escalation), never the recall side.

---

## 4. Drift, Recalibration Triggers, and Calibration-State Persistence

### Mechanism card - Sequential harmful-shift monitor

- **Name**: risk tracking with time-uniform confidence sequences (Podkopaev & Ramdas, ICLR 2022, arXiv 2110.06177 - archived); the modern, distribution-free replacement for classical CUSUM control charts in this role
- **Mechanism**: sequential test of "target risk ≤ source risk + ε_tol" using confidence sequences on the running miss rate; alarm → recalibrate
- **Exact guarantee**: level-δ sequential test: P(false alarm EVER fires on a benign stream) ≤ δ, valid under continuous monitoring and optional stopping; classical fixed-n tests re-run continuously have provably inflated false alarm rates (their Appendix A)
- **Data requirements**: the outcome stream (replay or validated proxies); handles delayed/batched labels - matching per-ingestion label cadence
- **Update cost**: running sums and counts; state is a handful of floats, mergeable across ingestions
- **Drift behavior**: the point - distinguishes harmful drift (miss rate up beyond tolerance) from benign drift (score distribution moved but recall held), which conformal-martingale-style exchangeability tests cannot
- **Fit verdict**: STRONG as the recalibration TRIGGER. It operationalizes "the certificate has expired" with a false-alarm budget, so re-fits happen when needed rather than every ingestion

### Mechanism card - Quantile sketches for score-distribution persistence

- **Name**: t-digest (Dunning & Ertl 2019, arXiv 1902.04023 - archived) and KLL (Karnin, Lang, Liberty, FOCS 2016, arXiv 1603.05346 - archived)
- **Mechanism**: mergeable streaming summaries of the UNLABELED gate-signal distribution - every retrieval computes the signal for free, thousands of samples per ingestion
- **Exact guarantees**: KLL: any rank query within εn with probability ≥ 1−δ in O((1/ε) log log(1/δ)) space, with matching lower bound - space independent of stream length. t-digest: error nearly constant relative to q(1−q) (sharp tails); fully merged size ≤ ⌈δ⌉ centroids for the k1 scale function; merges with no loss in accuracy (empirical design, no worst-case proof)
- **Data requirements**: none labeled - this is the label-free half of the calibration state
- **Update cost**: O(1) amortized insert; merge per ingestion
- **Drift behavior**: enables label-free early warning (new ingestion's sketch vs stored class sketch at the threshold quantile) and quantile re-expression of the threshold (θ = 0.765 ≈ the 25th percentile of class scores today; after benign shift, the same quantile re-derives a candidate θ before any label lands)
- **Fit verdict**: STRONG as persistence substrate. Choice between the two: t-digest for engineering maturity and tail sharpness, KLL when the auditability of a proven bound matters; the gate threshold sits at ~the 25th percentile, not an extreme tail, so both are adequate

### What the persisted calibration state must contain

The literature converges on a small, layered state. Per corpus class (a graph node, e.g. `(:CorpusClass)-[:HAS_CALIBRATION]->(:CalibrationState)`), store:

- **Labeled outcome ledger** - the raw replay outcomes: (probe id, signal value, rung-0 outcome, rung-2 outcome, timestamp, engine/embedder version). At tens of rows this is smaller than any sketch of it; raw retention is strictly better than any summary because every mechanism in Sections 1-2 (conformal quantile, CRC curve, Beta counts, Platt/beta fit) is a deterministic function of the ledger. Future ingestions APPEND; refits re-read
- **Unlabeled score sketch** - one mergeable t-digest/KLL per class over all gate evaluations; per-ingestion sub-sketches merged in. This is the only place sketches beat raw storage (thousands of values per ingestion)
- **Fitted operating point + provenance** - θ, method (split-conformal/CRC), α, n at fit time, fit date, fold cuts, probe-set version. Provenance is what makes "update vs refit" decidable later, and is exactly the metadata whose absence made the H157 transfer silent
- **Prior lineage** - pointer to the parent prior (global prior 0.765 with its 24-outcome pseudo-count ledger, or a parent corpus class); Beta pseudo-counts per signal bucket if S3's belief layer is adopted
- **Monitor state** - the confidence-sequence running sums/counts and the alarm log

Update semantics across ingestions: sketches merge (associative), ledgers append, counts add, conformal/CRC thresholds recompute from the merged ledger in O(n log n), monitor state accumulates until alarm → refit event resets the certificate and stamps new provenance. Nothing here ever requires the original corpus text - the state is self-contained, which is what "keep the calibration information for future ingestions" needs.

**Exchangeability discipline (H157 generalized)**: every guarantee in Section 1 is scoped to the exchangeability unit. Ship the METHOD and the PRIOR globally; scope calibration SETS, CERTIFICATES, and MONITORS per corpus class. A new corpus class starts at the prior (belief layer), runs the gate, harvests replay labels, and earns its own certificate at the first n ≥ 24 outcomes (α = 0.04 granularity requires n ≥ 24 for the finest step; n = 24 → α ∈ {0.04, 0.08, ...}).

---

## Ranked Solution Options (seeds for H383+)

### S1 (rank 1) - CRC-certified gate with prior warm-start and graph-persisted calibration ledger

The default design: conformal risk control per corpus class, shipped prior as cold-start, sequential monitor as refit trigger.

- **Stores**: labeled outcome ledger + score sketch + (θ, α, n, provenance) + monitor state + prior lineage, per corpus class, in the graph as above
- **Updates**: new corpus class → run at prior θ = 0.765 flagged UNCERTIFIED; first replay with n ≥ 24 outcomes → CRC fit at α = 0.08 (or 0.04 if affordable) → certified θ; subsequent ingestions → append labels, merge sketches, recompute λ̂ (cheap); monitor alarm or sketch shift at the threshold quantile → forced replay + refit
- **Why it wins**: exact finite-sample guarantee at exactly our n; the current operating point already satisfies it (θ ≈ 0.765 is the CRC solution at α = 0.08 on today's 24 probes); every stored artifact is an input to every other option, so S1 is forward-compatible
- **Falsifiers (H383 candidates)**: (a) on a held-out probe split of a NEW corpus class, the CRC-fit threshold's measured miss rate exceeds α by more than the B/(n+1) slack - would indicate probe non-exchangeability within class; (b) CRC at feasible α forces escalation rate above the always-escalate cost envelope (+27.8%) - guarantee too expensive at small n; (c) monotonicity violation: rung 2 answers fewer probes than rung 0 on some class, breaking CRC's premise

### S2 (rank 2) - Threshold-as-controller: conformal PID (or DtACI) between certificates

Steady-state companion to S1 for corpus classes with recurring ingestions and a continuing outcome stream (replay + validated proxies).

- **Stores**: current θ, learning rate η, integrator sum (PID) or 2k expert floats (DtACI), plus everything S1 stores
- **Updates**: every harvested outcome nudges θ by η(err − α); certificate refits (S1) re-anchor the controller; guarantees: long-run miss rate → α deterministically (PID Theorem 1) or with local-window adaptivity (DtACI Theorem 3.1/3.2)
- **Why rank 2**: guarantees are asymptotic - vacuous at 24 outcomes (ACI bound ≈ 0.81 at T = 24, γ = 0.05) - so it cannot replace S1, only extend it between refits; in exchange it is the only option that adapts DURING drift rather than after an alarm
- **Falsifiers**: (a) with realistic per-ingestion outcome counts (tens), controller oscillation produces windows with recall below never-escalate baseline; (b) measured long-run miss frequency deviates from α beyond the theoretical envelope - would indicate outcome-feedback coupling (gate decisions changing which labels arrive) that the theory does not model

### S3 (rank 3) - Hierarchical Beta-Binomial belief layer across corpus classes

The literal "a-priori belief that calibrates": prior pseudo-counts shipped globally, per-class conjugate posteriors, empirical-Bayes shrinkage pooling sparse classes toward the fleet mean.

- **Stores**: per-class, per-signal-bucket (miss, hit) counts + global prior pseudo-counts + bucket boundaries (from the score sketch quantiles)
- **Updates**: count increments per outcome; cross-ingestion merge = addition; optional exponential discounting for staleness; θ = lowest bucket with posterior miss probability under tolerance
- **Why rank 3**: weakest guarantee (model-based credibility, not risk control) - H157 is the standing warning against trusting transferred constants without a distribution-free check. Its role is cold-start ordering and cross-class pooling, wrapped inside S1's certificate; it also supplies the principled prior for any Thompson-sampling exploration of the OVER-escalation side
- **Falsifiers**: (a) on a new corpus class, the prior-derived threshold underperforms the naive shipped constant 0.765 (prior structure adds nothing); (b) posterior credible intervals at n = 24 are wider than the conformal certificate is tight - belief layer strictly dominated, drop it

### S4 (rank 4) - Standalone drift-triggered refit (monitor + sketch only, no online adaptation)

The minimal design if KGF wants no moving threshold at all: fixed certified θ per class, Podkopaev-Ramdas monitor on the outcome stream, sketch comparison on the unlabeled stream, full refit (S1 machinery) only on alarm.

- **Stores**: S1's state minus the controller; alarm log with fire reasons
- **Updates**: nothing between alarms except appends/merges; alarm (false-alarm budget δ over the whole monitoring horizon) → replay → refit → new certificate
- **Why rank 4 as a standalone**: strictly a subset of S1 (which already includes the monitor); listed separately because it is the cheapest incremental step from today's shipped gate and the natural FIRST experiment - it tests persistence and triggering without touching the decision rule
- **Falsifiers**: (a) injected harmful shift (e.g., swap embedder or corpus register) not detected within the label budget of two ingestions - monitor underpowered at KGF label rates; (b) benign-ingestion false-alarm rate empirically exceeds δ - confidence-sequence assumptions violated by label dependence

**Composition note**: S1 ⊃ S4, S1+S2 and S1+S3 compose without conflict (different layers: certificate / controller / belief). The recommended H383 registration order is S4's monitor test (cheapest, de-risks persistence), then S1 certification on a second corpus class (the H157-style transfer test done right), then S2/S3 as follow-ons.

---

## Papers Archived This Round (all verified %PDF, digests written)

| Paper | File | Role |
|---|---|---|
| Gibbs & Candes 2021, Adaptive Conformal Inference (NeurIPS) | [paper] Adaptive Conformal Inference, 2021-06.pdf | online threshold adaptation, founding guarantee |
| Gibbs & Candes 2022, DtACI | [paper] DtACI online conformal arbitrary shifts, 2022-08.pdf | step-size-free successor, local-window guarantees |
| Angelopoulos & Bates 2021, Gentle Intro to Conformal | [paper] Gentle Intro Conformal Prediction, 2021-07.pdf | split conformal exact finite-n guarantee |
| Angelopoulos et al. 2022, Conformal Risk Control | [paper] Conformal Risk Control, 2022-08.pdf | monotone-loss threshold certification - core of S1 |
| Angelopoulos, Candes, Tibshirani 2023, Conformal PID (NeurIPS) | [paper] Conformal PID Control, 2023-07.pdf | threshold-scale controller - core of S2 |
| Podkopaev & Ramdas 2021, Tracking Risk (ICLR 2022) | [paper] Tracking Risk of Deployed Model, 2021-10.pdf | recalibration trigger - core of S4 |
| Niculescu-Mizil & Caruana 2005 (ICML) | [paper] Platt vs Isotonic Calibration, 2005-08.pdf | small-n calibration evidence; H157 post-mortem citation |
| Kull, Silva Filho, Flach 2017, Beta Calibration (AISTATS) | [paper] Beta Calibration, 2017-04.pdf | parametric curve for bounded skewed scores |
| Russo et al. 2018, Thompson Sampling Tutorial (FnTML) | [paper] Thompson Sampling Tutorial, 2017-07.pdf | bandit threshold tuning + conjugate belief layer |
| Dunning & Ertl 2019, t-digest | [paper] t-digest quantile sketch, 2019-02.pdf | mergeable score-distribution persistence |
| Karnin, Lang, Liberty 2016, KLL (FOCS) | [paper] KLL optimal quantile streams, 2016-03.pdf | provably optimal quantile sketch |

Already archived, cited without re-download: Adaptive-RAG (replay outcome labels), Self-RAG and FLARE (self-supervised insufficiency proxies).

Unverified items deliberately excluded: no venue or number in this brief is stated from memory alone; classical CUSUM (Page 1954) is mentioned as lineage only and intentionally not cited as a source.

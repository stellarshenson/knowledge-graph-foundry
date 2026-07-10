**A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification, Angelopoulos, Bates, 2021 (arXiv 2107.07511)**

The canonical reference for split conformal prediction and its exact finite-sample guarantee. With **n** exchangeable calibration scores s_1..s_n and threshold q̂ = Quantile(s_1..s_n; ⌈(n+1)(1−α)⌉/n), the prediction set C(X_test) = {y : s(X_test,y) ≤ q̂} satisfies 1−α ≤ P(Y_test ∈ C(X_test)) ≤ 1−α + 1/(n+1) - a distribution-free, finite-n, both-sided coverage sandwich. The only assumption is exchangeability of calibration and test points; no model correctness, no distributional form.

**Key mechanism**
- Calibrate once on held-out scores: pick the ⌈(n+1)(1−α)⌉-th smallest score as the threshold - one sort, no fitting
- Guarantee granularity is 1/(n+1): with n = 24 calibration points the achievable miscoverage levels are multiples of 1/25 = **0.04**, so α = 0.04 or 0.08 are the natural small-n operating points
- Covariate-shift extension (Tibshirani et al.): re-weight calibration scores by likelihood ratios to restore exchangeability under known covariate shift
- Also covers conformalized quantile regression, class-conditional calibration, conformal outlier detection, and risk-control generalizations

**Main findings**
- Coverage is marginal (on average over draws), not conditional per-instance - the standard caveat
- Upper bound 1−α+1/(n+1) means small calibration sets are not just valid but nearly tight - n in the tens is workable, the cost is coarse α granularity, not invalidity
- Group-balanced or class-conditional variants require n per group, multiplying label needs

**Key takeaways**
- This is the distribution-free answer to "how do we set the H382 gate threshold from few labels": the threshold is an order statistic, the guarantee is exact at n = 24
- Exchangeability across corpus classes is exactly what H157 falsified for calibration constants - so calibration sets must be PER corpus class, and the guarantee is per class
- The quantile-of-scores view makes persistence natural: store scores (or a sketch), recompute the order statistic on update - no fitted curve to go stale

**Tags**: #ConformalPrediction #SplitConformal #DistributionFree #FiniteSample #CalibrationSet

**Source**: https://arxiv.org/abs/2107.07511. Local: [paper] Gentle Intro Conformal Prediction, 2021-07.pdf

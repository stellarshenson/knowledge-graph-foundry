**Conformal Risk Control, Angelopoulos, Bates, Fisch, Lei, Schuster, 2022 (arXiv 2208.02814, ICLR 2024)**

Generalizes split conformal from coverage to ANY monotone bounded loss - exactly the shape of a gate that trades escalation budget against miss risk. Given exchangeable loss functions L_i(λ) that are non-increasing in λ, right-continuous, and bounded by B, choose λ̂ = inf{λ : (n/(n+1)) R̂_n(λ) + B/(n+1) ≤ α} where R̂_n is the empirical risk on n calibration points. Theorem 1: E[L_{n+1}(λ̂)] ≤ α. Theorem 2: under i.i.d. continuous losses, E[L_{n+1}(λ̂)] ≥ α − 2B/(n+1) - tight up to O(1/n). On MS COCO multilabel FNR control with n = **4000** and α = 0.1, realized risk was **0.0996 ± 0.0052** over 1000 trials.

**Key mechanism**
- Replace "coverage" with any risk: false-negative rate, miss rate, graph-distance loss - anything monotone in the knob λ
- The B/(n+1) inflation term is the entire finite-sample correction: with binary loss (B = 1) and n = 24, the smallest controllable α is 1/25 = **0.04**
- Reduces exactly to split conformal when the loss is the miscoverage indicator
- Non-monotone losses break the guarantee (Section 2.4); monotonizing the loss restores it (Corollary 1)
- Extensions: distribution shift via weighting, quantile risk control, U-statistics, adversarial risk

**Main findings**
- Risk control holds at any n ≥ 1 provided α ≥ B/(n+1) is feasible - the method degrades into "always pick λ_max" rather than into invalidity when data is too scarce
- Demonstrated on vision (COCO, polyp segmentation) and NLP (FNR in open-domain QA retrieval) tasks

**Key takeaways**
- Direct fit for H382: let λ = escalation threshold, L_i(λ) = 1{probe i unanswered under the gated policy at threshold λ} - monotone if rung 2 never answers less than rung 0. CRC certifies E[miss] ≤ α from replay labels alone
- Concrete check at today's numbers: with n = 24 and 1 residual miss at θ ≈ 0.765, (24/25)(1/24) + 1/25 = 0.08 - the shipped operating point is exactly the CRC solution at α = 0.08
- The calibration state is the empirical risk curve R̂_n(λ) over candidate thresholds - a step function determined by the labeled outcome set, cheap to persist and to merge with new labels

**Tags**: #ConformalRiskControl #DistributionFree #MonotoneLoss #FiniteSample #ThresholdSelection

**Source**: https://arxiv.org/abs/2208.02814. Local: [paper] Conformal Risk Control, 2022-08.pdf

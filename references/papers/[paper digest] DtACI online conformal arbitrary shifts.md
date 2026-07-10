**Conformal Inference for Online Prediction with Arbitrary Distribution Shifts (DtACI), Gibbs, Candes, 2022-2023 (arXiv 2208.08401)**

The successor to ACI that removes its one tuning knob. DtACI runs **k** parallel copies of ACI with candidate step sizes γ_1 < ... < γ_k and selects among them online with an exponential re-weighting scheme (a modification of Gradu et al. 2020), so the procedure adapts to both the SIZE and the TYPE of distribution shift without knowing the rate of change in advance. Theorem 3.1 bounds the dynamic regret on the pinball loss against ANY comparator sequence over ANY local time interval; Theorem 3.2 bounds |1/T Σ E[err_t] − α| ≤ (1+2γ_max)/(Tγ_min) + O(η_t, σ_t) terms, and with decaying η_t, σ_t the empirical miss frequency converges to α exactly.

**Key mechanism**
- Expert pool = ACI instances with geometrically spaced step sizes (γ_{i+1}/γ_i ≤ 2 required by Theorem 3.1)
- Exponential weights with forgetting: recent performance dominates, so the pool re-selects quickly after abrupt changes - the stated fix for AgACI/MVP which "over-weight historical data"
- Output can be the weighted average of expert thresholds (Algorithm 2); Corollary 3.1 shows the same regret bound holds by Jensen
- Guarantees hold over every sliding window of a chosen width - locally adaptive validity, not just full-horizon averages

**Main findings**
- On stock volatility and COVID-19 case-count streams, DtACI tracks abrupt shifts that AgACI reacts to slowly, and matches the best fixed-γ ACI without knowing γ in advance
- Coverage errors on real data are close to an i.i.d. Bernoulli(α) sequence (Q-Q analysis) - near-ideal behavior
- With constant small η, σ a small persistent bias in long-run coverage can remain, empirically negligible

**Key takeaways**
- For KGF this is the production form of online threshold adaptation: no per-corpus step-size tuning, robust to unknown drift speed between ingestions
- State to persist per corpus class is tiny: k expert thresholds + k weights + the miss counter - fits a graph node property map
- Still asymptotic in the number of labeled outcomes - pair with a shipped prior threshold for cold start

**Tags**: #ConformalPrediction #OnlineCalibration #DistributionShift #ExpertAggregation #StepSizeFree

**Source**: https://arxiv.org/abs/2208.08401. Local: [paper] DtACI online conformal arbitrary shifts, 2022-08.pdf

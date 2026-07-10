**Adaptive Conformal Inference Under Distribution Shift, Gibbs, Candes, NeurIPS 2021 (arXiv 2106.00170)**

The founding paper of online conformal threshold adaptation. Instead of fixing the miscoverage level α of a conformal prediction set, ACI treats the WORKING level α_t as a state variable and runs online gradient descent on it: α_{t+1} = α_t + γ(α − err_t), where err_t = 1 if the target fell outside the set at time t. Proposition 4.1 guarantees, with probability **1** and for ALL T, that |1/T Σ err_t − α| ≤ (max{α_1, 1−α_1} + γ)/(Tγ) - long-run empirical coverage converges to the nominal 1−α under ANY data-generating process, including arbitrary distribution shift. Experiments used γ = **0.005**.

**Key mechanism**
- Working quantile level α_t is nudged after every observation: missed → α_t decreases (sets widen), covered → α_t increases (sets shrink)
- Lemma 4.1 bounds the state: α_t ∈ [−γ, 1+γ] almost surely, which is what makes the telescoping coverage bound work
- No distributional assumptions anywhere - the guarantee is deterministic-style, valid for every realization
- Sole tuning knob is the step size γ: larger γ adapts faster under bigger shifts but oscillates more; γ must match the (unknown) rate of drift

**Main findings**
- Fixed-threshold conformal loses coverage under shift; ACI restores the empirical coverage frequency exactly, at O(1/(Tγ)) rate
- When α_t < 0 the procedure emits infinite (always-escalate) sets - the price of coverage after a burst of misses
- Tested on stock-market volatility and election-night forecasting with real, nonstationary data

**Key takeaways**
- The KGF gate threshold need not be a constant: an ACI-style update on the escalation threshold gives a guaranteed long-run miss rate α without ANY assumption about corpus drift
- Guarantee is asymptotic in T - with tens of labeled probe outcomes per corpus the bound (max{α_1,1−α_1}+γ)/(Tγ) is loose (T=24, γ=0.05 → slack ~0.88), so ACI is the steady-state mechanism, not the cold-start one
- Step-size sensitivity is the known weakness - fixed by DtACI (successor, same authors)

**Tags**: #ConformalPrediction #OnlineCalibration #DistributionShift #AdaptiveThreshold #NeurIPS

**Source**: https://arxiv.org/abs/2106.00170. Local: [paper] Adaptive Conformal Inference, 2021-06.pdf

**Conformal PID Control for Time Series Prediction, Angelopoulos, Candes, Tibshirani, NeurIPS 2023 (arXiv 2307.16895)**

Reframes online conformal adaptation as feedback control and - crucially for KGF - moves the update from the abstract α-scale onto the THRESHOLD scale itself. Quantile tracking (P control) updates the threshold directly: q_{t+1} = q_t + η(err_t − α). Proposition 1: this alone achieves long-run coverage 1/T Σ err_t = α + o(1) for ANY score sequence bounded by an (unknown) constant b. Adding error integration (I control) yields Theorem 1: long-run coverage deterministically, with NO assumptions on the scores at all, for any scorecaster (D control) and any saturated integrator.

**Key mechanism**
- P term - online gradient descent on the pinball loss of the threshold: miss → raise threshold by η(1−α), hit → lower by ηα
- I term - running sum Σ(err_i − α) fed through a saturation function; forces the long-run error rate back to α even with adversarial scores
- D term (scorecaster) - any forecaster of the next score's quantile (theirs: Theta model, trend models); residualizes systematic drift for efficiency, never breaks validity
- Unlike ACI, quantile tracking does not emit infinite sets after a miss burst - the threshold moves by bounded increments on the score scale

**Main findings**
- On COVID-19 4-week-ahead death forecasting (CDC ensemble as base model) and electricity/stock datasets, PID variants hold coverage where fixed conformal drifts off, and the scorecaster shrinks sets under trend
- The guarantee is per-realization (deterministic), strictly more robust than stochastic coverage statements

**Main relevance to KGF is architectural**
- The H382 gate threshold (~0.765 cosine) can be the controlled variable itself: each miss/hit outcome from replay nudges it; no separate α-state or quantile recomputation
- The I-term is a built-in drift corrector: a corpus-class whose score distribution slides will be tracked without an explicit recalibration trigger
- Persisted state: current threshold, learning rate, integrator sum - three numbers per corpus class

**Key takeaways**
- Strongest "set it and let it breathe" candidate for steady-state operation; like ACI the guarantee is asymptotic, so cold start still needs a prior or a split-conformal fit
- Scorecaster slot is where a per-corpus prior model could inject structure without risking validity

**Tags**: #ConformalPrediction #ControlTheory #QuantileTracking #OnlineCalibration #TimeSeries

**Source**: https://arxiv.org/abs/2307.16895. Local: [paper] Conformal PID Control, 2023-07.pdf

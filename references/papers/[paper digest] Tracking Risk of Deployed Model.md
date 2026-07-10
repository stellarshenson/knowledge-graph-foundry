**Tracking the Risk of a Deployed Model and Detecting Harmful Distribution Shifts, Podkopaev, Ramdas, ICLR 2022 (arXiv 2110.06177)**

The recalibration-trigger paper: a sequential test that watches a deployed model's risk (accuracy, calibration, any bounded loss) and fires only on HARMFUL shifts, with a hard bound on false alarms over an infinite monitoring horizon. A level-δ sequential test satisfies P_H0(∃t ≥ 1 : test fires) ≤ δ - the probability the alarm EVER fires on a benign stream is at most δ, no matter how long monitoring runs. Built from time-uniform confidence sequences on source risk (lower bound) and running target risk (upper bound); alarm fires when the bounds separate by more than the chosen tolerance ε_tol.

**Key mechanism**
- Null hypothesis: target risk ≤ source risk + ε_tol; the tolerance is what distinguishes harmful from benign drift - small benign wobble never triggers retraining
- Time-uniform confidence sequences (Howard et al. style) remain valid under optional stopping and continuous monitoring; classical fixed-n tests do not - Appendix A shows non-sequential tests have "highly inflated false alarm rates" when re-run continuously
- Works with delayed or batched labels - matches replay-label harvesting cadence where outcomes arrive per ingestion, not per query
- Variance-adaptive bounds (empirical-Bernstein) tighten detection when losses have low variance → earlier detection of real shifts

**Main findings**
- On simulated and real vision datasets, the framework detects genuine risk increases quickly while never exceeding the false-alarm budget on benign shifts
- Conformal test martingales (detect ANY exchangeability break) flag benign shifts too - explicitly the wrong tool for deciding WHEN to recalibrate

**Key takeaways**
- This is the principled version of a CUSUM-style monitor for the KGF gate: track the gated policy's miss rate per corpus class; alarm → refit threshold; silence → keep shipped calibration
- The monitor state (running sums, counts, confidence-sequence radius) is small and mergeable across ingestions - persists naturally on the corpus-class node
- Sets the division of labor: conformal sets the threshold, this decides when the threshold's certificate has expired

**Tags**: #SequentialTesting #DriftDetection #ConfidenceSequences #RecalibrationTrigger #Monitoring

**Source**: https://arxiv.org/abs/2110.06177. Local: [paper] Tracking Risk of Deployed Model, 2021-10.pdf

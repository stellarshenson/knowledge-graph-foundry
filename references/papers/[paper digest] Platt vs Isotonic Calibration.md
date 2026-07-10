**Predicting Good Probabilities With Supervised Learning, Niculescu-Mizil, Caruana, ICML 2005**

The classic empirical answer to "Platt scaling or isotonic regression at small n". Across 8 classification problems and 10 learning methods, both calibrators were fit on independent calibration sets and compared on squared error as calibration-set size varied. The learning-curve verdict: when the calibration set is small - **less than about 200-1000 cases** - Platt scaling outperforms isotonic regression with ALL nine learning methods tested; isotonic wins only once data is plentiful, because its extra flexibility (any monotonic map, fit by PAV) turns into overfitting when points are scarce.

**Key mechanism**
- Platt scaling: fit a 2-parameter sigmoid P(y=1|s) = 1/(1+exp(As+B)) to calibration data; regularized with out-of-sample targets y+ = (N+ + 1)/(N+ + 2), y− = 1/(N− + 2) to avoid overfitting the extremes
- Isotonic regression: pool-adjacent-violators fit of any monotone step function - zero parametric assumptions, maximal variance at small n
- Both require a calibration set independent of model training, or the map degenerates (a perfectly separating model yields a 0/1 step)

**Main findings**
- Max-margin methods (boosted trees, SVMs) push scores away from 0/1 → sigmoid-shaped distortion, exactly Platt's home turf; Naive Bayes shows the opposite distortion where the sigmoid fits poorly
- After calibration, boosted trees, random forests and SVMs give the best probabilities; before calibration, random forests, neural nets and bagged trees
- Reliability diagrams with 10 bins used as the diagnostic

**Key takeaways**
- KGF's H157 failure (isotonic constants at ECE 0.2606 = 5.18x reference after corpus-class transfer) is the known small-n/shift pathology of isotonic maps - this paper is the standard citation for why
- At the H382 gate's n ≈ 24 labeled outcomes per corpus, isotonic refitting is contraindicated; a 2-3 parameter map (Platt, or beta calibration) is the evidence-backed choice if a probability curve is needed at all
- If only a THRESHOLD is needed, skip curve fitting entirely - conformal quantiles use the same tiny n with exact guarantees

**Tags**: #Calibration #PlattScaling #IsotonicRegression #SmallSample #ReliabilityDiagrams

**Source**: https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf. Local: [paper] Platt vs Isotonic Calibration, 2005-08.pdf

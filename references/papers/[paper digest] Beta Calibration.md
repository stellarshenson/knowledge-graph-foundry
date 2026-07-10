**Beta Calibration: a Well-Founded and Easily Implemented Improvement on Logistic Calibration for Binary Classifiers, Kull, Silva Filho, Flach, AISTATS 2017**

A **3**-parameter calibration family µ(s; a, b, c) derived from Beta score distributions, built for classifiers whose scores already live in [0, 1] - like a cosine-similarity gate signal. Logistic (Platt) calibration assumes per-class scores are Gaussian; when scores are heavily skewed (Naive Bayes, AdaBoost) logistic maps can make probabilities WORSE than the raw scores. Beta calibration's family contains the identity map (a = b = 1, c = 0), so it cannot uncalibrate an already-calibrated signal - the logistic family provably lacks the identity and can.

**Key mechanism**
- Model class-conditional score distributions as Beta rather than Gaussian → likelihood ratio LR(s; a,b,c) = e^{-c} s^a / (1−s)^b (parametrisation with K = e^{-c}); calibrated probability µ = 1/(1 + LR^{-1})
- Fitting is exactly logistic regression on the two features ln(s) and −ln(1−s) - as cheap and as stable as Platt at tiny n, one extra parameter
- Family includes sigmoids, inverse-sigmoids and the identity - covers both over-confident and under-confident distortions

**Main findings**
- Superior to logistic calibration for Naive Bayes and AdaBoost across extensive experiments; comparable elsewhere
- Logistic calibration applied to an already-calibrated classifier degrades it; beta calibration learns ~identity and leaves it intact
- Parametric form keeps variance low on small calibration sets, where isotonic overfits (consistent with Niculescu-Mizil & Caruana 2005)

**Key takeaways**
- If the H382 gate ever needs a miss-PROBABILITY curve (not just a threshold) from tens of labels, beta calibration is the right parametric family: the cosine signal is bounded in [0,1] and its distribution is skewed, the Gaussian-score assumption behind Platt does not hold
- Three scalars (a, b, c) + provenance persist trivially per corpus class; refitting on merged labeled outcomes is one small logistic regression
- Identity-containment matters for cross-corpus priors: initializing at the parent corpus-class curve and updating cannot be sabotaged by the family's own bias

**Tags**: #Calibration #BetaCalibration #ParametricCalibration #SmallSample #AISTATS

**Source**: http://proceedings.mlr.press/v54/kull17a/kull17a.pdf. Local: [paper] Beta Calibration, 2017-04.pdf

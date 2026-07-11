**Detecting Change Points in the Large-Scale Structure of Evolving Networks, Peel, Clauset, AAAI 2015 (arXiv 1403.0989)**

Model-based (Bayesian) change-point detection on network sequences: fit a **generalized hierarchical random graph (GHRG)** to a sliding window of w snapshots, then test "one set of parameters" vs "parameters changed at candidate time t" with a **posterior Bayes factor**; a change is declared when the factor clears a threshold calibrated for a target false-positive rate. Detects the three canonical structural change classes - community merge, split, and fragmentation/formation.

**Key mechanism**
- GHRG: dendrogram over nodes with per-internal-node connection probabilities (Bayesian priors on p to avoid degenerate MLE) - captures nested community structure at all scales
- Online detection: within window w, compare marginal likelihood of "no change" vs "change at t"; MCMC over dendrogram posterior
- Parametric bootstrap calibrates the detection threshold - the published answer to "what is this alarm's noise floor"

**Main findings**
- On synthetic merge/split/fragment scenarios, the network-model approach detects changes that scalar network statistics (mean degree, clustering, largest component) MISS entirely or detect late
- On MIT Reality Mining proximity and Enron email, detected change points align with semesters/holidays and with scandal-timeline events
- Key negative result for naive instrumentation: aggregate statistics are weak change detectors because distinct structural rearrangements leave means unchanged

**Key takeaways**
- The statistical-rigor pole of the design space: LAD is the cheap spectral heuristic, Peel-Clauset is the priced-hypothesis-test version - matches KGF's H351 noise-floor doctrine (bootstrap-calibrated alarm threshold, not magic tolerance)
- Their negative result predicts KGF's own R09 finding (type-JSD blind to structure) and warns that single scalar series (density, mean degree) may sit flat across the REG-1 boundary while the real rearrangement hides in community structure
- Window-based posterior test composes with per-document snapshots reconstructed from created_at

**Tags**: #ChangePointDetection #BayesFactor #HierarchicalRandomGraph #EvolvingNetworks #NoiseFloor

**Source**: https://arxiv.org/abs/1403.0989. Local: [paper] Detecting Change Points in Evolving Networks, 2014-03.pdf

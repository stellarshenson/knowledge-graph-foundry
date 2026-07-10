**A Tutorial on Thompson Sampling, Russo, Van Roy, Kazerouni, Osband, Wen, Foundations and Trends in ML Vol 11 No 1 (2018), pp 1-96 (arXiv 1707.02038)**

The standard reference for posterior-sampling bandits - the mechanism for ONLINE threshold tuning when labels are harvestable but exploration has a cost. Maintain a Bayesian posterior over each action's reward; each round, SAMPLE one hypothesis from the posterior and act greedily against the sample. This "probability matching" explores exactly in proportion to the probability an action is optimal: near-certainly-bad arms get written off, genuinely uncertain arms get tried - the failure mode of epsilon-greedy (wasting exploration on known-bad arms) is avoided by construction.

**Key mechanism**
- Beta-Bernoulli bandit: arm k has Beta(α_k, β_k) posterior over success probability; observe success → α_k += 1, failure → β_k += 1 - conjugate one-line updates
- Works with any posterior (Gaussian, hierarchical); information percolates across correlated actions - trying threshold 0.75 informs beliefs about 0.76
- Prior choice is the a-priori belief slot: informative priors from previous corpora reduce early exploration
- No hard safety guarantee out of the box - exploratory rounds can pick bad thresholds; safe/conservative variants constrain the sampled action near an incumbent

**Main findings**
- Broad applicability demonstrated: shortest paths, product recommendation, active learning, MDPs
- Effective when exploration is cheap relative to information gained; the tutorial explicitly discusses when TS is NOT the right tool (e.g., when exploration is dangerous or feedback is delayed)

**Key takeaways**
- For H382, TS over a small grid of candidate thresholds (or over the Beta posterior of miss-rate per threshold bucket) is the label-scarce ACTIVE option: it decides which threshold to run next ingestion to learn fastest
- Weakest guarantee of the surveyed mechanisms - regret bounds, not risk control; a probe miss during exploration is a real recall loss, so any KGF use needs a conservative clamp (never explore below the conformal certificate)
- The conjugate-counts state (α_k, β_k per bucket per corpus class) is the cheapest possible calibration persistence and merges across ingestions by addition

**Tags**: #ThompsonSampling #Bandits #BayesianUpdating #Exploration #OnlineTuning

**Source**: https://arxiv.org/abs/1707.02038. Local: [paper] Thompson Sampling Tutorial, 2017-07.pdf

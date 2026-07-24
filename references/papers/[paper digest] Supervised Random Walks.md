**Supervised Random Walks: Predicting and Recommending Links in Social Networks, Backstrom, Leskovec (Facebook, Stanford), WSDM 2011 (arXiv Nov 2010)**

The canonical method for learning edge strengths so a random walk visits the right nodes - the exact shape of "learn amplification weights from outcomes." Given a source node and a set of positive destination nodes (links that actually formed) versus negatives, the method learns a parametric edge-strength function `a_uv = f_w(psi_uv)` over node/edge features, runs Personalized PageRank with those strengths, and optimizes `w` so PPR scores of positives rank above negatives. Trained end-to-end by differentiating the stationary distribution of the walk w.r.t. the edge parameters. On the Facebook graph and co-authorship networks it beats unsupervised PPR/Adamic-Adar and flat feature-extraction classifiers.

**Key mechanism**
- Edge strength is a learned function of features, not a label or hand-set weight; the walk itself is the model
- Loss: a margin/ranking objective (positives outrank negatives in PPR score) with L2 regularization; solved by gradient descent through the power-iteration fixed point
- Supervision is per-source: each training query contributes its own positive/negative destination sets - a small number of sources can supply many labeled ranking pairs
- Purely structural + attribute features (degree, edge age, common neighbours); no text needed

**Main findings**
- Outperforms unsupervised PPR and feature-based logistic classifiers on link prediction (Facebook, arXiv, biology co-authorship)
- Learning edge weights end-to-end beats both fixed-weight PPR and post-hoc feature combination - the walk-integrated gradient is what wins
- Robust with modest label counts because each source multiplies into many pairwise constraints

**Relevance to KGF**
- The blueprint for family-1 "learned reset/edge weights from traversal outcomes": our succeeding-probe evidence is exactly the positive-destination supervision this method consumes; a learned edge-strength `f_w` over empirical features is the disciplined answer to R50's KILL (weights must be empirical, never label-driven) - SRW weights are outcome-derived, not vocabulary/type labels
- Directly tests the transfer question at our scale: ~130 labeled probes x several carriers each = the many-pairs-per-source regime SRW was designed for, but 6.6k nodes and tiny label count is far below the paper's graphs - overfitting/identifiability is the live risk to price
- LEAKAGE FENCE applies hard: SRW learns from positives, so train edge-weights on a split disjoint from the frozen-132 evaluation; the frozen set cannot both teach and judge
- Must beat the FREE incumbents (H627 one-step smoothing +9.5pt; anchor-reset 0.8661/131; max-gap 0.8740) before its GPU-trivial training cost is justified

**Tags**: #SupervisedRandomWalks #LearnedPPR #EdgeWeightLearning #LinkPrediction #AmplificationFamily1

**Source**: https://arxiv.org/abs/1011.4071. Local: [paper] Supervised Random Walks, 2011.pdf

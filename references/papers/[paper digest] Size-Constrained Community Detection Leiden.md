# Heuristic and Exact Modularity Optimization with Size-Constrained Communities

**Authors**: Filipi N. Silva, Samin Aref, Vincent Traag, Santo Fortunato

**arXiv link (source for re-download)**: https://arxiv.org/abs/2605.25248

**Publication date**: 2026-05-24 (first arXiv version)

## Summary

- **1015 nodes**: unconstrained Leiden (UL) on the Budapest brain connectome collapses to a trivial 4-community partition (front/back split of the two hemispheres); adding a size range of **[43, 187]** nodes per community (derived from averaging the Brainnetome and Schaefer parcellation atlases) yields **6 communities**, aligning with the 7 functionally coupled clusters reported by Yeo et al.; an arbitrary range of [50, 100] instead yields 10 communities, showing the range choice itself matters
- **Ring of cliques** (50 cliques of 5 nodes, consecutive cliques joined by one edge): UL only recovers the planted clique partition when the resolution parameter is hand-tuned into the narrow window **[5, 40]**; Constrained Leiden (CL) recovers it at the default resolution of 1.0 by supplying the known size range [2, 8] directly - no resolution search needed
- Across **12 synthetic planted-partition settings** (network sizes n = 64/128/192/256, average degrees k = 5/8/10), CL and the exact Constrained Integer Programming baseline (CIP) track each other closely in Adjusted Mutual Information (AMI) recovery, while UL's recovery rate is consistently and sometimes substantially lower for mixing parameter mu <= 0.4, despite UL frequently achieving *higher* raw modularity - constraint satisfaction, not modularity value, is what predicts correct partition recovery
- The resolution parameter controls only the mean community size, not its spread: on the Budapest network at resolution gamma = 0.4, the interquartile range of community sizes still spans roughly 200 to 500 nodes, and the spread grows further at higher gamma - size range cannot be reliably obtained by resolution tuning alone
- Mechanism: converts the constrained problem into an unconstrained one via a penalty method rather than a barrier/interior-point method (the latter forbids the temporary constraint violations heuristics need to escape local optima); penalty weight phi starts at 10^-4 and doubles each time the resulting partition violates the size bounds, warm-starting each re-optimization from the prior partition, until the first feasible phi is found; the per-community penalty theta(n_c) = sqrt(n_min - n_c) for undersized and sqrt(n_c - n_max) for oversized communities is deliberately sub-additive (proven via a counterexample on an edgeless graph) so that heuristics are not pushed toward artificially equal-sized communities
- Implementation is public in the Python `leidenalg` package (C++ core in `libleidenalg`); the exact CIP baseline formulates the size-constrained maximum-modularity k-partition (SMMk) as an integer program solved with Gurobi
- Authors note the same penalty-method approach generalizes to other quality functions, explicitly naming the Constant Potts Model (CPM)

**Relevance to Knowledge Graph Foundry**: KGF's Leiden communities (NMI 0.614 with source docs) are provenance artifacts whose size distribution is currently an unconstrained side effect of the resolution parameter; this paper's finding that resolution tuning controls mean size but not variance, plus its size-constrained penalty method, is a direct lever for R48's community segmentation/balancing work - a size range grounded in KGF's chunk/context-window economics (rather than an ad-hoc resolution sweep) could yield communities better matched to the H382 context-escalation gate's token budget.

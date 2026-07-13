# Graph Cuts with Arbitrary Size Constraints Through Optimal Transport

**Authors**: Chakib Fettal, Lazhar Labiod, Mohamed Nadif

**arXiv link (source for re-download)**: https://arxiv.org/abs/2402.04732

**Publication date**: 2024-02 (arXiv v1, per id); accepted to Transactions on Machine Learning Research 2024-09; arXiv v2 2024-10-04

## Summary

- Reformulates the min-cut/normalized-cut/ratio-cut family as a Gromov-Wasserstein optimal-transport problem with a concave regularizer (OT-cut), letting cluster "size" be an arbitrary target distribution instead of only volume (ncut) or cardinality (rcut)
- Solves the resulting nonconvex problem with an accelerated proximal gradient descent (nonconvex PGD) that provably converges globally to a critical point and produces sparse, extreme-point transport plans (at most **n + k - 1** nonzero entries)
- Per-iteration complexity is **O(kn^2 log n)**, an **O(log n)** overhead versus classical spectral clustering, but the paper reports it runs faster in wall-clock time in practice
- On graph benchmarks (ACM, DBLP, Village, EU-Email), OT-rcut/OT-ncut wins ARI on 3 of 4 datasets (Infomap wins EU-Email at 0.3087 ARI); on image-derived graphs (MNIST/Fashion-MNIST/KMNIST via LRSC/LSR/ENSC), one of the two OT variants gives the best ARI in 7 of 9 graph/dataset combinations, e.g. MNIST-LRSC OT-ncut ARI **0.4751 vs Spectral 0.4134**
- OT-rcut achieves **KL divergence of 0.0 on every tested dataset** between desired and resulting cluster-size distributions (integral transport-plan entries make exact size recovery structural); OT-ncut is near-zero (max observed **0.0011** on Village)
- OT-ncut/OT-rcut are the fastest methods on every reported dataset (Tables 2-3), e.g. **5.47-6.61s** vs Spectral's **8.82-13.6s** and SpecGWL's **268-454s** on the image graphs
- On long-tailed CIFAR-10 (imbalance ratios 5/10/50/100), feeding the true cluster-size distribution as the target beats standard spectral clustering at every imbalance level, e.g. balance-5: OT-ncut **0.0831** vs Spectral **0.0566** ARI
- A Neményi post-hoc rank test at 95% confidence shows OT-rcut and OT-ncut significantly outperform Spectral, S-GWL, and SpecGWL as a pair, with no significant difference between the two OT variants

**Key mechanism**
- Graph cut as trace minimization `Tr(X^T L X)` constrained to the OT transportation polytope `Π(π_s, π_t)` (source = per-node size, target = desired per-cluster size distribution) instead of the usual `X^T X = I` / `X ∈ {0,1}^{n×k}` relaxations
- Concave `-λ‖X‖^2` regularizer pushes the OT solution toward the polytope's extreme points, which are exactly sparse hard-partition-like matrices - avoiding a separate discretization/k-means step that spectral clustering needs
- Each PGD step reduces to a classical OT problem solved via the network-simplex/earth-mover's-distance LP, reusing the mature POT (Python Optimal Transport) library

**Relevance to Knowledge Graph Foundry**: KGF's Leiden communities are acknowledged provenance artifacts (NMI 0.614 with source docs) whose size distribution is unconstrained and uneven; OT-cut's arbitrary-size-constrained graph partitioning is a candidate mechanism for R48's community segmentation/balancing lever - it lets community size be set as a target distribution (uniform, degree-weighted, or corpus-informed) rather than accepted as whatever Leiden's modularity objective happens to produce, and its sparse solutions map directly onto hard community assignment without a discretization pass.

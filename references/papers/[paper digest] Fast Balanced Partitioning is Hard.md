# Fast Balanced Partitioning is Hard, Even on Grids and Trees

**Authors**: Andreas Emil Feldmann

**arXiv link (source for re-download)**: https://arxiv.org/abs/1111.6745

**Publication date**: 2011-11-29 (first arXiv version; a preliminary version appeared at MFCS 2012)

## Summary

- Proves that for solid grid graphs, no polynomial-time algorithm can approximate the k-BALANCED PARTITIONING cut size within n^c for any constant c < 1/2, unless P=NP (Theorem 6) - even though the corresponding graph class is planar and bounded-degree
- For the bicriteria (near-balanced) relaxation, where each set may have size up to (1+ε)⌈n/k⌉, shows no fully polynomial time algorithm exists on solid grid graphs achieving α = n^c/ε^d for any constants c < 1/2, d (Theorem 5) - these are stated as the first bicriteria inapproximability results for the problem
- The same bicriteria hardness holds for trees, but with a weaker exponent bound c < 1 (Theorem 7), driven by unbounded vertex degree (stars) rather than grid isoperimetry
- Both hardness bounds are shown asymptotically tight: an O(√n) approximation exists for grids (via cutting out ⌈n/k⌉ vertices per set using O(k√n) edges, since a bounded-degree planar graph admits O(√(Δn))-edge vertex cuts), and a trivial α = n approximation (cut every edge) is tight for trees
- The reduction is a single general framework (from 3-PARTITION) that only needs a graph class to admit a "reduction set" of gadget graphs where cutting off vertices is provably edge-expensive - grids pay via isoperimetric (boundary-to-area) properties, trees via high-degree star gadgets, letting one proof technique cover two combinatorially dissimilar graph classes
- Frames the practical motivation as 2D finite-element-mesh partitioning for parallel computation, where cut size is inter-processor communication and set-size balance is machine load; existing fast heuristics (Metis, Scotch) give no cut-size guarantee, and the only guaranteed near-balanced algorithm known at the time has running time that grows exponentially as \\(\varepsilon \to 0\\)

**Relevance to Knowledge Graph Foundry**: KGF's R48 round treats Leiden community segmentation as a context-assembly lever (balancing community size against provenance fidelity, NMI 0.614 with source docs); this paper is a hardness result rather than an algorithm, and its takeaway for R48 is a ceiling on ambition - no fast method can guarantee both near-equal community sizes and a tightly-bounded cut (inter-community edge loss) simultaneously, so any balancing heuristic applied to Leiden output should be evaluated empirically against retrieval metrics (dense@16, H382 escalation gate) rather than pursued as a provably-optimal partition.

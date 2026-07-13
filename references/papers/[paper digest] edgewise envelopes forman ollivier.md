**Edgewise Envelopes Between Balanced Forman and Ollivier-Ricci Curvature (2026)**

Ollivier-Ricci (OR) curvature needs an optimal-transport solve per edge - prohibitive at scale. This paper derives explicit two-sided piecewise-affine transfer moduli bounding OR curvature by the cheap combinatorial Balanced Forman (BF) curvature of Topping et al., cutting edgewise evaluation from an OT linear program to worst-case O(max_v deg(v)^1.5) time with no global solver.

**Key mechanism**
- Constructs a lazy transport envelope plus a cross-edge matching statistic augmenting the Jost-Liu bound
- Yields deterministic two-sided bounds on OR curvature parameterized by 2-hop local combinatorics
- Complexity drops from OT-per-edge to O(max degree^1.5), eliminating global transport solvers

**Main findings**
- Analytical bands enclose the empirical OR curvature distribution on random and real-world networks
- Bound tightness holds independent of degree heterogeneity, geometry, or clustering

**Key takeaways**
- Gives a formal transfer from cheap BF/Forman curvature to Ollivier-grade signal, with a quantified degree-dependent cost
- Quantifies exactly how much cheaper the Forman half of an Ollivier-equivalent signal is - the O(deg^1.5) term is the price of closing the gap
- Relevance to KGF: bounds the error of using Forman curvature as an Ollivier-Ricci proxy on the graph, giving a principled fallback if a tighter signal is ever needed without paying full OT cost

**Tags**
- #GraphCurvature #OllivierRicci #FormanRicci #ComputationalComplexity

**Source**
- Download: https://arxiv.org/pdf/2603.13535
- Local: [paper] edgewise envelopes forman ollivier, 2026.pdf

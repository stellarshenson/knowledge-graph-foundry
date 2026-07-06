**Understanding Oversquashing in GNNs through the Lens of Effective Resistance (2023)**

This paper gives over-squashing a rigorous, globally computable measure. It bounds the Jacobian sensitivity of one node's embedding to another node's input by their effective resistance, defines total effective resistance (the Kirchhoff index) as a graph-level over-squashing quantity, and proposes adding edges that maximally reduce it. Resistance-reduction rewiring is competitive with or beats SDRF from a single principled global objective.

**Key mechanism**
- Bounds Jacobian sensitivity between two nodes by their effective resistance
- Defines total effective resistance (Kirchhoff index) as the graph-level over-squashing quantity
- Rewiring adds edges that maximally reduce total effective resistance

**Main findings**
- Resistance-reduction rewiring improves GNN accuracy on long-range/heterophilic benchmarks
- Competitive with or beating SDRF from a single principled global objective

**Key takeaways**
- Effective resistance is a one-shot global measure, computed from the Laplacian pseudoinverse
- The measure doubles as an audit signal, not just a rewiring target
- Trivial to compute at a few-thousand-node scale

**Relevance**
- Effective resistance between candidate-duplicate nodes measures path redundancy, computed in one shot from the Laplacian pseudoinverse (scipy, trivial at 2,800 nodes)
- We invert the prescription - audit existing SAME_AS edges by residual resistance: genuine co-reference leaves low resistance when the edge is removed (shared neighbors reconnect), a spurious transitive-closure bridge leaves high resistance - catching exactly the false-SAME_AS defect

**Tags**
- #EffectiveResistance #OverSquashing #GNN #GraphAudit

**Source**
- Download: https://arxiv.org/pdf/2302.06835
- Local: [paper] effective resistance over-squashing, 2023.pdf

**Simplicial Hopfield Networks, Burns, Fukai (OIST), ICLR 2023 (arXiv 2305.05179)**

The paper on **which** associative connections to keep. Inspired by setwise connectivity in biology, Hopfield networks are extended with setwise connections embedded in a simplicial complex - higher-dimensional analogues of graphs that represent pairwise and setwise relations together.

**Key mechanism**
- Replace the complete pairwise graph over N neurons with a simplicial complex containing simplices of order > 2 (setwise connections)
- Weights are assigned over simplices rather than edges, so a single connection can encode a relation among a whole set of items

**Main findings**
- Simplicial Hopfield networks **increase memory storage capacity** over pairwise networks
- **Even when connections are limited to a small random subset of equivalent size to the all-pairwise network, the simplicial networks still outperform their pairwise counterparts** - the gain comes from connection structure, not connection count
- The scenarios where this holds involve non-trivial simplicial topology; analogous modern continuous versions are tested as a route to improving attention

**Key takeaways**
- Direct evidence that **a sparse, well-chosen set of associative connections beats a dense pairwise set of the same budget** - the materialisation-budget question has a published answer favouring selectivity
- Setwise connections are the natural representation for "these k entities were co-present in this chunk", which a pairwise co-occurrence expansion destroys by decomposing into edges
- Establishes that going from pairwise co-occurrence edges to setwise hyperedges is a capacity gain, not just a modelling nicety

**Tags**: #SimplicialHopfield #SetwiseConnections #SparseConnectivity #Capacity #R59

**Source**: https://arxiv.org/abs/2305.05179. Local: [paper] Simplicial Hopfield Networks, 2023.pdf

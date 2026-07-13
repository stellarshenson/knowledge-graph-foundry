**Equivariant Subgraph Aggregation Networks (ESAN, 2022, ICLR Spotlight)**

ESAN is the canonical escape route from the 1-WL expressiveness bound. Its premise: two graphs an MPNN cannot tell apart often contain distinguishable SUBGRAPHS. So it represents each graph as a BAG of subgraphs (produced by a fixed policy) and processes the bag with an equivariant architecture that shares information across subgraphs, provably exceeding 1-WL via new **DSS-WL** and **DS-WL** test variants.

**Key mechanism**
- Subgraph selection policy generates a bag: node-deleted, edge-deleted, or ego-network (k-hop egonets) subgraphs
- DSS (Deep Sets for Symmetric elements) layers process the bag equivariantly - each subgraph is encoded and cross-subgraph information is aggregated
- Expressiveness bounded below by DSS-WL / DS-WL, strictly above plain 1-WL

**Main findings**
- Distinguishes graph pairs MPNNs provably cannot
- Boosts the expressive power and accuracy of popular base GNNs on real and synthetic data (abstract reports no single headline number)
- Ego-network policy is a cheap, widely adopted default

**Key takeaways**
- The standard, least-exotic recipe for a GNN that can see multi-node patterns - trade K-fold forward passes (K subgraphs) for expressiveness
- Egonet-bag is conceptually close to running a GNN per seed neighborhood - a structure KGF already materializes for PPR

**Relevance**
- If KGF ever builds a GNN that must detect bridge/comparison SHAPE (which vanilla GNN cannot, per the substructure-counting theorem), ESAN's egonet-bag is the default architecture
- Cost realism: K x forward passes over 6,626 entities is affordable offline, but the binding constraint is training data (n~132), not compute
- The egonet bag overlaps KGF's existing seed-neighborhood materialization, so the incremental structural cost is modest - the modelling/labeling cost is not

**Tags**
- #SubgraphGNN #Expressiveness #ESAN #EgoNetworks

**Source**
- Download: https://arxiv.org/pdf/2110.02910
- Local: [paper] ESAN Subgraph Aggregation Networks, 2022.pdf

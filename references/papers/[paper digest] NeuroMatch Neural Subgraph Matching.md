**Neural Subgraph Matching (NeuroMatch, 2020)**

NeuroMatch predicts subgraph containment (is query graph Q a subgraph of target graph T?) without combinatorial search. It decomposes both graphs into small overlapping node-anchored neighborhoods, GNN-embeds each, and places them in an ORDER-EMBEDDING space where the subgraph relation becomes a coordinate-wise partial order. It runs **100x faster** than combinatorial matchers and is **18% more accurate** than prior approximate subgraph-matching methods.

**Key mechanism**
- Decompose query + target into small overlapping k-hop neighborhoods anchored at each node
- GNN embeds each neighborhood; an order-embedding geometry enforces emb(A) <= emb(B) coordinate-wise iff A is a subgraph of B
- Max-margin loss trains the order constraint; containment test at inference is a cheap vector comparison, not a search

**Main findings**
- Order embeddings respect the algebraic structure of the subgraph relation (transitivity, closure under intersection)
- 100x speedup over exact combinatorial matching, +18% accuracy over approximate baselines
- Converts an NP-complete decision (subgraph isomorphism) into a partial-order test in vector space

**Key takeaways**
- The order-embedding trick is the transferable idea: "does the data graph contain this typed shape?" answered by a coordinate comparison
- Node-anchored, so it needs a candidate anchor set (dense seeds could supply this)
- Supervised on subgraph / non-subgraph pairs

**Relevance**
- Directly the primitive H595 (typed-path certified structural-negative) and H583 (topology oracle) reach for - a cheap "the graph cannot hold this answer shape" test
- On KGF's noisy self-extracted graph the subgraph relation itself is fuzzy (H107 extraction variance), so the clean order geometry may not hold; a zero-training variant would impose the order test on frozen Titan/local embeddings, untested
- Anchoring on dense@16 seeds sidesteps the NP-complete enumeration H594 flags

**Tags**
- #SubgraphMatching #OrderEmbedding #GNN #StructuralRetrieval

**Source**
- Download: https://arxiv.org/pdf/2007.03092
- Local: [paper] NeuroMatch Neural Subgraph Matching, 2020.pdf

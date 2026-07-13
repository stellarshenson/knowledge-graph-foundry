**Graph Matching Networks for Learning the Similarity of Graph Structured Objects (2019)**

GMN is the canonical learned graph-to-graph similarity model. It offers two designs: a Graph Embedding Network that embeds each graph independently then compares vectors, and the Graph Matching Network proper, which computes a similarity score for a PAIR of graphs by jointly reasoning over both through a **cross-graph attention** matching mechanism. On control-flow-graph binary-function similarity search (vulnerability detection) the matching model beats the embedding model and hand-engineered domain baselines.

**Key mechanism**
- Graph Embedding Network: independent GNN embedding per graph + learned vector metric - indexable, cacheable
- Graph Matching Network: at every propagation layer, each node in graph A attends over all nodes in graph B (cross-graph attention), so the two graphs' representations are computed jointly, not independently
- Cross-graph attention is where the accuracy comes from - it aligns substructures across the pair

**Main findings**
- Cross-graph matching outperforms independent embedding + hand-engineered systems on function-similarity search
- The matching model is inherently PAIRWISE: cost is O(|A| x |B|) per pair and cannot be precomputed to a single-graph index
- The embedding model is cacheable but strictly weaker

**Key takeaways**
- Cross-graph attention is the mechanism for "align a query graph onto a data graph" - exactly the Step-1 topology match in a two-step meta-matcher
- The accuracy lever (joint cross-graph reasoning) is fundamentally uncacheable - it re-runs per query-region pair
- Supervised: needs many labeled similar/dissimilar graph pairs

**Relevance**
- This IS the learned form of R50's "map the query's speculative topology onto the graph topology" - but the strong variant is quadratic and query-time, incompatible with KGF's fuse-never-seed, precompute-at-ingest doctrine
- The indexable embedding variant is what KGF could afford, and it is the weaker one - a structural argument for staying with PPR
- Training regime (thousands of graph pairs) dwarfs KGF's ~132 probe-flip labels

**Tags**
- #GraphMatching #CrossGraphAttention #GNN #SimilarityLearning

**Source**
- Download: https://arxiv.org/pdf/1904.12787
- Local: [paper] Graph Matching Networks, 2019.pdf

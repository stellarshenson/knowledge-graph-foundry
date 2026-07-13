**PathSim: Meta Path-Based Top-K Similarity Search in Heterogeneous Information Networks (2011)**

The paper introduces meta paths - typed sequences of relations over a heterogeneous graph's schema (e.g. venue-paper-author-paper-venue) - as the unit that gives similarity search a semantics-aware handle in networks with multiple node and edge types, and defines PathSim, a symmetric similarity measure over any given meta path. On a labeled DBIS benchmark PathSim scores **0.7446 nDCG@15**, beating random walk (0.7061), SimRank (0.6289), P-PageRank (0.5552) and pairwise random walk (0.5284); on a 4-area clustering benchmark it reaches the best **weighted-average NMI of 0.6507** across venue and author node types. A partial-materialization-plus-online-concatenation query engine (PathSim-pruning) then makes top-k search over these measures tractable at DBLP scale.

**Key mechanism**
- A meta path P = A1 -R1-> A2 -R2-> ... -Rl-> Al+1 defines a composite typed relation between two node types; concrete paths in the graph that follow this typed sequence are its "path instances"
- PathSim(x,y) = 2·M(x,y) / (M(x,x) + M(y,y)), where M is the commuting matrix (product of type-to-type adjacency matrices) for a symmetric round-trip meta path - the numerator counts connecting paths, the denominator normalizes by each node's own "visibility" (self-path count), so the measure favors comparably-visible peers over merely high-degree hubs
- Proven properties: symmetric, self-maximum (s(x,x)=1), and bounded by the ratio of the two nodes' visibilities - large visibility mismatch caps the achievable similarity
- Query engine avoids full O(n²) materialization: it partially materializes the commuting matrix for a short partial meta path, then concatenates it online per query; PathSim-pruning adds co-clustering of the partial matrix (KL-divergence-based block assignment) to compute cheap similarity upper bounds per target cluster/candidate, pruning most of the search space before the exact dot product is ever computed

**Main findings**
- Case study and nDCG@15 (Table 4/5, DBIS "PKDD" query): PathSim uniquely returns topically-and-reputation-matched peers (ICDM, SDM, PAKDD) where P-PageRank returns merely high-visibility venues and SimRank returns obscure, over-concentrated ones; PathSim nDCG 0.7446 is the best of the five measures compared
- Clustering (4-area dataset, Normalized Cut + NMI): PathSim wins weighted-average NMI (0.6507) though pairwise random walk edges it out on the venue-only NMI (0.8198 vs 0.8116)
- Meta path length matters and saturates fast: clustering accuracy for CAC degrades from 0.8116 (length-2 base pattern) to 0.4603 at (CAC)² and 0.4531 at (CAC)³; as path length grows to infinity, PathSim provably collapses into a global-ranking-based similarity (a function only of the network's principal eigenvector), which the paper shows empirically loses topical relevance (Table 8c returns AAAI, ESA, IEEE Trans. Commun. as "similar" to SIGMOD)
- Different meta paths over the same node pair encode genuinely different semantics: co-author path (APA) surfaces close collaborators for a given author, while shared-venue path (APCPA) surfaces topical peers publishing in the same venues - the same two nodes, two different "similar" sets
- PathSim-pruning beats the vector-matrix baseline consistently; improvement rate is density-dependent, ranging 18.23%-68.04% across the two meta paths tested, and grows with the number of neighbors a query node has

**Key takeaways**
- A similarity measure defined per typed path (not per single edge label) is the mechanism that lets a heterogeneous graph express multiple, mutually incompatible notions of "similar" for the same pair of typed nodes
- The visibility-balance normalization is what keeps a topology-based similarity from degenerating into a popularity ranking - directly relevant wherever hub nodes would otherwise dominate a raw path-count or random-walk score
- Short meta paths are not just cheaper but qualitatively better - the paper demonstrates that longer paths dilute rather than deepen the similarity signal

**Relevance**
- PathSim's visibility-normalized, per-meta-path similarity is the deterministic, non-learned sibling of PCRW/PRA (also in this batch) - a candidate scoring primitive for KGF's typed/topology matching where a fixed, symmetric, hub-resistant score is preferable to a trained one
- The finding that similarity collapses with meta-path length is a direct caution for any KGF traversal-based matching score: deep multi-hop paths should be expected to dilute rather than strengthen a match signal, reinforcing a shallow-traversal design bias
- The co-clustering pruning scheme (compress query and candidates into cluster-level upper bounds before exact scoring) is a reusable pattern for bounding the cost of any typed pairwise-similarity search over a large candidate set

**Tags**
- #MetaPath
- #HeterogeneousInformationNetworks
- #SimilaritySearch
- #TypedGraph
- #TopologyRetrieval

**Source**
- Download: http://www.vldb.org/pvldb/vol4/p992-sun.pdf
- Local: [paper] PathSim Meta Path Similarity HIN, 2011.pdf

**DELTACON: A Principled Massive-Graph Similarity Function, Koutra, Vogelstein, Faloutsos, SDM 2013 (arXiv 1304.4657)**

The standard instrument for "how different are two snapshots of the same graph": a similarity score in [0,1] over graphs with aligned node sets, computed in **O(|E|) linear time**, satisfying formal axioms that Graph-Edit-Distance and vector-of-metrics approaches fail - specifically edge importance (changes that disconnect components count more), weight awareness, and "edge submodularity" (the same edge change matters more in a sparse graph).

**Key mechanism**
- Node affinity matrix S = [I + eps^2 D − eps A]^{-1} via Fast Belief Propagation - identical in spirit to personalized RWR; captures multi-hop influence, not just adjacency
- Similarity = 1 / (1 + Matusita root-Euclidean distance between the two affinity matrices); sqrt-transform boosts sensitivity to small affinity shifts
- DELTACON_0 exact O(n^2); DELTACON approximates with g random node groups → O(g|E|) - tunable precision/cost
- Node/edge attribution extension (DeltaCon-Attr) ranks WHICH nodes and edges drive the difference - a built-in forensic localizer

**Main findings**
- Vector-of-summary-statistics similarity (degree dist, clustering, etc.) misses connectivity-critical changes that DELTACON catches - a bridge-edge removal barely moves summary stats but collapses affinities
- Detects anomalous instants in real temporal graphs (ENRON email) as similarity drops between consecutive days
- Scales to billions of edges (Twitter/YahooWeb tested)

**Key takeaways**
- For the REG-1 forensics: DELTACON(G_t, G_{t+1}) per document is the principled per-step structural change series; a spike near doc 135-154 localizes the shift; DeltaCon-Attr then names the culpable nodes/edges
- At 1.4k nodes / 3.4k edges the exact O(n^2) variant costs milliseconds - no approximation needed at KGF scale
- Edge-submodularity axiom matters at KGF sparsity (median degree 1): single-edge changes are LARGE events in sparse graphs, and DELTACON prices that correctly where raw edit counts do not

**Tags**: #GraphSimilarity #DeltaCon #ChangeDetection #BeliefPropagation #Attribution

**Source**: https://arxiv.org/abs/1304.4657. Local: [paper] DeltaCon Graph Similarity, 2013-04.pdf

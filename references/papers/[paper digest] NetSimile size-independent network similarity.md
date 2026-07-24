**NetSimile: A Scalable Approach to Size-Independent Network Similarity (2012)**

The origin paper for the "cheap local structural features aggregated into a graph signature" family. Given k networks with **no node correspondence and different sizes**, NetSimile extracts a small numeric signature per graph from seven per-node egonet features, aggregates them with five moments, and compares graphs by Canberra distance. Linear in the number of edges. It is a **whole-graph** similarity method - the node features are a means to a graph-level end, not a retrieval key.

**Key mechanism**
- Seven per-node features, all computable from the node's egonet: degree; clustering coefficient; average degree of neighbours; average clustering coefficient of neighbours; number of edges in the egonet; number of edges leaving the egonet; number of neighbours of the egonet
- Aggregation: each feature's distribution over all nodes is summarised by five moments (median, mean, standard deviation, skewness, kurtosis), giving a fixed **35-dimensional** signature independent of |V|
- Comparison by Canberra distance between signatures; no node-correspondence problem is ever solved
- Size invariance comes from the moment aggregation, not from the features themselves

**Main findings**
- Outperforms baseline graph-comparison methods on synthetic and real graphs across clustering, visualization, discontinuity (change-point) detection, network transfer learning, and cross-network re-identification
- Signature extraction is linear in |E|, making million-edge comparison practical

**Key takeaways**
- Extremely cheap local structural features carry enough signal to discriminate whole graphs, which is a statement about graph *populations*, not about locating anything inside one graph
- The seven-feature set became the standard "local structural profile" reused by later work (see the LDP baseline)

**Relevance**
- **Fenced for KGF.** The feature family is exactly what R45-H545 / H556 / H573 and R10-H100 already tested and killed on our substrate: cheap structural features collapse to seed-hop-distance and predict probe fate no better than the trivial control. R10-H95 adds the mechanism - structural adjacency is anti-correlated with identity on this graph class
- Its object is wrong for our problem in the first place: we have ONE graph and need to locate carriers inside it, not to compare a population of graphs
- Retained as the reference for why the whole "statistical fingerprint" branch of the chapter is a closed axis rather than an untested one

**Tags**
- #GraphSimilarity
- #StructuralFeatures
- #Egonet
- #WholeGraphDescriptor

**Source**
- Download: https://arxiv.org/abs/1209.2684
- Local: [paper] NetSimile size-independent network similarity, 2012.pdf

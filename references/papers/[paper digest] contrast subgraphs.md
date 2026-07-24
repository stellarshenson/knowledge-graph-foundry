**Explainable Classification of Brain Networks via Contrast Subgraphs (2020)**

The one paper in the fingerprints chapter that produces a **localised, interpretable structure** rather than a global signature. Given two classes of graphs over a shared node set, it extracts a **contrast subgraph** - a vertex set whose induced subgraph is dense in one class and sparse in the other - and classifies using only the edge counts inside that subgraph. Applied to autism-spectrum vs typically-developed brain networks, the discovered patterns match neuroscience background knowledge while beating more complex methods on accuracy.

**Key mechanism**
- Requires a **shared node correspondence** across all graphs (brain regions), which is what makes the difference graph well defined
- Build the difference graph from the summed adjacency of class A minus class B, then find the densest subgraph in that difference
- Formulated as a densest-subgraph problem with an L1 size penalty, solved with the standard Charikar / Goldberg machinery plus a local-search refinement
- Classification features are simply the number of edges each graph induces on the contrast subgraph - two numbers when both directions are extracted
- Explainability is structural: the answer is a named vertex set, not a weight vector

**Main findings**
- Superior classification accuracy to more complex state-of-the-art methods on the ASD/TD brain-network task
- Discovered vertex sets align with regions independently implicated in the neuroscience literature, supporting the interpretability claim
- Extends to other classification tasks with the same simplicity

**Key takeaways**
- Densest-subgraph-in-the-difference is a clean, principled formulation for "which structure distinguishes these two populations", with real optimisation guarantees behind it
- The method's hard prerequisite is node correspondence across graphs - without it there is no difference graph to mine

**Relevance**
- **Fenced on V1, and structurally inapplicable besides.** The KGF analogue would be "which subgraph structure distinguishes answered from failed probes", which is exactly the fate-prediction question R50-H587 killed (typed structure adds +0.0023 AUC over hop distance, wrong-signed) and that R45-H545 / H556 / H573 killed for cheap structural features generally
- The node-correspondence prerequisite does not hold for us: our probes induce different, overlapping regions of ONE graph, not a population of graphs over a shared vertex set
- Retained because the densest-subgraph-in-difference formulation is genuinely reusable machinery should a future KGF question take the two-population shape (for example contrasting pre- and post-repair graph snapshots over a stable node set, where correspondence DOES hold)

**Tags**
- #DensestSubgraph
- #Explainability
- #DiscriminativeStructure
- #GraphClassification

**Source**
- Download: https://arxiv.org/abs/2006.05176
- Local: [paper] contrast subgraphs, 2020.pdf

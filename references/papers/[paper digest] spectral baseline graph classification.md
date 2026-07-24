**A Simple Baseline Algorithm for Graph Classification (2018)**

A short workshop paper (NIPS Relational Representation Learning) proposing the minimal spectral baseline for graph classification: take the k smallest non-trivial eigenvalues of the normalized Laplacian as the graph's feature vector and feed them to an off-the-shelf classifier. Sits alongside the LDP baseline as a control against which more sophisticated graph-classification machinery must justify itself.

**Key mechanism**
- Compute the normalized Laplacian spectrum; keep the k smallest non-zero eigenvalues as a fixed-length descriptor
- Size- and permutation-invariant by construction, since eigenvalues do not depend on node ordering
- No learning of the representation; a standard classifier (e.g. a neural net or SVM) does all the work
- Multiplicity of the zero eigenvalue counts connected components, so the truncation point matters on disconnected graphs

**Main findings**
- Competitive with substantially more complex graph-kernel and GNN methods on standard graph-classification benchmarks
- Cheap: only a partial eigendecomposition is needed

**Key takeaways**
- The low end of the Laplacian spectrum alone carries much of the class-discriminative signal available in these benchmarks - a caution against attributing wins to architecture
- Another instance of the chapter's recurring lesson: strong trivial baselines, weak claimed advances

**Relevance**
- **Fenced for KGF, and doubly so.** R43-H474 tested the top-k Laplacian spectrum (LAD-class) on our graph and recorded it BLIND for the pathology class; R09-H77 found the spectral channel real but low-power, with a tiny baseline Fiedler value (~0.012) making it a secondary marker rather than a trigger
- On our archipelago (1,830 components) the low spectrum is dominated by the component structure, so the descriptor would mostly re-report a component count we already have exactly
- Whole-graph object, wrong granularity for retrieval, same as the rest of the chapter
- Kept for completeness of the fingerprints-chapter triage

**Tags**
- #Baseline
- #SpectralGraphTheory
- #GraphClassification
- #WholeGraphDescriptor

**Source**
- Download: https://arxiv.org/abs/1810.09155
- Local: [paper] spectral baseline graph classification, 2018.pdf

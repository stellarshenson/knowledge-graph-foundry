**NetLSD: Hearing the Shape of a Graph (2018)**

Proposes the Network Laplacian Spectral Descriptor - the first graph representation that is simultaneously permutation-invariant, size-invariant, scale-adaptive and efficiently computable. NetLSD's signature is the **heat-kernel trace** (or wave-kernel trace) of the normalized Laplacian sampled at a range of diffusion times, borrowing the "hearing the shape of a drum" idea from spectral geometry. It is a **whole-graph** descriptor for comparing graphs against each other.

**Key mechanism**
- Heat kernel `H_t = e^{-tL} = Σ_j e^{-tλ_j} φ_j φ_jᵀ` on the normalized Laplacian L; the signature is the trace `h_t = Σ_j e^{-tλ_j}` sampled over a logarithmic grid of diffusion times t
- Small t probes local structure (the trace approaches |V|), large t probes global structure (the trace approaches the number of connected components) - this is what "scale-adaptive" means
- The wave-kernel variant substitutes `e^{-itλ_j}`, emphasising different structural scales
- Size invariance by normalising against a reference (empty or complete) graph
- Eigenvalue computation is the bottleneck; the paper uses Taylor expansion and eigenvalue interpolation approximations for large graphs

**Main findings**
- Outperforms prior graph-comparison methods (graph kernels, representation-based methods, direct approaches) on both expressiveness and efficiency across a variety of real-world graph collections
- The heat trace's asymptotic behaviour encodes interpretable quantities: node count at t→0, component count at t→∞

**Key takeaways**
- The heat kernel is the canonical multi-scale structural summary and is exactly diagonalisable, which is why it recurs in every spectral graph-comparison method
- The trace throws away node identity by construction - the signature describes a graph, never a location inside one

**Relevance**
- **Triple-fenced for KGF.** R52-H598 tested the heat kernel directly as a retrieval mechanism on our medium graph: the exact-expm heat-sum arm reads **-1.85pp** vs single-source PPR from the same gold anchors, the true joint heat-product form **collapses -65 to -72pp**, and the trivial hop control (0.926) beats every diffusion arm
- The whole-graph descriptor form is separately dead: R43-H474 found the top-k Laplacian spectrum BLIND for our pathology class and R10-H95 killed unsupervised whole-graph embeddings against text embeddings
- H598 also explains WHY at the mechanism level: our medium graph is a 1,830-component archipelago, so the heat kernel is block-diagonal and cross-component proximity is 0 by construction
- Kept as the reference for the heat-kernel family so any future proposal to "try spectral signatures" resolves against a recorded verdict rather than re-deriving it

**Tags**
- #SpectralGraphTheory
- #HeatKernel
- #GraphSimilarity
- #WholeGraphDescriptor

**Source**
- Download: https://arxiv.org/abs/1805.10712
- Local: [paper] NetLSD hearing the shape of a graph, 2018.pdf

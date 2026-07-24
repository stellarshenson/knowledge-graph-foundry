**Hunt For The Unique, Stable, Sparse And Fast Feature Learning On Graphs (2017)**

Introduces FGSD - a **family of graph spectral distances** defined by a choice of spectral filter f(λ), and builds graph features by histogramming the resulting node-pair distances. The paper's contribution is to state four properties a graph representation should have (uniqueness, stability, sparsity, fast computation) and then show which members of the f(λ) family satisfy them. A plain SVM over FGSD features beats far more sophisticated methods on unlabeled-node graph-classification datasets in both accuracy and speed, **without using any node label information**.

**Key mechanism**
- A graph spectral distance between nodes u and v is `S_f(u,v) = Σ_j f(λ_j)(φ_j(u) − φ_j(v))²` over the Laplacian eigenpairs - the family is parametrised by the filter f
- Familiar members: f(λ)=1/λ is the **harmonic** distance (effective resistance / commute time up to scaling); f(λ)=1/λ² is the **biharmonic** distance; f(λ)=e^{−tλ} is heat
- The graph feature is the **histogram of the multiset of all node-pair distances** - this discards node identity and yields a fixed-length, sparse, permutation-invariant graph descriptor
- Uniqueness and stability are proven for particular f choices; the biharmonic member is highlighted as satisfying the property set best
- Computation avoids the full eigendecomposition by working with the Moore-Penrose pseudoinverse of the Laplacian

**Main findings**
- SVM on FGSD features significantly outperforms state-of-the-art graph kernels and neural methods on unlabeled-node datasets, in accuracy AND speed
- Competitive on labeled datasets despite ignoring node labels entirely
- The choice of f materially changes representational quality, so the "family" framing is the real result

**Key takeaways**
- Commute time / effective resistance and the biharmonic distance are distinct members of one parametric family, and they degenerate differently at scale - a distinction worth knowing before picking a node-pair metric
- Histogramming node-pair distances is the standard route from a node-pair metric to a whole-graph feature, and it is exactly where node identity is discarded

**Relevance**
- **Fenced on V1/V3 - re-testing a different f is the re-derivation trap the vetting protocol exists to prevent.** R52-H598 swept this family on our substrate at oracle level: heat-kernel arms (exact expm and truncated spectral), commute-time arms, and spectral-distance arms at every eigen-k up to 256. Best arm reads **-1.85pp** vs single-source PPR from the same gold anchors; the trivial hop control at **0.926** beats every diffusion arm
- H598 also priced the remaining headroom directly: oracle single-source PPR is already at ceiling on co-component targets (**49/54**, only 5 misses exist to recover), so no new f can win more than a rounding error
- The histogram form is a whole-graph descriptor and inherits the H95 / H474 fences with the rest of the chapter
- Useful as the map of the distance family, so a future proposal naming "biharmonic" or "effective resistance" resolves against H598's sweep rather than looking novel. R10-H91 separately tested effective resistance for identity auditing and found AUC 0.458, worse than chance

**Tags**
- #SpectralGraphTheory
- #GraphKernels
- #EffectiveResistance
- #WholeGraphDescriptor

**Source**
- Download: https://proceedings.neurips.cc/paper/2017/hash/d2ddea18f00665ce8623e36bd4e3c7c5-Abstract.html
- Local: [paper] FGSD family of graph spectral distances, 2017.pdf

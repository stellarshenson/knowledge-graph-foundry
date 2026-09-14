**On Sparse Modern Hopfield Model, Hu, Yang, Wu, Xu, Chen, Liu (Northwestern / NTU), NeurIPS 2023 (arXiv 2309.12673)**

The sparse counterpart of Ramsauer's model, derived rather than assumed. A closed-form sparse Hopfield energy follows from the convex conjugate of a sparse entropic regulariser; its one-step retrieval is exactly **sparse-structured attention** (sparsemax-family), just as the dense model's one step is softmax attention.

**Key mechanism**
- Replace the softmax with a sparse transformation induced by an entropic regulariser; the resulting retrieval assigns exactly zero weight to most stored patterns
- Retains one-step retrieval, fixed-point convergence and exponential memory capacity

**Main findings**
- Derives a **sparsity-dependent retrieval error bound provably tighter than the dense analogue**, and identifies the conditions under which sparsity actually helps
- Empirically the sparse model outperforms the dense model in many situations on synthetic and real data

**Key takeaways**
- Sparse and dense modern Hopfield differ only in the separation function, and the sparse one has the better error bound - further evidence that the sharp end of the separation axis is the right end
- A hard-zero separation function is the associative-memory formalisation of top-k retrieval, so a top-k dense retriever is closer to the theoretically favoured model than a softmax one
- Confirms the separation axis is genuinely sweepable with theory attached, but the sweep's favourable direction is toward sparsity

**Tags**: #SparseHopfield #SparseAttention #ErrorBound #Separation #R59

**Source**: https://arxiv.org/abs/2309.12673. Local: [paper] On Sparse Modern Hopfield Model, 2023.pdf

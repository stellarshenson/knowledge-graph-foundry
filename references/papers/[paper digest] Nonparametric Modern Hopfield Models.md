**Nonparametric Modern Hopfield Models, Hu, Chen, Wu, Ruan, Liu (Northwestern / NTU), ICML 2024 (arXiv 2404.03900)**

The framework that reads memory storage and retrieval as a **nonparametric regression** over query-memory pairs, and uses that reading to generate efficient variants. It recovers the dense modern Hopfield model as a special case and fills the gap on sub-quadratic modern Hopfield models.

**Key mechanism**
- Treat retrieval as kernel regression: the stored memories are the training points, the cue is the query, and the separation function is the kernel weighting
- Sparse-structured variants follow with **sub-quadratic complexity** while inheriting the connection to transformer attention, fixed-point convergence and exponential capacity
- Constructs a family - linear, random-masked, **top-K**, and positive-random-feature modern Hopfield models

**Main findings**
- The top-K variant is an explicit member of the modern Hopfield family with the same theoretical guarantees
- Validated on synthetic and realistic memory-retrieval and learning tasks

**Key takeaways**
- Settles the reduction question from the other direction: **top-K retrieval is a modern Hopfield model**, formally, not merely analogous to one
- The nonparametric reading makes the design space explicit as a kernel choice, which is the similarity axis, again pointing at the embedding rather than the separation function as the remaining lever

**Tags**: #NonparametricHopfield #TopK #KernelRegression #Reduction #R59

**Source**: https://arxiv.org/abs/2404.03900. Local: [paper] Nonparametric Modern Hopfield Models, 2024.pdf

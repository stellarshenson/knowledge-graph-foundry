**The Exponential Capacity of Dense Associative Memories, Lucibello, Mézard (Bocconi), Physical Review Letters 2024 (arXiv 2304.14964)**

The statistical-mechanics account of where exponential capacity actually breaks. For dense associative memories storing **P = exp(αN)** random patterns, the paper gives exact asymptotic thresholds for retrieval of a typical pattern (**α₁**), lower bounds on the load **α_c** at which all patterns are retrievable, and the sizes of the basins of attraction.

**Key mechanism**
- Replica/statistical-mechanics analysis over a generic family of pattern ensembles, worked in detail for **Gaussian and spherical** pattern distributions
- Distinguishes the typical-pattern threshold α₁ from the all-patterns threshold α_c - retrieval degrades gradually, pattern by pattern, not at a single cliff

**Main findings**
- Gaussian and spherical ensembles produce **rich and qualitatively different phase diagrams** - the capacity constant depends on the pattern distribution, not only on dimension
- Classical Hebb-rule Hopfield stores α_c N ≈ 0.14 N; p-spin interactions give order N^(p-1); exponential interactions give exp(αN)
- Basin sizes are computed alongside capacity, so the capacity-versus-robustness trade is explicit

**Key takeaways**
- The formula usable as a scale-safety instrument is **distribution-dependent**; quoting 2^(d/2) for real embeddings is not defensible, because real embeddings are neither Gaussian nor uniform on the sphere
- The gradual α₁ → α_c degradation means the practical question is "at what N does the *hardest* pattern stop being retrievable", which is a per-pattern separation question, not a global capacity question
- Establishes that any capacity forecast must be conditioned on the observed pattern-similarity distribution

**Tags**: #Capacity #PhaseDiagram #StatisticalMechanics #ScaleForecast #R59

**Source**: https://arxiv.org/abs/2304.14964. Local: [paper] Exponential Capacity Dense Associative Memories, 2023.pdf

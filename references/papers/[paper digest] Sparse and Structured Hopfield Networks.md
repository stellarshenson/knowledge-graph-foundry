**Sparse and Structured Hopfield Networks, Santos, Niculae, McNamee, Martins (IST Lisbon / Amsterdam / Champalimaud), ICML 2024 (arXiv 2402.13725)**

The principled route to retrieving a **set** rather than a single pattern. The paper unifies sparse Hopfield networks through Fenchel-Young losses, yielding energies whose update rules are end-to-end differentiable sparse transformations, and extends them via **SparseMAP** so the network can retrieve **pattern associations** - a structured subset of memories - instead of one item.

**Key mechanism**
- Energy built from a Fenchel-Young loss parameterised by a generalised entropy; Tsallis and norm entropies give sparse (α-entmax-like) update rules
- A margin in the Fenchel-Young loss produces **exact retrieval** - the update returns a stored pattern exactly, not an approximation, once the margin condition holds
- SparseMAP replaces the softmax with a structured-prediction transformation whose support is a set of patterns selected jointly

**Main findings**
- Establishes a three-way connection between **loss margin, sparsity and exact retrieval**: sparse transformations retrieve single patterns exactly where dense softmax cannot
- States plainly that Ramsauer et al.'s dense model is **incapable of exact retrieval and may need low temperature to avoid metastable states (states which mix multiple input patterns)**
- Demonstrated on multiple instance learning and text rationalisation

**Key takeaways**
- The literature's own position is that **metastability is a defect to be engineered away**, not a regime to exploit; the sanctioned way to retrieve a set is a structured sparse transformation with an explicit support, not a tuned β
- If set-valued associative retrieval is wanted, SparseMAP is the published mechanism with a principled support; β-tuning into the metastable band is the mechanism the same authors are removing

**Tags**: #SparseHopfield #FenchelYoung #SparseMAP #SetRetrieval #Metastable #R59

**Source**: https://arxiv.org/abs/2402.13725. Local: [paper] Sparse and Structured Hopfield Networks, 2024.pdf

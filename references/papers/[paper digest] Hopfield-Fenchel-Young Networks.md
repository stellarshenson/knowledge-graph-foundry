**Hopfield-Fenchel-Young Networks: A Unified Framework for Associative Memory Retrieval, Santos, Niculae, McNamee, Martins, JMLR 26 (2025) (arXiv 2411.08590)**

The journal-length generalisation of the sparse/structured Hopfield line. Energies are written as the difference of two Fenchel-Young losses - one, parameterised by a generalised entropy, defines the scoring; the other applies a post-transformation to the output. The framework subsumes classical, dense-modern and sparse Hopfield networks, and gives an energy-minimisation reading of common post-transformations such as **l2-normalisation and layer normalisation**.

**Key mechanism**
- Tsallis and norm entropies yield differentiable sparse update rules with tunable support size
- Margin analysis links sparsity to **exact retrieval of a single memory pattern**
- SparseMAP extension retrieves **pattern associations rather than a single pattern**, with the association structure specified by a factor graph rather than by temperature

**Main findings**
- Unifies the model family and explains why normalisation layers behave as energy-minimisation steps
- Confirms and extends the margin-sparsity-exactness relationship from the ICML version
- Provides the general vocabulary for choosing a separation function with a controlled support size

**Key takeaways**
- The current best answer to "how do I retrieve k related items, principledly" is a structured sparse transformation whose support is an explicit combinatorial object - not an inverse-temperature setting
- Post-transformations already present in retrieval stacks (l2-normalise the embedding) are themselves part of the energy, so a Hopfield reading of an existing dense retriever accounts for more of the pipeline than just the softmax

**Tags**: #HopfieldFenchelYoung #SparseMAP #ExactRetrieval #StructuredRetrieval #R59

**Source**: https://arxiv.org/abs/2411.08590. Local: [paper] Hopfield-Fenchel-Young Networks, 2024.pdf

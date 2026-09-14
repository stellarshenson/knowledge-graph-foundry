**Equivalence of Personalized PageRank and Successor Representations, Millidge (Zyphra), 2025 (arXiv 2512.24722)**

The short note that fixes where personalized PageRank sits in the memory-model taxonomy. Personalized PageRank, proposed as the hippocampal algorithm for **memory retrieval**, and the successor representation, proposed for **planning and navigation**, are shown to be **isomorphic**: both compute the stationary distribution of a random walk on a graph.

**Key mechanism**
- Both quantities are the resolvent (Neumann series) of a discounted transition operator over the graph, differing only in parameterisation and in what the reset/discount term means
- The hypothesised hippocampal computation is to produce this representation over arbitrary input graphs

**Main findings**
- One algorithm, two literatures: retrieval by diffusion and planning by successor features are the same object
- The representation is a property of the **graph transition operator**, computed by iteration to a fixed point

**Key takeaways**
- Personalized PageRank is an **iterated** linear system, not a single-shot similarity-separation-projection pass; it therefore does not fit inside the Universal Hopfield triple, which is explicitly a framework for single-shot models
- Being a function of the transition operator, it is block-diagonal over connected components - a diffusion cannot reach a component the reset mass never touches, whatever the memory model wrapped around it
- The same author wrote the Universal Hopfield paper, so the separation of the two families is deliberate, not an oversight

**Tags**: #PersonalizedPageRank #SuccessorRepresentation #Diffusion #Hippocampus #R59

**Source**: https://arxiv.org/abs/2512.24722. Local: [paper] Equivalence Personalized PageRank Successor Representations, 2025.pdf

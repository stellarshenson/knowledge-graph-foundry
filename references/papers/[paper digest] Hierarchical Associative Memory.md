**Hierarchical Associative Memory, Krotov (MIT-IBM Watson AI Lab), 2021 (arXiv 2107.06446)**

The multi-layer generalisation of dense associative memory. All prior models in the class had **one hidden layer** and dense all-to-all connectivity; this paper gives a fully recurrent associative memory with an arbitrary number of layers, some of which may be locally connected (convolutional), and an energy function that decreases along the dynamical trajectory.

**Key mechanism**
- Memories of the full network are **dynamically assembled** from primitives encoded in the lower layers, with the assembly rules encoded in the higher layers
- Rich top-down feedback: higher layers influence how lower-layer neurons respond to the input, in addition to the usual bottom-up propagation
- A single global Lyapunov energy covers the whole hierarchy

**Main findings**
- Removes the two structural restrictions (single hidden layer, dense connectivity) that blocked machine-learning use of the model class
- The compositional reading - a stored memory is a combination of reusable lower-level parts - is the model's main conceptual contribution

**Key takeaways**
- The published route to retrieving a **composed** object rather than a single stored pattern: composition happens through layered assembly rules, not by cueing with a sum of patterns
- Relevant to any proposal that wants a memory to return "the set of things that go together": the hierarchical model does this by construction, the flat model does it only as a metastable blend

**Tags**: #HierarchicalAssociativeMemory #Krotov #Compositionality #R59

**Source**: https://arxiv.org/abs/2107.06446. Local: [paper] Hierarchical Associative Memory, 2021.pdf

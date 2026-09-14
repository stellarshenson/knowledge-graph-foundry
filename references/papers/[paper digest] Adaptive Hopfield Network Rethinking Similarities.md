**Adaptive Hopfield Network: Rethinking Similarities in Associative Memory, Wang, Pan, Shen, Zhang, Wang, Li (Zhejiang University / CAS Institute of Automation), 2025 (arXiv 2511.20609)**

The paper that argues the **similarity** function, not the separation function, is where associative-memory retrieval is actually decided. Existing models judge retrieval by proximity, which does not guarantee the retrieved pattern has the strongest association with the query. A-Hop reframes the query as a **generative variant** of a stored pattern and asks for the pattern with maximum a posteriori probability of having generated it.

**Key mechanism**
- Define a **variant distribution** modelling the context-dependent generative process that turns a stored pattern into the observed query
- Correct retrieval = argmax over stored patterns of the likelihood of generating the query, which no fixed pre-defined similarity can compute
- **Adaptive similarity** learns to approximate that likelihood from samples drawn from context

**Main findings**
- Proves adaptive similarity achieves optimal correct retrieval under three canonical variant types: **noisy, masked and biased**
- Reports state-of-the-art results across memory retrieval and downstream tasks against fixed-similarity Hopfield models

**Key takeaways**
- Directly relevant to mention-to-prototype matching: a surface-form variant of an entity is exactly a "generative variant of a stored pattern", and the paper's claim is that a fixed cosine cannot rank these correctly by construction
- The remaining headroom in the Hopfield triple is on the **similarity axis** - learning a likelihood-shaped comparison - not on the separation axis, which is already saturated by sparse/top-k
- Under review at time of filing; the theoretical results are conditional on the assumed variant families

**Tags**: #AdaptiveSimilarity #AHop #Similarity #VariantDistribution #R59

**Source**: https://arxiv.org/abs/2511.20609. Local: [paper] Adaptive Hopfield Network Rethinking Similarities, 2025.pdf

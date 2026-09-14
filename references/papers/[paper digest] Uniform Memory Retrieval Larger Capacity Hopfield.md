**Uniform Memory Retrieval with Larger Capacity for Modern Hopfield Models (U-Hop), Wu, Hu, Hsiao, Liu (Northwestern / NTU), ICML 2024 (arXiv 2404.03827)**

The paper that makes separation a **trainable** quantity rather than an observed one. U-Hop is a two-stage retrieval: first minimise a **separation loss** that spreads the stored memory patterns apart in a learned kernel space, then run standard Hopfield energy minimisation.

**Key mechanism**
- A learnable feature map Φ transforms the Hopfield energy into kernel space, so that local minima of the kernelised energy coincide with fixed points of the retrieval dynamics
- The kernel norm induced by Φ becomes a new similarity measure; the separation loss L_Φ explicitly separates stored patterns, using the memories themselves as training data
- Stage I: minimise L_Φ for a more uniform memory distribution. Stage II: standard retrieval

**Main findings**
- Significant reduction of possible metastable states, hence higher effective capacity, by **preventing memory confusion**
- Outperforms existing modern Hopfield models and state-of-the-art similarity measures on real-world datasets, in both associative retrieval and downstream deep-learning tasks

**Key takeaways**
- Confirms the causal chain the theory predicts: separation drives retrieval correctness, metastable states are the failure, and separation can be **optimised directly**
- If a merge certificate is to be based on Δ_i, U-Hop is the published way to make Δ_i large enough to be usable rather than accepting whatever the embedding gives
- Reinforces that the similarity/embedding choice, not the separation function, is where the remaining headroom sits

**Tags**: #UHop #SeparationLoss #Metastable #Capacity #KernelSpace #R59

**Source**: https://arxiv.org/abs/2404.03827. Local: [paper] Uniform Memory Retrieval Larger Capacity Hopfield, 2024.pdf

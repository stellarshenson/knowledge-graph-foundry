**Dynamic Manifold Hopfield Networks for Context-Dependent Associative Memory, Li, Zeng, Xue, Feng (Fudan University), 2026 (arXiv 2506.01303)**

Continuous Hopfield networks descend a **fixed** energy landscape, so retrieval is confined to one static attractor geometry. DMHN lets contextual modulation reshape the attractor geometry itself, turning a static manifold into a context-dependent family of manifolds, with the interactions learned from data rather than parameterised per context.

**Key mechanism**
- Network interactions are learned so that a context cue intrinsically deforms the attractor manifold; no explicit context-specific parameters
- Retrieval then happens on the manifold selected by context, so the same stored content can resolve differently under different cues

**Main findings**
- Storing **2N patterns in a network of N neurons**, DMHN reaches average retrieval accuracy **64%**, against **13% for modern Hopfield and 1% for classical Hopfield**
- Presented as a mechanism for context-dependent remapping in neural associative memory

**Key takeaways**
- The 64% vs 13% vs 1% comparison is the strongest single number on how badly flat modern Hopfield retrieval degrades once the stored count exceeds the dimension - directly relevant to any scale forecast
- Context-dependent geometry is the published answer to "the same mention means different entities in different contexts", which a single global pattern bank cannot express
- Evaluated on synthetic pattern-retrieval tasks, not on text or retrieval benchmarks

**Tags**: #DynamicManifold #ContextDependent #Capacity #Remapping #R59

**Source**: https://arxiv.org/abs/2506.01303. Local: [paper] Dynamic Manifold Hopfield Networks, 2026.pdf

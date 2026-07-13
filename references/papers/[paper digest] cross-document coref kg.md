# Cross-Document Contextual Coreference Resolution in Knowledge Graphs

**arXiv 2504.05767 (2025), Dong et al.** Introduces a **dynamic linking mechanism** that resolves coreference across multiple documents by tying textual mentions directly to entities already present in a knowledge graph, reporting "substantial improvements in both precision and recall" over traditional coreference methods on benchmark datasets.

**Key mechanism**: entities in the KG are dynamically linked to their corresponding textual mentions using contextual embeddings combined with graph-based inference; the graph's existing relationship structure is used as an additional signal (beyond text-only context) to decide whether two mentions in different documents refer to the same entity.

**Main findings**: contextual information derived from the KG itself improves understanding of complex cross-document relationships, leading to better entity linking and information extraction than approaches that treat coreference as a text-only problem; gains hold across multiple benchmark datasets.

**Key takeaways for KGF**: directly targets H566 - bridging pronoun-subject facts ("it", "the device", "he") to their carrier entity across documents by using the graph-under-construction as a coreference signal, not just local text context. Reinforces the speculative-ingest-context approach (in-flight graph informs entity pinning) already adopted for extraction-time variance reduction.

**Tags**: coreference, cross-document, entity-linking, kg-construction
**Source**: https://arxiv.org/abs/2504.05767 (PDF: `[paper] cross-document coref kg, 2025.pdf`)

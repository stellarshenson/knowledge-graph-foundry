# From RAG to Memory: Non-Parametric Continual Learning for Large Language Models (HippoRAG 2)

**Authors**: Bernal Jiménez Gutiérrez, Yiheng Shu, Weijian Qi, Sizhe Zhou, Yu Su

**arXiv link (source for re-download)**: https://arxiv.org/abs/2502.14802

**Publication date**: 2025-02-20 (first arXiv version)

## Summary

- Extends HippoRAG by placing both phrase (entity) nodes and full passage nodes into a single Personalized PageRank graph, so retrieval propagates across concepts and source passages together
- Query-to-triple linking replaces query-to-phrase matching: the query is linked against extracted triples, improving seed quality (+12.5% recall@5 on average, +21 points on MuSiQue)
- Adding passage nodes into the PPR graph itself is worth +11 recall points versus a phrase-only graph
- Recognition-memory-style seed filtering: an LLM screens candidate seed nodes before PPR to suppress spurious anchors
- Asymmetric reset weights in PPR - passage nodes 0.05, phrase nodes 1.0 - bias propagation toward conceptual structure while still surfacing passages
- MuSiQue F1 48.6 vs 35.1 for HippoRAG 1 - large multi-hop gain
- Framed as non-parametric continual learning: new knowledge is added to the graph, not the model weights
- Balances factual, sense-making, and associative memory tasks better than prior graph RAG and dense-retrieval baselines

**Relevance to Knowledge Graph Foundry**: Its unified phrase+passage PPR graph with asymmetric reset weights and LLM seed filtering is a near-direct blueprint for KGF's vector-seeded PPR retrieval over a Neo4j entity/text graph.

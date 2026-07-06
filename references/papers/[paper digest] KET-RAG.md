# KET-RAG: A Cost-Efficient Multi-Granular Indexing Framework for Graph-RAG

**Authors**: Yiqian Huang, Shiqi Zhang, Xiaokui Xiao

**arXiv link (source for re-download)**: https://arxiv.org/abs/2502.09304

**Publication date**: 2025-02-13 (first arXiv version)

## Summary

- Addresses the high LLM cost of building a full knowledge graph over an entire corpus by indexing at two granularities
- Skeleton layer: runs the expensive LLM triple extraction only over a PageRank-selected core of the most important chunks, building a precise KG skeleton where it matters most
- Keyword-chunk bipartite layer: a cheap text-keyword bipartite graph spans all chunks, giving coverage without per-chunk LLM extraction
- Retrieval combines both layers so queries can hit the precise skeleton or fall back on the broad keyword layer
- Roughly 10x reduction in indexing cost versus building a full graph over every chunk
- Up to +32% generation quality on some datasets relative to comparable graph-RAG baselines at that reduced cost
- Multi-granular design lets budget be spent on structurally central content rather than uniformly across the corpus

**Relevance to Knowledge Graph Foundry**: Its PageRank-core selection for where to spend expensive LLM extraction offers KGF a cost-control strategy for scaling graph construction over large corpora without extracting every chunk.

# When to Use Graphs in RAG

**Title**: When to Use Graphs in RAG: A Comprehensive Analysis for Graph Retrieval-Augmented Generation
**Authors**: See arXiv listing (source of truth below)
**Source (re-download)**: https://arxiv.org/abs/2506.05690
**Publication date**: 2025-06 (first arXiv version)

## Core mechanism + measured results
- Survey/benchmark analyzing when graph-based RAG actually beats vanilla vector RAG
- Winning graph frameworks share two structural properties: highest average node degree and lowest orphan (disconnected node) fraction
- HippoRAG2 average degree 8.75 vs Microsoft GraphRAG 1.48 - denser, better-connected graphs win
- GraphRAG global mode is extremely token-hungry: 331,375 tokens for a query vs 954 tokens for vanilla RAG (~348x more)
- Basic RAG beats GraphRAG on simple factual questions: 60.92% vs 49.29%
- Graph RAG's advantage concentrates on multi-hop / global sensemaking, not simple lookups
- Implication: graph density and connectivity are the key quality levers, and graph RAG must be used selectively

## Relevance to Knowledge Graph Foundry
Sets KGF's design targets: maximize average degree and minimize orphans in the cured Neo4j ontology, and route simple factual queries to plain vector retrieval rather than expensive community-summary sensemaking.

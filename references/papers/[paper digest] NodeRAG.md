# NodeRAG: Structuring Graph-based RAG with Heterogeneous Nodes

**Authors**: Tianyang Xu, Haojie Zheng, Chengze Li, Haoxiang Chen, Yixin Liu, Ruoxi Chen, Lichao Sun

**arXiv link (source for re-download)**: https://arxiv.org/abs/2504.11544

**Publication date**: 2025-04-15 (first arXiv version)

## Summary

- Reframes graph-based RAG around a heterogeneous graph where nodes carry distinct roles: Entity, Relationship, SemanticUnit, Attribute, HighLevel element, and Text - each role serving a different retrieval function
- Only content-bearing nodes (semantic units, attributes, high-level elements, text) are embedded; entity and relationship names act as string-match entry points, keeping the index lean
- Retrieval uses a shallow Personalized PageRank (2 iterations, alpha 0.5) seeded from matched entry-point nodes, spreading relevance across the heterogeneous graph rather than deep multi-hop traversal
- Dual-search entry: exact string matching on entity names plus vector similarity on embedded content nodes, then PPR to expand
- MuSiQue: 46.3% accuracy at 5.9k retrieved tokens vs GraphRAG 41.7% at 6.6k tokens - higher accuracy with a smaller context
- HotpotQA: 89.5% accuracy at ~5k tokens
- Retrieval ratio (fraction of retrieved tokens that are relevant) 94.9% vs GraphRAG 86.3% - markedly less noise per retrieval
- Positions node heterogeneity as the mechanism that lets a single graph serve both fine-grained entity lookup and high-level thematic retrieval

**Relevance to Knowledge Graph Foundry**: The heterogeneous-node + shallow-PPR design directly parallels KGF's vector-seeded PPR retrieval and argues that embedding only content nodes while using entity names as string entry points sharpens retrieval precision.

# LeanRAG: Knowledge-Graph-Based Generation with Semantic Aggregation and Hierarchical Retrieval

**Authors**: Yaoze Zhang, Rong Wu, Pinlong Cai, Xiaoman Wang, Guohang Yan, Song Mao, Ding Wang, Botian Shi

**arXiv link (source for re-download)**: https://arxiv.org/abs/2508.10391

**Publication date**: 2025-08-14 (first arXiv version)

## Summary

- Targets two failures of hierarchical graph RAG: "semantic islands" (high-level community summaries that sit disconnected from each other) and flat, redundant retrieval
- Semantic aggregation clusters entities and builds explicit relations between the resulting aggregation-level summaries, linking previously isolated community summaries into a navigable network
- Hierarchical retrieval is bottom-up: anchor on the most relevant fine-grained entities, then traverse upward through the now-connected summary network to gather concise, non-redundant evidence
- The explicit inter-summary edges are what let retrieval move laterally across themes instead of being trapped inside one community
- Reports ~46% reduction in retrieval redundancy versus prior graph-RAG retrieval
- Improves answer quality across multiple QA benchmarks while retrieving less overlapping context
- Structure-guided traversal replaces flat similarity search over summaries

**Relevance to Knowledge Graph Foundry**: Its fix for "semantic islands" - adding explicit edges between community/aggregation summaries - informs how KGF should connect its statistically-cured ontology's high-level clusters so PPR retrieval can traverse across themes.

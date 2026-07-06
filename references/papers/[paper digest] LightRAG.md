# LightRAG: Simple and Fast Retrieval-Augmented Generation

**Authors**: Zirui Guo, Lianghao Xia, Yanhua Yu, Tu Ao, Chao Huang

**arXiv link (source for re-download)**: https://arxiv.org/abs/2410.05779

**Publication date**: 2024-10-08 (first arXiv version)

## Summary

- Builds an entity-and-relation knowledge graph from the corpus and pairs it with a dual-level retrieval scheme rather than flat chunk retrieval
- Low-level retrieval keys target specific entities and their immediate relations, answering concrete detail questions
- High-level retrieval keys target broader themes and concepts, answering abstract or sense-making questions
- Both levels combine graph structure with vector similarity so retrieval spans precise facts and thematic context in one pass
- Incremental-update friendly: new documents add nodes and edges without rebuilding the whole index, suiting evolving corpora
- Reports lower retrieval cost and faster response than GraphRAG-style community-summary approaches while improving answer quality and diversity
- Positions dual-level keys as the mechanism to serve both fine-grained and holistic queries from a single graph index

**Relevance to Knowledge Graph Foundry**: Its dual-level (entity vs thematic) retrieval keys and incremental graph updates map onto KGF's need to serve both precise entity queries and higher-level thematic retrieval over a continuously ingested Neo4j graph.

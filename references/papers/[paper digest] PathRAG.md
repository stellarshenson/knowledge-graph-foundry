# PathRAG: Pruning Graph-based Retrieval Augmented Generation with Relational Paths

**Authors**: Boyu Chen, Zirui Guo, Zidan Yang, Yuluo Chen, Junze Chen, Zhenghao Liu, Chuan Shi, Cheng Yang

**arXiv link (source for re-download)**: https://arxiv.org/abs/2502.14902

**Publication date**: 2025-02-18 (first arXiv version)

## Summary

- Argues graph RAG retrieves too much loosely-connected context; the fix is to retrieve pruned relational paths between the query's anchor nodes rather than whole neighborhoods
- Flow-based pruning: models a decaying flow along candidate paths so distant, weakly-connected nodes are penalized, keeping only paths with strong relational signal
- Reliability scoring orders the surviving paths, and the prompt presents them in that order so the most reliable paths sit where the LLM attends best
- Path-based retrieval reduces context size by ~44% while holding answer accuracy - much less noise per query
- LLM-judged win-rate 59.9% versus GraphRAG across evaluated dimensions
- Reduces redundancy and mitigates the "lost in the middle" effect by both trimming and ordering evidence
- Positions relational paths, not node sets, as the natural retrieval unit for graph RAG

**Relevance to Knowledge Graph Foundry**: Flow-based path pruning is a candidate refinement for KGF's PPR retrieval - trimming weakly-connected expansions to cut context size and order surviving paths by reliability before handing them to the generator.

# CatRAG

**Title**: CatRAG - query-time hub damping for Personalized PageRank retrieval (see arXiv for full title)
**Authors**: See arXiv listing (source of truth below)
**Source (re-download)**: https://arxiv.org/abs/2602.01965
**Publication date**: 2026-02 (first arXiv version)

## Core mechanism + measured results
- Targets the "super-hub" problem in Personalized PageRank (PPR) retrieval, where high-degree nodes absorb disproportionate probability mass
- Symbolic anchoring: sets the PPR reset (teleport) probability to 0.2 concentrated on query entities, biasing the walk toward query-relevant nodes
- LLM edge tiering: an LLM assigns importance tiers to edges, damping mass flow through generic hub connections at query time
- Super-hub probability mass reduced from 45.7% to 42.5%
- Recall@5 improvement of +2.5 to +5.6 points across benchmarks
- On MuSiQue, Recall@5 rises from 61.4 to 64.9
- All damping applied at query time (no master-graph mutation)

## Relevance to Knowledge Graph Foundry
Direct recipe for KGF's vector-seeded PPR retrieval: query-time hub damping (reset prob 0.2 on seed entities + edge tiering) to stop community super-hubs from dominating PPR mass.

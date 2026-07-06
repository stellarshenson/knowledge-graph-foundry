# Zep: A Temporal Knowledge Graph Architecture for Agent Memory (Graphiti)

**Authors**: Preston Rasmussen, Pavlo Paliychuk, Travis Beauvais, Jack Ryan, Daniel Chalef

**arXiv link (source for re-download)**: https://arxiv.org/abs/2501.13956

**Publication date**: 2025-01-20 (first arXiv version)

## Summary

- Zep is agent memory built on Graphiti, a temporally-aware knowledge graph engine that ingests messages and business data into an evolving graph
- Three-tier hierarchy: an episode subgraph (raw ingested data), a semantic entity subgraph (extracted entities and relations), and a community subgraph (clusters of related entities)
- Bitemporal edges: every edge records both when a fact holds in the world and when the system learned it, so history is queryable at any point in time
- Facts are invalidated, not deleted - when new information contradicts an edge, the old edge is marked invalid with an end time rather than removed, preserving audit history
- Dynamic label propagation for community assignment instead of periodic full Leiden re-clustering, letting communities update incrementally as data arrives
- Entity resolution runs per-entity and incrementally at ingestion, with P95 latency around 300ms
- Deep Memory Retrieval (DMR) benchmark: 94.8% accuracy
- LongMemEval: +18.5% accuracy while cutting latency by ~90% versus a full-context baseline

**Relevance to Knowledge Graph Foundry**: Directly validates KGF's bitemporal edges and incremental entity resolution - Graphiti's invalidate-don't-delete edges and per-entity resolution are the operational pattern KGF's longevity (months/years, entity versioning) requirements demand.

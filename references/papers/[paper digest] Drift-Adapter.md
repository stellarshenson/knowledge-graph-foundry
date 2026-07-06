# Drift-Adapter

**Title**: Drift-Adapter: Mitigating Embedding Drift Without Re-Embedding (short name Drift-Adapter)
**Authors**: See arXiv listing (source of truth below)
**Source (re-download)**: https://arxiv.org/abs/2509.23471
**Publication date**: 2025-09 (first arXiv version)

## Core mechanism + measured results
- Problem: upgrading the embedding model normally forces re-embedding the entire corpus (expensive, disruptive)
- Solution: a small learnable transform maps queries encoded by the NEW model back into the LEGACY vector space, so the existing index stays untouched
- Adapter trained on ~5k paired samples (same text encoded by old and new models)
- Retains 95-99% of full re-embedding recall
- Training cost ~0.5 GPU-hour vs ~100 GPU-hours for a full corpus re-embed (roughly 200x cheaper)
- Adds <10 microseconds query-time overhead (transform is a lightweight projection)
- Enables incremental/rolling embedding-model upgrades without index rebuilds

## Relevance to Knowledge Graph Foundry
Directly addresses KGF's vector-seeded PPR retrieval longevity: lets KGF swap embedding models over months/years without re-embedding its Neo4j vector index, preserving seed quality cheaply.

# GPT Semantic Cache: Reducing LLM Costs and Latency via Semantic Embedding Caching

**Authors**: Sajal Regmi, Chetan Phakami Pun

**arXiv link (source for re-download)**: https://arxiv.org/abs/2411.05276

**Publication date**: 2024-11-08 (v3: 2024-12-09)

## Summary

- **68.8%** peak cache hit rate (Order and Shipping category), with hit rates ranging **61.6%-68.8%** across four query categories - each hit avoids an LLM API call
- **97%+** positive hit rate (GPT-4o Mini-judged correctness of the cached response for the incoming query), confirming cached responses stay reliable at the chosen threshold
- **8,000** question-answer pairs across four categories (basic Python programming, customer service, technical support, general knowledge) built the cache; **2,000** held-out test queries (500/category) drove evaluation
- Embeddings via `all-MiniLM-L6-v2` (384-dim) for the benchmark, with the production system also supporting OpenAI `text-embedding-ada-002` (1536-dim) or any ONNX model
- Similarity threshold of **0.8** cosine similarity selected empirically by sweeping 0.6-0.9 in 0.05 steps: below 0.8 raised hit rate but admitted irrelevant matches and dropped positive-hit accuracy; above 0.8 suppressed hit rate without accuracy gain
- Per-category cache-hit counts out of 500 queries: Python 335, network support 335, order/shipping 344, shopping QA 308 - shopping QA is both the lowest hit rate and lowest positive-hit rate, attributed to broader semantic variability in that category
- Architecture: query -> embedding -> HNSW-based Approximate Nearest Neighbor search (via `hnswlib-node`) against a Redis-backed store of embedding+response pairs, partitioned by embedding dimension and expired via TTL; cache miss falls through to the LLM API and the new pair is written back
- HNSW gives ~O(log n) similarity search versus O(n) exhaustive comparison, with periodic graph rebalancing as the store grows
- Stated limitations: a single fixed threshold does not generalize across query types, no handling of multi-turn/context-dependent queries, and TTL alone is insufficient for rapidly changing source data

## Key Mechanism

A single-vector, single-threshold semantic cache: each incoming query is embedded once, compared by cosine similarity against all previously cached query embeddings via ANN search, and served directly from the cache above a fixed 0.8 threshold - otherwise the query pays for a full LLM call whose result is then cached for future reuse. No query decomposition, no multi-signal gating, and no per-category threshold tuning despite category-level accuracy differing by several points.

**Relevance to Knowledge Graph Foundry**: A direct precedent for a query-level answer cache sitting in front of the local vLLM gpt-oss-120b serving path - KGF's H274 answer-cache already occupies this niche, and this paper's single global 0.8 cosine threshold (versus per-category variance in positive-hit rate) is a cautionary data point for H382's calibrated context-escalation gate, which should not assume one static similarity cutoff generalizes across KGF's query types.

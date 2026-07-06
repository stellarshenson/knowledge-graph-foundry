# Microsoft GraphRAG

**Title**: From Local to Global: A Graph RAG Approach to Query-Focused Summarization
**Authors**: Darren Edge, Ha Trinh, Newman Cheng, Joshua Bradley, Alex Chao, Apurva Mody, Steven Truitt, Jonathan Larson (Microsoft Research)
**Source (re-download)**: https://arxiv.org/abs/2404.16130
**Publication date**: 2024-04 (first arXiv version)

## Core mechanism + measured results
- Two-stage pipeline: LLM extracts an entity knowledge graph (entities, relationships, and optional claims/covariates) from source documents, then builds community summaries for related entity groups
- Communities detected via hierarchical Leiden algorithm, producing nested levels C0 (root) through C3 (leaf), enabling summarization at multiple granularities
- Claims/covariates extraction is a separate pass and is off by default (adds latency/cost)
- Query answering is map-reduce: each community summary generates a partial answer, then partials are combined into a global answer for "global sensemaking" questions
- Reported ~50-70% win rate in comprehensiveness and diversity over naive vector RAG on global sensemaking queries (LLM-judged, two datasets ~1M tokens each)
- Root-level community summaries (C0) give comparable answer quality at far lower token cost than source-text summarization
- Graph index is reusable across many queries, amortizing the up-front LLM extraction cost

## Relevance to Knowledge Graph Foundry
Foundational blueprint for KGF's community-summary layer and Leiden community detection; validates statistically-cured ontology + community summaries as the global-sensemaking retrieval tier over Neo4j.

# GraphRAG Survey

**Title**: Graph Retrieval-Augmented Generation: A Survey
**Authors**: See arXiv listing (source of truth below)
**Source (re-download)**: https://arxiv.org/abs/2501.00309
**Publication date**: 2025-01 (first arXiv version)

## Core mechanism + measured results
- Comprehensive survey of Graph RAG, organizing the field into graph construction, retrieval, and generation stages
- Catalogues techniques for query-aware dynamic edge weighting (edge importance re-scored per query rather than fixed)
- Highlights retrieved-subgraph pruning: prune the retrieved subgraph per query rather than mutating the master graph
- Taxonomizes graph indexing choices, retriever designs, and integration patterns with downstream generators
- Consolidates evaluation practices and open challenges (scalability, freshness, faithfulness)
- Serves as a reference map of design options rather than reporting a single benchmark number

## Relevance to Knowledge Graph Foundry
Reference catalogue for KGF's retrieval design: supports query-time subgraph pruning and per-query edge weighting over the persistent Neo4j graph, keeping the master ontology stable while tailoring each retrieval.

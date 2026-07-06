# TCR-QF

**Title**: Training-free Continual Retrieval / Query-Feedback KG refinement (TCR-QF; see arXiv for full title)
**Authors**: See arXiv listing (source of truth below)
**Source (re-download)**: https://arxiv.org/abs/2501.15378
**Publication date**: 2025-01 (first arXiv version)

## Core mechanism + measured results
- Query-feedback graph refinement: the knowledge graph is iteratively improved using signal from queries it fails to answer
- Failed/underserved queries act as a maintenance trigger, identifying missing knowledge in the KG
- Query-relevant missing knowledge is retrieved and incorporated back into the graph, closing gaps incrementally
- Refinement loop runs without retraining the base model (training-free)
- Reports improved multi-hop QA accuracy over static-KG RAG baselines (see paper tables for per-dataset gains)
- Treats the KG as a living structure that adapts to the query workload rather than a fixed index

## Relevance to Knowledge Graph Foundry
Motivates a maintenance loop for KGF's statistically-cured ontology: use failed queries as triggers to extend/repair the Neo4j graph over time, aligning with KGF's months/years longevity goal.

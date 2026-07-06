# Simple Is Effective: The Roles of Graphs and LLMs in Knowledge-Graph-Based RAG (SubgraphRAG)

**Authors**: Mufei Li, Siqi Miao, Pan Li

**arXiv link (source for re-download)**: https://arxiv.org/abs/2410.20724

**Publication date**: 2024-10-28 (first arXiv version)

## Summary

- Separates the retrieval problem from reasoning: a lightweight learned retriever selects a small, relevant subgraph, then the LLM reasons over it
- Retriever is a simple MLP paired with a parallel triple-scoring mechanism that scores and selects triples, avoiding expensive iterative graph traversal
- Structural distance encoding injects graph topology into the retriever so subgraph selection respects connectivity, not just per-triple relevance
- Subgraph size is tunable, letting the system trade retrieval breadth against the LLM's reasoning and context budget
- WebQSP F1 of 78.2 with GPT-4o - strong KGQA accuracy from a deliberately simple retriever
- Demonstrates that a well-scoped subgraph plus a capable LLM beats more complex retrieval pipelines
- Assumes a pre-existing curated knowledge graph (e.g. Freebase) rather than building one from text

**Relevance to Knowledge Graph Foundry**: Its learned MLP+triple-scorer subgraph selection over a curated KG is a retrieval alternative to PPR for KGF, relevant precisely because KGF also operates over a statistically-cured (curated) ontology.

**G-Retriever: Retrieval-Augmented Generation for Textual Graph Understanding and Question Answering (2024)**

G-Retriever retrieves a CONNECTED subgraph for a textual-graph question by solving a **Prize-Collecting Steiner Tree (PCST)** optimization - nodes and edges earn prizes from query relevance, and PCST finds the maximum-prize connected subtree within a budget. A GNN encodes that subgraph into a soft prompt for a frozen LLM. It resists hallucination, handles graphs exceeding the LLM context window, scales with graph size, and beats baselines across scene-graph, commonsense, and KG tasks; it ships the GraphQA benchmark.

**Key mechanism**
- Assign query-relevance prizes to nodes and edges (embedding similarity)
- PCST selects a connected, budget-bounded subtree that maximizes retained prize minus edge cost - retrieval that GUARANTEES connectivity
- GNN encodes the subgraph -> soft prompt prepended to a (fine-tuned) LLM

**Main findings**
- PCST yields a connected answer-region, unlike top-k triple selection which can return disconnected fragments
- Reduces hallucination and scales past the context window
- Soft-prompt arm requires LLM fine-tuning

**Key takeaways**
- Connectivity as an explicit retrieval constraint is the transferable idea - answer regions for bridge/comparison questions must link the involved entities
- The learned soft-prompt injection is not transferable to a retrieval-only, LLM-free loop

**Relevance**
- PCST is a structural alternative to PPR for R50's Step-2 region selection, and its connectivity guarantee is directly relevant to the bridge/comparison classes where two entities must be joined (H593's two-slot concern)
- The soft-prompt arm violates KGF's Failure Mode A (no LLM in the retrieval loop) and R50's retrieval-level-only fence - only the PCST region-selection half is admissible
- PCST needs per-node/edge prizes = query relevance, which KGF already has from dense cosine; a training-free PCST-over-cosine region is a concrete cheap arm

**Tags**
- #GraphRAG #SteinerTree #ConnectedSubgraph #GNN

**Source**
- Download: https://arxiv.org/pdf/2402.07630
- Local: [paper] G-Retriever, 2024.pdf

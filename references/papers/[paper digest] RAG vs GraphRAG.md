**RAG vs. GraphRAG: A Systematic Evaluation and Key Insights, Han et al., 2025 (arXiv 2502.11371)**

Controlled benchmark of dense RAG against four GraphRAG classes (KG-based, community-based, HippoRAG2, RAPTOR) across QA and query-based summarization under one unified retrieval/generation protocol. Headline: RAG wins single-hop QA (NQ F1 64.78 vs best GraphRAG 63.01), GraphRAG wins multi-hop QA (MultiHop-RAG accuracy 70.27 for HippoRAG2 vs RAG's 67.02) - and on MultiHop-RAG, 13.6% of queries are answered correctly ONLY by GraphRAG while 11.6% are answered correctly ONLY by RAG, confirming genuine complementarity rather than a strict winner.

**Key mechanism**
- Four GraphRAG classes under identical chunking (256 tokens), embedding (text-embedding-ada-002), top-k=10, optional bge-reranker-large, optional IRCoT iterative retrieval, graphs built with GPT-4o-mini
- KG-based GraphRAG (LlamaIndex): extracts triples, traverses multi-hop KG neighborhoods; triplets-only vs triplets+text variants
- Community-based GraphRAG (Microsoft GraphRAG): hierarchical community summaries; Local search hits entity neighborhoods + low-level reports, Global search hits only high-level summaries
- HippoRAG2: entity-linked graph is auxiliary - selects which text chunks to retrieve, not the retrieved content itself
- RAPTOR (RaptorRAG): recursive clustering + hierarchical summaries, no explicit KG
- Two hybrid strategies: Selection (LLM classifies query fact-based vs reasoning-based, routes to one method) and Integration (run both, concatenate evidence)

**Main findings**
- NQ F1 (single-hop): RAG 64.78 > Community-Local 63.01 > HippoRAG2 61.03 > RaptorRAG 60.04 > Community-Global 54.48 > KG Triplets+Text 50.27 > KG Triplets-only 34.28
- HotpotQA F1 (multi-hop): HippoRAG2 63.01 > Community-Local 61.66 > RaptorRAG 61.31 > RAG 60.04 > Community-Global 45.16 > KG Triplets+Text 42.60 > KG Triplets-only 25.02
- KG-based GraphRAG's ceiling is coverage, not retrieval: only 65.8% of HotpotQA answer entities and 65.5% of NQ answer entities appear in the constructed KG at all
- Community-GraphRAG (Global) spikes hallucination risk on no-answer queries - Null accuracy 19.27 vs RAG's 96.01 on MultiHop-RAG - while still winning Comparison (64.02) and Temporal (53.34) queries that need corpus-level aggregation
- Graph construction quality dominates architecture choice: MultiHop-RAG overall accuracy (Llama-3.1-70B) climbs 65.77 (RAG, no graph) -> 71.17 (GPT-4o-mini graph) -> 75.08 (GPT-4o graph); Temporal jumps 25.73 -> 49.06 -> 58.49
- Selection and Integration hybrids beat the best single baseline by 1.1% and 6.4% respectively on MultiHop-RAG (Llama-3.1-70B)
- Cost (MultiHop-RAG): RAG builds in 135s / retrieves in 1724s / 127MB; KG-GraphRAG builds in 7702s / retrieves in 14434s / 117MB; Community-GraphRAG builds in 5560s / retrieves in 1249s / 165MB
- Summarization: chunk-retrieving methods (RAG, RaptorRAG, HippoRAG2) beat KG/Community-GraphRAG on ROUGE-2/BERTScore against human references because they preserve original text; Integration does not reliably help summarization
- LLM-as-judge summarization evaluation shows strong position bias - reversing presentation order flips preferences, undercutting prior judge-based GraphRAG wins

**Key takeaways**
- Direct support for R47-H501's contrarian framing: RAG's margin is largest exactly where H501 predicts graphs help least - detail-oriented, spec-heavy, exact-answer queries (NovelQA detail subset avg: RAG 55.28 vs Community-Global 30.89 vs KG-Triplets+Text 33.60)
- KG-based GraphRAG fails on coverage, not mechanics - roughly a third of gold answer entities are simply missing from the constructed graph, a ceiling no query-time fix lifts
- Global/aggregate retrieval answering confidently on no-evidence (Null) queries is a concrete warning for KGF's abstention/gap-ledger design
- Extraction/construction fidelity moves downstream accuracy more than which GraphRAG architecture is chosen
- Neither paradigm dominates; the paper's own prescribed fix is query-type routing (Selection/Integration), structurally validating KGF's use-case-regime doctrine over a single global retrieval architecture

**Tags**: #RAGvsGraphRAG #Benchmark #MultiHopQA #GraphConstruction #HybridRetrieval

**Source**: https://arxiv.org/abs/2502.11371. Local: [paper] RAG vs GraphRAG, 2025.pdf

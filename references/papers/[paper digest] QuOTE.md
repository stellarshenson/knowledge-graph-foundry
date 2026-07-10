**QuOTE: Question-Oriented Text Embeddings, Neeser, Latimer, Khatri, Latimer, Ramakrishnan (Virginia Tech), 2025-02**

The RAG-era formalization of ingest-time hypothetical question indexing ("reverse HyDE"). For each chunk an LLM generates the questions the chunk can answer; each question is concatenated with its chunk and stored as a separate vector entry, so query time is near-pure question-to-question matching. Top-1 context accuracy rises **67.11% → 77.65% on SQuAD (+10.5)**, **32.92% → 38.00% on Natural Questions (+5.1)**, and full-match@20 on MultiHop-RAG **22.50% → 35.00% (+12.5)** over naive chunk RAG. Indexing cost is **~16x** naive (170.3s vs 10.4s on SQuAD) but one-time; query latency **141 ms vs 1,274 ms for HyDE**, which pays the LLM call per query instead.

**Key mechanism**
- Prompt an LLM per chunk to generate a set of answerable questions (best results ~10 questions/chunk; 5-20 pushes partial-match above 50-60%, diminishing returns past 10-15)
- Embed each (question + chunk) concatenation as its own index entry - multiple aliases per chunk in the same vector space
- Query time: over-retrieve top-(k x M), deduplicate by source chunk id, return top-k distinct chunks
- Cheap generators suffice: llama3.2-3b stays within a few points of gpt-4o-mini (>70% top-1)

**Main findings**
- SQuAD C@1 +10.5, NQ C@1 +5.1, MultiHop-RAG full@20 +12.5 points over naive RAG
- Equals or beats HyDE accuracy at ~1/9 the query latency - the same alignment idea, paid at ingest instead of per query
- Question count is a measured budget dial with dataset-dependent optimum; LLM-decides-count underperforms fixed count on NQ (38.31% top-1)
- Multi-hop remains hard - absolute full-match numbers stay modest even with large relative gains

**Key takeaways**
- Question-to-question matching demonstrably closes the query/declarative-content embedding mismatch, especially for ambiguous or context-dependent chunks
- Over-retrieve-then-dedup by source is the standard query-time pattern when one chunk owns many generated aliases
- Ingest-time generation dominates query-time generation (HyDE) on latency at equal or better accuracy - the cost argument for foundry-style systems

**Tags**: #QuOTE #HypotheticalQuestions #QuestionIndexing #ReverseHyDE #RAG

**Source**: https://arxiv.org/abs/2502.10976. Local: [paper] QuOTE, 2025-02.pdf

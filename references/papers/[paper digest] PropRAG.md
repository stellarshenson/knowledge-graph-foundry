# PropRAG: Guiding Retrieval with Beam Search over Proposition Paths

**Authors**: Jingjin Wang, Jiawei Han (UIUC)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2504.18070

**Publication date**: 2025-04-25 (first arXiv version; EMNLP 2025)

## Summary

- Replaces the triple layer of HippoRAG-2-style graphs with **context-rich propositions as implicit hyper-edges**: entities within one proposition are fully connected through the proposition node; propositions link when they share (or have synonymous) entities
- Core diagnosis: triples suffer **context collapse** - S-P-O fragmentation drops n-ary relations, temporal qualifiers, and joint participation (their example: three co-authors become three disconnected pairwise triples)
- Zero-shot Recall@5: **MuSiQue 77.3, 2Wiki 93.7, HotpotQA 97.0, PopQA 55.3** - beats HippoRAG 2 (MuSiQue 74.7) on the same benches; top F1 52.4 on MuSiQue
- Online retrieval is **LLM-free beam search over proposition paths**: multi-hop retrieval reformulated as finding the best path of interconnected propositions scoring against the query via pre-computed embeddings - no per-query LLM filter (contrast HippoRAG 2's recognition-memory LLM call)
- Offline indexing uses Llama-3.3-70B-Instruct to extract propositions; all context fidelity is paid at ingest, none at query - the retrieval-first cost profile
- Explicitly positions against PPR: PPR ranks nodes by proximity/centrality but never constructs or evaluates an actual reasoning PATH

**Relevance to Knowledge Graph Foundry**: Direct published evidence that the proposition layer can be the PRIMARY graph substrate, not a side index - and that LLM-extracted (paraphrase-risk) propositions beat triples on the very benches KGF targets. KGF's deterministic render-from-graph propositions (faithful by construction) are the trustworthiness-preserving counter-design; the open question PropRAG raises is whether KGF's relationship-level granularity re-introduces exactly the context collapse PropRAG measured.

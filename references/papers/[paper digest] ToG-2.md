# Think-on-Graph 2.0: Deep and Faithful LLM Reasoning with Knowledge-guided Retrieval Augmented Generation (ToG-2)

**Authors**: Shengjie Ma, Chengjin Xu, Xuhui Jiang, Muzhi Li, Huaren Qu, Cehao Yang, Jiaxin Mao, Jian Guo

**arXiv link (source for re-download)**: https://arxiv.org/abs/2407.10805

**Publication date**: 2024-07-15 (first arXiv version)

## Summary

- Agentic, iterative retrieval that alternates between a knowledge graph and a text corpus, using each to guide the other (graph structure narrows passage search; passages verify and expand graph exploration)
- Runs a beam search over the graph: at each step the LLM scores and keeps the top candidate entities/relations, then retrieves and reads passages tied to them before deciding whether to continue
- Tight graph-text loop yields deeper, more faithful multi-hop reasoning than one-shot retrieval, reducing hallucination
- SOTA on 6 of 7 evaluated datasets using GPT-3.5 as the backbone
- +5.51% improvement on HotpotQA over strong baselines
- Cost of depth: ~5.4 API calls and 27.3s per query vs 1 call / 10.2s for naive RAG - a real latency/cost tradeoff
- Lifts a weaker LLaMA-2-13B backbone to roughly GPT-3.5-level performance, showing the retrieval loop compensates for model capacity

**Relevance to Knowledge Graph Foundry**: Its alternating graph+passage agentic retrieval is a higher-cost, higher-faithfulness query mode KGF could offer on top of single-shot PPR when a query needs deep multi-hop reasoning, with the API-call/latency budget made explicit.

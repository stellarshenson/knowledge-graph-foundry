# AttnComp: Attention-Guided Adaptive Context Compression for Retrieval-Augmented Generation

**Authors**: Lvzhou Luo, Yixuan Cao, Ping Luo

**arXiv link (source for re-download)**: https://arxiv.org/abs/2509.17486

**Publication date**: 2025-09-22 (first arXiv version)

## Summary

- **17x compression rate** on average across five QA benchmarks while lifting accuracy **1.9 points** over the uncompressed baseline - every other compression baseline tested (RECOMP-ext, LongLLMLingua, CompAct, Provence) loses at least 3 accuracy points
- On multi-hop QA (HotpotQA, 2WikiMultiHopQA, MuSiQue), which needs cross-document integration, AttnComp gains **3.3 points** average accuracy over uncompressed retrieval and beats the next-best extractive method (Provence) by **8.8 points** on 2WikiMultiHopQA
- End-to-end RAG latency drops to **49%** of the uncompressed baseline (0.91s compression + 0.16s generation vs 2.18s uncompressed); CompAct's abstractive summarization reaches 80x compression but costs 41.30s total due to multiple LLM calls
- Mechanism: reuses the first L=13 transformer layers of the reader LLM (Llama-3.1-8B-Instruct) plus one added cross-attention layer (H=16 heads) to score query-to-document attention, then a Top-P algorithm retains the fewest top-scoring documents whose cumulative attention (plus the instruction's score) exceeds threshold p=0.95 - adaptively landing anywhere from 0 to 23 retained documents per query (HotpotQA averages 7.5, PopQA averages 3.7)
- Only ~0.5% of parameters are updated during fine-tuning (the cross-attention layer only, base layers frozen); training data is 8,000 HotpotQA examples with 100 documents each, 2,000 of which have zero relevant documents, built via an automated label-then-verify pipeline rather than manual annotation
- Confidence estimation is a free byproduct: instruction attention score s_ins acts as a proxy for retrieval quality (confidence = 1 - s_ins) - instances in the bottom confidence decile average F1 0.13 vs 0.91 in the top decile, Pearson correlation 0.35 between confidence and F1
- Middle-layer ablation (Table 2) confirms L=13/15 layers are the sweet spot pre-fine-tuning (7 and 23/31-layer configs score far worse); fine-tuning substantially lifts accuracy and compression at every depth
- Grounded in an attention observation study: specific middle-layer heads track evidence sentences in the LooGLE benchmark, attention concentrates more under short-dependency (single-fact) queries and spreads out under long-dependency (multi-hop) queries, and attention to the context's initial token rises as overall relevance drops (consistent with attention-sink behavior)

**Relevance to Knowledge Graph Foundry**: AttnComp's attention-derived confidence score (1 - instruction attention) is a training-free reliability signal computed for free during retrieval-time inference, directly relevant to H382's calibrated context-escalation gate - it could serve as an additional or alternative feature alongside KGF's existing calibration inputs to decide when to escalate context rather than answer from a thin retrieval set.

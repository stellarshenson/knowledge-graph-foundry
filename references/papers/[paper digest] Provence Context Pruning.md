# Provence: Efficient and Robust Context Pruning for Retrieval-Augmented Generation

**Authors**: Nadezhda Chirkova, Thibault Formal, Vassilina Nikoulina, Stéphane Clinchant (NAVER LABS Europe)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2501.16214

**Publication date**: 2025-01-27 (first arXiv version)

## Summary

- On Natural Questions, Provence with the unified reranker prunes **76.0%** of retrieved context while lifting LLM-judged QA score from 71.8 (full context) to **72.4** - on PopQA it prunes **75.8%** while lifting the score from 57.8 to **59.5**, evidence that pruning removes noise rather than just tokens
- On HotpotQA the same configuration prunes **82.4%** of context for a **1.0-point** score drop (57.0 to 56.0) - the paper reports Provence achieves the highest QA performance of any pruning method at matched compression ratios across all tested domains (NQ, HotpotQA, TydiQA, PopQA, SyllabusQA, BioASQ, RGB)
- Standalone pruning runs in **25s** for 50 samples (top-5 documents, batch size 1) versus **194s** for LongLLMLingua and **499s** for abstractive RECOMP, at **7.9e14 MFLOPS** versus LongLLMLingua's 5.4e16 MFLOPS
- With the reranker unified into the same model, pruning is folded into a step the RAG pipeline already runs, so its marginal cost is near zero; at **49%** compression, end-to-end generation speeds up **1.2x-1.4x** at batch size 1 and **1.9x-2x** at batch size 256 across LLama-2-7B, LLama-2-13B, and SOLAR-10.7B generators
- A single fixed threshold T generalizes out-of-the-box: pruning ratio self-adjusts from **50% to 80%** depending on the dataset without per-dataset tuning, because the model outputs a calibrated per-sentence relevance probability rather than a fixed top-N or percentage
- Mechanism: reformulates context pruning as binary sequence labeling (0/1 per token, rounded to whole sentences) over a lightweight DeBERTa-v3 model, trained on silver labels from Llama-3-8B-Instruct instructed to answer-and-cite (citation produced **~90%** of the time, filtered otherwise) so relevance detection is grounded in actual answering behavior rather than a separate relevance-judgment prompt
- Unification with reranking is the second key mechanism: because a cross-encoder reranker and a context pruner share the same architecture and input (query + passage), Provence is initialized from and jointly fine-tuned with a DeBERTa-v3 reranker, preserving reranking quality (NQ R@5 84.4 vs 83.0 baseline, MS MARCO MRR@10 40.6 vs 40.5, mean BEIR nDCG@10 55.9 vs 55.4) while adding pruning for free
- Robust to context granularity: trained only on variable-length passages (1-10 sentences), it holds performance when tested on fixed chunk sizes it never saw - e.g. NQ at 6-sentence chunks scores 68.1 pruned vs 68.3 full context at 50% compression, and HotpotQA at the same granularity slightly improves (55.1 pruned vs 54.6 full) at 55% compression

**Relevance to Knowledge Graph Foundry**: Provence's near-zero-cost pruning (folded into the reranking step KGF's retrieval pipeline already runs) and its self-calibrating per-sentence relevance probability are a direct architectural pattern for the post-retrieval side of H382's calibrated context-escalation gate - rather than escalating on a coarse retrieval-confidence signal, a Provence-style unified reranker-pruner could trim PPR-seeded and Leiden-community context down to the sentences that actually answer the query before the gate decides whether more context is needed, cutting tokens fed to the local vLLM gpt-oss-120b generator without the accuracy loss the paper shows on comparable methods.

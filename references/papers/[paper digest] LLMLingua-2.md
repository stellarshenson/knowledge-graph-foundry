# LLMLingua-2: Data Distillation for Efficient and Faithful Task-Agnostic Prompt Compression

**Authors**: Zhuoshi Pan, Qianhui Wu, Huiqiang Jiang, Menglin Xia, Xufang Luo, Jue Zhang, Qingwei Lin, Victor Rühle, Yuqing Yang, Chin-Yew Lin, H. Vicky Zhao, Lili Qiu, Dongmei Zhang

**arXiv link (source for re-download)**: https://arxiv.org/abs/2403.12968

**Publication date**: 2024-03-19 (v2: 2024-08-12)

## Summary

- Recasts prompt compression as binary token classification (preserve/discard) trained on a GPT-4-distilled extractive dataset, replacing the information-entropy metric used by prior task-agnostic methods (LLMLingua, Selective-Context)
- Compression dataset built from 5,169 MeetingBank transcripts, chunk-wise compressed by GPT-4, yielding an average 2.57x compression ratio (3,635 to 1,415 tokens); a data annotation algorithm back-projects the compressed text onto word-level labels in the original, with an Alignment Gap filter discarding the worst 10% of examples for quality control
- Classifier is a fine-tuned Transformer encoder (XLM-RoBERTa-large for LLMLingua-2, multilingual-BERT for LLMLingua-2-small) using full bidirectional context, trained 10 epochs at learning rate 1e-5
- In-domain (MeetingBank, GPT-3.5-Turbo target): EM 86.92 vs LLMLingua 67.52 and Selective-Context 66.28, at a comparable 3.1x compression ratio (970 vs 3,003 original tokens)
- Out-of-domain generalization (LongBench, 2000-token constraint, task-agnostic methods): average score 39.1 vs LLMLingua 34.6 and Selective-Context 24.8, despite training only on meeting transcripts
- Latency on a V100-32G GPU: LLMLingua-2 compression itself takes 0.4-0.5s vs 1.5-2.9s for LLMLingua and 15.5-15.9s for Selective-Context; end-to-end speedup reaches 1.6x-2.9x across 1x-5x compression ratios, with 3x-6x faster compression and 8x lower GPU memory than existing methods
- With Mistral-7B as target LLM, LLMLingua-2 compressed prompts (76.22 EM on MeetingBank QA) outperform the original uncompressed prompt (66.95 EM), suggesting compression can remove noise as well as redundancy
- Compression strategy: given target ratio 1/τ, retain the top τN words by preserve-probability while keeping original word order, guaranteeing faithfulness (no paraphrasing, no hallucinated content) since it is purely extractive

**Relevance to Knowledge Graph Foundry**: KGF's context-escalation gate (H382) and community-segmentation work (R48) both grapple with token budget vs information density when assembling retrieval context; LLMLingua-2's task-agnostic, order-preserving extractive compression is a candidate lever for shrinking PPR-seeded or community-summary context blocks before they reach the local vLLM gpt-oss-120b server, without the entropy-metric or unidirectional-context weaknesses of its LLaMA-based predecessor.

# FastKV: Decoupling of Context Reduction and KV Cache Compression for Prefill-Decoding Acceleration

**Authors**: Dongwon Jo, Jiwon Song, Yulhwa Kim, Jae-Joon Kim

**arXiv link (source for re-download)**: https://arxiv.org/abs/2502.01068

**Publication date**: 2025-02 (first arXiv version)

## Summary

- **1.82x** prefill speedup and **2.87x** decoding speedup vs a full-context baseline, with LongBench accuracy staying within about 1 point of full-context
- LongBench average on LLaMA-3.1-8B-Instruct: full-context 50.19 vs FastKV 48.47 (10% KV retention) / 49.07 (20% KV retention) - both above SnapKV's decoding-only 48.73/49.43 and far above prefill-aware GemFilter (38.61/42.39) and PyramidInfer (39.32) at similar prefill-compute budgets
- RULER average (LLaMA-3.1-8B-Instruct, 8K-128K): FastKV 75.6 vs full-context 86.0, SnapKV 73.6, GemFilter 69.6 - best among methods that also cut prefill compute
- Needle-in-a-Haystack score: FastKV 99.9 vs full-context 99.0, SnapKV 99.0, GemFilter 95.8 - FastKV essentially loses nothing here despite the compression
- Key mechanism: a single Token-Selective Propagation (TSP) layer placed mid-stack (layer 15 of 32 for LLaMA-3.1-8B) forwards only the most salient tokens (default TSP rate 20%, yielding 60% prefill compute) to later layers, while every layer independently prunes its own KV cache to a separate retention rate (evaluated at 10% and 20%) - decoupling how much context is computed during prefill from how much KV is kept for decoding
- Motivating observation: attention-based token importance is unstable across the early decoder layers but stabilizes from roughly the middle layers onward, so early layers must see the full context while later layers can safely share a pruned token subset
- Prior prefill-aware methods (GemFilter, PyramidInfer) couple the two reductions - forcing all layers, including unstable early ones, onto the same reduced token set - which FastKV identifies as the accuracy-degradation source it removes

**Relevance to Knowledge Graph Foundry**: KGF's context-escalation gate (H382) and local vLLM gpt-oss-120b serving both pay a real prefill/decode cost when a query escalates to wider community or multi-hop context; FastKV's layer-dependent, decoupled prefill/KV compression is a serving-side lever (not a retrieval-design one) for cutting that cost on long escalated contexts without touching PPR seeding, Leiden segmentation, or the retrieval pipeline itself.

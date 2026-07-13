# From Tokens to Layers: Redefining Stall-Free Scheduling for MoE Serving with Layered Prefill

**Authors**: Gunjun Lee, Jiwon Kim, Jaiyoung Park, Younjoo Lee, Jung Ho Ahn (Seoul National University)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2510.08055

**Publication date**: 2025-10 (arXiv id 2510.08055); PDF header shows v2 dated 2026-04-16, accepted to the 9th MLSys Conference 2026

## Summary

- Chunked prefill (splitting long prompts along the token dimension and interleaving with decode) inflates MoE expert weight loads by up to **39%** and per-token energy by up to **22%** because every chunk re-traverses the same layers and reloads experts
- Proposes **layered prefill**: partitions the decoder stack into Nlg contiguous layer groups and treats the layer dimension, not the token dimension, as the scheduling unit - prefill for one layer group runs alongside decode for the rest, completing in exactly Nlg iterations with each layer traversed only once
- On Qwen3-30B-A3B / arXiv-summarization workload, layered prefill cuts mean TTFT from 2.80s to 1.24s and p99 TTFT from 8.65s to 4.10s at 1.3 req/s, versus chunked prefill (512-token chunks)
- Expert weight load traffic (100-request trace) drops **12%** on ShareGPT and **39%** on arXiv-summarization versus chunked prefill, with the larger reduction on long-prompt workloads where chunking would otherwise force many redundant reloads
- End-to-end latency for a single request falls from 9.4s to 5.5s (**-41%**), and layered prefill sustains near-100% SLO attainment to higher request rates than chunked prefill on both Qwen3-30B-A3B and GPT-OSS-20B across arXiv and ShareGPT workloads
- Energy per output token drops **20-22%** at matched or higher sustainable request rates: Qwen3-30B-A3B goes from 56.6 to 44.2 mJ/tok while sustaining 1.6 req/s vs 1.3 req/s (+23% throughput); GPT-OSS-20B goes from 37.4 to 29.8 mJ/tok while sustaining 2.7 vs 2.1 req/s (+29%)
- Broader validation (Table 9) includes gpt-oss-120b (fp4) on H100x2: layered prefill (Nlg=12) cuts mean TTFT from 3.110s to 1.090s and mean TBT from 34.9ms to 20.5ms versus chunked prefill (512-token chunks) on the arXiv workload at 1.2 req/s; on H100x8 the same model sees mean TTFT fall from 1.050s to 0.530s at 3.0 req/s
- Layer-group count Nlg plays the same tuning role chunk size plays in chunked prefill: results validated across A100x2, H100x2, and H100x8, and across Qwen3-30B-A3B, Qwen3-235B-A22B/A23B, GPT-OSS-20B, and gpt-oss-120b

**Key mechanism**: chunked prefill amplifies MoE memory traffic because each token chunk must reload the full expert set for every transformer layer it passes through; layered prefill instead fixes the traversal order at the layer level, so each layer group's experts are loaded exactly once per iteration regardless of how many concurrent requests are in prefill, decoupling MoE weight-reload cost from the chunking granularity needed to keep decode stall-free.

**Relevance to Knowledge Graph Foundry**: KGF serves gpt-oss-120b locally via vLLM for ingest-time extraction and context-escalation; this paper's directly measured gpt-oss-120b numbers (TTFT 3.11s to 1.09s on H100x2, per-token energy and TBT gains from layered over chunked prefill) bear on serving-layer throughput and latency for the H382 calibrated escalation gate and any future batch-ingest scheduling tuning, independent of KGF's own graph-construction and retrieval work.

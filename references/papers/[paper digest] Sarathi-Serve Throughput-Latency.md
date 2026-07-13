# Taming Throughput-Latency Tradeoff in LLM Inference with Sarathi-Serve

**Authors**: Amey Agrawal, Nitin Kedia, Ashish Panwar, Jayashree Mohan, Nipun Kwatra, Bhargav S. Gulavani, Alexey Tumanov, Ramachandran Ramjee (Microsoft Research India / Georgia Tech)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2403.02310

**Publication date**: 2024-03 (first arXiv version; v3 revision 2024-06-17)

## Summary

- Sarathi-Serve achieves **2.6× higher serving capacity** for Mistral-7B on a single A100 and up to **3.7× higher serving capacity** for Yi-34B on two A100s, compared to vLLM
- With pipeline parallelism on Falcon-180B (two nodes, 100 Gbps Ethernet), it delivers up to **5.6× gain in end-to-end serving capacity**
- Under strict P99 time-between-tokens (TBT) SLO, Sarathi-Serve sustains up to **4.0× higher load than Orca and 3.7× higher than vLLM** (Yi-34B, openchat_sharegpt4); for LLaMA2-70B with pipeline parallelism, gains reach **6.3× vs Orca and 4.3× vs vLLM**
- Naive hybrid batching (mixing prefill and decode without chunking) causes up to **28.3× increase in TBT latency** versus a decode-only batch - the core problem chunked-prefills solves
- Tile-quantization effect: using a prefill chunk size of 257 instead of 256 tokens increases prefill time by **32%**, because GPU matmul tiling favors chunk sizes divisible by the tile size
- Linear operators (not attention) dominate runtime, contributing **more than 80% of total time** even at high sequence lengths, motivating the paper's focus on linear-layer arithmetic intensity
- Falcon-180B: pipeline-parallel Sarathi-Serve increases capacity **4.3× over vLLM's tensor-parallel-only config and 3.6× over vLLM's hybrid-parallel config** under strict SLO; cross-node tensor parallelism has **~2× higher median decode latency** than pipeline parallelism
- Mistral-7B: **3.5× higher capacity than vLLM** under a strict 100ms SLO using a small token budget (512); Yi-34B: **1.65× higher capacity** than vLLM under a relaxed 1s SLO using a larger token budget (2048)

**Key mechanism**
- Chunked-prefills: split a prefill request into near-equal compute-sized chunks processed over multiple scheduling iterations, rather than one large prefill pass
- Stall-free scheduling: every iteration first packs all ongoing decode tokens into the batch, then fills remaining "token budget" with prefill chunks from new or in-progress requests - decodes are never paused to let a prefill finish
- Token budget is the tunable knob: smaller budgets favor tail latency (strict SLO), larger budgets favor throughput (relaxed SLO); determined via one-time profiling or the Vidur simulator
- Exploits the memory-bound/compute-bound asymmetry: decode batches have low arithmetic intensity (memory-bound, GPU compute idle) while prefill is compute-bound, so coalescing prefill chunks into decode batches raises compute utilization without adding decode latency
- Uniform-sized hybrid batches also reduce pipeline-parallel bubbles, since micro-batch runtimes stop varying wildly between prefill-heavy and decode-heavy iterations
- Implemented on top of vLLM (PagedAttention retained); open-sourced at github.com/microsoft/sarathi-serve

**Relevance to Knowledge Graph Foundry**: KGF's local vLLM gpt-oss-120b serving sits directly on the throughput-latency tradeoff Sarathi-Serve targets - chunked-prefills and stall-free scheduling (or a serving stack that implements them) would let large-context extraction and context-escalation calls (H382 gate) share GPU capacity with concurrent decode-heavy generation without stalling either, which matters as ingest concurrency scales past the R30-tuned c64 rung.

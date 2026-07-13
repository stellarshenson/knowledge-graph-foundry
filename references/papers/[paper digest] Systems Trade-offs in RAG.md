# Towards Understanding Systems Trade-offs in Retrieval-Augmented Generation Model Inference

**Authors**: Michael Shen, Muhammad Umar, Kiwan Maeng, G. Edward Suh, Udit Gupta (Cornell University, NVIDIA, Pennsylvania State University)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2412.11854

**Publication date**: 2024-12-16

## Summary

- TTFT latency nearly doubles with RAG, from **495ms to 965ms**, with the retrieval stage alone accounting for **~35% of total TTFT latency**
- Retrieval and re-ranking make up **41% of end-to-end latency** and **45-47% of TTFT latency** in the paper's setup
- Tail latency for retrieval is disproportionately worse than other stages: p99-p50 gap of **50ms for HNSW-SQ** and **60ms for IVF-SQ**, versus a minimal gap for encoding and prefill
- An aggressive re-retrieval stride of 4 tokens pushes end-to-end latency to **nearly 30 seconds**, with RAG-unique components (retrieval + additional prefill) accounting for **~97%** of that latency (36% retrieval, 45% additional prefill)
- Retrieval index comparison at 100M chunks: HNSW-SQ reaches **0.87 recall** at **166GB** storage; IVF-SQ reaches **0.86 recall** at **71GB** (2.3x less memory than HNSW-SQ); IVF-PQ caps at **~0.61 recall** but only **23GB** (7.2x less memory than HNSW-SQ)
- A billion-chunk datastore requires roughly **1TB** of index memory for the accuracy-oriented HNSW-SQ index
- Throughput degrades by up to **20x** as the datastore grows from 1 million to 100 million chunks
- At large batch sizes, HNSW-SQ throughput exceeds **300 QPS** versus **150 QPS for IVF-SQ** and **110 QPS for IVF-PQ**, a **2.2x** gap at scale
- IVF indices can hit retrieval latencies as low as **30ms** (10x lower than HNSW-SQ) by trading away recall via nProbe

**Key mechanism**: The paper decomposes the RAG inference pipeline into offline datastore/index construction (chunking, embedding, index type - HNSW vs IVF, with quantization variants SQ/PQ) and online inference (query encoding, ANN search, re-ranking, context integration, retrieval striding). It benchmarks a concrete pipeline - BGE-Large encoder, Gemma-2 9B generator, FAISS indices over a 100M-chunk Common Crawl subset, TriviaQA queries - to isolate where systems overhead accumulates, showing that accuracy-oriented indices (HNSW) buy recall and throughput at large batch sizes at the cost of memory, while memory-efficient indices (IVF-PQ/SQ) sacrifice recall or scale poorly, and that retrieval frequency (stride) is a first-order lever on end-to-end latency independent of index choice.

**Relevance to Knowledge Graph Foundry**: KGF's PPR-seeded retrieval (dense@16=0.854) sits downstream of exactly this index/latency trade-off surface - the paper's finding that retrieval, not prefill or decoding, dominates both average and tail latency argues for treating KGF's Neo4j/vector retrieval hop as the primary latency budget item when reasoning about H382's context-escalation gate or scaling the corpus past the current rung sizes; the recall-vs-memory-vs-throughput trade-off between HNSW and IVF variants is also a direct analogue for any future decision on how KGF indexes entity/community embeddings at larger scale.

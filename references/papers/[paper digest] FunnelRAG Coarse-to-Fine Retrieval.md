**FunnelRAG: A Coarse-to-Fine Progressive Retrieval Paradigm for RAG (2024)**

FunnelRAG replaces the flat, single-shot retrieval-then-rerank pipeline with a three-stage funnel - clustered document, document, passage - each stage shrinking the candidate count while increasing retriever capacity (BM25/lightweight scorer -> cross-encoder -> FiD cross-attention). On NQ and TQA, the progressive pipeline **matches flat retrieval's Answer Recall (75.43% vs. 75.90% on NQ; 80.69% vs. 81.29% on TQA)** while cutting end-to-end retrieval time cost by **43% on NQ and 36% on TQA** (2.97s vs. 5.25s; 3.47s vs. 5.41s), by funneling from a 21M-passage corpus down through 600K clustered documents to a final handful of passages instead of scoring all 21M passages directly.

**Key mechanism**
- Retrieval stage: documents are offline-clustered into ~600K clusters (max size S=4K tokens, tuned via sweep - 8K brings negligible extra gain over 4K, 1K degrades notably); a cross-encoder pre-ranks clusters against the query, so the corpus the query first meets is hundreds of clusters, not 21M passages ("the needle case, not the haystack")
- Pre-ranking stage: top clusters are segmented into document-level units and scored by a cross-encoder to select top-N documents
- Post-ranking stage: documents are segmented into passages only at this late point ("Later Chunking", after JinaAI 2024) and scored via a Fusion-in-Decoder (FiD) model's cross-attention - the top-lr representative tokens per passage (by decoder cross-attention score) approximate the passage's relevance without full sequence scoring
- Local-to-global (L2G) distillation bridges the granularity gap between adjacent stages: post-ranking passage scores are aggregated up to their parent document via α·max + (1-α)·mean, and the preceding (pre-ranking) stage is distilled toward this aggregated signal so successive stages stay mutually consistent despite operating at different unit sizes
- Retriever capacity increases stage by stage (cheap scorer for the retrieval stage, cross-encoder for pre-ranking, FiD for post-ranking), spreading the workload that flat retrieval dumps entirely on one retriever over the full corpus

**Main findings**
- Fine-grained retrieval units degrade far less under aggressive cutoff than coarse-grained ones: at a top-20% cutoff on NQ, fine-grained retrieval drops only 2.25% of its original performance vs. 37.93% for coarse-grained - the core motivation for later chunking
- High-capacity rerankers consistently beat low-capacity ones at matched fine granularity, and the gain grows as the cutoff position shrinks (+5.45% Answer Recall at cutoff@10% on NQ for bge-reranker-v2-m3 over BM25)
- Progressive retrieval achieves Answer Recall within 0.5-0.6 points of the best flat-retrieval configuration on both NQ and TQA, at 36-43% lower time cost
- Query tokens contribute a modest but consistent improvement to post-ranking scores: +5.17% at Top-1 on TQA down to +0.11% at Top-4 on NQ
- Progressive retrieval also improves contextual integrity (a lower-is-better fragmentation measure): 1.259 vs. 1.330 on NQ, 1.494 vs. 1.760 on TQA, vs. flat retrieval

**Key takeaways**
- A staged, granularity-increasing pipeline with capacity increasing per stage load-balances retrieval instead of forcing one retriever to score the entire corpus at once
- "Later chunking" - deferring fine-grained segmentation to the stage where the candidate pool is already small - preserves contextual integrity better than chunking everything up front at flat, constant granularity
- L2G score aggregation (max+mean blend across stages) is the mechanism that keeps a multi-granularity pipeline's stages trained consistently with each other, rather than each stage optimizing an independent objective

**Relevance**
- The coarse-to-fine funnel (cluster -> document -> passage, capacity increasing per stage) is a directly transferable pattern for a topology-retrieval variant of KGF: community/cluster-level pre-filtering before entity/chunk-level scoring shrinks the candidate set the same way it shrinks 21M passages to hundreds of clusters, without sacrificing fine-grained final precision
- The L2G aggregation trick (blend downstream scores back into upstream stage scoring) is a reusable pattern if KGF stages community-level and entity-level match scores together within a single ranked-retrieval pass rather than treating them as separate, disconnected phases

**Tags**
- #ProgressiveRetrieval
- #CoarseToFine
- #RAG
- #RetrievalGranularity
- #TopologyRetrieval

**Source**
- Download: https://arxiv.org/pdf/2410.10293
- Local: [paper] FunnelRAG Coarse-to-Fine Retrieval, 2024.pdf

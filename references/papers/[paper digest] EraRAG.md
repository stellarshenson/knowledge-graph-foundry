**EraRAG: Efficient and Incremental Retrieval Augmented Generation for Growing Corpora, Zhang et al., 2025-06**

The published template for LOCALIZED maintenance of a hierarchical derived index. EraRAG replaces RAPTOR-style global clustering (non-incremental: any insert can reshuffle every cluster) with hyperplane-based LSH bucketing whose hash functions are FROZEN at build time, so a new chunk deterministically lands in one bucket and only that bucket's summary chain is recomputed. Versus re-building baselines it cuts incremental-update token consumption by up to **57.6%** (vs RAPTOR on PopQA) and graph re-construction time by up to **77.5%** (vs RAPTOR on QuALITY); single-document insertion completes in **~20 seconds** - **one order of magnitude** faster than RAPTOR/HippoRAG updates and **two orders** faster than GraphRAG - while QA accuracy stays superior (QuALITY **60.25% vs RAPTOR 55.48%** with Llama-3.1-8B; best on 8 of 10 metrics across PopQA, HotpotQA, MuSiQue, MultihopQA).

**Key mechanism**
- Build: embed chunks, project onto random hyperplanes → binary LSH codes → order-preserving buckets; each bucket LLM-summarized; recurse upward into a multi-layer segment tree (RAPTOR-like, but partitioning is hashing, not learned clustering)
- Insert: hash the new chunk with the STORED hyperplanes → exactly one affected bucket; if bucket size exceeds S_max split it, below S_min merge with neighbor - size thresholds bound both summary quality drift and recompute fan-out
- Repair: re-summarize only affected buckets, propagate the change recursively to ancestor summaries; untouched branches are never re-summarized
- The frozen hash function is the trick that makes the derived structure SELF-LOCALIZING: dependency scope of an insert is computable without touching the rest of the index

**Main findings**
- Update cost scales with the size of the affected region, not corpus size; accuracy does not degrade after many incremental rounds vs one-shot full rebuild
- Deterministic bucketing (vs GMM/Leiden re-clustering) is what converts a global derived object into a sum of locally-maintainable derived objects
- Selective re-summarization with upward propagation = DRed-style delta maintenance applied to LLM-generated summaries

**Key takeaways**
- Design derived objects so their dependency footprint is cheap to compute (hash/bucket assignment) - then invalidation is local by construction
- Thresholded split/merge keeps per-object recompute bounded and prevents slow structural drift
- Propagate-upward-only repair is the right pattern for hierarchical generated content (community summaries, cluster reports)

**Tags**: #EraRAG #IncrementalGraphRAG #LSH #SummaryMaintenance #LocalizedRepair

**Source**: https://arxiv.org/abs/2506.20963. Local: [paper] EraRAG, 2025-06.pdf

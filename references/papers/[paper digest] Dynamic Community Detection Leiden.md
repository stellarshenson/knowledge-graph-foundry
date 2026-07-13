# A Starting Point for Dynamic Community Detection with Leiden Algorithm

**Authors**: Subhajit Sahu (IIIT Hyderabad)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2405.11658

**Publication date**: 2024-05-19 (first arXiv version; v4 2024-12-27)

## Summary

- Extends three dynamic-update strategies - Naive-dynamic (ND), Delta-screening (DS), and Dynamic Frontier (DF) - to a multicore Leiden implementation (GVE-Leiden), the first attempt to apply dynamic approaches to Leiden rather than Louvain
- On 12 large real-world graphs (SuiteSparse, 3.07M-214M vertices, 25.4M-3.80B edges) with random 80%/20% insertion/deletion batch updates, ND, DS, and DF Leiden achieve mean speedups of **1.37x, 1.47x, and 1.98x** respectively versus rerunning Static Leiden from scratch
- Speedup is largest for the smallest batch updates (10^-7 of graph edges): ND, DS, DF reach **1.46x, 1.74x, and 3.72x** respectively at that batch size
- Modularity of the dynamically updated communities differs from Static Leiden by no more than **0.002** on average, so the speedup is not bought with materially worse community quality
- Strong-scaling test (batch size fixed at 10^-3 of edges, 1-64 threads on a 64-core AMD EPYC-7742): ND, DS, DF reach **10.2x, 9.9x, 9.0x** speedup over sequential at 32 threads, scaling at a mean rate of **1.6x per doubling of threads**
- Root cause of the modest ceiling on speedup: only about **37%** of Static Leiden's total runtime is spent in the local-moving phase of the first pass - the only phase the dynamic approaches can meaningfully shortcut, since the refinement phase must still run in full to avoid poorly-connected communities
- Key mechanism is selective refinement: track which vertices migrate between communities during local-moving and mark only the source/target communities (not the whole graph) for refinement in the following phase, plus a subset-renumbering procedure to prevent internally disconnected communities when refining only a subset
- DF Leiden (which marks affected vertices via a frontier-style traversal seeded from vertices that actually changed community) consistently outperforms both ND (reprocess everything) and DS (modularity-based screening of a candidate region) across web graphs, social networks, road networks, and protein k-mer graphs

**Relevance to Knowledge Graph Foundry**: KGF's Leiden communities are provenance artifacts (NMI 0.614 with source docs) recomputed statically on each ingest batch; this paper's selective-refinement/affected-vertex tracking is the direct blueprint for incremental Leiden updates as the graph grows post-RC, avoiding a full recompute per ingest while keeping modularity within 0.002 of the from-scratch result - relevant once R48-style community segmentation work moves from batch to incremental ingestion.

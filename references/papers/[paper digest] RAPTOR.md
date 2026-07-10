**RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval, Sarthi et al. (Stanford), 2024-01**

Index-time generation of a recursive summary tree whose every node is a first-class retrieval target. Chunks are embedded, clustered (UMAP + GMM with BIC model selection, soft assignment), each cluster LLM-summarized, and the process recurses upward; retrieval searches all tree levels at once. With GPT-4 as reader, QuALITY accuracy reaches **82.6% vs prior SOTA 62.3%** (+20 absolute; QuALITY-HARD **76.2% vs 54.7%**); QASPER **55.7% F1**; NarrativeQA ROUGE-L **30.8 vs 21.6** for prior recursive summarization. Summaries average **131 tokens from 6.7 children of ~86 tokens each (~72% compression)**; build cost and tokens scale linearly with corpus length.

**Key mechanism**
- Bottom-up tree: leaf chunks → UMAP dimensionality reduction → GMM soft clustering (BIC picks cluster count) → LLM summary per cluster → repeat on summaries
- All nodes (leaves and every summary level) are embedded into ONE flat vector index
- "Collapsed tree" retrieval - rank all nodes of every level against the query and take top nodes to a ~2000-token budget - beats level-by-level tree traversal
- The query itself selects the abstraction level: broad questions hit high-level summaries, detail questions hit leaves

**Main findings**
- QuALITY 82.6% (+20.3 absolute over SOTA); QASPER +1.8-4.5 F1 over DPR, +5.5-10.2 over BM25; NarrativeQA METEOR SOTA
- Collapsed-tree (flat index over mixed granularities) > hierarchical traversal - let similarity decide the level
- Linear build-time and token scaling to 80k-token documents; summarization adds a bounded fraction of corpus tokens (~x1.5 index units in the geometric limit)
- Gains compound with stronger readers (GPT-4 > GPT-3 > UnifiedQA)

**Key takeaways**
- Generated abstractive objects (summaries) recover what chunk retrieval structurally cannot: theme-level and cross-chunk questions
- Mixing granularities in one embedding index and letting the query pick works better than routing logic
- Soft clustering matters - a chunk can serve multiple themes

**Tags**: #RAPTOR #SummaryTree #IndexTimeGeneration #HierarchicalRetrieval #QuALITY

**Source**: https://arxiv.org/abs/2401.18059. Local: [paper] RAPTOR, 2024-01.pdf

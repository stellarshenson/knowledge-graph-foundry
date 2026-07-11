**Plan-on-Graph: Self-Correcting Adaptive Planning of Large Language Model on Knowledge Graphs (PoG), Chen, Tong, Jin, Sun, Ye, Xiong, NeurIPS 2024 (arXiv 2410.23875)**

The best-tuned agentic KG walk - and the paper that publishes the walk's exact token bill. Beats ToG on all 3 datasets: CWQ **75.0 vs 67.6**, WebQSP **87.3 vs 82.6**, GrailQA **84.7 vs 81.4** (GPT-4, Hits@1). Efficiency table (GPT-3.5, per question): CWQ **PoG 13.3 LLM calls / 8,156 tokens / 23.3 s vs ToG 22.6 calls / 9,669 tokens / 96.5 s** - even the OPTIMIZED walk burns ~8k tokens and 13 calls per question.

**Key mechanism**
- Decompose question into sub-objectives (Guidance), then loop: adaptively explore paths (breadth chosen per question, not fixed beam), update Memory (sub-objective status + visited subgraph), Reflect on whether to backtrack and self-correct erroneous paths
- Self-correction = LLM picks which previously-seen entities to backtrack to, guided by sub-objective states - replaces ToG's blind fixed-breadth extension
- Training-free prompting; Freebase KGs

**Main findings**
- Ablations: w/o Memory worst (-4.3 CWQ), then w/o Reflection (-3.8), w/o Guidance (-3.1), w/o Adaptive Breadth (-1.9) - the walk's accuracy lives in its bookkeeping, not its breadth
- Cuts ToG's LLM calls by >= 40.8% and output tokens by ~76%, 4x+ speedup - yet still 6.5-13.3 calls per question vs 1-2 for single-shot RAG
- GPT-3.5 PoG beats all fine-tuned baselines on GrailQA zero-shot subset (81.7) - self-correction pays most where no training data exists

**Key takeaways**
- THE adversary cost anchor: the efficiency frontier of published agentic KG walks is ~8k tokens / ~13 LLM calls / ~23 s per question - a single-shot bridge (1 embed + 1 answer call) must be priced against this, not against ToG's naive bill
- Sub-objective decomposition is the transferable single-shot piece: PoG's own ablation shows guidance is worth +3.1 as ONE upfront call - decomposition does not require the walk that follows it
- Memory/reflection machinery is the cost of navigating blind; a graph that materializes multi-hop structure at ingest (HippoRAG-style) makes that machinery redundant

**Tags**: #PlanOnGraph #AgenticRetrieval #SelfCorrection #KGQA #TokenCost #AdversaryBaseline #NeurIPS

**Source**: https://arxiv.org/abs/2410.23875. Local: [paper] Plan-on-Graph, 2024-10.pdf

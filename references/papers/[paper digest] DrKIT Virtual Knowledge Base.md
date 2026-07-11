# DrKIT - Differentiable Reasoning over a Virtual Knowledge Base

**arXiv 2002.10640 (ICLR 2020, Google/CMU, Dhingra et al.)**. Treats a raw text CORPUS as a virtual KB: entity mentions + contextual embeddings stand in for nodes/edges that were never extracted, and a differentiable module traverses "paths of relations" between mentions at query time - multi-hop reasoning over graph structure that exists only implicitly, materialized transiently per query. **+9 points accuracy on MetaQA 3-hop** (cutting the text-vs-KB SOTA gap by **70%**), **+10%** over BERT re-ranking on HotpotQA passage retrieval, **10-100x more queries/second** than existing multi-hop systems.

**Key mechanism**: each hop = sparse TFIDF co-occurrence matrices x maximum inner product search (MIPS) over pre-computed mention encodings; the "edge" between two entities is never stored - it is computed on demand from mention co-occurrence and contextual similarity, then discarded. Pretraining generates hard negatives from an existing KB.

**Main findings**: never-materialized relational structure supports multi-hop composition competitively with an explicit KB; the entire graph is speculative in the strongest sense - inferred at query time, in memory, zero commitment - and this is FASTER than iterative retrieve-read systems because hops are matrix operations.

**Key takeaways for KGF**: published anchor for the query-time transient-subgraph sense of speculative construction: bridges the extractor never materialized can be walked without ever entering the committed graph. Contrast with KGF doctrine: retrieval-first pushes work to ingest; DrKIT is the opposite pole (all structure at query time) and its accuracy ceiling on complex questions shows why KGF commits structure - but a bounded transient bridge layer at retrieval (compute, use, discard, log to gap ledger) needs no trust machinery at all, since nothing is ever committed.

**Tags**: virtual-kb, query-time-construction, transient-subgraph, multi-hop, mips
**Source**: https://arxiv.org/abs/2002.10640 (PDF: `[paper] DrKIT Virtual Knowledge Base, 2020-02.pdf`)

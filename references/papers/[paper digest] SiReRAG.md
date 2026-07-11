# SiReRAG: Indexing Similar and Related Information for Multihop Reasoning

**Authors**: Nan Zhang, Prafulla Kumar Choubey, Alexander Fabbri, Gabriel Bernadett-Shapiro, Rui Zhang, Prasenjit Mitra, Caiming Xiong, Chien-Sheng Wu (Penn State + Salesforce AI Research)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2412.06206

**Publication date**: 2024-12-09 (first arXiv version; ICLR 2025)

## Summary

- **+1.9% average F1** over SOTA indexing methods on MuSiQue, 2WikiMultiHopQA, HotpotQA; **up to +7.8% average F1** when composed with reranking - from indexing BOTH similarity and relatedness instead of one
- Core claim: existing indexes organize data by semantic similarity (RAPTOR-style summary trees, dense retrieval) OR by relatedness (entity-linked graph structure), never both; each alone leaves multihop failures the other would catch
- Similarity side: a RAPTOR-like recursive-summarization tree over chunks
- Relatedness side: extract atomic propositions per chunk via LLM, group propositions by SHARED ENTITIES into "proposition aggregates" (concatenated in original chunk order), build recursive summaries with soft clustering on top - the relatedness tree
- Both trees are flattened into ONE unified retrieval pool; retrieval is flat dense search over the union - no graph traversal at query time
- Propositions themselves are excluded from the relatedness tree (only aggregates and summaries enter the pool) - granularity is controlled at the aggregate level
- Ablations show proposition aggregates are the load-bearing addition: adding them to a similarity-only pool captures most of the gain

**Relevance to Knowledge Graph Foundry**: The nearest published relative of KGF's multi-channel retrieval pool (entities + propositions + passages queried jointly). Its entity-grouped proposition aggregates are a cross-document object KGF does not build: KGF propositions are per-entity sentences, never concatenated into an entity's cross-chunk evidence bundle - exactly the P15 cross-document class. Also evidence that dense/sparse duality generalizes beyond HippoRAG's PPR: SiReRAG gets its gain with NO graph walk, pure pool union.

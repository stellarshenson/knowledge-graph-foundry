# HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models

**Authors**: Bernal Jiménez Gutiérrez, Yiheng Shu, Yu Gu, Michihiro Yasunaga, Yu Su

**arXiv link (source for re-download)**: https://arxiv.org/abs/2405.14831

**Publication date**: 2024-05-23 (first arXiv version)

## Summary

- Models retrieval on the hippocampal indexing theory: an LLM extracts an open KG from the corpus (the "neocortex"), and Personalized PageRank over that KG acts as the hippocampal index for single-shot multi-hop association
- Offline indexing builds an open knowledge graph of entities and relations from all passages via OpenIE
- Query entities seed PPR; the propagated node scores rank passages, enabling multi-hop retrieval in one retrieval step rather than iterative retrieve-read loops
- Synonym edges connect near-duplicate entity nodes when embedding cosine similarity exceeds 0.8, healing extraction variance and linking co-referent entities
- Node specificity (an IDF-like weighting) down-weights over-connected generic nodes during PPR
- Multi-hop evidence recall 87.9-90.9% vs 59.8-64.5% for standard single-step dense RAG - large recall gain on MuSiQue and 2WikiMultiHopQA
- Single-step retrieval is cheaper and faster than iterative multi-hop methods like IRCoT while remaining competitive or better on accuracy
- Establishes the PPR-over-KG retrieval pattern that later graph RAG systems build on

**Relevance to Knowledge Graph Foundry**: This is the foundational PPR-over-KG retrieval paradigm KGF adopts; its cosine>0.8 synonym edges prefigure KGF's Bayesian entity resolution for healing extraction variance.

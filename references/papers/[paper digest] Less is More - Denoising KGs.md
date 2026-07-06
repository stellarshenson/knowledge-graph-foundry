# Less is More: Denoising Knowledge Graphs for Retrieval Augmented Generation

**Source**: https://arxiv.org/abs/2510.14271
**Authors**: Yilun Zheng, Dan Yang, Jie Li, Lin Shang, Lihui Chen, Jiahao Xu, Sitao Luan
**Venue/Date**: Preprint (NTU / Nanjing / Mila), October 2025

## Summary

DEG-RAG denoises LLM-generated knowledge graphs by entity resolution (merging redundant entities) and triple reflection (LLM-as-judge removing erroneous relations). Removing about 40% of entities and relations, it consistently improves QA across four Graph-based RAG systems and four datasets, arguing KG quality matters more than size. It is the first systematic study of entity resolution for LLM-generated KGs.

## Method

- Entity resolution pipeline: blocking (semantic, entity-type, structural), matching by embedding similarity, then merging or linking
- Compared embeddings: KG embeddings (TransE, DistMult, ComplEx), GNNs (CompGCN, R-GCN), and LLM embeddings (Qwen3-Embedding-8B)
- Merge strategies: direct merging (pick canonical, absorb others), synonym-linking-only (add alias edges, keep duplicates), and merge-plus-synonym-link
- Triple reflection: LLM assigns a reliability score, triples below threshold 0.2 are dropped
- Proposition 1: without entity resolution, graph-based RAG degrades to vanilla RAG (all benefit comes from resolution-created connectivity)

## Key Findings

- ~40% entity/relation reduction while preserving or improving QA winning rate (>50%) across LightRAG, HippoRAG, LGraphRAG, GGraphRAG
- Type-aware blocking is the most effective blocking strategy
- Classical KG embeddings (ComplEx) can rival or beat LLM embeddings, especially on Legal/Agriculture
- Direct merging generally surpasses synonym-linking-only, which leaves the graph redundant and needing more hops
- On Mix/Legal, up to 70% entity reduction still does not hurt performance

## Relevance to KGF

- ARGUES AGAINST H29 (keep duplicates with alias edges, resolve at read time): the paper's explicit finding is that ingest-time direct merging beats synonym-linking-only, because keeping duplicates connected by alias edges leaves the graph redundant and inflates retrieval hops
- Tension for KGF to resolve: this is aggregate QA winning-rate evidence on static corpora, not read-time-resolution latency or longevity/versioning - the regime where H29 might still hold
- Relevant to the self-auditing loop: triple reflection is a concrete fidelity-gap repair mechanism (LLM-judge filtering low-quality relations)

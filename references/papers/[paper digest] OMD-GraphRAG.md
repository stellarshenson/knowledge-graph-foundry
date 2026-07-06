# OMD-GraphRAG: Enhancing GraphRAG with Ontology-Guided Extraction, Multi-Dimensional Clustering and Dual-Channel Fusion

**Source**: https://arxiv.org/abs/2603.25152
**Authors**: Jie Wang, Honghua Huang, Xi Ge, Jianhui Su, Wen Liu, Shiguo Lian (China Unicom)
**Venue/Date**: Preprint (v3), May 2026

## Summary

OMD-GraphRAG extends open-source GraphRAG with three additions: ontology-guided extraction, multi-dimensional community clustering, and dual-channel retrieval fusion. On the MultiHop-RAG benchmark it improves average F1 by 9.21% over LightRAG and 28.89% over naive RAG, with each of the three modules independently contributing roughly a 3.2-3.4% F1 gain.

## Method

- Ontology-guided extraction injects a domain schema S = (E, R, Phi) into the LLM prompt and discards triples whose head/tail types violate relation domain/range constraints (post-hoc type checking)
- Multi-dimensional clustering extends Leiden with attribute-aware modularity, epsilon-neighbor boundary completion, and path-pattern-constrained multi-hop subgraphs
- Dual-channel retrieval: a trie-based entity/graph channel and a community-report semantic channel, fused by a query-complexity weight beta(q), then reranked by qwen3-reranker-8b
- Static indexing-time fusion avoids per-query LLM routing overhead; Qwen3-235B is the extraction/generation backbone

## Key Findings

- +9.21% average F1 over LightRAG; +28.89% over Dify naive RAG (single-run, no significance testing)
- Ontology-guided extraction alone: +3.17% F1 (75.60% -> 78.77%)
- Multi-dimensional community: +3.43% F1; dual-channel fusion: +3.32% F1
- Largest gains on comparison and temporal queries; comparison F1 +15.15% over LightRAG
- Limitation noted: schema definition is expert-dependent and hard to scale

## Relevance to KGF

- ARGUES AGAINST H28 (type/ontology quality has near-zero effect on QA): the paper's headline result is that injecting an entity/relation ontology and type-filtering triples measurably raises multi-hop QA F1, directly attributing accuracy gains to ontology guidance
- Its own limitation (expert-dependent schema, poor scalability) is a partial concession KGF can exploit - the accuracy gain may not survive weak or automatically-induced schemas
- Dual-channel static fusion supports the retrieval-first idea of encoding complementary evidence at index time

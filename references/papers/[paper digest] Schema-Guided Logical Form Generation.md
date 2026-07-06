# Beyond Seen Data: Improving KBQA Generalization Through Schema-Guided Logical Form Generation

**Source**: https://arxiv.org/abs/2502.12737
**Authors**: Shengxiang Gao, Jey Han Lau, Jianzhong Qi (University of Melbourne)
**Venue/Date**: Preprint (v3), September 2025

## Summary

SG-KBQA is a semantic-parsing KBQA model that injects knowledge-base schema context into both entity retrieval and logical-form generation to generalize to unseen KB elements and compositions. On the non-I.I.D. GrailQA hidden test it tops all three leaderboards, beating prior SOTA by 3.3%, 2.9%, and 4.0% F1 on overall, zero-shot, and compositional settings.

## Method

- Schema-first pipeline: retrieve relations first (PLM retriever generalizes better than entity retrieval), then derive logical-form sketches
- Schema-guided entity retrieval (SER) uses sketch relations plus schema context (domain/range classes) to fix entity mention boundaries and prune candidates
- Logical-form generation constrained to schema-feasible compositions of classes and relations rather than compositions memorized at training
- Combined schema-based pruning filters unlikely candidate entities to raise recall

## Key Findings

- GrailQA non-I.I.D.: +3.3% overall F1, +2.9% zero-shot F1, +4.0% compositional F1 over SOTA
- Evaluated on three benchmarks (GrailQA, WebQSP, CWQ) across I.I.D. and non-I.I.D. splits
- Entity retrieval identified as the propagating bottleneck that schema context repairs
- Schema-feasible composition prevents invalid, unexecutable logical forms (e.g., book-series entity wrongly bound to book-authorship relation)

## Relevance to KGF

- ARGUES AGAINST H28 (type/ontology quality has near-zero effect on QA): schema/type information is the direct driver of accuracy and generalization here - class domain/range constraints prevent invalid compositions and lift F1 on unseen data
- Reinforces that type structure matters most exactly where the graph must generalize to unseen entities and compositions, a stress case KGF should test H28 against
- Its schema-guided read-time composition is a counterpoint to purely identity-only "hollow" retrieval (H27) for structured multi-hop queries

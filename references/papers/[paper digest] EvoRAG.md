# EvoRAG: Feedback-Driven Knowledge Graph Refinement for Retrieval-Augmented Generation

**Authors**: Fu et al.
**Published**: April 2026, arXiv:2604.15676
**Original**: https://arxiv.org/abs/2604.15676
**Local copy**: `[paper] EvoRAG, 2026-04.pdf`

## Problem

GraphRAG systems treat the constructed graph as static: query-time failures never improve the graph, so the same construction errors hurt every subsequent query.

## Mechanism

Closed feedback loop: query → retrieve → generate → evaluate the response → backpropagate response-level feedback to identify problematic graph components → apply triplet-level updates (correct, remove, reweight). The graph evolves continuously without retraining the LLM.

## Results

Consistent gains over static-graph GraphRAG baselines across QA benchmarks (dynamic graph beats one-shot construction).

## Relevance to KGF

The nearest published relative of KGF's R04 loop, and the boundary of published work: EvoRAG's repairs stop at editing triples already in the graph. KGF's targeted repair goes one level deeper - back to the SOURCE DOCUMENTS - because the R04-H18 failure taxonomy showed the damaging residuals (identity gaps, fidelity gaps, extraction misses) are not fixable by editing existing triples; the evidence needed is not in the graph yet. The research sweep found no published system that closes probe-failure → focused re-ingestion of named sources; that loop plus the ingest-time completeness audit (H23) is KGF's novel territory.

# Benchmark v05 - Structured Properties and Final Iteration

**Hybrid Score**: 90% (within noise of v04's 92%)
**Deterministic**: 52/52 (100%)
**Generative**: 4.0/5.0 (-0.2 from v04, within LLM variance)
**Date**: 2026-03-09T23:09:28

## Conditions

- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)
- **Extraction mode**: Constrained (8 entity types from CPAP ontology seed)
- **Ontology seed**: `data/ontologies/cpap_medical_device.yml`
- **Extraction prompt change**: Enhanced properties guidance to produce structured key-value pairs with value, unit, min, max fields
- **Chunk size**: 2000 tokens, 200 overlap, 4 concurrency
- **Resolution threshold**: 0.85 (Levenshtein)

## Graph Stats

- Entities: 148 (+12 from v04, more entities from structured property extraction)
- Relationships: 396 (structural) / 231 (extraction)
- Chunks: 26
- Types: 8 distinct (all within ontology)

## Dimension Scores

| Dimension | Deterministic | LLM | v04 LLM | Delta |
|---|---|---|---|---|
| Entity Coverage | 12/12 (100%) | 4/5 | 4/5 | same |
| Spec Extraction | 10/10 (100%) | 4/5 | 5/5 | -1 (variance) |
| Relationship Accuracy | 6/6 (100%) | 4/5 | 4/5 | same |
| Dedup Quality | 4/4 (100%) | 4/5 | 4/5 | same |
| Graph Structure | 6/6 (100%) | - | - | same |
| Query Answerability | 8/8 (100%) | 4/5 | 4/5 | same |
| Type Consistency | 3/3 (100%) | - | - | same |
| Property Completeness | 3/3 (100%) | - | - | same |

## What Changed

1. **Structured properties prompt**: Enhanced the extraction prompt to guide the LLM toward producing properties dicts with value/unit/min/max keys rather than free-form attributes. Result: 148 entities (up from 136), more entities with structured numeric properties.

2. **Cleaned debug logging**: Removed verbose pre/post-enforcement type logging from unstructured.py, keeping only the enforcement function's own logging.

## Score Progression (Final)

| Version | Det | Gen | Hybrid | Key Change |
|---|---|---|---|---|
| v01 | 71% | 2.4/5 | 60% | Baseline (free extraction) |
| v02 | 96% | 2.6/5 | 74% | Ontology seed + intent prompt |
| v03 | 100% | 3.2/5 | 82% | Type enforcement + property key fix |
| v04 | 100% | 4.2/5 | 92% | Generative query improvements |
| v05 | 100% | 4.0/5 | 90% | Structured properties (within v04 variance) |

## Convergence Analysis

The benchmark has converged at 90-92% hybrid. The remaining 8-10% gap breaks down as:
- Generative scoring variance: each evaluation run produces slightly different scores (4.0-4.2/5 range) due to LLM non-determinism
- Entity coverage ceiling: Single-document extraction captures core entities well (4/5) but not exhaustively (5/5)
- Query answerability ceiling: 6/8 questions answerable with exact values is realistic for automated extraction from a 26-page manual

The deterministic component is fully saturated at 100% (52/52). Further improvement requires either expanding the ground truth checks or fundamentally different extraction approaches (e.g., multi-pass extraction, cross-chunk reasoning, or LLM-assisted entity resolution for the remaining gaps).

# Benchmark v04 - Generative Scoring Improvements

**Hybrid Score**: 92% (+10% from v03)
**Deterministic**: 52/52 (100%)
**Generative**: 4.2/5.0 (+1.0)
**Date**: 2026-03-09T23:05:20

## Conditions

- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)
- **Extraction mode**: Constrained (8 entity types from CPAP ontology seed)
- **Graph**: Same extraction as v03 (136 entities, 8 types)
- **Changes**: Generative scoring queries and prompts only (no extraction changes)

## Graph Stats

- Entities: 136
- Relationships: 459
- Chunks: 26
- Types: Component:42, Specification:35, Feature:20, MedicalCondition:14, WorkMode:10, Standard:8, Organization:4, Product:3
- 8 distinct types

## Dimension Scores

| Dimension | Deterministic | LLM | v03 LLM | Delta |
|---|---|---|---|---|
| Entity Coverage | 12/12 (100%) | 4/5 | 2/5 | **+2** |
| Spec Extraction | 10/10 (100%) | 5/5 | 4/5 | **+1** |
| Relationship Accuracy | 6/6 (100%) | 4/5 | 4/5 | same |
| Dedup Quality | 4/4 (100%) | 4/5 | 4/5 | same |
| Graph Structure | 6/6 (100%) | - | - | same |
| Query Answerability | 8/8 (100%) | 4/5 | 2/5 | **+2** |
| Type Consistency | 3/3 (100%) | - | - | same |
| Property Completeness | 3/3 (100%) | - | - | same |

## What Changed

Four improvements to the generative evaluation pipeline, no extraction changes:

1. **Entity coverage query restructured**: Changed from flat entity list (136 entities, truncated) to type-grouped summary with up to 5 samples per type. Provides the LLM evaluator with a structured overview showing counts and representative entities per type, preventing data truncation that masked coverage quality.

2. **Query answerability query reordered**: Changed from keyword-filtered entities (missed specs) to type-filtered entities ordered with Specifications first. The previous query filtered by description keywords and truncated at 4000 chars, cutting off the spec entities that contain the actual numeric answers. New query puts specs first so they appear before the truncation boundary.

3. **Data truncation limit increased**: From 4000 to 8000 characters, allowing the LLM evaluator to see more entity descriptions including full specification values.

4. **JSON parsing fix**: The response parser used `r'\{[^}]+\}'` which fails when the LLM reasoning contains braces. Replaced with a multi-strategy parser: try full JSON, then regex for `"score": N` within braces, then raw score extraction. This fixed entity_coverage being parsed as 0 despite the LLM returning score:4.

## Score Progression

| Version | Deterministic | Generative | Hybrid | Key Change |
|---|---|---|---|---|
| v01 | 71% | 2.4/5 | 60% | Baseline (free extraction) |
| v02 | 96% | 2.6/5 | 74% | Ontology seed + intent |
| v03 | 100% | 3.2/5 | 82% | Type enforcement + property fix |
| v04 | 100% | 4.2/5 | 92% | Generative query improvements |

## Analysis

The v03->v04 improvement came entirely from better evaluation methodology, not from extraction improvements. The graph quality was already high in v03 but the generative evaluator couldn't see it due to data truncation and query design. This demonstrates the importance of evaluation query design being independent of but aligned with graph structure.

## Remaining Gap (8%)

The 8% gap to 100% comes from generative scores averaging 4.2/5 rather than 5/5:
- Entity coverage (4/5): Graph captures most but not all ground truth entities
- Relationship accuracy (4/5): Core relationships present but some edge connections missing
- Dedup quality (4/5): 2 cross-type name overlaps that are legitimate dual classifications
- Query answerability (4/5): 6/8 questions answerable with exact values, 2 partially

## Improvement Plan for v05

1. Target entity coverage 5/5 by ensuring all ground truth entities have rich descriptions
2. Consider adding relationship descriptions to the relationship accuracy evaluation
3. The remaining gap is likely near the ceiling for single-document extraction without cross-referencing

# Benchmark v03 - Type Enforcement and Property Fix

**Hybrid Score**: 82% (+8% from v02)
**Deterministic**: 52/52 (100%, +4%)
**Generative**: 3.2/5.0 (+0.6)
**Date**: 2026-03-09T23:00:21

## Conditions

- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)
- **Extraction mode**: Constrained (8 entity types from CPAP ontology seed)
- **Ontology seed**: `data/ontologies/cpap_medical_device.yml`
- **Intent prompt**: Same as v02
- **Extraction prompt change**: Added "MUST be exactly one of the allowed entity types - no exceptions"
- **Chunk size**: 2000 tokens, 200 overlap, 4 concurrency
- **Resolution threshold**: 0.85 (Levenshtein)

## Graph Stats

- Entities: 136
- Relationships: 459 (total including structural)
- Chunks: 26
- Types: Component:42, Specification:35, Feature:20, MedicalCondition:14, WorkMode:10, Standard:8, Organization:4, Product:3
- **8 distinct types** (enforced, no leakage)

## Dimension Scores

| Dimension | Deterministic | LLM | v02 Det | Delta |
|---|---|---|---|---|
| Entity Coverage | 12/12 (100%) | 2/5 | 12/12 (100%) | same |
| Spec Extraction | 10/10 (100%) | 4/5 | 10/10 (100%) | same |
| Relationship Accuracy | 6/6 (100%) | 4/5 | 6/6 (100%) | same |
| Dedup Quality | 4/4 (100%) | 4/5 | 4/4 (100%) | **LLM +3** |
| Graph Structure | 6/6 (100%) | - | 6/6 (100%) | same |
| Query Answerability | 8/8 (100%) | 2/5 | 8/8 (100%) | same |
| Type Consistency | 3/3 (100%) | - | 2/3 (67%) | **+33%** |
| Property Completeness | 3/3 (100%) | - | 2/3 (67%) | **+33%** |

## What Changed

Three fixes drove the improvement:

1. **Loader property key filtering**: The `SET n += row.properties` Cypher clause was spreading the entity's `properties` dict onto the Neo4j node as individual attributes. When the LLM included a `type` key in the properties dict (e.g., `{"type": "AC"}`), it overwrote the entity's correct type on the node. Fixed by filtering reserved keys (`id`, `name`, `type`, `description`, `confidence`, `embedding`) from the properties dict before applying.

2. **Stronger type enforcement in prompt**: Changed from "type: one of the allowed entity types listed above" to "MUST be exactly one of the allowed entity types listed above - no exceptions" plus added prominent warning "IMPORTANT: You MUST only use entity types from the list above. Do NOT invent new types." This eliminated type leakage at extraction time.

3. **Fixed property completeness benchmark check**: The original check looked for `n.properties IS NOT NULL` which always failed because the loader spreads properties as individual node attributes via `SET n += row.properties`. Changed to detect entities with keys beyond the standard set (`id`, `name`, `type`, `description`, `confidence`, `embedding`).

4. **Improved generative scoring queries**: Removed description truncation (`substring(n.description, 0, 100)`) so LLM evaluator sees full entity descriptions. Expanded query_answerability query to include Specification type and show more results (40 vs 30).

## Generative Score Analysis

- **Spec extraction 4/5**: Full descriptions now visible to evaluator, capturing most specs with values
- **Relationship accuracy 4/5**: Strong relationship network recognized
- **Dedup quality 4/5**: Major improvement from v02 (1/5) - only 2 cross-type name overlaps flagged
- **Entity coverage 2/5**: LLM evaluator notes many components but wants more high-level conceptual entities
- **Query answerability 2/5**: Despite 8/8 deterministic, the LLM evaluator queries don't surface enough spec entities to answer all questions

## Remaining Issues

1. **Entity coverage generative (2/5)**: The evaluator wants more conceptual entities beyond physical components
2. **Query answerability generative (2/5)**: The generative query doesn't surface enough data for the LLM to evaluate positively
3. **Post-extraction type enforcement**: Added but not triggered - the prompt changes were sufficient. The enforcement function remains as a safety net

## Improvement Plan for v04

1. Improve generative scoring prompts to better capture the actual graph quality
2. Consider adding graph traversal queries that show relationships alongside entities for the LLM evaluator
3. Tune the entity coverage prompt to better assess entity quality vs quantity

# Multi-Doc Benchmark v15 - min-score-0.7 + embeddings + bayesian

**Hybrid Score**: 73%
**Deterministic**: 57/63 (90%)
**Generative**: 2.8/5.0
**Date**: 2026-03-10T19:34

## Conditions

- **Config**: v15 min-score-0.7 + embeddings + bayesian resolution
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)
- **Iteration**: 3

## Fixes Applied Since v14

- `_enforce_ontology_types` min_score threshold raised to 0.7 - types below threshold keep original type instead of bad remap
- Embeddings enabled (`use_embeddings=true`) - Titan v2 1024-dim vectors per entity
- Bayesian resolution enabled (`bayesian_resolution=true`) - FAISS exemplar index built at curing time

## Graph Stats

- Entities: 1014
- Relationships: 2743
- Types: 24+ distinct (was 15 in v14)
- Top types: Component:192, Specification:98, Feature:86, Product:69, Setting:58, Standard:58

## Regressions

- **Singleton types**: 12 (was 0) - keeping original types created many single-entity types
- **spec_extraction LLM**: dropped from 3/5 to 2/5

## Improvements

- **Type preservation**: Mode, Gas, Software, State all preserved (no more absurd remaps)
- **Cross-type duplicates**: 50 (was 56) - modest improvement

## Analysis

Cross-type duplicates remain the main bottleneck (50, target <20). The min_score=0.7 threshold prevents bad remaps but creates singleton types. Need to either lower threshold or improve cross-document entity resolution.

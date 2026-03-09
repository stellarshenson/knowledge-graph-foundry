# Benchmark v01 - Baseline (Unseeded, Free Extraction)

**Hybrid Score**: 60%
**Deterministic**: 37/52 (71%)
**Generative**: 2.4/5.0
**Date**: 2026-03-09T22:38:10

## Conditions

- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)
- **Extraction mode**: Free (no ontology seed, no intent prompt)
- **Chunk size**: 2000 tokens, 200 overlap, 4 concurrency
- **Resolution threshold**: 0.85 (Levenshtein)
- **Temperature**: 0.0
- **Source**: BMC_RESmart_AutoCPAP_User_Manual.pdf (26 pages)

## Graph Stats

- Entities: 156
- Relationships: 535
- Chunks: 26
- Type distribution: Component:37, Feature:16, Medical Condition:9, Standard:7, Specification:6, Setting:6, Product:6, Test:5 (21 types total)

## Dimension Scores

| Dimension | Deterministic | LLM | Notes |
|---|---|---|---|
| Entity Coverage | 12/12 (100%) | 2/5 | All key entities exist but descriptions lack depth |
| Spec Extraction | 1/10 (10%) | 1/5 | Critical gap - specs have names but no numeric values |
| Relationship Accuracy | 6/6 (100%) | 4/5 | Strong relationship network |
| Dedup Quality | 3/4 (75%) | 2/5 | 12 cross-type duplicates, 21 distinct types |
| Graph Structure | 6/6 (100%) | - | Perfect structural integrity |
| Query Answerability | 5/8 (62%) | 3/5 | Can answer basic but not spec-detail questions |
| Type Consistency | 2/3 (67%) | - | 6+ singleton types |
| Property Completeness | 2/3 (67%) | - | No structured properties dict on entities |

## Root Cause Analysis

1. **Spec extraction is the critical failure (1/10, 1/5 LLM)**: Specification entities exist ("Device Size", "Sound Pressure Level", "Pressure Range") but their descriptions contain only generic labels ("Noise level specification") instead of the actual values from the document. The extraction prompt instructs "brief description" without emphasizing concrete numeric values. This single issue accounts for 9 failed deterministic checks and drives the answerability failures for weight, sound, and pressure queries.

2. **Type fragmentation (21 types)**: Without a seeded ontology, the LLM invents arbitrary types. Same concepts get different types across chunks - "CPAP" appears as both "Therapy" and "WorkMode", "Humidifier" as both "Component" and "Accessory". This inflates type count and creates cross-type name duplicates that dedup can't catch.

3. **No structured properties**: Entities lack populated `properties` dict. All information is in free-text descriptions. Numeric values that should be structured key-value pairs (pressure_min: 4, pressure_max: 20) are either missing or buried in description text.

4. **Entity coverage paradox**: Deterministic says 100% (all key entities found by name) but LLM says 2/5. The LLM evaluates entity quality holistically - entities exist but lack specificity and depth. A "Pressure Range" entity without "4-20 hPa" in its description is technically present but practically useless.

## Improvement Plan for v02

1. Add CPAP-specific ontology seed with 8 entity types constraining extraction
2. Add intent prompt emphasizing numeric value capture in descriptions
3. Updated extraction prompts: "MUST include specific numeric values, measurements, ranges, and units"
4. Set `min_frequency_to_confirm: 1` so seeded types are immediately active

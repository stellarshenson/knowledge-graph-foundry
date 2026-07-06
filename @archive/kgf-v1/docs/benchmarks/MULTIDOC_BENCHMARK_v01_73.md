# Multi-Doc Benchmark v01 - Baseline (Free Mode)

**Hybrid Score**: 73%
**Deterministic**: 54/63 (86%)
**Generative**: 3.0/5.0
**Date**: 2026-03-09T23:47:23

## Conditions

- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)
- **Extraction mode**: Free (no ontology constraint, 33 entity types emerged)
- **Ontology seed**: None
- **Standard properties**: Not yet active (pre-base_entity implementation)
- **Chunk size**: 2000 tokens, 200 overlap, 4 concurrency
- **Resolution threshold**: 0.85 (Levenshtein)

## Corpus (10 PDFs)

| File | Size | Manufacturer | Chunks |
|---|---|---|---|
| BMC_RESmart_AutoCPAP_User_Manual.pdf | 379 KB | BMC Medical | 26 |
| 3B_User-Manual_CPAP-Auto-CPAP_RESmart_BMC_V1.7_ENG-1.pdf | 649 KB | BMC Medical | 35 |
| Airsense-Brochure.pdf | 913 KB | ResMed | 3 |
| airstart-10-cpap_fact-sheet_apac_eng.pdf | 252 KB | ResMed | 2 |
| BC-Dreamstation-Standard-CPAP.pdf | 135 KB | Philips | 2 |
| CPAP_Eng.pdf | 421 KB | Generic | 3 |
| DreamStation_CPAP_Pro_DataSheet.pdf | 3.9 MB | Philips | 2 |
| DreamStation_CPAP_User_Manual.pdf | 3.2 MB | Philips | 32 |
| Resvent-iBreeze-Auto-CPAP-User-Manual.pdf | 897 KB | Resvent | 40 |
| SleepStyle_200_Operating_Manual.pdf | 1.0 MB | Fisher & Paykel | 13 |

## Graph Stats

- Entities: 1007
- Relationships: 3744 (structural + extraction)
- Chunks: 158
- Documents: 10 (23 shown due to leftover nodes from previous runs)
- Types: 33 distinct (free extraction, no ontology constraint)
- Top types: Specification:181, Component:151, Feature:111, Accessory:82, Product:48

## Dimension Scores

| Dimension | Deterministic | LLM |
|---|---|---|
| Document Coverage | 3/4 (75%) | - |
| Manufacturer Coverage | 5/5 (100%) | 5/5 |
| Product Coverage | 7/7 (100%) | 3/5 |
| Cross-Doc Resolution | 1/6 (17%) | 3/5 |
| Relationship Patterns | 8/8 (100%) | - |
| Spec Extraction | 8/8 (100%) | 2/5 |
| Type Distribution | 5/5 (100%) | - |
| Graph Structure | 5/5 (100%) | - |
| Query Answerability | 9/10 (90%) | 2/5 |
| Property Completeness | 3/5 (60%) | - |

## Key Failures

1. **Cross-document resolution (17%)**: 97 cross-type duplicates, 30 same-type duplicates. 12 OSA entities instead of 1-3. 33 humidifier entities instead of 1-5. Free mode produces inconsistent type labels across documents, preventing MERGE-based dedup
2. **Property completeness (60%)**: No `model_name` on Product entities, no `standard_id` on Standard entities. Free extraction does not respect ontology property schemas
3. **Document coverage**: 13 orphan Document nodes from previous benchmark runs (graph not fully clean)
4. **Generative spec_extraction (2/5)**: Specs exist but lack structured value/unit properties. Values buried in descriptions rather than extractable properties
5. **Generative query_answerability (2/5)**: MANUFACTURES relationships exist but not consistently typed. Cross-manufacturer comparison queries require traversing inconsistent relationship types

## Improvement Plan for v02

1. Add ontology constraint (8 types from cpap_medical_device.yml) to enforce type consistency
2. Enable standard base_entity properties (created_at, source_document, update_count)
3. Clean graph fully between runs (remove all leftover nodes)
4. Ontology-typed relationships (MANUFACTURES, HAS_SPECIFICATION, etc.) enable single-hop queries

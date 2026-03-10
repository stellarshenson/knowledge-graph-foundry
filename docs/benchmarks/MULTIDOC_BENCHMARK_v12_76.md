# Multi-Doc Benchmark v12 - graph query tool, early stopping, LLM advisor prompts

**Hybrid Score**: 76%
**Deterministic**: 56/63 (89%)
**Generative**: 3.2/5.0
**Date**: 2026-03-10T18:15:08.975746

## Conditions

- **Config**: v12 fluid graph-query early-stopping
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 1105
- Relationships: 3307
- Chunks: 158
- Documents: 41
- Types: 15 distinct
- Top types: Component:279, Specification:144, Product:73, Section:72, Concept:62, Feature:48, Interface:44, Standard:38

## Dimension Scores

| Dimension | Deterministic | LLM |
|---|---|---|
| Document Coverage | 3/4 (75%) | - |
| Manufacturer Coverage | 5/5 (100%) | 5/5 |
| Product Coverage | 7/7 (100%) | 3/5 |
| Cross Doc Resolution | 4/6 (67%) | 3/5 |
| Relationship Patterns | 7/8 (88%) | - |
| Spec Extraction | 8/8 (100%) | 3/5 |
| Type Distribution | 5/5 (100%) | - |
| Graph Structure | 5/5 (100%) | - |
| Query Answerability | 7/10 (70%) | 2/5 |
| Property Completeness | 5/5 (100%) | - |

## Key Failures

1. **document_coverage** - All docs have chunks (actual=31)
2. **cross_doc_resolution** - Cross-type duplicates < 20 (actual=72)
3. **cross_doc_resolution** - Humidifier entity consolidated (actual=4)
4. **relationship_patterns** - SUPPORTS_MODE relationships (actual=0)
5. **query_answerability** - Q: What is the pressure range of DreamStation?
6. **query_answerability** - Q: What modes does SleepStyle support?
7. **query_answerability** - Q: iBreeze specifications?

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are present with meaningful descriptions: BMC Medical Co., Ltd. (with full address and contact details), ResMed/ResMed Ltd (manufacturer of AirStart 10), Philips/Respironics entities including Koninklijke Philips N.V., Philips Healthcare, Philips Respironics, and Respironics Inc. (with comprehensive contact information), Resvent/Resvent Medical Technology Co., Ltd. (with complete address and contact details), and Fisher & Paykel/Fisher & Paykel Healthcare (manufacturer of Icon series with international presence). Additionally, the knowledge graph includes expected regulatory elements like EU authorized representatives (Shanghai International Holding Corp. GmbH) and standards organizations, demonstrating comprehensive coverage of the CPAP device ecosystem.
- **product_coverage** (3/5): The knowledge graph captures 5 of the 6 expected products: RESmart Auto CPAP (3B Products), AirSense series (ResMed), AirStart 10 (missing manufacturer), DreamStation variants (Philips/Koninklijke Philips N.V.), and SleepStyle 200 (Fisher & Paykel). However, iBreeze is completely missing, and several key products lack proper manufacturer linkage (AirStart 10, Auto CPAP, CPAP Pro). While product descriptions are generally meaningful, the inconsistent manufacturer attribution and missing iBreeze product prevent a higher score.
- **cross_doc_resolution** (3/5): The results show some duplicates but core entities appear reasonably well resolved. Key CPAP entities like 'humidifier', 'ahi', 'ramp' appear only 3 times across 10 documents, which suggests decent but not perfect resolution. Common technical terms like 'accessories', 'power supply', 'sd card' also show limited duplication (2-3 instances). However, the presence of duplicates for fundamental concepts indicates the resolution process could be improved. The duplication levels are moderate rather than severe, with most entities appearing 2-3 times rather than approaching the full document count of 10.
- **spec_extraction** (3/5): The extraction shows some specs with concrete numeric values from 2-3 products, but coverage is incomplete. Good examples include AirStart 10 with complete specs (dimensions: 116x205x150mm, weight: 1106g, pressure: 4-20 cmH2O, sound: 26.6 dBA). However, many extracted entities lack product association (product: null) and some have inconsistent or missing values (e.g., '30 seconds' description shows 40 seconds value). The extraction captures key CPAP specifications like pressure ranges, dimensions, and sound levels, but doesn't demonstrate comprehensive coverage across all 10 devices as expected.
- **query_answerability** (2/5): The knowledge graph can answer only 2-3 of the 8 question types with specific data. It clearly identifies manufacturers (3B Medical, BMC Medical, Fisher & Paykel Healthcare, and references to Philips Respironics) and shows which devices treat OSA through product descriptions. However, it lacks critical comparative data needed for the other questions: no specific pressure ranges, device specifications (weight, dimensions, sound levels), detailed component lists, compliance standards, or operational modes are present in the provided relationships. The graph appears to focus more on organizational structure and basic product identification rather than technical specifications needed for meaningful cross-manufacturer comparisons.

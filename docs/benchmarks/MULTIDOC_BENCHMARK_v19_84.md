# Multi-Doc Benchmark v19 - Bayesian cross-type dedup, SUPPORTS_MODE fix

**Hybrid Score**: 84%
**Deterministic**: 61/63 (97%)
**Generative**: 3.6/5.0
**Date**: 2026-03-11T11:57:00.203556

## Conditions

- **Config**: v19 Bayesian cross-type dedup, SUPPORTS_MODE fix
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 1022
- Relationships: 3779
- Chunks: 158
- Documents: 10
- Types: 12 distinct
- Top types: Component:209, Specification:200, Feature:169, Setting:90, Standard:63, Accessory:62, Interface:56, Section:52

## Dimension Scores

| Dimension | Deterministic | LLM |
|---|---|---|
| Document Coverage | 4/4 (100%) | - |
| Manufacturer Coverage | 5/5 (100%) | 5/5 |
| Product Coverage | 7/7 (100%) | 4/5 |
| Cross Doc Resolution | 5/6 (83%) | 3/5 |
| Relationship Patterns | 8/8 (100%) | - |
| Spec Extraction | 8/8 (100%) | 4/5 |
| Type Distribution | 5/5 (100%) | - |
| Graph Structure | 5/5 (100%) | - |
| Query Answerability | 9/10 (90%) | 2/5 |
| Property Completeness | 5/5 (100%) | - |

## Key Failures

1. **cross_doc_resolution** - Cross-type duplicates < 20 (actual=39)
2. **query_answerability** - Q: What modes does SleepStyle support?

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are present with meaningful descriptions: BMC Medical Co., Ltd. (with full address and contact details), ResMed/ResMed Ltd (manufacturer of AirStart 10), Philips/Respironics Inc. (with detailed warranty and contact information), Resvent Medical Technology Co., Ltd. (comprehensive manufacturer details including Shenzhen address and contact info), and Fisher & Paykel Healthcare (with international presence noted). Additionally, regulatory bodies (Department of Health, Medical Device Division) and EU authorized representatives (Shanghai International Holding Corp. GmbH) are properly captured, demonstrating comprehensive coverage of the CPAP device ecosystem.
- **product_coverage** (4/5): The knowledge graph covers 6 out of 7 expected products with manufacturer linkages: RESmart Auto CPAP (multiple manufacturer variants including BMC Medical Co., Ltd., 3B Medical Inc.), AirSense series (ResMed), AirStart 10 (ResMed), DreamStation Standard and Pro variants (Philips Respironics), and SleepStyle 200 (Fisher & Paykel Healthcare via HC230 Product Range). Missing iBreeze product entirely. All covered products have meaningful descriptions and proper manufacturer linkages, but some entities show duplicate entries with slight variations.
- **cross_doc_resolution** (3/5): The entity resolution shows mixed results. Core entities like 'humidifier' appear only 2 times across 10 documents, which is reasonable consolidation. Most duplicates are at low counts (2-3 instances), suggesting decent but not perfect resolution. However, fundamental CPAP components like 'tubing', 'filters', 'headgear', and 'power cord' still appear duplicated when they should ideally be single entities across all documents. The system successfully avoided severe duplication but missed opportunities to fully consolidate common medical device terminology.
- **spec_extraction** (4/5): The extraction shows good coverage across multiple CPAP products with concrete numeric values and proper units. Key specifications are well-represented including pressure ranges (4-20 cmH2O), dimensions (116x205x150 mm), weight (1106g), sound levels (26.6 dBA), operating temperatures (+5 to +35°C), and power requirements (100-240 VAC). Multiple products are covered including AirStart 10 CPAP, DreamStation models, and 3B/BMC devices. Most specs have exact numeric values with appropriate units and clear product linkage. However, the extraction appears incomplete as it cuts off mid-specification and may not represent all 10 devices mentioned, preventing a perfect score.
- **query_answerability** (2/5): The knowledge graph can answer only 2-3 of the 8 question types with specific data. It clearly shows which manufacturers make CPAP devices (3B Medical/BMC, Fisher & Paykel Healthcare) and can identify that devices treat OSA based on product descriptions. However, it lacks the detailed technical data needed for most comparison questions - no pressure ranges, specific features like ramp or pressure relief, supported modes, component lists, compliance standards, or specifications like weight/dimensions/sound levels are present in the relationships shown.

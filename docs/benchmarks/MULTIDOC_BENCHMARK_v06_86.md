# Multi-Doc Benchmark v06 - improved generative prompts + threshold tuning

**Hybrid Score**: 86%
**Deterministic**: 61/63 (97%)
**Generative**: 3.8/5.0
**Date**: 2026-03-10T01:09:03.235321

## Conditions

- **Config**: v06 improved generative prompts + threshold tuning
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 855
- Relationships: 3056
- Chunks: 158
- Documents: 10
- Types: 8 distinct
- Top types: Component:235, Specification:228, Feature:188, Standard:75, WorkMode:38, Product:37, MedicalCondition:31, Organization:23

## Dimension Scores

| Dimension | Deterministic | LLM |
|---|---|---|
| Document Coverage | 4/4 (100%) | - |
| Manufacturer Coverage | 5/5 (100%) | 5/5 |
| Product Coverage | 7/7 (100%) | 4/5 |
| Cross Doc Resolution | 5/6 (83%) | 4/5 |
| Relationship Patterns | 8/8 (100%) | - |
| Spec Extraction | 8/8 (100%) | 4/5 |
| Type Distribution | 5/5 (100%) | - |
| Graph Structure | 5/5 (100%) | - |
| Query Answerability | 9/10 (90%) | 2/5 |
| Property Completeness | 5/5 (100%) | - |

## Key Failures

1. **cross_doc_resolution** - No same-type name duplicates (actual=1)
2. **query_answerability** - Q: What modes does SleepStyle support?

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are present with meaningful descriptions: BMC Medical Co., Ltd. (with Beijing address), ResMed Ltd (with Australia address), Philips Respironics/Respironics Inc. (with Pennsylvania location and contact details), Resvent Medical Technology Co., Ltd. (with Shenzhen address), and Fisher & Paykel Healthcare (F&P). The knowledge graph also correctly captures regulatory bodies (Department of Health, Medical Device Division) and EU authorized representatives (Shanghai International Holding Corp. GmbH Europe). Each manufacturer entity includes substantive details like locations, product lines, and business roles, demonstrating comprehensive coverage of the expected organizational landscape.
- **product_coverage** (4/5): Found 6 out of 7 expected products: RESmart Auto CPAP (multiple variants with manufacturer links to 3B Medical/BMC), AirSense 10 (multiple variants with ResMed manufacturer links), AirStart 10 CPAP (with ResMed manufacturer), DreamStation variants including Pro (with Philips Respironics manufacturer links), and SleepStyle 200 series represented by HC230 Product Range (Fisher & Paykel Healthcare). Missing iBreeze product entirely. Most products have proper manufacturer linkage and meaningful descriptions, though some entities lack manufacturer information.
- **cross_doc_resolution** (4/5): The cross-document entity resolution shows minor duplication with only 11 duplicate entities found across 10 CPAP PDFs. Importantly, the major common entities like 'CPAP', 'OSA', and 'humidifier' are not present in the duplicates list, indicating they were properly resolved. The duplicates that exist are mostly technical specifications and features (like 'ahi', 'ramp time', 'power supply') that reasonably could appear in multiple documents with slight variations in context or typing. The duplicate counts are low (mostly 2-3 occurrences), suggesting the resolution process worked well overall with only minor edge cases remaining.
- **spec_extraction** (4/5): The extraction shows good coverage across multiple CPAP products with concrete numeric values and proper units. Key specifications are well-represented including pressure ranges (4-20 cmH2O), dimensions (313×194×112 mm), weights (1.33-2.4 kg), power requirements (100-240 VAC), and operational parameters like temperature limits (43°C) and altitude compensation (7500 feet). The data includes proper product linkage and covers expected categories like pressure accuracy, maintenance intervals, and electrical specifications. However, some critical specs like sound levels (dB) appear to be missing, and the extraction seems to cover fewer than the expected 10 devices comprehensively, preventing a perfect score.
- **query_answerability** (2/5): The knowledge graph can only answer 2-3 of the 8 question types with specific data. It identifies some manufacturers (BMC, ResMed, Philips from product names) and shows which devices treat OSA. However, it lacks critical comparative data: no pressure ranges, incomplete feature comparisons across brands, limited mode information, missing compliance standards, and no specifications like weight/dimensions/sound levels. The data is fragmented and insufficient for meaningful cross-manufacturer comparisons.

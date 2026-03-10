# Multi-Doc Benchmark v08 - enriched buffer prompts + configurable thresholds

**Hybrid Score**: 88%
**Deterministic**: 63/63 (100%)
**Generative**: 3.8/5.0
**Date**: 2026-03-10T09:42:57.657748

## Conditions

- **Config**: v08 enriched buffer prompts + configurable thresholds
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 954
- Relationships: 2935
- Chunks: 158
- Documents: 10
- Types: 8 distinct
- Top types: Feature:277, Component:248, Specification:244, Standard:77, Product:31, MedicalCondition:29, WorkMode:26, Organization:22

## Dimension Scores

| Dimension | Deterministic | LLM |
|---|---|---|
| Document Coverage | 4/4 (100%) | - |
| Manufacturer Coverage | 5/5 (100%) | 5/5 |
| Product Coverage | 7/7 (100%) | 4/5 |
| Cross Doc Resolution | 6/6 (100%) | 4/5 |
| Relationship Patterns | 8/8 (100%) | - |
| Spec Extraction | 8/8 (100%) | 4/5 |
| Type Distribution | 5/5 (100%) | - |
| Graph Structure | 5/5 (100%) | - |
| Query Answerability | 10/10 (100%) | 2/5 |
| Property Completeness | 5/5 (100%) | - |

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are present with meaningful descriptions: BMC Medical Co., Ltd. (with Beijing address), ResMed/ResMed Ltd (with Australian headquarters), Philips/Respironics entities (including Koninklijke Philips N.V., Philips Respironics, Respironics Inc. with Pennsylvania address), Resvent Medical Technology Co., Ltd. (with Shenzhen address), and Fisher & Paykel Healthcare (with Auckland headquarters). Additionally, regulatory bodies (Department of Health, Medical Device Division) and EU authorized representatives (Fisher & Paykel Healthcare UK, Shanghai International Holding Corp. GmbH) are properly captured with contact details and locations.
- **product_coverage** (4/5): The knowledge graph captures 6 out of 6 expected products: RESmart Auto CPAP (multiple variants with BMC/3B Medical manufacturers), AirSense (ResMed), AirStart 10 (ResMed), DreamStation Standard and Pro (Philips Respironics), iBreeze (Resvent), and SleepStyle 200 (F&P). Most products have proper manufacturer linkage and meaningful descriptions. However, some entities have null manufacturers and there are duplicate entries for the same products, indicating extraction inconsistencies that prevent a perfect score.
- **cross_doc_resolution** (4/5): The entity resolution shows minor duplication with only 11 duplicate entities found across 10 CPAP documents. Importantly, the most common entities like 'CPAP', 'OSA', and 'humidifier' mentioned in the prompt are not in the duplicates list, indicating they were properly resolved. The duplicates that exist are mostly technical specifications and features (like 'ramp time', 'ahi', 'power supply') that reasonably appear 2-3 times across documents, which is acceptable for a 10-document corpus. The duplication level is minimal and doesn't affect core domain entities.
- **spec_extraction** (4/5): The extraction shows good coverage across multiple CPAP products with concrete numeric values and proper units. Key specifications are well-represented including pressure ranges (4-20 cmH2O), dimensions (116x205x150 mm), weights (1106g, 1.33kg), power supply voltages (100-240V), operating temperatures (+5°C to +35°C), and sound levels (26.6 dBA). The data covers at least 3-4 different products (AirStart 10, DreamStation CPAP Pro, and others) with consistent specification extraction. Most entries have proper numeric values, units, and product linkage as required. However, some entries have null values and the extraction appears incomplete for all 10 devices mentioned, preventing a perfect score.
- **query_answerability** (2/5): The knowledge graph can answer questions 1 (manufacturers: 3B Medical/BMC, Fisher & Paykel, Philips Respironics, ResMed are clearly identified) and 6 (components: extensive component relationships exist for masks, tubing, filters, humidifiers, headgear, power supplies). However, it lacks the specific technical data needed for questions 2-5, 7-8 such as pressure ranges, feature comparisons, therapy modes, compliance standards, and device specifications like weight/dimensions/sound levels. The graph shows manufacturing relationships and component associations but missing the detailed product specifications required for meaningful cross-manufacturer comparisons.

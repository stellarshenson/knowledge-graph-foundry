# Multi-Doc Benchmark v18 - intent-driven discovery model

**Hybrid Score**: 81%
**Deterministic**: 60/63 (95%)
**Generative**: 3.4/5.0
**Date**: 2026-03-11T11:02:42.324127

## Conditions

- **Config**: v18 intent-driven discovery model
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 1035
- Relationships: 3822
- Chunks: 158
- Documents: 10
- Types: 12 distinct
- Top types: Specification:207, Component:179, Feature:170, Accessory:90, Setting:76, Interface:72, Standard:65, Section:56

## Dimension Scores

| Dimension | Deterministic | LLM |
|---|---|---|
| Document Coverage | 4/4 (100%) | - |
| Manufacturer Coverage | 5/5 (100%) | 5/5 |
| Product Coverage | 7/7 (100%) | 4/5 |
| Cross Doc Resolution | 5/6 (83%) | 2/5 |
| Relationship Patterns | 7/8 (88%) | - |
| Spec Extraction | 8/8 (100%) | 4/5 |
| Type Distribution | 5/5 (100%) | - |
| Graph Structure | 5/5 (100%) | - |
| Query Answerability | 9/10 (90%) | 2/5 |
| Property Completeness | 5/5 (100%) | - |

## Key Failures

1. **cross_doc_resolution** - Cross-type duplicates < 20 (actual=56)
2. **relationship_patterns** - SUPPORTS_MODE relationships (actual=0)
3. **query_answerability** - Q: What modes does SleepStyle support?

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are present with meaningful descriptions: BMC Medical Co., Ltd. (with full address in Beijing), ResMed/ResMed Ltd (manufacturer of AirStart 10 CPAP with Australian address), Philips/Respironics Inc. (with detailed Pennsylvania address and contact info), Resvent Medical Technology Co., Ltd. (comprehensive Shenzhen address and contact details), and Fisher & Paykel Healthcare (manufacturer of Icon series and Sleep Style systems with international presence). Additionally, regulatory bodies (Department of Health, Medical Device Division) and EU authorized representatives (Shanghai International Holding Corp. GmbH) are properly captured as expected.
- **product_coverage** (4/5): The knowledge graph captures 6 out of 7 expected products with manufacturer linkages: RESmart Auto CPAP (BMC Medical Co., Ltd./3B Medical), AirSense series (ResMed), AirStart 10 (ResMed), DreamStation Standard and Pro variants (Philips Respironics), and iBreeze (as PAP System). SleepStyle 200 is partially covered as 'Integrated CPAP Range' but lacks manufacturer linkage. All captured products have meaningful descriptions detailing specifications, intended use, and key features.
- **cross_doc_resolution** (2/5): Many common CPAP entities are duplicated across documents, including fundamental components like 'humidifier' (2 instances), 'headgear' (2), 'power cord' (2), and 'sd card' (2). Critical medical terms like 'ahi' (Apnea-Hypopnea Index) appear 3 times with inconsistent typing (Specification/Interface/Setting). Core features like 'mask fit', 'ramp button', and 'supplemental oxygen' each have 3 instances with conflicting entity types. While the duplication isn't as severe as it could be with 10 documents, the cross-document entity resolution is clearly failing for standard CPAP terminology that should have single canonical representations.
- **spec_extraction** (4/5): The extraction shows good coverage across multiple CPAP products with concrete numeric values and proper units. Key specifications are well-represented including pressure ranges (4-20 cmH2O), dimensions (116x205x150 mm), weight (1106g), sound levels (26.6 dBA), power supply (100-240V, 50-60Hz), and operating conditions (temperature +5 to +35°C, humidity 10-95%). The data includes comprehensive specs from products like AirStart 10 CPAP with detailed technical parameters, safety classifications (Class II, Type BF, IP22), and regulatory compliance information. However, some entries lack numeric values (marked as null) and the extraction appears incomplete for reaching all 10 devices mentioned, preventing a perfect score.
- **query_answerability** (2/5): The knowledge graph can answer questions 1 and 4 with specific data. Question 1 is fully answerable as the graph shows manufacturers including 3B Medical/BMC, Fisher & Paykel Healthcare, and F&P making CPAP devices. Question 4 is answerable since multiple devices are described as treating OSA. However, the graph lacks sufficient data for questions 2, 3, 5, 6, 7, and 8. There are no feature comparisons, pressure ranges, mode specifications, component lists, compliance standards, or technical specifications like weight/dimensions/sound levels in the provided relationships. The data is primarily limited to manufacturer-product relationships with basic descriptions.

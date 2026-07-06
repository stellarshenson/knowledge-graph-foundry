# Multi-Doc Benchmark v16 - H2-embedding-cross-type-gate-direct-mode

**Hybrid Score**: 73%
**Deterministic**: 57/63 (90%)
**Generative**: 2.8/5.0
**Date**: 2026-03-10T20:46:13.382901

## Conditions

- **Config**: v16 H2-embedding-cross-type-gate-direct-mode
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 1088
- Relationships: 4120
- Chunks: 158
- Documents: 28
- Types: 15 distinct
- Top types: Component:198, Specification:105, Section:90, Feature:83, Product:74, Standard:67, Setting:64, Interface:50

## Dimension Scores

| Dimension | Deterministic | LLM |
|---|---|---|
| Document Coverage | 3/4 (75%) | - |
| Manufacturer Coverage | 5/5 (100%) | 5/5 |
| Product Coverage | 7/7 (100%) | 3/5 |
| Cross Doc Resolution | 4/6 (67%) | 2/5 |
| Relationship Patterns | 7/8 (88%) | - |
| Spec Extraction | 8/8 (100%) | 2/5 |
| Type Distribution | 4/5 (80%) | - |
| Graph Structure | 5/5 (100%) | - |
| Query Answerability | 9/10 (90%) | 2/5 |
| Property Completeness | 5/5 (100%) | - |

## Key Failures

1. **document_coverage** - All docs have chunks (actual=18)
2. **cross_doc_resolution** - Cross-type duplicates < 20 (actual=52)
3. **cross_doc_resolution** - Humidifier entity consolidated (actual=4)
4. **relationship_patterns** - HAS_SPECIFICATION relationships (actual=0)
5. **type_distribution** - Singleton types < 3 (actual=13)
6. **query_answerability** - Q: What modes does SleepStyle support?

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are present with meaningful descriptions: BMC Medical Co., Ltd. (with full address), ResMed Ltd and ResMed (manufacturer of AirStart 10), Philips/Respironics (multiple entities including Koninklijke Philips N.V., Philips Healthcare, Philips Respironics, and Respironics Inc. with contact details), Resvent Medical Technology Co., Ltd. (with complete address and contact information), and Fisher & Paykel Healthcare (with international office coverage). Additionally, regulatory bodies (Department of Health, Medical Device Division) and EU authorized representatives (Shanghai International Holding Corp. GmbH) are properly captured as expected.
- **product_coverage** (3/5): The knowledge graph captures 5 of the 6 expected products: AirSense (multiple variants including AirSense 10), AirStart 10, DreamStation (both Standard and Pro variants), iBreeze (as PAP System), and SleepStyle (as SleepStyle 200). However, RESmart Auto CPAP appears to be incomplete (cut off in the data). Manufacturer linkage is inconsistent - ResMed products are well-linked, DreamStation has multiple manufacturer entries (Philips variants), but several key products lack manufacturer information. Descriptions are generally meaningful but some entities are duplicated with different manufacturer attributions.
- **cross_doc_resolution** (2/5): Many common entities that should appear once are duplicated across documents. Critical entities like 'cpap' (2 instances), 'humidifier' (3 instances), and 'integrated heated humidifier' vs 'integrated humidifier' (4+2 instances) show poor cross-document resolution. Multiple variations of the same concept (user buttons, +/- user buttons) and component duplicates (SD card, power supply, accessories) indicate the system failed to properly merge entities across the 10 CPAP PDFs. This level of duplication significantly impacts knowledge graph quality.
- **spec_extraction** (2/5): The specification entities show few concrete specs with proper numeric values linked to actual CPAP products. Most entries lack product associations (all show 'product': null), and many specifications are incomplete or cut off (like 'Operating Frequency Range' ending mid-sentence). While some key CPAP specs are present (pressure accuracy ±1 cmH2O, altitude ranges, power consumption), there's insufficient coverage across the expected 10 devices. The extraction appears to capture individual specifications but fails to systematically extract comprehensive spec sets from multiple products with proper product linkage.
- **query_answerability** (2/5): The knowledge graph can answer only 2-3 of the 8 question types with specific data. It clearly identifies manufacturers (BMC Medical Co. Ltd., Fisher & Paykel Healthcare, 3B Medical Inc.) and shows which devices treat OSA through product descriptions. However, it lacks critical technical specifications like pressure ranges, detailed feature comparisons, supported modes, component lists, compliance standards, and device specifications (weight, dimensions, sound levels). The relationships focus heavily on organizational structure and basic product associations rather than the technical details needed for meaningful cross-manufacturer comparisons.

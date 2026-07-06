# Multi-Doc Benchmark v20 - benchmark spec update - expanded judge context

**Hybrid Score**: 88%
**Deterministic**: 61/63 (97%)
**Generative**: 4.0/5.0
**Date**: 2026-03-11T12:46:50.401395

## Conditions

- **Config**: v20 benchmark spec update - expanded judge context
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 1007
- Relationships: 3496
- Chunks: 158
- Documents: 10
- Types: 12 distinct
- Top types: Specification:200, Component:184, Feature:180, Accessory:83, Setting:76, Interface:67, Standard:64, Product:40

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
| Query Answerability | 9/10 (90%) | 4/5 |
| Property Completeness | 5/5 (100%) | - |

## Key Failures

1. **cross_doc_resolution** - Cross-type duplicates < 20 (actual=52)
2. **query_answerability** - Q: What modes does SleepStyle support?

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are well-represented with meaningful descriptions: BMC Medical (BMC Medical Co., Ltd. with full address), ResMed (ResMed Ltd with address and ResMed as device manufacturer), Philips/Respironics (both Philips Respironics and Respironics Inc. with detailed contact info), Resvent (Resvent Medical Technology Co., Ltd. with complete address and contact details), and Fisher & Paykel (multiple entities including Fisher & Paykel Healthcare with international presence). Additionally, regulatory bodies (Department of Health, Medical Device Division) and EU authorized representatives (Shanghai International Holding Corp. GmbH) are properly captured, demonstrating comprehensive coverage of the CPAP device ecosystem.
- **product_coverage** (4/5): The knowledge graph captures 6 out of 6 expected products with manufacturer linkages: RESmart Auto CPAP (multiple manufacturer variants including BMC Medical Co., Ltd., 3B Medical Inc.), AirSense (ResMed), AirStart 10 (ResMed), DreamStation Standard and Pro variants (Philips Respironics), iBreeze (Resvent), and SleepStyle 200 (though manufacturer not explicitly linked). All products have meaningful descriptions detailing their therapeutic purposes, technical specifications, and key features. The extraction shows good coverage with proper manufacturer attribution for most products.
- **cross_doc_resolution** (3/5): The entity resolution shows mixed results. Core CPAP entities like 'humidifier', 'mask', 'tubing' appear only 2 times each, which is reasonable given they can legitimately be both integrated components and separate accessories. However, there are clear resolution failures for entities like 'ahi', 'ramp button', and 'mask fit' which appear 3 times each with nearly identical descriptions that should have been merged (e.g., all 'ahi' instances refer to the same Apnea/Hypopnea Index concept). The duplicates mostly represent genuine type ambiguity rather than severe duplication, but several cases show missed opportunities to consolidate semantically identical entities across different interface contexts.
- **spec_extraction** (4/5): The extraction shows good coverage across multiple CPAP products with concrete numeric values and proper units. Key specifications are well-represented including pressure ranges (4-20 cmH2O), weights (1106g, 1.33-1.98kg), dimensions (116x205x150mm, 29.7x19.3x8.4cm), sound levels (26.6 dBA), power supply (100-240V), and operating temperatures (+5°C to +35°C, -20°C to +60°C). The data covers at least 6-7 different products including AirStart 10 CPAP, DreamStation variants, and 3B/BMC models. Most specs have exact numeric values with appropriate units and clear product linkage. However, some entries lack values (marked as null) and there are minor inconsistencies in dimension formatting, preventing a perfect score.
- **query_answerability** (4/5): The knowledge graph can answer 6-7 of the 8 question types with specific data. It has comprehensive manufacturer relationships (3B Medical, BMC, Fisher & Paykel, and implied ResMed from AirStart), detailed specifications with actual values (pressure ranges like 4-20 cm H2O, dimensions, sound levels in dBA), extensive mode/feature coverage (CPAP, Auto-CPAP, APAP modes), and some component relationships. However, it appears to lack sufficient component/accessory detail for question 6 (what comes with specific devices) and has limited standards compliance data beyond brief mentions. The specification data is particularly strong with numeric values and units, enabling meaningful cross-manufacturer comparisons on technical parameters.

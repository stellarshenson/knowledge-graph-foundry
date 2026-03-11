# Multi-Doc Benchmark v21 - deferred cross-type dedup

**Hybrid Score**: 88%
**Deterministic**: 61/63 (97%)
**Generative**: 4.0/5.0
**Date**: 2026-03-11T14:27:37.014811

## Conditions

- **Config**: v21 deferred cross-type dedup
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 964
- Relationships: 3290
- Chunks: 158
- Documents: 10
- Types: 12 distinct
- Top types: Specification:185, Component:182, Feature:169, Accessory:86, Setting:73, Interface:63, Standard:60, Product:34

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

1. **cross_doc_resolution** - Cross-type duplicates < 20 (actual=48)
2. **query_answerability** - Q: What modes does SleepStyle support?

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are well-represented with meaningful descriptions: BMC Medical (as 'BMC Medical Co., Ltd.' with technical support details), ResMed (multiple entities including main manufacturer and regional offices), Philips/Respironics (both 'Philips Respironics' and 'Respironics, Inc.' with specific contact details and warranty information), Resvent (with safety and performance responsibilities for iBreeze systems), and Fisher & Paykel (multiple related entities including 'Fisher & Paykel Healthcare' and 'F&P' covering different product lines). The knowledge graph also appropriately captures regulatory bodies like Department of Health and Medical Device Division, plus distributors and parent companies, showing comprehensive coverage beyond just the core manufacturers.
- **product_coverage** (4/5): The knowledge graph captures 6 out of 6 expected products: RESmart Auto CPAP (multiple entries with manufacturers 3B Medical, BMC Medical Co.), AirSense (AirSense 10 series and AutoSet for Her with ResMed), AirStart 10 (with ResMed), DreamStation Standard and Pro variants (with Philips Respironics), iBreeze (iBreeze 20C and 20C Pro with Resvent), and SleepStyle 200 (though missing manufacturer). Most products have proper manufacturer linkage and meaningful descriptions, but some entries have null manufacturers and there are duplicate entries with inconsistent manufacturer attribution that could indicate extraction issues.
- **cross_doc_resolution** (3/5): The duplicates show a mixed pattern. Core CPAP entities like 'humidifier', 'mask', 'filter' appear only 2 times each, which is reasonable given they legitimately function as both integrated Components and separate Accessories. Most duplicates (2 copies each) represent genuine type ambiguity rather than resolution failures - for example, 'ramp' appropriately appears as both a Feature (the functionality) and Setting (the configuration). The descriptions are meaningfully different per type, indicating proper semantic distinction. However, some entities like 'ahi', 'mask fit', and 'accessories' appear 3 times with overlapping descriptions that suggest partial resolution failures. The absence of severe duplication (5+ copies) and the fact that most common entities are reasonably consolidated indicates decent cross-document resolution, though not perfect.
- **spec_extraction** (4/5): The extraction shows good coverage across multiple CPAP products with concrete numeric values and proper units. Key specifications are well-represented including pressure ranges (4-20 cmH2O), dimensions (116x205x150 mm), weights (1106g, 1.33kg), sound levels (26.1-34.1 dB(A)), power specifications (12VDC, 80W), and operating conditions (temperature +5°C to +35°C, humidity 10-95%). The data covers at least 6-7 different CPAP models including AirStart 10, DreamStation variants, and 3B/BMC devices. Most entries have proper numeric values with units and clear product associations. However, some entries lack values (marked as null) and the extraction could be more comprehensive across all 10 devices mentioned in the task.
- **query_answerability** (4/5): The knowledge graph can answer 6-7 of the 8 question types well. It has comprehensive manufacturer-product relationships (3B Medical, BMC, Fisher & Paykel, Philips), detailed specifications with actual numeric values (pressure ranges, dimensions, weight, sound levels), extensive mode/feature coverage (CPAP, Auto-CPAP, ramp modes, humidification), and standards compliance data. However, it appears to lack comprehensive component/accessory relationships for answering 'what comes with specific devices' questions, and the OSA treatment indication data seems limited to certain products rather than being systematically available across all devices.

# Multi-Doc Benchmark v23 - H5g hierarchy resolution + rate limiter + Docker DNS

**Hybrid Score**: 83%
**Deterministic**: 60/63 (95%)
**Generative**: 3.6/5.0
**Date**: 2026-03-11T19:22:59.332360

## Conditions

- **Config**: v23 H5g hierarchy resolution + rate limiter + Docker DNS
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 1054
- Relationships: 3727
- Chunks: 159
- Documents: 10
- Types: 12 distinct
- Top types: Component:190, Feature:181, Specification:171, Section:101, Accessory:90, Standard:78, Setting:76, Interface:50

## Dimension Scores

| Dimension | Deterministic | LLM |
|---|---|---|
| Document Coverage | 4/4 (100%) | - |
| Manufacturer Coverage | 5/5 (100%) | 5/5 |
| Product Coverage | 7/7 (100%) | 3/5 |
| Cross Doc Resolution | 4/6 (67%) | 3/5 |
| Relationship Patterns | 8/8 (100%) | - |
| Spec Extraction | 8/8 (100%) | 4/5 |
| Type Distribution | 5/5 (100%) | - |
| Graph Structure | 5/5 (100%) | - |
| Query Answerability | 9/10 (90%) | 3/5 |
| Property Completeness | 5/5 (100%) | - |

## Key Failures

1. **cross_doc_resolution** - OSA entity consolidated (actual=4)
2. **cross_doc_resolution** - Cross-type duplicates < 20 (actual=45)
3. **query_answerability** - Q: What modes does SleepStyle support?

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are present with meaningful descriptions and contact details: BMC Medical Co., Ltd. (Beijing location with phone), ResMed Ltd (Australia location), Philips Respironics/Respironics Inc. (Pennsylvania location with customer service numbers), Resvent Medical Technology Co., Ltd. (Shenzhen location with contact info), and Fisher & Paykel Healthcare (with international offices). The knowledge graph also correctly captures regulatory bodies (Department of Health, Medical Device Division) and EU authorized representatives (Shanghai International Holding Corp. GmbH). Entity descriptions include specific roles, locations, and contact information, demonstrating comprehensive coverage of the manufacturer ecosystem.
- **product_coverage** (3/5): The knowledge graph captures 5 of the 6 expected products: RESmart Auto CPAP (multiple entries with BMC/3B Medical manufacturers), AirSense (ResMed), AirStart 10 (ResMed), DreamStation (Philips Respironics with both Standard and Pro variants), and iBreeze (Resvent). SleepStyle 200 is present but lacks manufacturer linkage (Fisher & Paykel missing). While most products have manufacturer information, there are inconsistencies and missing manufacturer data for some key entries, preventing a higher score.
- **cross_doc_resolution** (3/5): The entity resolution shows mixed results. Core CPAP entities like 'CPAP', 'OSA' appear to be properly resolved (not in duplicate list), which is good. However, there are many legitimate dual-type entities that represent genuine ambiguity rather than resolution failures. Items like 'integrated heated humidifier', 'flexible tubing', 'power cord', 'mask', 'tubing', 'filters' correctly appear as both Component (internal parts) and Accessory (purchasable items). Settings like 'ramp', 'time setting', 'reslex' appropriately have both Feature and Setting types. The 'dreamstation cpap pro' duplicate appears to be a genuine resolution issue with near-identical descriptions. Overall, most duplicates represent valid multi-type entities rather than resolution failures, with only minor actual duplication problems.
- **spec_extraction** (4/5): The extraction shows good coverage across multiple CPAP devices with concrete numeric values and proper units. Key specifications are well-represented including pressure ranges (4-20 cmH2O), dimensions (116x205x150 mm), weights (1106g, 1.33kg), power requirements (100-240 VAC, 12 VDC), operating temperatures (+5°C to +35°C), and sound levels (27.3 dB(A)). The data includes specs from at least 6-7 different products (DreamStation variants, AirSense 10, 3B/BMC devices) with proper product linkage. However, some entries show inconsistencies (like conflicting weight values for same product) and the extraction appears incomplete for a full 10-device evaluation, suggesting some devices may have had limited spec extraction.
- **query_answerability** (3/5): The knowledge graph can answer 4-5 of the 8 questions with specific data. It has good manufacturer coverage (3B Medical/BMC, Fisher & Paykel, plus references to ResMed devices), mode support data (Auto mode, CPAP mode, SmartRamp), standards compliance (CISPR 11, CE mark, AS3200.1.0), and some specific specifications with values (pressure ranges like 20/40 cm H2O, warranty periods of 2 years, altitude limits of 7500 feet). However, it lacks comprehensive feature comparison data across brands, complete component listings for specific devices, and detailed numeric specifications like weight, dimensions, and sound levels that would be needed for thorough cross-manufacturer comparisons.

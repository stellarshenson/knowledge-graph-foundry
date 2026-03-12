# Multi-Doc Benchmark v25 - event-driven architecture with streaming event log

**Hybrid Score**: 87%
**Deterministic**: 60/63 (95%)
**Generative**: 4.0/5.0
**Date**: 2026-03-12T10:55:58.958925

## Conditions

- **Config**: v25 event-driven architecture with streaming event log
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 1023
- Relationships: 3885
- Chunks: 159
- Documents: 10
- Types: 12 distinct
- Top types: Specification:187, Component:184, Feature:134, Section:110, Accessory:86, Standard:77, Setting:72, Interface:51

## Dimension Scores

| Dimension | Deterministic | LLM |
|---|---|---|
| Document Coverage | 4/4 (100%) | - |
| Manufacturer Coverage | 5/5 (100%) | 5/5 |
| Product Coverage | 7/7 (100%) | 3/5 |
| Cross Doc Resolution | 4/6 (67%) | 4/5 |
| Relationship Patterns | 8/8 (100%) | - |
| Spec Extraction | 8/8 (100%) | 4/5 |
| Type Distribution | 5/5 (100%) | - |
| Graph Structure | 5/5 (100%) | - |
| Query Answerability | 9/10 (90%) | 4/5 |
| Property Completeness | 5/5 (100%) | - |

## Key Failures

1. **cross_doc_resolution** - OSA entity consolidated (actual=4)
2. **cross_doc_resolution** - Cross-type duplicates < 20 (actual=28)
3. **query_answerability** - Q: What modes does SleepStyle support?

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are present with meaningful descriptions: BMC Medical Co., Ltd. (with location in Beijing), ResMed/ResMed Ltd (with Australian headquarters and AirStart device details), Philips/Respironics (with Pennsylvania location and contact info), Resvent Medical Technology Co., Ltd. (with Shenzhen address and contact details), and Fisher & Paykel Healthcare (with Icon series platform and international presence). Additionally, regulatory bodies and EU authorized representatives are properly captured, including Medical Device Division Department of Health and Shanghai International Holding Corp. GmbH as EU representative.
- **product_coverage** (3/5): The knowledge graph captures 5 of the 6 expected products: RESmart Auto CPAP (multiple entries with BMC/3B Medical manufacturers), AirSense (ResMed), AirStart 10 (ResMed), DreamStation (Philips Respironics with both standard and pro variants), and SleepStyle 200 (Fisher & Paykel Healthcare). The iBreeze product is present but lacks manufacturer linkage (shows null instead of Resvent). While most products have proper manufacturer associations and meaningful descriptions, the missing manufacturer link for iBreeze and some duplicate/fragmented entries prevent a higher score.
- **cross_doc_resolution** (4/5): The duplicates represent genuine multi-type entities rather than resolution failures. Each entity appears exactly twice with meaningfully different descriptions that justify the different types. For example, 'tubing' is legitimately both an Accessory (purchasable item) and Component (functional part), 'apnea' is both a MedicalCondition and a Feature (detection capability), and 'humidifier' serves dual roles as both standalone Accessory and integrated Component. The descriptions are distinct and contextually appropriate for each type assignment. Core entities like 'CPAP', 'OSA' are properly resolved to single instances. This represents successful cross-document resolution with appropriate handling of genuine semantic ambiguity.
- **spec_extraction** (4/5): The extraction shows good coverage across multiple CPAP products with concrete numeric values and proper units. Key specifications are well-represented including pressure ranges (4-20 cmH2O), dimensions (116x205x150 mm), weights (1106g, 1.33kg), sound levels (26.6 dBA), power supply specs (100-240 VAC, 12 VDC), and operating temperatures (+5°C to +35°C). The data includes specifications from various products like DreamStation Auto CPAP, DreamStation CPAP Pro, AirSense 10, and BMC devices. Most entries have proper numeric values with appropriate units (cmH2O, mm, kg, dBA, VAC, °C). However, some entries lack concrete values (like '90% Pressure' and 'Maximum Flow Rate') and there appear to be some data quality issues (inconsistent dimension values). The extraction covers most expected specification categories but could be more comprehensive across all 10 devices mentioned.
- **query_answerability** (4/5): The knowledge graph can answer 6-7 of the 8 question types well. It has comprehensive manufacturer-product relationships (Q1), extensive feature/mode data across brands (Q2, Q5), OSA treatment indications (Q4), component relationships (Q6), and standards compliance data (Q7). However, it has significant gaps in specific numeric specifications needed for Q3 and Q8 - while some pressure ranges, weights, and sound levels exist in the specification data, coverage appears incomplete across all devices. The graph excels at structural relationships and qualitative features but lacks comprehensive quantitative specifications for detailed cross-manufacturer comparisons.

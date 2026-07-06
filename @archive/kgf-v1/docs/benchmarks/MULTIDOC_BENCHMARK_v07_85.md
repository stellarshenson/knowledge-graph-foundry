# Multi-Doc Benchmark v07 - final tuning - broader query answerability view

**Hybrid Score**: 85%
**Deterministic**: 62/63 (98%)
**Generative**: 3.6/5.0
**Date**: 2026-03-10T01:24:07.920781

## Conditions

- **Config**: v07 final tuning - broader query answerability view
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 853
- Relationships: 3033
- Chunks: 158
- Documents: 10
- Types: 8 distinct
- Top types: Component:236, Specification:225, Feature:189, Standard:75, WorkMode:37, Product:37, MedicalCondition:31, Organization:23

## Dimension Scores

| Dimension | Deterministic | LLM |
|---|---|---|
| Document Coverage | 4/4 (100%) | - |
| Manufacturer Coverage | 5/5 (100%) | 5/5 |
| Product Coverage | 7/7 (100%) | 4/5 |
| Cross Doc Resolution | 6/6 (100%) | 4/5 |
| Relationship Patterns | 8/8 (100%) | - |
| Spec Extraction | 8/8 (100%) | 3/5 |
| Type Distribution | 5/5 (100%) | - |
| Graph Structure | 5/5 (100%) | - |
| Query Answerability | 9/10 (90%) | 2/5 |
| Property Completeness | 5/5 (100%) | - |

## Key Failures

1. **query_answerability** - Q: What modes does SleepStyle support?

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are present with meaningful descriptions: BMC Medical Co., Ltd. (with Beijing address), ResMed Ltd (with Australia address), Philips Respironics/Respironics Inc. (with contact details and warranty info), Resvent Medical Technology Co., Ltd. (with Shenzhen address), and Fisher & Paykel Healthcare (with device compatibility details). Additionally, regulatory bodies (Department of Health, Medical Device Division) and EU authorized representatives (Shanghai International Holding Corp. GmbH) are included as expected.
- **product_coverage** (4/5): The knowledge graph captures 6 out of 6 expected products: RESmart Auto CPAP (multiple variants with BMC/3B Medical manufacturers), AirSense (AirSense 10 series with ResMed), AirStart 10 (with ResMed), DreamStation Standard and Pro (with Philips Respironics), and SleepStyle 200 Series (though manufacturer cut off, likely Fisher & Paykel). Only iBreeze is missing. Most products have proper manufacturer linkage and meaningful descriptions, though some entities have null manufacturers and there are duplicate entries that could be consolidated.
- **cross_doc_resolution** (4/5): The cross-document entity resolution shows minor duplication with only 10 duplicate entities found across 10 CPAP PDFs. Most importantly, the core common entities mentioned (CPAP, OSA, humidifier) do not appear in the duplicates list, suggesting they were properly resolved. The duplicated entities are mostly technical specifications and components that legitimately might have slight variations in context or type classification across documents. The duplicate counts are low (2-3 instances) and the type variations suggest these may be contextually appropriate rather than true duplicates.
- **spec_extraction** (3/5): The extraction shows some specs with concrete numeric values from 2-3 products (mainly DreamStation CPAP Pro and some filter/tubing components), but coverage is incomplete across the expected 10 CPAP devices. While pressure ranges (4-20 cmH2O), dimensions (313×194×112 mm), weights (1.33-2.4 kg), and power specs (100-240 VAC) are present with proper units, many entries lack values (like '90% Pressure'), have inconsistent formatting, or appear to be from limited product range. Missing comprehensive specs for sound levels, operating temperature ranges, and full coverage across all 10 devices. The extraction captures key specification types but needs broader device coverage and more consistent value extraction.
- **query_answerability** (2/5): The knowledge graph can answer 2-3 questions with specific data. Question 1 (manufacturers) is clearly answerable - BMC/3B Medical, Philips Respironics, Fisher & Paykel, and F&P are identified as manufacturers. Question 6 (components) is partially answerable as various components are listed (tubing, filters, masks, power cords, headgear) though not systematically linked to specific devices. However, the graph lacks critical data for cross-manufacturer comparisons: no pressure ranges, no treatment modes (CPAP/Auto), no technical specifications (weight, dimensions, sound levels), no standards compliance information, and no feature comparisons. The relationships focus heavily on manufacturing and warranty information rather than technical specifications needed for meaningful product comparisons.

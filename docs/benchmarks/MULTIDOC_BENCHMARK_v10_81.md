# Multi-Doc Benchmark v10 - fluid mode with two-layer type normalization: deterministic surface collapsing + LLM-assisted semantic clustering, enforcement threshold 0.5%, dynamic type priority

**Hybrid Score**: 81%
**Deterministic**: 60/63 (95%)
**Generative**: 3.4/5.0
**Date**: 2026-03-10T13:28:20.152836

## Conditions

- **Config**: v10 fluid mode with two-layer type normalization: deterministic surface collapsing + LLM-assisted semantic clustering, enforcement threshold 0.5%, dynamic type priority
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 1062
- Relationships: 3780
- Chunks: 158
- Documents: 23
- Types: 15 distinct
- Top types: Specification:251, Component:167, Feature:122, Accessory:101, Standard:73, Product:43, Interface:35, Organization:34

## Dimension Scores

| Dimension | Deterministic | LLM |
|---|---|---|
| Document Coverage | 3/4 (75%) | - |
| Manufacturer Coverage | 5/5 (100%) | 5/5 |
| Product Coverage | 7/7 (100%) | 4/5 |
| Cross Doc Resolution | 5/6 (83%) | 2/5 |
| Relationship Patterns | 8/8 (100%) | - |
| Spec Extraction | 8/8 (100%) | 4/5 |
| Type Distribution | 5/5 (100%) | - |
| Graph Structure | 5/5 (100%) | - |
| Query Answerability | 9/10 (90%) | 2/5 |
| Property Completeness | 5/5 (100%) | - |

## Key Failures

1. **document_coverage** - All docs have chunks (actual=16)
2. **cross_doc_resolution** - Cross-type duplicates < 20 (actual=42)
3. **query_answerability** - Q: What modes does SleepStyle support?

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are present with meaningful descriptions: BMC Medical Co., Ltd. (with full address and contact details), ResMed/ResMed Ltd (manufacturer of AirStart 10 and other devices), Philips Respironics/Respironics Inc. (with warranty and location information), Resvent Medical Technology Co., Ltd. (with complete address and contact details), and Fisher & Paykel Healthcare (with international office support). Additionally, regulatory bodies like Department of Health and Medical Device Division are captured, along with EU authorized representative Shanghai International Holding Corp. GmbH. The knowledge graph also includes relevant trademark information, parent companies, and supporting organizations.
- **product_coverage** (4/5): The knowledge graph captures 6 out of 7 expected products with good manufacturer linkage: RESmart Auto CPAP (multiple manufacturer variants including BMC Medical Co., 3B Medical Inc.), AirSense 10 series (ResMed), AirStart 10 (ResMed), DreamStation Standard and Pro variants (Philips Respironics), and iBreeze (referenced as PAP System). Missing SleepStyle 200. Most products have meaningful descriptions with technical specifications, though some generic CPAP entries lack manufacturer information. The duplicate RESmart Auto-CPAP entries with different manufacturers suggest good data extraction but potential normalization issues.
- **cross_doc_resolution** (2/5): Many common entities that should appear once are duplicated, including core CPAP terminology like 'cpap', 'humidifier', 'sleep therapy', and 'positive airway pressure therapy'. Critical components like 'water chamber', 'headgear', 'flexible tubing', and 'battery' are also duplicated. While the duplication count is relatively low (mostly 2-3 instances), these are fundamental entities that should have been resolved to single instances across the 10 documents. The entity resolution system is failing on basic cross-document merging of identical concepts.
- **spec_extraction** (4/5): The extraction shows good coverage across multiple CPAP products with concrete numeric values and proper units. Key specifications are well-represented including pressure ranges (4-20 cmH2O), dimensions (116x205x150 mm), weight (1106g), sound levels (26.6 dBA), power supply (100-240V), and operating conditions. However, some entries lack numeric values (marked as null) and the extraction appears incomplete for a full evaluation of 10 devices - only showing partial coverage from products like AirStart 10, DreamStation CPAP, and a few others. The format is consistent with proper value-unit pairing, but comprehensive coverage across all 10 devices is not evident.
- **query_answerability** (2/5): The knowledge graph can answer only 2-3 questions with specific data. Question 1 (manufacturers) is answerable - I can identify 3B Medical/BMC, Fisher & Paykel Healthcare, and Philips Respironics as CPAP manufacturers. Question 4 (OSA treatment) is partially answerable since multiple devices mention OSA treatment. However, the graph lacks sufficient data for cross-manufacturer comparisons: no pressure ranges are provided for most devices, limited feature comparison data across brands, minimal component listings, no standards compliance information, and no detailed specifications like weight/dimensions/sound levels for comparison purposes. The data is too sparse and manufacturer-specific to enable meaningful cross-brand analysis.

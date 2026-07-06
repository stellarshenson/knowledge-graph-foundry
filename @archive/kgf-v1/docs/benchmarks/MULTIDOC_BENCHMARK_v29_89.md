# Multi-Doc Benchmark v29 - adaptive calibration hot-load and continuous prior reshaping

**Hybrid Score**: 89%
**Deterministic**: 60/63 (95%)
**Generative**: 4.2/5.0
**Date**: 2026-03-18T05:33:12.733898

## Conditions

- **Config**: v29 adaptive calibration hot-load and continuous prior reshaping
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 1041
- Relationships: 3973
- Chunks: 159
- Documents: 10
- Types: 12 distinct
- Top types: Component:190, Specification:183, Feature:138, Section:118, Accessory:95, Standard:76, Setting:67, Product:54

## Dimension Scores

| Dimension | Deterministic | LLM |
|---|---|---|
| Document Coverage | 4/4 (100%) | - |
| Manufacturer Coverage | 5/5 (100%) | 5/5 |
| Product Coverage | 7/7 (100%) | 4/5 |
| Cross Doc Resolution | 4/6 (67%) | 4/5 |
| Relationship Patterns | 8/8 (100%) | - |
| Spec Extraction | 8/8 (100%) | 4/5 |
| Type Distribution | 5/5 (100%) | - |
| Graph Structure | 5/5 (100%) | - |
| Query Answerability | 9/10 (90%) | 4/5 |
| Property Completeness | 5/5 (100%) | - |

## Key Failures

1. **cross_doc_resolution** - OSA entity consolidated (actual=4)
2. **cross_doc_resolution** - Cross-type duplicates < 20 (actual=47)
3. **query_answerability** - Q: What modes does SleepStyle support?

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are present with meaningful descriptions and contact information: BMC Medical Co., Ltd. (Beijing location with phone), ResMed Ltd (Australia headquarters), Philips/Respironics entities (including Koninklijke Philips N.V., Philips Respironics, and Respironics Inc. with detailed addresses and service info), Resvent Medical Technology Co., Ltd. (Shenzhen location with contact details), and Fisher & Paykel Healthcare (Auckland headquarters with global offices). Additionally, regulatory entities like Department of Health and EU authorized representative Shanghai International Holding Corp. GmbH are included, demonstrating comprehensive coverage of the manufacturer ecosystem.
- **product_coverage** (4/5): The knowledge graph captures 6 out of 7 expected products with good coverage: RESmart Auto CPAP (multiple entries with BMC/3B Medical manufacturers), AirSense 10 series (ResMed), AirStart 10 CPAP (ResMed), DreamStation variants including Standard and Pro (Philips Respironics), iBreeze CPAP System (Resvent), and SleepStyle 200 Series (Fisher & Paykel Healthcare). Most products have proper manufacturer linkages and meaningful descriptions. However, some entries show inconsistent manufacturer attribution (e.g., multiple manufacturers for same product) and there are many generic/duplicate entries that could be consolidated. The coverage is comprehensive but could benefit from data normalization.
- **cross_doc_resolution** (4/5): The duplicates represent genuine multi-type entities rather than resolution failures. Each entity appears only 2-3 times with meaningfully different descriptions per type - for example, 'ramp time' as a Specification (technical range), Setting (user control), and Feature (functional description). Core CPAP entities like 'humidifier', 'tubing', and 'power cord' legitimately exist as both Components (internal parts) and Accessories (purchasable items). The descriptions are distinct and contextually appropriate for each type classification, indicating successful entity resolution with proper recognition of semantic ambiguity rather than failed deduplication.
- **spec_extraction** (4/5): The extraction shows good coverage across multiple CPAP products with concrete numeric values and proper units. Key specifications are well-represented including pressure ranges (4-20 cmH2O), dimensions (116x205x150 mm), weights (1.33-1.98 kg), power requirements (100-240 VAC, 12 VDC), sound levels (27.3-35.3 dB(A)), and operating temperatures (+5 to +35°C). The data covers at least 6-7 different products (3B/BMC devices, AirSense 10, DreamStation variants) with consistent specification extraction. However, some entries lack numeric values (Mask fit, Periodic Breathing) and there are occasional unit inconsistencies or missing details that prevent a perfect score. The extraction successfully captures the most critical CPAP specifications with exact values and appropriate units across most products.
- **query_answerability** (4/5): The knowledge graph can answer 6-7 of the 8 questions well. It has comprehensive manufacturer data (3B Medical, BMC, Fisher & Paykel, etc.), extensive feature comparisons across brands (ramp, pressure relief, auto-start, humidification modes), OSA treatment indication for multiple devices, detailed mode support (CPAP, Auto, various specialized modes), component relationships (masks, tubing, filters, power supplies), and standards compliance (IEC, ISO, CISPR, etc.). However, it appears to lack sufficient specific numeric specification data for comprehensive pressure range and device specification comparisons - while some pressure values and specifications exist in the data, the coverage seems incomplete for thorough cross-manufacturer numeric comparisons of weight, dimensions, and sound levels.

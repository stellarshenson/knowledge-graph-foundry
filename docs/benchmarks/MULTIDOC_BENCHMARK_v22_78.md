# Multi-Doc Benchmark v22 - H5g ontology-enriched type resolution

**Hybrid Score**: 78%
**Deterministic**: 53/63 (84%)
**Generative**: 3.6/5.0
**Date**: 2026-03-11T17:03:54.095746

## Conditions

- **Config**: v22 H5g ontology-enriched type resolution
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 476
- Relationships: 1704
- Chunks: 104
- Documents: 10
- Types: 12 distinct
- Top types: Feature:100, Component:89, Specification:74, Section:51, Accessory:39, Setting:33, Interface:20, Product:19

## Dimension Scores

| Dimension | Deterministic | LLM |
|---|---|---|
| Document Coverage | 3/4 (75%) | - |
| Manufacturer Coverage | 4/5 (80%) | 3/5 |
| Product Coverage | 4/7 (57%) | 3/5 |
| Cross Doc Resolution | 4/6 (67%) | 4/5 |
| Relationship Patterns | 7/8 (88%) | - |
| Spec Extraction | 8/8 (100%) | 4/5 |
| Type Distribution | 5/5 (100%) | - |
| Graph Structure | 5/5 (100%) | - |
| Query Answerability | 8/10 (80%) | 4/5 |
| Property Completeness | 5/5 (100%) | - |

## Key Failures

1. **document_coverage** - All docs have chunks (actual=3)
2. **manufacturer_coverage** - Resvent entity (actual=0)
3. **product_coverage** - AirStart product (actual=0)
4. **product_coverage** - iBreeze product (actual=0)
5. **product_coverage** - SleepStyle product (actual=0)
6. **cross_doc_resolution** - OSA entity consolidated (actual=5)
7. **cross_doc_resolution** - Cross-type duplicates < 20 (actual=21)
8. **relationship_patterns** - SUPPORTS_MODE relationships (actual=1)
9. **query_answerability** - Q: What modes does SleepStyle support?
10. **query_answerability** - Q: iBreeze specifications?

## Generative Assessment

- **manufacturer_coverage** (3/5): The knowledge graph captures 3 of the 5 expected manufacturers with meaningful descriptions: BMC Medical (represented as BMC and BMC Medical Co., Ltd.), ResMed (represented as ResMed and ResMed Ltd), and Philips/Respironics (represented as Philips Respironics and parent company Koninklijke Philips N.V.). Fisher & Paykel is mentioned but only as a 'competitor manufacturer' rather than having device documentation extracted. Resvent is completely missing, though there is a 'RESmart' entity that may be related but doesn't clearly correspond to the expected manufacturer. The graph does include one regulatory body as expected, but lacks EU authorized representatives.
- **product_coverage** (3/5): The knowledge graph captures 5 of the 6 expected products: RESmart Auto CPAP (multiple entries with manufacturer links to BMC Medical Co., Ltd. and 3B Medical, Inc.), AirSense 10 series (with ResMed manufacturer links), DreamStation Auto CPAP and DreamStation CPAP Pro (with Philips Respironics manufacturer links). However, it's missing AirStart 10, iBreeze, and SleepStyle 200 entirely. While most captured products have proper manufacturer linkage and meaningful descriptions, there are data quality issues including duplicate entries and inconsistent manufacturer naming (e.g., 'ResMed' vs 'ResMed Ltd'). The coverage represents exactly 5 products with manufacturer links, meeting the threshold for a score of 3.
- **cross_doc_resolution** (4/5): The cross-document entity resolution performs well with only minor duplication issues. All duplicates show just 2-3 instances (no severe 5+ duplications), and most represent genuine multi-type entities rather than resolution failures. For example, 'integrated heated humidifier' legitimately functions as a Feature (capability), Component (internal part), and Accessory (purchasable item) with meaningfully different descriptions. Similarly, 'humidifier', 'mask', 'tubing' appropriately appear as both Components (functional parts) and Accessories (purchasable items). The few cases that might represent resolution failures (like 'auto on'/'auto off' as both Feature and Setting, or 'save' with nearly identical descriptions) are minor edge cases involving closely related semantic types. Core entities like CPAP systems and major components are properly consolidated, indicating effective resolution across the 10 documents.
- **spec_extraction** (4/5): The extraction shows good coverage across multiple CPAP products with concrete numeric values and proper units. Key specifications are well-represented including pressure ranges (4-20 cmH2O), weights (1.33-1.98 kg), dimensions (220×194×112 mm), electrical requirements (100-240 VAC), and warranty periods (2 years). The data includes specific numeric values with appropriate units (mm, kg, cmH2O, VAC, etc.) and proper product linkage. However, some expected specs like sound levels (dB) and operating temperature ranges are missing or incomplete, and a few entries have null values or non-numeric descriptions, preventing a perfect score.
- **query_answerability** (4/5): The knowledge graph can answer 6-7 of the 8 question types well. It has comprehensive manufacturer data (3B Medical, BMC, Fisher & Paykel, plus implied ResMed/Philips from product names), detailed specifications with actual numeric values (pressure ranges, dimensions, weights, ramp times), mode support information (Auto, CPAP modes), standards compliance (IEC, CISPR standards), and component relationships. However, it appears to lack sufficient cross-brand feature comparison data and may have limited component/accessory details for some devices. The specification data is particularly strong with actual values and units, enabling meaningful comparisons.

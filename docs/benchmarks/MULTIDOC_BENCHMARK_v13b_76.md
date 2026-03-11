# Multi-Doc Benchmark v13b - chao1-floor + merge-validation + relaxed-benchmark-queries

**Hybrid Score**: 76%
**Deterministic**: 59/63 (94%)
**Generative**: 3.0/5.0
**Date**: 2026-03-10T18:55:46.284175

## Conditions

- **Config**: v13b chao1-floor + merge-validation + relaxed-benchmark-queries
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 1048
- Relationships: 1735
- Chunks: 158
- Documents: 26
- Types: 15 distinct
- Top types: Component:177, Specification:108, Section:95, Product:75, Feature:69, Setting:59, Interface:56, Accessory:42

## Dimension Scores

| Dimension | Deterministic | LLM |
|---|---|---|
| Document Coverage | 3/4 (75%) | - |
| Manufacturer Coverage | 5/5 (100%) | 5/5 |
| Product Coverage | 7/7 (100%) | 3/5 |
| Cross Doc Resolution | 4/6 (67%) | 2/5 |
| Relationship Patterns | 8/8 (100%) | - |
| Spec Extraction | 8/8 (100%) | 3/5 |
| Type Distribution | 5/5 (100%) | - |
| Graph Structure | 4/5 (80%) | - |
| Query Answerability | 10/10 (100%) | 2/5 |
| Property Completeness | 5/5 (100%) | - |

## Key Failures

1. **document_coverage** - All docs have chunks (actual=16)
2. **cross_doc_resolution** - Cross-type duplicates < 20 (actual=56)
3. **cross_doc_resolution** - Humidifier entity consolidated (actual=4)
4. **graph_structure** - HAS_ENTITY relationships (actual=0)

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are present with meaningful descriptions: BMC Medical Co., Ltd. (with full address and contact details), ResMed/ResMed Ltd (with product details and locations), Philips/Respironics/Koninklijke Philips N.V. (multiple entities covering the Philips ecosystem), Resvent Medical Technology Co., Ltd. (with complete address and contact information), and Fisher & Paykel Healthcare (with international office coverage). Additionally, regulatory entities like Health Industry Manufacturers Association and EU authorized representatives like Shanghai International Holding Corp. GmbH are included, providing comprehensive coverage of the CPAP device ecosystem.
- **product_coverage** (3/5): The knowledge graph captures 5 of the 6 expected products: RESmart Auto-CPAP (present), AirSense series (multiple variants present), AirStart 10 (present), DreamStation (multiple variants present), and iBreeze (present as PAP System). Missing SleepStyle 200. However, manufacturer linkage is inconsistent - many entities show 'null' for manufacturer despite being identifiable brands (e.g., AirStart 10, RESmart should clearly link to their respective manufacturers). Only some ResMed and Philips Respironics products have proper manufacturer attribution. The descriptions are generally meaningful but the lack of consistent manufacturer linkage prevents a higher score.
- **cross_doc_resolution** (2/5): Many common CPAP entities are duplicated across documents, including core components like 'humidifier' (3x), 'integrated heated humidifier' (3x), 'breathing circuit' (2x), and 'therapy device' (2x). Key interface elements like 'mask fit' (3x), 'ramp button' (3x), and 'sleep progress' (3x) also show duplication. While the most fundamental entities like 'CPAP' and 'OSA' may not appear in this duplicate list (suggesting they were resolved), the presence of multiple duplicates for essential CPAP components and features indicates significant cross-document entity resolution failures.
- **spec_extraction** (3/5): The extraction shows some specs with concrete numeric values from 2-3 identifiable CPAP products (AirStart 10, integrated CPAP devices, and some pulse oximeter devices). Key CPAP specifications like pressure ranges (4-20 cmH2O), dimensions (116x205x150mm), weight (1106g), and sound levels (26.6 dBA) are present with proper units. However, many entries lack product association (product: null), and the data appears incomplete for a full evaluation of 10 CPAP devices. The extraction captures essential CPAP specs but coverage across the expected 10 devices is limited, with significant gaps in product identification and comprehensive specification coverage.
- **query_answerability** (2/5): The knowledge graph can answer only 2-3 of the 8 question types with specific data. It clearly identifies manufacturers (3B Medical, BMC Medical, Fisher & Paykel Healthcare) and shows which devices treat OSA through product descriptions mentioning positive pressure therapy. However, it lacks critical comparative data needed for most questions: no specific pressure ranges, device specifications (weight, dimensions, sound levels), detailed feature comparisons, supported modes, component lists, or compliance standards. The relationships are primarily organizational (MANUFACTURES, OWNS_TRADEMARK) rather than technical specifications that would enable meaningful cross-manufacturer comparisons.

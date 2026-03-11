# Multi-Doc Benchmark v14 - relaxed-queries + HAS_ENTITY-fix + chao1-floor

**Hybrid Score**: 76%
**Deterministic**: 58/63 (92%)
**Generative**: 3.0/5.0
**Date**: 2026-03-10T19:11:56.650413

## Conditions

- **Config**: v14 relaxed-queries + HAS_ENTITY-fix + chao1-floor
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 1023
- Relationships: 3928
- Chunks: 158
- Documents: 28
- Types: 15 distinct
- Top types: Component:174, Specification:110, Section:96, Feature:94, Product:72, Setting:61, Interface:51, Accessory:51

## Dimension Scores

| Dimension | Deterministic | LLM |
|---|---|---|
| Document Coverage | 3/4 (75%) | - |
| Manufacturer Coverage | 5/5 (100%) | 5/5 |
| Product Coverage | 7/7 (100%) | 3/5 |
| Cross Doc Resolution | 4/6 (67%) | 2/5 |
| Relationship Patterns | 7/8 (88%) | - |
| Spec Extraction | 8/8 (100%) | 3/5 |
| Type Distribution | 5/5 (100%) | - |
| Graph Structure | 5/5 (100%) | - |
| Query Answerability | 9/10 (90%) | 2/5 |
| Property Completeness | 5/5 (100%) | - |

## Key Failures

1. **document_coverage** - All docs have chunks (actual=18)
2. **cross_doc_resolution** - Cross-type duplicates < 20 (actual=53)
3. **cross_doc_resolution** - Humidifier entity consolidated (actual=4)
4. **relationship_patterns** - SUPPORTS_MODE relationships (actual=0)
5. **query_answerability** - Q: What modes does SleepStyle support?

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are present with meaningful descriptions: BMC Medical Co., Ltd. (with full address), ResMed/ResMed Ltd (with AutoRamp and AirSense 10 details), Philips/Respironics entities (Koninklijke Philips N.V., Philips Healthcare, Philips Respironics, Respironics Inc. with warranty and contact details), Resvent/Resvent Medical Technology Co., Ltd. (with full address and contact info), and Fisher & Paykel/Fisher & Paykel Healthcare (with Icon series and international offices). Also includes expected regulatory elements like EU Authorized Representative (Shanghai International Holding Corp. GmbH) and standards organizations.
- **product_coverage** (3/5): The knowledge graph captures 5 of the 6 expected products: RESmart Auto CPAP (with manufacturer linkage to 3B Medical/3B Products), AirSense series (ResMed), AirStart 10 (present but missing manufacturer), DreamStation (Philips Respironics), and iBreeze (as PAP System but missing manufacturer). SleepStyle 200 is completely missing. While some products have proper manufacturer linkage, several are missing this critical information, and there are data quality issues like duplicate entries and inconsistent naming conventions.
- **cross_doc_resolution** (2/5): Many common CPAP entities are duplicated across documents, including core components like 'humidifier' (3 times), 'integrated heated humidifier' (3 times), and 'breathing circuit' (2 times). Critical interface elements like 'ramp button', 'control dial', and '+/- user buttons' appear multiple times. While the most basic terms like 'CPAP' and 'OSA' may have been resolved, the system failed to merge many fundamental CPAP-related entities that should clearly be unified across documents, indicating poor cross-document entity resolution.
- **spec_extraction** (3/5): The extraction shows some specs with concrete numeric values from 2-3 products, but coverage is incomplete. Good examples include AirStart 10 with complete specs (dimensions: 116x205x150mm, pressure: 4-20 cmH2O, sound: 26.6 dBA, weight: 1106g). However, many entries lack product association (product: null) and some have missing values (n.value: null). The extraction captures key CPAP specifications like pressure ranges, dimensions, sound levels, and power requirements, but doesn't demonstrate comprehensive coverage across all 10 devices. Many specifications appear to be technical test parameters rather than core device specs.
- **query_answerability** (2/5): The knowledge graph can answer only 2-3 questions with specific data. Question 1 (manufacturers) is answerable - I can identify BMC Medical Co. Ltd., 3B Medical Inc., Fisher & Paykel Healthcare, and Philips Respironics from the MANUFACTURES relationships. Question 4 (OSA treatment) is partially answerable since multiple devices show treatment intent in descriptions. However, the graph lacks the detailed technical data needed for most other questions: no pressure ranges, device modes, specific components, compliance standards, or technical specifications like weight/dimensions/sound levels are present in the provided relationships. The data is primarily organizational and high-level product relationships rather than detailed feature comparisons.

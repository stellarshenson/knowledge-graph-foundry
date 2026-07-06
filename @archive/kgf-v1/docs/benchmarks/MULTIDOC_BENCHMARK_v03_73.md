# Multi-Doc Benchmark v03 - embeddings + name normalization + graph resolution

**Hybrid Score**: 73%
**Deterministic**: 55/63 (87%)
**Generative**: 3.0/5.0
**Date**: 2026-03-10T00:34:11.280288

## Conditions

- **Config**: v03 embeddings + name normalization + graph resolution
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 815
- Relationships: 3003
- Chunks: 158
- Documents: 10
- Types: 8 distinct
- Top types: Component:224, Specification:209, Feature:173, Standard:75, WorkMode:41, Product:37, MedicalCondition:34, Organization:22

## Dimension Scores

| Dimension | Deterministic | LLM |
|---|---|---|
| Document Coverage | 4/4 (100%) | - |
| Manufacturer Coverage | 5/5 (100%) | 5/5 |
| Product Coverage | 7/7 (100%) | 4/5 |
| Cross Doc Resolution | 1/6 (17%) | 2/5 |
| Relationship Patterns | 8/8 (100%) | - |
| Spec Extraction | 8/8 (100%) | 2/5 |
| Type Distribution | 5/5 (100%) | - |
| Graph Structure | 5/5 (100%) | - |
| Query Answerability | 9/10 (90%) | 2/5 |
| Property Completeness | 3/5 (60%) | - |

## Key Failures

1. **cross_doc_resolution** - Single CPAP mode entity (not per-doc duplicates) (actual=6)
2. **cross_doc_resolution** - OSA entity consolidated (actual=10)
3. **cross_doc_resolution** - No same-type name duplicates (actual=1)
4. **cross_doc_resolution** - Cross-type duplicates < 20 (actual=22)
5. **cross_doc_resolution** - Humidifier entity consolidated (actual=32)
6. **query_answerability** - Q: What modes does SleepStyle support?
7. **property_completeness** - Products have model_name property (actual=0)
8. **property_completeness** - Standards have standard_id property (actual=0)

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are present with meaningful descriptions: BMC Medical Co., Ltd. (Beijing-based RESmart manufacturer), ResMed (AirStart 10 CPAP producer), Philips Respironics (DreamStation manufacturer), Resvent Medical Technology Co., Ltd. (Shenzhen-based iBreeze systems), and Fisher & Paykel Healthcare (Sleep Style 200 Series). The knowledge graph also captures expected regulatory entities (Department of Health) and EU authorized representatives (Shanghai International Holding Corp. GmbH), demonstrating comprehensive coverage of the CPAP device ecosystem from the 10 PDFs across all 5 manufacturers.
- **product_coverage** (4/5): The knowledge graph captures 6 out of 7 expected products with good manufacturer linkage: RESmart Auto CPAP (multiple entries with BMC Medical Co., Ltd./3B Medical manufacturers), AirSense series (ResMed), AirStart 10 (ResMed), DreamStation Standard and Pro variants (Philips Respironics), and SleepStyle 200 (F&P). Missing iBreeze product entirely. Most products have meaningful descriptions and proper manufacturer attribution, though some entities show duplicate entries and inconsistent manufacturer naming that could be consolidated.
- **cross_doc_resolution** (2/5): Many common CPAP entities are duplicated across documents, including fundamental components like 'cpap device', 'display', 'controls', 'power supply', 'humidifier controller', and 'integrated heated humidifier'. These are core entities that should appear once in a well-resolved knowledge graph. While the duplication count is only 2 per entity (suggesting good but incomplete resolution), the breadth of duplicated common terms indicates systematic cross-document entity resolution issues rather than isolated cases.
- **spec_extraction** (2/5): The extraction shows few specifications with concrete numeric values. Only 8 out of 35+ specs have actual numeric values (like 22mm tubing diameter, 26.6 dBA sound level, 1106g weight, 7500 feet altitude, 2 years warranty, 30 seconds timeout, 10 cmH2O pressure, 30 nights filter life). Most specs have null values despite having units specified. The data appears to come from only 2-3 products (mainly AirStart 10 CPAP and DreamStation variants) rather than 10 different devices. Critical specifications like pressure ranges, dimensions, and power supply mostly lack concrete values, making this extraction incomplete for practical use.
- **query_answerability** (2/5): The knowledge graph can only answer 2-3 of the 8 question types. It provides good coverage for ResMed AirStart 10 CPAP specifications (pressure range, weight, dimensions, sound level, standards compliance) and some feature information, but lacks multi-manufacturer data needed for cross-brand comparisons. Missing are other manufacturers (BMC, Philips, Resvent, Fisher & Paykel), comprehensive feature comparisons across brands, complete component listings, and broad device mode support information. The graph is too manufacturer-specific to support meaningful cross-manufacturer analysis.

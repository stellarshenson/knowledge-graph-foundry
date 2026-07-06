# Multi-Doc Benchmark v04 - property defs + improved prompts + refined benchmark queries

**Hybrid Score**: 83%
**Deterministic**: 62/63 (98%)
**Generative**: 3.4/5.0
**Date**: 2026-03-10T00:49:27.259827

## Conditions

- **Config**: v04 property defs + improved prompts + refined benchmark queries
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 856
- Relationships: 3037
- Chunks: 158
- Documents: 10
- Types: 8 distinct
- Top types: Component:233, Specification:226, Feature:190, Standard:75, Product:40, WorkMode:38, MedicalCondition:31, Organization:23

## Dimension Scores

| Dimension | Deterministic | LLM |
|---|---|---|
| Document Coverage | 4/4 (100%) | - |
| Manufacturer Coverage | 5/5 (100%) | 5/5 |
| Product Coverage | 7/7 (100%) | 4/5 |
| Cross Doc Resolution | 6/6 (100%) | 2/5 |
| Relationship Patterns | 8/8 (100%) | - |
| Spec Extraction | 8/8 (100%) | 4/5 |
| Type Distribution | 5/5 (100%) | - |
| Graph Structure | 5/5 (100%) | - |
| Query Answerability | 9/10 (90%) | 2/5 |
| Property Completeness | 5/5 (100%) | - |

## Key Failures

1. **query_answerability** - Q: What modes does SleepStyle support?

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are present with meaningful descriptions: BMC Medical Co., Ltd. (with Beijing address), ResMed Ltd (with Australian address), Philips Respironics/Respironics Inc. (with Pennsylvania address and parent company Koninklijke Philips N.V.), Resvent Medical Technology Co., Ltd. (with Shenzhen address), and Fisher & Paykel Healthcare. The knowledge graph also includes expected regulatory bodies (Department of Health, Medical Device Division) and EU authorized representatives (Shanghai International Holding Corp. GmbH). Each manufacturer entry contains substantive details including locations, product lines, and business relationships.
- **product_coverage** (4/5): The knowledge graph captures 6 out of 7 expected products with manufacturer linkages: RESmart Auto CPAP (BMC/3B Medical), AirSense 10 series (ResMed), AirStart 10 (ResMed), DreamStation Standard and Pro variants (Philips Respironics), and SleepStyle 200 series as HC230 Product Range (Fisher & Paykel Healthcare). Missing iBreeze product. Most entities have meaningful descriptions and proper manufacturer attribution, though some duplicates exist and manufacturer names show minor inconsistencies.
- **cross_doc_resolution** (2/5): Many common CPAP entities are duplicated across documents, including core concepts like 'cpap device', 'ahi' (Apnea-Hypopnea Index), 'ramp', 'oximetry', and 'supplemental oxygen'. Technical components like 'power supply', 'display', 'humidifier' variants, and user interface elements ('ramp button', 'controls') appear multiple times. While the most basic entities like 'CPAP' and 'OSA' may have been resolved, the extensive duplication of domain-specific terms and components indicates poor cross-document entity resolution for a specialized medical device corpus.
- **spec_extraction** (4/5): The specification extraction shows good coverage across multiple CPAP device products with concrete numeric values and proper units. Key strengths include: comprehensive pressure specifications (4-20 cmH2O ranges), detailed dimensions (313×194×112 mm), weights (1.33-2.4 kg), power requirements (100-240 VAC, 80W/12V), and maintenance intervals (30 days, 1-6 months). The data covers expected categories like pressure ranges, dimensions, weights, power supply, and includes product-specific linking. However, some critical specs like sound levels (dB) and operating temperature ranges are missing from this sample, and there are occasional inconsistencies in value formatting. The extraction demonstrates solid technical specification capture but falls short of comprehensive coverage across all 10 devices and all expected specification categories.
- **query_answerability** (2/5): The knowledge graph can only answer 2-3 of the 8 question types with specific data. It identifies some manufacturers (3B/BMC, ResMed via AirSense products) and shows some devices treat OSA (AirSense 10 AutoSet for Her). However, it lacks comprehensive cross-manufacturer data for feature comparisons, specific pressure ranges, complete component lists, standards compliance details, and quantitative specifications like weight/dimensions/sound levels. The graph is heavily skewed toward ResMed products with limited representation of other manufacturers, making meaningful cross-brand comparisons impossible.

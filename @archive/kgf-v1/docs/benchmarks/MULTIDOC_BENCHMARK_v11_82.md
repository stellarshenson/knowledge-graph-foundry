# Multi-Doc Benchmark v11 - graph-aware cured-phase resolution, doc-chunk linkage fix, post-cure metrics, progression-based curing

**Hybrid Score**: 82%
**Deterministic**: 59/63 (94%)
**Generative**: 3.6/5.0
**Date**: 2026-03-10T15:16:47.019259

## Conditions

- **Config**: v11 graph-aware cured-phase resolution, doc-chunk linkage fix, post-cure metrics, progression-based curing
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 1055
- Relationships: 3057
- Chunks: 158
- Documents: 24
- Types: 15 distinct
- Top types: Specification:233, Component:188, Feature:127, Accessory:76, Standard:75, Setting:55, Medical_Condition:43, Product:38

## Dimension Scores

| Dimension | Deterministic | LLM |
|---|---|---|
| Document Coverage | 3/4 (75%) | - |
| Manufacturer Coverage | 5/5 (100%) | 5/5 |
| Product Coverage | 7/7 (100%) | 4/5 |
| Cross Doc Resolution | 4/6 (67%) | 3/5 |
| Relationship Patterns | 8/8 (100%) | - |
| Spec Extraction | 8/8 (100%) | 4/5 |
| Type Distribution | 5/5 (100%) | - |
| Graph Structure | 5/5 (100%) | - |
| Query Answerability | 9/10 (90%) | 2/5 |
| Property Completeness | 5/5 (100%) | - |

## Key Failures

1. **document_coverage** - All docs have chunks (actual=14)
2. **cross_doc_resolution** - Same-type name duplicates <= 2 (actual=3)
3. **cross_doc_resolution** - Cross-type duplicates < 20 (actual=24)
4. **query_answerability** - Q: What modes does SleepStyle support?

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are present with meaningful descriptions: BMC Medical Co., Ltd. (with full address and contact details), ResMed Ltd (with location), Philips Respironics (as manufacturer of CPAP devices), Resvent Medical Technology Co., Ltd. (with warranty services details), and Fisher & Paykel Healthcare (with headquarters address). Additionally, regulatory bodies like Department of Health and Medical Device Division are included, along with EU authorized representative Shanghai International Holding Corp. GmbH. The entities contain comprehensive information including addresses, roles, and business relationships.
- **product_coverage** (4/5): The knowledge graph captures 6 out of 7 expected products with good manufacturer linkage: RESmart Auto CPAP (multiple manufacturer entries including BMC, 3B Medical), AirSense 10 series (ResMed), AirStart 10 (ResMed), DreamStation Standard and Pro variants (Philips Respironics), and SleepStyle 200 (F&P). Missing iBreeze product entirely. Most products have meaningful descriptions with technical specifications, though some have null manufacturers. The RESmart Auto-CPAP has redundant entries with different manufacturers, and there are some generic CPAP entities without clear product identification.
- **cross_doc_resolution** (3/5): The entity resolution shows mixed results. While major entities like 'CPAP' and 'OSA' appear to be properly resolved (not in duplicates list), there are still 20 duplicate entities with counts of 2 each. These duplicates include common CPAP components (humidifier, water chamber, filters) and technical specifications that should logically appear as single entities across documents. However, the duplication is limited (only 2 instances each) and doesn't include the most critical domain entities, suggesting the core resolution is working but needs refinement for component-level terms.
- **spec_extraction** (4/5): The extraction shows good coverage across multiple CPAP products with concrete numeric values and proper units. Key specifications are well-represented including pressure ranges (4-20 cmH2O), dimensions (116x205x150 mm), weight (1106g), sound levels (26.6 dBA), power supply (100-240V), and operating temperature (+5°C to +35°C). Multiple products are covered including AirStart 10, DreamStation CPAP, and various components. Most specs have exact numeric values with appropriate units and clear product linkage. However, some entries lack values (marked as null) and coverage could be more comprehensive across all 10 expected devices, preventing a perfect score.
- **query_answerability** (2/5): The knowledge graph can answer only 2-3 questions with specific data. Question 1 (manufacturers) is answerable - I can identify BMC/3B Medical, Fisher & Paykel, and Philips Respironics as manufacturers. Question 4 (OSA treatment) is partially answerable as some devices mention OSA treatment. However, the graph lacks sufficient data for cross-manufacturer comparisons: no comprehensive pressure ranges, limited feature comparisons across brands, minimal component listings, no standards compliance data, and no detailed specifications like weight/dimensions/sound levels for comparison purposes. Most relationships focus on single products rather than enabling systematic cross-manufacturer analysis.

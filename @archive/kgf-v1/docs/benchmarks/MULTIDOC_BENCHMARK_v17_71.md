# Multi-Doc Benchmark v17 - H1-skip-double-enforcement-H2-embedding-cross-type-fluid

**Hybrid Score**: 71%
**Deterministic**: 55/63 (87%)
**Generative**: 2.8/5.0
**Date**: 2026-03-10T21:05:14.250707

## Conditions

- **Config**: v17 H1-skip-double-enforcement-H2-embedding-cross-type-fluid
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 1014
- Relationships: 3885
- Chunks: 158
- Documents: 27
- Types: 15 distinct
- Top types: Component:193, Section:98, Specification:95, Feature:92, Product:70, Standard:58, Setting:50, Accessory:42

## Dimension Scores

| Dimension | Deterministic | LLM |
|---|---|---|
| Document Coverage | 3/4 (75%) | - |
| Manufacturer Coverage | 5/5 (100%) | 5/5 |
| Product Coverage | 7/7 (100%) | 3/5 |
| Cross Doc Resolution | 4/6 (67%) | 2/5 |
| Relationship Patterns | 6/8 (75%) | - |
| Spec Extraction | 8/8 (100%) | 2/5 |
| Type Distribution | 4/5 (80%) | - |
| Graph Structure | 5/5 (100%) | - |
| Query Answerability | 8/10 (80%) | 2/5 |
| Property Completeness | 5/5 (100%) | - |

## Key Failures

1. **document_coverage** - All docs have chunks (actual=17)
2. **cross_doc_resolution** - Cross-type duplicates < 20 (actual=40)
3. **cross_doc_resolution** - Humidifier entity consolidated (actual=4)
4. **relationship_patterns** - HAS_SPECIFICATION relationships (actual=0)
5. **relationship_patterns** - SUPPORTS_MODE relationships (actual=1)
6. **type_distribution** - Singleton types < 3 (actual=12)
7. **query_answerability** - Q: What is the pressure range of DreamStation?
8. **query_answerability** - Q: What modes does SleepStyle support?

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are present with meaningful descriptions: BMC Medical Co., Ltd. (with full contact details), ResMed/ResMed Ltd (with product details like AirSense 10 series), Philips/Respironics entities (Koninklijke Philips N.V., Philips Healthcare, Philips Respironics, Respironics Inc. with warranty services), Resvent/Resvent Medical Technology Co., Ltd. (with complete address and contact information), and Fisher & Paykel/Fisher & Paykel Healthcare (with Icon series platform details). Additionally, regulatory bodies and EU authorized representatives are present as expected, including Shanghai International Holding Corp. GmbH as EU Authorized Representative with full contact details.
- **product_coverage** (3/5): {"score": 3, "reasoning": "The knowledge graph captures 5 of the 6 expected products: RESmart Auto CPAP (with multiple manufacturer entries), AirSense series (AirSense 10, AirSense 10 AutoSet for Her)
- **cross_doc_resolution** (2/5): Many common CPAP entities are duplicated across documents, indicating poor cross-document entity resolution. Critical components like 'humidifier' (3 instances), 'integrated humidifier' (2 instances), and 'integrated heated humidifier' (4 instances) should clearly be resolved as single entities. Basic interface elements like 'ramp button', 'lcd', 'user buttons' appearing multiple times suggests the system failed to recognize these as standard CPAP components that would naturally appear across multiple product manuals. While the duplicates aren't as severe as they could be (mostly 2-4 instances rather than 10), the failure to resolve fundamental domain entities represents a significant shortcoming in cross-document entity resolution.
- **spec_extraction** (2/5): The specification entities show inconsistent extraction with several critical issues: many specs lack concrete numeric values (e.g., 'Auto-CPAP Altitude Setting' has null value), units are often malformed or inconsistent (e.g., 'VAC, Hz, A' as single unit), values don't match descriptions (e.g., '0.01W' spec has value '100'), and most importantly, all products are null indicating no linkage between specs and actual CPAP devices. While some valid specs exist like dimensions and temperature ranges, the overall extraction quality is poor with incomplete coverage and data integrity issues.
- **query_answerability** (2/5): The knowledge graph can answer questions 1 and 4 with some data. For question 1, it identifies manufacturers like BMC Medical Co. Ltd., 3B Medical Inc., Fisher & Paykel Healthcare, and references to Philips Respironics and ResMed, though the data is incomplete. For question 4, it shows multiple devices are intended for OSA treatment. However, it lacks sufficient data for the other 6 questions - there's minimal feature comparison data, no specific pressure ranges, limited mode information, few component details, no standards compliance data, and no technical specifications like weight, dimensions, or sound levels. The graph appears to focus more on organizational relationships and basic product identification rather than detailed technical specifications needed for comprehensive cross-manufacturer comparisons.

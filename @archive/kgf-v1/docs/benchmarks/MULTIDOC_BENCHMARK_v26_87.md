# Multi-Doc Benchmark v26 - dead code pass 2 - removed unused deps, fixed defaults mismatch, added missing config entries

**Hybrid Score**: 87%
**Deterministic**: 60/63 (95%)
**Generative**: 4.0/5.0
**Date**: 2026-03-12T13:32:04.403083

## Conditions

- **Config**: v26 dead code pass 2 - removed unused deps, fixed defaults mismatch, added missing config entries
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 1004
- Relationships: 3803
- Chunks: 159
- Documents: 10
- Types: 12 distinct
- Top types: Component:185, Specification:183, Feature:148, Section:106, Accessory:82, Standard:72, Setting:66, Interface:52

## Dimension Scores

| Dimension | Deterministic | LLM |
|---|---|---|
| Document Coverage | 4/4 (100%) | - |
| Manufacturer Coverage | 5/5 (100%) | 5/5 |
| Product Coverage | 7/7 (100%) | 3/5 |
| Cross Doc Resolution | 4/6 (67%) | 4/5 |
| Relationship Patterns | 8/8 (100%) | - |
| Spec Extraction | 8/8 (100%) | 4/5 |
| Type Distribution | 5/5 (100%) | - |
| Graph Structure | 5/5 (100%) | - |
| Query Answerability | 9/10 (90%) | 4/5 |
| Property Completeness | 5/5 (100%) | - |

## Key Failures

1. **cross_doc_resolution** - OSA entity consolidated (actual=4)
2. **cross_doc_resolution** - Cross-type duplicates < 20 (actual=28)
3. **query_answerability** - Q: What modes does SleepStyle support?

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are present with meaningful descriptions: BMC Medical Co., Ltd. (with location in Beijing), ResMed Ltd (with Australian location and trademarks), Philips/Respironics (both Koninklijke Philips N.V. as parent and Philips Respironics/Respironics Inc. with Pennsylvania locations and contact details), Resvent Medical Technology Co., Ltd. (with Shenzhen location and contact info), and Fisher & Paykel Healthcare (with international offices mentioned). Additionally, regulatory bodies and EU authorized representatives are properly captured, including Medical Device Division Department of Health and Shanghai International Holding Corp. GmbH as EU Authorized Representative.
- **product_coverage** (3/5): The knowledge graph captures 5 of the 6 expected products: RESmart Auto CPAP (multiple entries with BMC/3B Medical manufacturers), AirSense (ResMed), AirStart 10 (ResMed), DreamStation (Philips Respironics with Standard/Pro variants), and SleepStyle 200 (Fisher & Paykel Healthcare). The iBreeze product is present but lacks manufacturer linkage (shows null instead of Resvent). Most products have proper manufacturer associations and meaningful descriptions, but the incomplete manufacturer coverage for iBreeze and some duplicate entries with missing manufacturer data prevent a higher score.
- **cross_doc_resolution** (4/5): The duplicates represent genuine multi-type entities rather than resolution failures. Each entity appears exactly twice with meaningfully different descriptions that justify the different types. For example, 'humidifier' as Component (internal system part) vs Accessory (purchasable item), 'ramp' as Feature (therapy function) vs Component (physical control), and 'warranty' as Section (documentation) vs Specification (technical detail). Core entities like CPAP, OSA are properly resolved to single instances. The dual typing reflects legitimate conceptual distinctions where the same named entity serves different roles in the CPAP ecosystem.
- **spec_extraction** (4/5): The extraction shows good coverage across multiple CPAP products with concrete numeric values and proper units. Key specifications are well-represented including pressure ranges (4-20 cmH2O), dimensions (116x205x150 mm), weights (1106g, 1.33kg), sound levels (26.1-34.1 dB(A)), power supply (12VDC, 100-240VAC), and operating temperatures (+5°C to +35°C). The data covers at least 8-9 different products including DreamStation models, AirSense devices, and various CPAP accessories. Most entries have proper numeric values with appropriate units (cmH2O, mm, kg, dB, VAC, °C). However, some entries lack complete numeric values (like 'Maximum dynamic pressure variation' showing null values) and coverage could be more comprehensive across all 10 expected devices. The specification linking to products is consistent and the technical detail level is appropriate for medical device documentation.
- **query_answerability** (4/5): The knowledge graph can answer 6-7 of the 8 question types well. It has comprehensive manufacturer-product relationships (Q1), mode/feature data across brands (Q2, Q5), OSA treatment indications (Q4), component relationships (Q6), and standards compliance (Q7). Specifications include many numeric values like warranty periods, data storage capacities, altitude limits, and AHI values (Q3, Q8). However, critical specifications like pressure ranges, weight, dimensions, and sound levels appear limited or missing from the sample data, which would prevent complete answers to device specification comparisons. The graph structure supports cross-manufacturer queries but lacks some key technical specifications users commonly need for device comparisons.

## Forensic Analysis

### Failure Root Causes

| Issue | Root Cause | Actionable? |
|-------|-----------|-------------|
| Cross-type dupes = 28 (target <20) | 15 blocked pairs with posteriors 0.45-0.60, just below 0.6 threshold. Top offenders: `integrated heated humidifier` (3 pairs), `type bf applied part`, `flexible tubing`, Section/Interface trio (`home screen`, `my setup`, `patient standby interface`) | Yes - hierarchy enforcement or threshold tuning |
| OSA = 4 (target 1-3) | Extracted 7x as MedicalCondition, 3 merged during load, 4 name variants survived normalization. Graph-load merge miss, not cross-type | Yes - name normalization |
| SleepStyle modes | No mode entities extracted from SleepStyle's 13 chunks at all. Extraction gap, not resolution | Prompt investigation needed |
| iBreeze -> Resvent | No MANUFACTURES relationship created. Resvent never appears as Organization in events. Extraction gap | Prompt investigation needed |

### Pipeline Health

- **Curing**: metric trigger at doc 4 (4 fluid, 6 cured)
- **LLM**: 0 failures across 159 calls, avg 19s, max 40s
- **Resolution**: 74 cross-type decisions (36 hierarchy_merge, 12 merged, 15 blocked, 9 multi_facet, 2 deferred)
- **Deferred dedup**: minimal impact - 2 pairs deferred, both skipped at resolution

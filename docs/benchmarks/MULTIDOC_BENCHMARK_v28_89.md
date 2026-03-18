# Multi-Doc Benchmark v28 - dead code cleanup, FSM active, calibration and correlation signals

**Hybrid Score**: 89%
**Deterministic**: 60/63 (95%)
**Generative**: 4.2/5.0
**Date**: 2026-03-18T03:38:50.631854

## Conditions

- **Config**: v28 dead code cleanup, FSM active, calibration and correlation signals
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 1008
- Relationships: 3817
- Chunks: 159
- Documents: 10
- Types: 12 distinct
- Top types: Component:189, Specification:165, Feature:151, Section:113, Accessory:82, Standard:82, Setting:65, Interface:50

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
2. **cross_doc_resolution** - Cross-type duplicates < 20 (actual=35)
3. **query_answerability** - Q: What modes does SleepStyle support?

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are present with meaningful descriptions: BMC Medical Co., Ltd. (with location in Beijing), ResMed/ResMed Ltd (with Australian headquarters and AirStart device details), Philips Respironics/Respironics Inc. (with Pennsylvania location and contact info), Resvent Medical Technology Co., Ltd. (with Shenzhen address and contact details), and Fisher & Paykel Healthcare (with Icon series platform). Additionally, regulatory bodies and EU authorized representatives are properly captured, including Medical Device Division Department of Health and Shanghai International Holding Corp. GmbH as EU Authorized Representative.
- **product_coverage** (4/5): The knowledge graph captures 6 out of 6 expected products: RESmart Auto CPAP (multiple entries with BMC/3B Medical manufacturers), AirSense (ResMed), AirStart 10 (ResMed), DreamStation Standard/Pro (Philips Respironics), iBreeze (Resvent), and SleepStyle 200 (Fisher & Paykel Healthcare). All products have manufacturer linkages and meaningful descriptions. However, there are data quality issues including duplicate entries with inconsistent manufacturer names (e.g., 'ResMed' vs 'ResMed Ltd'), some missing manufacturer fields, and overly generic entries like 'system' and 'therapy device' that add noise to the dataset.
- **cross_doc_resolution** (4/5): The duplicates represent genuine multi-type entities rather than resolution failures. Each entity appears exactly twice with meaningfully different descriptions that justify the different types. For example, 'heater' as a Component (physical heating element) vs Setting (temperature control), 'ramp' as Interface (button) vs Feature (therapy function), and 'humidifier' as Component (internal part) vs Accessory (separate add-on). Core entities like CPAP, OSA are not duplicated, and the 2-instance duplicates show proper semantic distinction between physical components, user interfaces, settings, and features - indicating successful cross-document resolution with appropriate type disambiguation.
- **spec_extraction** (4/5): The extracted specifications show good coverage across multiple CPAP devices with concrete numeric values and proper units. Key strengths include: comprehensive pressure ranges (4-20 cmH2O), precise dimensions (116x205x150 mm), specific weights (1106g, 1.33kg), electrical requirements (100-240 VAC), sound levels (26.1-34.1 dB(A)), temperature ranges (+5°C to +35°C), and service specifications (warranty periods, data storage capacities). The extraction covers most expected specification categories across different product models (DreamStation, AirSense, 3B/BMC). However, some inconsistencies exist in dimension values and a few specifications lack numeric values entirely, preventing a perfect score. The overall quality demonstrates systematic extraction with proper value-unit-product linkage across the majority of devices.
- **query_answerability** (4/5): The knowledge graph can answer 6-7 of the 8 question types well. It has comprehensive manufacturer-product relationships (Q1), extensive mode/feature data across brands (Q2, Q5), detailed specification values with units for pressure ranges and other numeric specs (Q3, Q8), treatment indications for OSA (Q4), component relationships (Q6), and standards compliance data (Q7). However, some specification comparisons may be limited by incomplete coverage across all products, and while the graph contains substantial numeric specification data, complete cross-manufacturer comparison for all technical specs may not be fully answerable due to potential gaps in the dataset.

## Changes Since v27

1 commits since last benchmark (MULTIDOC_BENCHMARK_v27_85.md):

- `ced43b2 docs: update FSC-3 implementation status and add FSC-9 curing semantic breadth`


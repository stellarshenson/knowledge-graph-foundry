# Multi-Doc Benchmark v27 - FSM implementation with graph-resident control plane

**Hybrid Score**: 85%
**Deterministic**: 60/63 (95%)
**Generative**: 3.8/5.0
**Date**: 2026-03-17T21:19:23.923413

## Conditions

- **Config**: v27 FSM implementation with graph-resident control plane
- **Model**: eu.anthropic.claude-sonnet-4-20250514-v1:0 (Bedrock)

## Graph Stats

- Entities: 1036
- Relationships: 3880
- Chunks: 159
- Documents: 10
- Types: 12 distinct
- Top types: Specification:182, Component:181, Feature:148, Section:107, Accessory:92, Standard:74, Setting:72, Interface:59

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
| Query Answerability | 9/10 (90%) | 3/5 |
| Property Completeness | 5/5 (100%) | - |

## Key Failures

1. **cross_doc_resolution** - OSA entity consolidated (actual=4)
2. **cross_doc_resolution** - Cross-type duplicates < 20 (actual=34)
3. **query_answerability** - Q: What modes does SleepStyle support?

## Generative Assessment

- **manufacturer_coverage** (5/5): All 5 expected manufacturers are present with meaningful descriptions: BMC Medical Co., Ltd. (with full address in Beijing), ResMed Ltd (with Australian address and AirStart device details), Philips/Respironics represented by both Koninklijke Philips N.V. and Respironics Inc. (with Pennsylvania address and warranty details), Resvent Medical Technology Co., Ltd. (with Shenzhen address and contact info), and Fisher & Paykel Healthcare (with device recommendations). Additionally, regulatory bodies and EU authorized representatives are properly captured, including Shanghai International Holding Corp. GmbH as EU representative and Medical Device Division Department of Health as regulatory body.
- **product_coverage** (3/5): The knowledge graph captures 5 of the 6 expected products: RESmart Auto CPAP (multiple entries with BMC Medical Co., Ltd. manufacturer), AirSense (ResMed manufacturer), AirStart 10 (ResMed manufacturer), DreamStation Standard/Pro (Philips Respironics manufacturer), and SleepStyle 200 (Fisher & Paykel Healthcare manufacturer). The iBreeze product is present but lacks manufacturer linkage (shows null instead of Resvent). While most products have proper manufacturer associations and meaningful descriptions, the missing manufacturer link for iBreeze and some duplicate entries with inconsistent manufacturer information (like multiple RESmart entries with different manufacturers) indicate room for improvement in data consistency.
- **cross_doc_resolution** (4/5): The entity resolution is quite good with only minor duplication in edge cases. All duplicates show exactly 2 instances (no severe multiplication), and most represent genuine multi-type entities rather than resolution failures. For example, 'humidifier' legitimately exists as both a Component (internal system) and Accessory (external add-on), 'time setting' appears as both Feature (display capability) and Setting (configuration option), and 'warranty' exists as both Section (documentation) and Specification (terms). The descriptions are meaningfully different per type, indicating proper semantic distinction rather than failed deduplication. Core CPAP entities like 'CPAP', 'OSA' are not duplicated, suggesting the resolution successfully handled the most important common terms across the 10 documents.
- **spec_extraction** (4/5): The extraction shows good coverage across multiple CPAP products with concrete numeric values and proper units. Key specifications are well-represented including pressure ranges (4-20 cmH2O), dimensions (116x205x150 mm), weights (1106g, 1.33kg), power requirements (100-240 VAC, 12 VDC), sound levels (27.3-35.3 dB(A)), operating temperatures (+5°C to +35°C), and altitude limits (0-3000m). The data includes proper product linkage and covers expected specs like warranty periods (2 years), data storage capacities, and technical specifications. However, some entries have missing values (null) and the coverage appears to be from fewer than 10 distinct devices, suggesting incomplete extraction from all PDFs.
- **query_answerability** (3/5): The knowledge graph can answer 4-5 of the 8 question types. It has good manufacturer-product relationships (Q1), some feature/mode data (Q2, Q5), treatment indications for OSA (Q4), and standards compliance (Q7). However, it lacks comprehensive numeric specifications for pressure ranges (Q3), complete component listings (Q6), and detailed device specifications like weight, dimensions, sound levels (Q8). While some numeric values exist (warranty periods, altitude limits, data storage), critical comparison metrics like pressure ranges and physical specifications are missing or incomplete, limiting cross-manufacturer comparisons.

## Changes Since v26

36 commits since last benchmark (MULTIDOC_BENCHMARK_v26_87.md):

- `87b13bd chore: move FSM implementation log to project root`
- `1671dea feat: implement pipeline lifecycle FSM with graph-resident control plane`
- `6099669 docs: add pipeline lifecycle FSM section and generative simulations`
- `e0c4400 docs: extract foundational research concepts from design conversations`
- `d197eed fix: sanitize NaN in event log, add timestamps and doc_index to LLM calls`
- `ede668f docs: update benchmark spec to log into tmp/ with both event and processing logs`
- `0876bbd chore: updated with the latest changes to the references (projects)`
- `a473e6b docs: rename DESIGN_ASSUMPTIONS to DESIGN_CONCEPTS, add future concepts`
- `38d6fe3 chore: organize references into articles, papers, other-projects`
- `8047a69 docs: move project reference insights to references/other-projects/`
- `2f12036 feat: add --input multi-option and --structured/--unstructured pipeline modes`
- `246704d docs: update journal with SVG path fix`
- `8e3c62f fix: correct SVG image paths in KGF_DESIGN.md`
- `adb32f2 docs: add 6 KGF design infographics and refine SVG design system`
- `ee8c270 docs: clean up LLM engagement matrix and call site SVG labels`
- `479afc0 fix: standardize arrow stems and swatch layout`
- `0c04d66 docs: standardize SVG card shape and arrow design across all infographics`
- `53fb3e8 docs: update header banner credits with full format`
- `3f100a1 docs: simplify header banner credits line`
- `e027a4b docs: rename kg-builder-cli to kgf in header banner`
- `d5038c8 docs: embed SVG infographics in KGF_DESIGN.md`
- `97892ea docs: fix SVG layout issues and add header banner`
- `dc23577 docs: add KGF design infographics with WCAG AA validated palette`
- `e586d26 docs: add KGF theme swatch derived from Stellars-Tech logo palette`
- `70962b4 docs: tighten pipeline-first language, escalation logging, and no-mutation mandate in KGF_DESIGN`
- `a4df25c fix: harden LLM cassette system and wire token usage tracking`
- `b38e692 chore: add MIT license`
- `3ac5af7 docs: update testing strategy with LLM cassette system`
- `e400287 feat: add LLM cassette recording/replay system for deterministic tests`
- `d9d4c38 docs: fix hybrid architecture integrity in KGF_DESIGN.md`
- `47c2c3a docs: replace aspirational agent architecture with hybrid design in KGF_DESIGN.md`
- `7f1b4f8 docs: remove /forensics reference from README, update journal`
- `e07b48e docs: rewrite README with plain-language explanation of what KGF does`
- `3b43383 feat: agentic /forensics command for post-benchmark investigation`
- `98760c5 docs: add post-benchmark forensics procedure to benchmark spec`
- `be47240 feat: add implementation delta section to benchmark reports`


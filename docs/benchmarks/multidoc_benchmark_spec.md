# Multi-Document Benchmark Specification

Evaluates knowledge graph quality built from a 10-document CPAP device corpus across 5 manufacturers. Measures entity coverage, cross-document resolution, relationship patterns, specification extraction, and query answerability.

## Corpus

| # | File | Size | Manufacturer | Type |
|---|------|------|-------------|------|
| 1 | BMC_RESmart_AutoCPAP_User_Manual.pdf | 379 KB | BMC Medical | User manual |
| 2 | 3B_User-Manual_CPAP-Auto-CPAP_RESmart_BMC_V1.7_ENG-1.pdf | 649 KB | BMC Medical | User manual |
| 3 | Airsense-Brochure.pdf | 913 KB | ResMed | Brochure |
| 4 | airstart-10-cpap_fact-sheet_apac_eng.pdf | 252 KB | ResMed | Fact sheet |
| 5 | BC-Dreamstation-Standard-CPAP.pdf | 135 KB | Philips Respironics | One-pager |
| 6 | CPAP_Eng.pdf | 421 KB | Generic | Technical doc |
| 7 | DreamStation_CPAP_Pro_DataSheet.pdf | 3.9 MB | Philips Respironics | Datasheet |
| 8 | DreamStation_CPAP_User_Manual.pdf | 3.2 MB | Philips Respironics | User manual |
| 9 | Resvent-iBreeze-Auto-CPAP-User-Manual.pdf | 897 KB | Resvent | User manual |
| 10 | SleepStyle_200_Operating_Manual.pdf | 1.0 MB | Fisher & Paykel | Operating manual |

Total corpus: ~11.8 MB, 5 manufacturers, mix of manuals/datasheets/brochures.

## Scoring Method

Hybrid score = (deterministic_pct * 0.5) + (generative_avg_normalized * 0.5)

Where `generative_avg_normalized = (generative_avg / 5.0) * 100`

- Deterministic: 63 Cypher queries against ground truth (pass/fail)
- Generative: 5 LLM-assessed dimensions (1-5 scale, normalized to 0-100%)
- Model for generative scoring: Claude Sonnet 4 via Bedrock (`eu.anthropic.claude-sonnet-4-20250514-v1:0`)

## Standard Properties (Base Entity)

All entity nodes carry system-populated standard properties defined in `types/ontology.py` as `DEFAULT_BASE_PROPERTIES`. These enable 0-hop provenance queries instead of 3-hop Entity -> Chunk -> Document traversals.

| Category | Properties | Auto |
|----------|-----------|------|
| Provenance | source_document, source_chunks, source, source_type | Yes |
| Confidence | confidence, extraction_method, source_frequency | Yes |
| Lifecycle | created_at, updated_at, ingestion_run_id, update_count | Yes |

The `update_count` increments on every MERGE update. `created_at` is immutable after first write. Properties are configurable via `base_entity` section in ontology YAML.

## Dimensions (10 deterministic + 5 generative)

Check distribution: 4 + 5 + 7 + 6 + 8 + 8 + 5 + 5 + 10 + 5 = 63 deterministic checks.

### 1. Document Coverage (4 checks)

Validates all 10 PDFs are ingested with proper graph structure.

- 10 Document nodes present
- All documents have chunks (no orphan documents)
- Total chunks > 100 across corpus
- NEXT_CHUNK chains exist per document

### 2. Manufacturer Coverage (5 checks + generative)

Validates all 5 CPAP device manufacturers are extracted as Organization entities.

- BMC Medical
- ResMed
- Philips / Respironics
- Resvent
- Fisher & Paykel

Generative: rates 1-5 based on how many of the 5 manufacturers are present with meaningful descriptions.

### 3. Product Coverage (7 checks + generative)

Validates distinct product entities from each manufacturer.

- RESmart (BMC)
- AirSense (ResMed)
- AirStart (ResMed)
- DreamStation (Philips)
- iBreeze (Resvent)
- SleepStyle (Fisher & Paykel)
- At least 5 distinct Product-typed entities

Generative: rates product completeness and manufacturer linkage.

### 4. Cross-Document Entity Resolution (6 checks + generative)

The critical multi-doc dimension. Common entities appearing across documents should merge, not duplicate per-document.

- CPAP mode entity consolidated (not 10 copies)
- OSA entity consolidated
- No same-type name duplicates
- Cross-type duplicates < 20
- Humidifier entity consolidated
- Mask entity consolidated

Generative: rates deduplication quality across the 10-doc corpus.

### 5. Relationship Patterns (8 checks)

Validates ontology-defined relationship types are populated.

- MANUFACTURES (>= 3)
- HAS_SPECIFICATION (>= 5)
- HAS_FEATURE (>= 5)
- HAS_COMPONENT (>= 3)
- SUPPORTS_MODE (>= 3)
- TREATS (>= 1)
- COMPLIES_WITH (>= 1)
- Orphan ratio < 20%

### 6. Specification Extraction (8 checks + generative)

Validates numeric specifications with units are extracted across products.

- Pressure specs with hPa/cmH2O
- Weight specs with kg/lbs
- Sound/noise level with dB
- Dimension/size specs with mm
- Power/voltage specs
- Specs have `value` property (>= 5)
- Specs have `unit` property (>= 3)
- Total spec entities >= 10

Generative: rates spec completeness across products.

### 7. Type Distribution (5 checks)

Validates the ontology type system is well-utilized.

- All 8 ontology types present (Product, Specification, Feature, Component, Organization, Standard, MedicalCondition, WorkMode)
- Entity count 100-2000
- No type casing variants
- Singleton types < 3

### 8. Graph Structure (5 checks)

Validates structural integrity of the graph.

- HAS_CHUNK relationships >= 100
- HAS_ENTITY relationships >= 50
- Total relationships > 200
- Entity-to-entity relationships > 50
- Most entities have descriptions (> 80%)

### 9. Query Answerability (10 checks + generative)

Validates the graph can answer real cross-manufacturer comparison questions.

- Which manufacturers make CPAP devices?
- What products does ResMed make?
- What products does Philips make?
- Compare product features
- DreamStation pressure range
- Which devices treat OSA?
- RESmart components
- SleepStyle modes
- Device compliance standards
- iBreeze specifications

Generative: rates ability to answer 8 cross-manufacturer comparison questions.

### 10. Property Completeness (5 checks)

Validates structured properties from the ontology are populated.

- Confidence scores on entities
- Products have `model_name` property
- Organizations have `role` property
- Standards have `standard_id` property
- Features have descriptions

## Ground Truth Expectations

### Manufacturers (5)
BMC Medical Co. Ltd., ResMed, Philips Respironics, Resvent, Fisher & Paykel Healthcare

### Products (7+)
RESmart Auto CPAP, AirSense (10), AirStart 10, DreamStation Standard CPAP, DreamStation CPAP Pro, iBreeze Auto CPAP, SleepStyle 200

### Common Entities (should merge across docs)
CPAP (therapy/mode), Obstructive Sleep Apnea / OSA, humidifier, mask, tubing, air filter, power supply

### Expected Specs (per product where available)
Pressure ranges (4-20 hPa typical), weight, dimensions, sound level, power supply voltage, operating temperature

## Execution

All ingestion runs use the `kg` CLI tool:

```bash
# Clean graph before each iteration
# Free mode (no ontology)
kg ingest data/raw/cpap-benchmark/ --config tmp/.kg-builder/config.yml

# Constrained mode (with ontology)
kg ingest data/raw/cpap-benchmark/ --config tmp/.kg-builder/config.yml --ontology data/ontologies/cpap_medical_device.yml
```

Benchmark scoring: `python tests/benchmark_multidoc.py "description of iteration"`

## Iteration Results

| Iteration | Hybrid | Det | Gen | Focus |
|-----------|--------|-----|-----|-------|
| v01 (baseline) | 73% | 54/63 (86%) | 3.0/5.0 | Free mode, no ontology, 33 emergent types |
| v02 | - | - | - | Ontology constraint + standard base_entity properties |
| v03 | - | - | - | Cross-doc resolution improvement |
| v04 | - | - | - | Specification property extraction |
| v05 | - | - | - | Query answerability and relationship completeness |

## Iteration Targets

| Iteration | Target Score | Focus |
|-----------|-------------|-------|
| v01 (baseline) | Establish baseline | Free mode, no ontology - **actual: 73%** |
| v02 | > 80% | Add ontology constraint + standard properties |
| v03 | > 85% | Improve cross-doc resolution |
| v04 | > 88% | Specification property extraction |
| v05 | > 90% hybrid | Query answerability and relationship completeness |

## v01 Key Findings

- 1007 entities, 3744 relationships, 158 chunks, 10 documents
- 33 distinct types emerged (free mode) - top: Specification:181, Component:151, Feature:111, Accessory:82, Product:48
- Cross-doc resolution scored 17% (1/6) - 97 cross-type duplicates, 30 same-type duplicates
- 12 OSA entities instead of 1-3, 33 humidifier entities instead of 1-5
- Property completeness 60% - no structured properties (model_name, standard_id, role)
- Spec values buried in descriptions rather than extractable value/unit properties

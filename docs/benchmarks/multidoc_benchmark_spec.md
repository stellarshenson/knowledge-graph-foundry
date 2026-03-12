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

**Generative judge context**: Full Organization entity list with `name`, `description`, `role` properties. No truncation.

**Quality criteria**: Each manufacturer should have a meaningful description (not just the name repeated) and ideally a `role` property indicating "manufacturer". The judge evaluates presence, description quality, and whether the manufacturer ecosystem (regulatory bodies, authorized representatives) is captured.

**Scoring rubric**: 1=0-1 manufacturers, 2=2, 3=3, 4=4, 5=all 5 with meaningful descriptions.

**Known failure modes**:
- Manufacturer name variants not merged (e.g. "ResMed" vs "ResMed Ltd" as separate entities)
- Regulatory bodies extracted as Organization but without role differentiation
- Description containing only address/contact info instead of business description

### 3. Product Coverage (7 checks + generative)

Validates distinct product entities from each manufacturer.

- RESmart (BMC)
- AirSense (ResMed)
- AirStart (ResMed)
- DreamStation (Philips)
- iBreeze (Resvent)
- SleepStyle (Fisher & Paykel)
- At least 5 distinct Product-typed entities

**Generative judge context**: Product entities with `name`, `description`, plus MANUFACTURES relationship showing linked Organization entity name.

**Quality criteria**: Each product should have (a) a descriptive name matching source documents, (b) a description explaining what it is, (c) a MANUFACTURES link to its manufacturer Organization. The judge evaluates product count, description quality, and manufacturer linkage completeness.

**Scoring rubric**: 1=0-2 products, 2=3-4, 3=5, 4=6, 5=7+ all with manufacturer links.

**Known failure modes**:
- Product name variants not merged (e.g. "DreamStation Standard CPAP" and "DreamStation CPAP" as separate entities)
- Missing iBreeze - Resvent manual may have parsing issues or the product name appears in non-standard formatting
- Products missing MANUFACTURES link despite manufacturer existing as a separate entity
- Product descriptions that are too generic ("a CPAP device") rather than capturing distinguishing features

### 4. Cross-Document Entity Resolution (6 checks + generative)

The critical multi-doc dimension. Common entities appearing across documents should merge, not duplicate per-document.

- CPAP mode entity consolidated (not 10 copies)
- OSA entity consolidated
- No same-type name duplicates
- Cross-type duplicates < 20
- Humidifier entity consolidated
- Mask entity consolidated

**Generative judge context**: Top 20 duplicated entity names with their type lists and instance counts, sorted by count descending. Shows how many times each entity name appears with potentially different types.

**Quality criteria**: The judge evaluates (a) whether core domain entities (CPAP, OSA, humidifier, mask, tubing, filter) are consolidated to 1-2 instances, (b) whether duplication is from genuine type ambiguity (acceptable) or resolution failures (not acceptable), (c) overall deduplication ratio. The judge should distinguish between entities that legitimately carry multiple types (e.g. "humidifier" is both Component when inside a device and Accessory when sold separately) versus entities that are simply unresolved duplicates.

**Scoring rubric**: 1=severe duplication (core entities appear 5+ times), 2=many common entities duplicated (3-4 times), 3=some duplicates but core entities clean (1-2 times), 4=minor duplication only in edge cases, 5=excellent resolution with no meaningful duplicates.

**Known failure modes**:
- Cross-type duplicates where same entity name has different types (Component vs Accessory, Feature vs Interface vs Setting) - these survive dedup because the dedup key includes entity type
- Description divergence blocking Bayesian merge - "humidifier" as Component has technical description, as Accessory has purchasing description, resulting in low Jaccard and posterior below threshold
- Entities from cured-phase documents that lack embeddings on the graph side, preventing the embedding cosine signal from contributing to the Bayesian posterior
- Genuinely ambiguous entities that are both types simultaneously (15-20 of the ~39 remaining cross-type duplicates in v19)

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

**Note on APOC relationship types**: Relationships are created via APOC `apoc.merge.relationship()` which creates native Neo4j relationship types. Use `type(r)` to access the relationship type name. The `r.type` property is NULL for APOC-created relationships. This distinction is critical for all Cypher queries that filter or return relationship types.

**Note on SUPPORTS_MODE**: The ontology has no `Mode` entity type. Modes are extracted as `Feature` or `Setting` entities (e.g. "CPAP Mode" as Feature, "standby mode" as Setting). The SUPPORTS_MODE check must match on entity name containing "mode" with type in `['feature', 'setting']`, and include relationship types `HAS_FEATURE` and `HAS_SETTING` alongside `SUPPORTS_MODE`.

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

**Generative judge context**: Full Specification entity list with `name`, `description`, `value`, `unit` properties, plus linked Product name via HAS_SPECIFICATION relationship. No description truncation.

**Quality criteria**: The judge evaluates (a) whether specs have concrete numeric values (not just descriptive text), (b) whether units are proper measurement units (cmH2O, kg, dB, mm, V), (c) whether specs are linked to the correct product, (d) coverage across multiple products (not just one device). The judge specifically looks for extractable data points: exact pressure ranges, weights, dimensions, noise levels, power ratings.

**Scoring rubric**: 1=no numeric values, 2=few specs without values, 3=some specs with values from 2-3 products, 4=good coverage across most products, 5=comprehensive specs with exact values from most products.

**Known failure modes**:
- Spec values buried in description text instead of extracted into `value`/`unit` properties (e.g. description says "4-20 cmH2O" but value and unit fields are null)
- Specs extracted without product linkage (orphan Specification entities with no HAS_SPECIFICATION relationship)
- Unit normalization issues (e.g. "hPa" vs "cmH2O" for the same pressure measurement)
- Specifications from the generic CPAP_Eng.pdf not linked to any specific product

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

**Generative judge context**: This is the most complex generative dimension. The judge receives data from **three separate Cypher queries** to cover the full scope of answerable questions:

1. **Product-outgoing relationships** - all relationships FROM Product/Organization entities, showing source, relationship type, target entity name, type, full description (up to 200 chars), plus `value` and `unit` properties for Specification targets. Limit 300 rows sorted by source type, source name, relationship type.

2. **Specification detail** - dedicated query returning Product -> Specification links with `name`, `description`, `value`, `unit` for all Specification entities. This ensures the judge sees numeric spec data that may be truncated or missing from the relationship query.

3. **Mode and standard coverage** - entities with "mode" in their name (type Feature/Setting) and their relationships, plus Standard entities with compliance relationships. This covers questions 5, 7, and 8 that the relationship query may miss.

**Quality criteria per question**:

| Question | What the judge must see | Required data signals |
|----------|------------------------|---------------------|
| Q1: Which manufacturers? | Organization entities with MANUFACTURES links | >= 3 org->product pairs |
| Q2: Compare features? | Product -> Feature relationships | Feature names + descriptions for 3+ products |
| Q3: Pressure range of [device]? | Product -> Specification with numeric value | value + unit fields populated (e.g. "4-20", "cmH2O") |
| Q4: Which devices treat OSA? | Product/Feature -> MedicalCondition TREATS links | At least 1 TREATS relationship |
| Q5: Supported modes? | Feature/Setting entities with "mode" in name | Mode entities linked to products via HAS_FEATURE/HAS_SETTING |
| Q6: Components of [device]? | Product -> Component HAS_COMPONENT links | Component names for specific products |
| Q7: Compliance standards? | Product/Org -> Standard COMPLIES_WITH links | Standard names with standard_id |
| Q8: Compare specs? | Specification entities with value + unit across products | Numeric values for 3+ products on same spec type |

**Scoring rubric**: 1=0-1 answerable, 2=2-3, 3=4-5, 4=6-7, 5=all 8 answerable with specific data (not just entity existence, but retrievable values).

**Known failure modes** (v19 analysis):
- **Context truncation** (primary cause of 2/5 in v19): The judge received `left(b.description, 60)` which truncates spec descriptions at 60 characters. Specifications like "Operating pressure range: 4-20 cmH2O with 0.5 cmH2O increments" become "Operating pressure range: 4-20 cmH2O with 0.5 cmH2O incr" - the value is present but the judge may not see complete data. More critically, `b.value` and `b.unit` properties were not included in the query at all, so even when the extraction pipeline correctly populates these structured fields, the judge cannot see them.
- **Missing relationship types in context**: The single query `WHERE toLower(a.type) IN ['product', 'organization']` only returns outgoing relationships from Product and Organization nodes. Relationships between other entity types (Feature -> MedicalCondition for TREATS, Standard -> Product for compliance) are invisible to the judge.
- **LIMIT too restrictive**: `LIMIT 200` on a graph with 1000+ entities and 3000+ relationships may cut off important Product relationships, especially for products appearing later alphabetically.
- **Deterministic-generative disconnect**: v19 scores 9/10 deterministic (the data exists and can be queried) but 2/5 generative (the judge doesn't receive enough context to evaluate). This gap indicates a judge context problem, not an extraction quality problem. The fix is query expansion, not pipeline changes.

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

## Generative Judge Design Principles

The generative scoring component accounts for 50% of the hybrid score. Its effectiveness depends entirely on the quality and completeness of the context provided to the LLM judge. The following principles govern judge query design.

### Context completeness over brevity

Each generative prompt must include ALL data the judge needs to evaluate the dimension. Truncating descriptions, omitting properties, or limiting rows below the meaningful threshold produces artificially low scores that reflect judge blindness rather than graph quality. When deterministic checks pass at 90%+ but generative scores are below 3/5, the first investigation should be judge context - not pipeline changes.

### Property inclusion rules

- **Specification entities**: Always include `name`, `description` (full, up to 200 chars), `value`, `unit`, and linked product name
- **Organization entities**: Include `name`, `description`, `role`
- **Product entities**: Include `name`, `description`, and linked manufacturer name
- **Feature/Setting entities**: Include `name`, `description`, and linked product name
- **Relationship type**: Always use `type(r)` (APOC native types), never `r.type` (which is NULL)

### Multi-query judges

Complex dimensions like query_answerability cannot be evaluated from a single Cypher query. When a single query cannot capture the full scope of a dimension, use multiple queries and concatenate results in the prompt. Each query should be labeled in the prompt so the judge understands what data it is seeing.

### Failure diagnosis from judge reasoning

The judge's `reasoning` field in the JSON response is the primary diagnostic tool for understanding quality gaps. The reasoning should identify specific missing data points (not vague statements like "incomplete data"). When the judge says "no pressure ranges visible", check whether (a) the extraction pipeline produced pressure specs, (b) the spec entities have value/unit properties, (c) the judge query includes those properties. This three-step diagnosis distinguishes extraction failures from judge context failures.

## Benchmark Configuration

The `.kgf/config.yml` configuration used for all benchmark runs (v18+):

```yaml
llm:
  provider: bedrock
  model: "eu.anthropic.claude-sonnet-4-20250514-v1:0"
  region: eu-central-1
  profile: kolomolo
  max_retries: 3
  timeout: 120
extract:
  use_embeddings: true
  bayesian_resolution: true
  deferred_dedup: true
  embedding_model: "amazon.titan-embed-text-v2:0"
  concurrency: 1  # reduce to avoid Bedrock rate limits (default 4)
ontology_buffer:
  resolution_intent: "Compare CPAP and auto-titrating positive airway pressure therapy devices across manufacturers, focusing on product specifications, clinical features, therapy modes, regulatory compliance, and component architecture"
curing:
  enabled: true
neo4j:
  uri: bolt://neo4j:7687
  user: neo4j
  password: kg-builder-pass
```

The `ontology_buffer.resolution_intent` is the use-case intent that constrains the LLM extraction hypothesis space to CPAP domain-relevant entity types. Without it, the LLM samples from a broad prior over all possible types, producing inconsistent extraction across documents. This intent was the single largest signal improvement (v17 72% -> v18 82%).

## Neo4j Setup

### Container creation

The Neo4j container must be on the same Docker user-defined network as the client environment (e.g. JupyterLab) for Docker DNS resolution to work. The `--network-alias neo4j` registers the hostname with Docker's embedded DNS server (`127.0.0.11`), eliminating the need for `/etc/hosts` workarounds.

```bash
# 1. Discover which network the current environment uses
docker inspect "$(hostname)" --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}'
# -> jupyterhub_network (or whatever your environment uses)

# 2. Create container on the same network
docker run -d --name kg-builder-neo4j \
  --network jupyterhub_network \
  --network-alias neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/kg-builder-pass \
  -e 'NEO4J_PLUGINS=["apoc"]' \
  neo4j:5

# Start existing container
docker start kg-builder-neo4j
```

### Hostname resolution

Docker's embedded DNS resolves the `neo4j` alias automatically on user-defined networks. No `/etc/hosts` entries required. If a stale `/etc/hosts` entry exists from a previous setup, remove it - it overrides Docker DNS and points to a dead IP.

```bash
# Verify DNS resolves to the container IP (not a stale /etc/hosts entry)
ping -c1 neo4j

# Verify bolt connectivity
uv run python -c "from neo4j import GraphDatabase; d=GraphDatabase.driver('bolt://neo4j:7687', auth=('neo4j','kg-builder-pass')); d.verify_connectivity(); print('OK'); d.close()"
```

Connection URI: `bolt://neo4j:7687`, Browser: `http://neo4j:7474`

### Recreating the container

When recreating (e.g. after version upgrade or config change), stop, remove, and re-run:

```bash
docker stop kg-builder-neo4j && docker rm kg-builder-neo4j
# Then re-run the docker run command above
```

### Graph management

```bash
# Wipe graph between benchmark runs
docker exec kg-builder-neo4j cypher-shell -u neo4j -p kg-builder-pass "MATCH (n) DETACH DELETE n"

# Verify APOC is loaded
docker exec kg-builder-neo4j cypher-shell -u neo4j -p kg-builder-pass "RETURN apoc.version()"
```

## Execution

### Full benchmark procedure

All benchmark runs execute from the `tmp/` directory under the project root. The CLI creates `.kgf/` relative to the current working directory, so running from `tmp/` keeps all runtime artefacts (config, evolved ontology, logs) isolated from the source tree. The `tmp/` directory is gitignored.

```bash
# 0. Prepare tmp working directory with input documents and config
mkdir -p tmp/input
cp data/raw/cpap-benchmark/* tmp/input/
cp docs/examples/config.yml.example tmp/.kgf/config.yml  # or create manually
# Edit tmp/.kgf/config.yml as needed (see Benchmark Configuration above)

# 1. Ensure Neo4j is running
docker start kg-builder-neo4j

# 2. Verify connectivity (Docker DNS resolves neo4j alias)
uv run python -c "from neo4j import GraphDatabase; d=GraphDatabase.driver('bolt://neo4j:7687', auth=('neo4j','kg-builder-pass')); d.verify_connectivity(); print('OK'); d.close()"

# 3. Wipe graph
docker exec kg-builder-neo4j cypher-shell -u neo4j -p kg-builder-pass "MATCH (n) DETACH DELETE n"

# 4. Run ingestion from tmp/ (all .kgf/ artefacts stay in tmp/)
cd tmp
uv run kgf ingest input/ --batch --fluid --event-log vNN-events.log --processing-log vNN-ingestion.log
cd ..
# Event log streams to tmp/vNN-events.log as JSONL (one event per line, written continuously)

# 5. Verify no extraction failures in log
grep "extraction failed\|ExtractionFailedError" tmp/vNN-ingestion.log && echo "FAILED - rerun needed" || echo "OK"

# 6. Run benchmark
uv run python tests/benchmark_multidoc.py vNN "description of iteration"

# 7. Check results
cat docs/benchmarks/MULTIDOC_BENCHMARK_vNN_*.md
```

### Clean run (wipe previous tmp artefacts)

```bash
# Remove evolved ontology and re-wipe graph between runs
rm -f tmp/.kgf/ontology.yml
docker exec kg-builder-neo4j cypher-shell -u neo4j -p kg-builder-pass "MATCH (n) DETACH DELETE n"
# Then repeat from step 4
```

### Rate limit handling

Bedrock rate limits can cause `ExtractionFailedError` when all chunks in a document fail. If this happens:
- Add `rate_limit.requests_per_second: 1.0` under `llm` in config (token bucket throttling)
- Reduce `extract.concurrency` in config (default 4, use 1-2 for rate-limited accounts)
- Wait 5 minutes for rate limit cooldown, then re-run from step 3
- The CLI exits with code 1 on extraction failure - never silently continues

### Ingestion modes

```bash
# All commands assume cwd is tmp/

# Fluid mode (default for benchmarks - discovers ontology from data)
uv run kgf ingest input/ --batch --fluid

# Constrained mode (uses pre-existing ontology seed)
uv run kgf ingest input/ --batch --fluid --ontology ../data/ontologies/cpap_medical_device.yml
```

## Iteration Results

| Iteration | Hybrid | Det | Gen | Focus |
|-----------|--------|-----|-----|-------|
| v01 (baseline) | 73% | 54/63 (86%) | 3.0/5.0 | Free mode, no ontology, 33 emergent types |
| v06-v08 | 86-88% | 61-63/63 | 3.6-3.8 | Enriched buffer prompts, configurable thresholds |
| v09 (fluid) | 81% | 59/63 (94%) | 3.4/5.0 | Fluid mode, empty ontology + intent prompt, cured at doc 4 |
| v17 | 72% | - | - | Clustering prompt hardening |
| v18 | 82% | 60/63 (95%) | 3.4/5.0 | Intent-driven discovery model |
| v19 | 84% | 61/63 (97%) | 3.6/5.0 | Bayesian cross-type dedup, SUPPORTS_MODE fix |

## v19 Failure Analysis

### Deterministic failures (2/63)

1. **cross_doc_resolution** - Cross-type duplicates < 20 check: actual=39. The Bayesian posterior reduced duplicates from 56 to 39 (30% reduction) but 15-20 remaining are genuinely ambiguous entities where the type boundary is real
2. **query_answerability** - "What modes does SleepStyle support?" - SleepStyle modes are extracted as Feature/Setting entities but the query path from Product to mode entities may be indirect

### Generative failures (biggest scoring gap)

| Dimension | Det | Gen | Gap | Root Cause |
|-----------|-----|-----|-----|-----------|
| query_answerability | 9/10 | 2/5 | -7 | Judge context truncation (60-char desc, no value/unit, LIMIT 200) |
| cross_doc_resolution | 5/6 | 3/5 | -2 | Judge sees counts but cannot assess genuine vs false duplicates |
| product_coverage | 7/7 | 4/5 | -3 | iBreeze possibly missing, duplicate product variants visible |

The deterministic-generative gap for query_answerability (9/10 vs 2/5) is the single largest contributor to the hybrid score deficit. The graph contains the data (deterministic proves it), but the judge's Cypher context window is too narrow to see it. This is a benchmark implementation issue, not an extraction quality issue.

### Priority fixes for v20 benchmark implementation

1. **Expand query_answerability judge context** - Replace single 200-row query with multi-query approach including spec details (value, unit), mode coverage, and standard compliance. Increase description from 60 to 200 chars. This alone could lift generative from 2/5 to 4/5 (+2 points -> +20% on generative -> +10% on hybrid)
2. **Add type context to cross_doc_resolution prompt** - Include entity descriptions alongside duplicate counts so the judge can distinguish genuine type ambiguity from resolution failures
3. **Product coverage prompt enrichment** - Include product descriptions and Feature/Component counts per product so the judge can assess completeness beyond name matching

## v01 Key Findings

- 1007 entities, 3744 relationships, 158 chunks, 10 documents
- 33 distinct types emerged (free mode) - top: Specification:181, Component:151, Feature:111, Accessory:82, Product:48
- Cross-doc resolution scored 17% (1/6) - 97 cross-type duplicates, 30 same-type duplicates
- 12 OSA entities instead of 1-3, 33 humidifier entities instead of 1-5
- Property completeness 60% - no structured properties (model_name, standard_id, role)
- Spec values buried in descriptions rather than extractable value/unit properties

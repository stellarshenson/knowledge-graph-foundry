# Benchmark Specification

This benchmark evaluates the quality of knowledge graphs produced by kg-builder-cli. It uses a hybrid scoring approach - deterministic Cypher queries for structural pass/fail checks combined with LLM generative scoring for nuanced quality dimensions that resist binary classification.

## Test Data

The benchmark corpus is the BMC RESmart Auto CPAP User Manual, a 26-page technical PDF containing product specifications, operating instructions, troubleshooting guidance, and regulatory information. This document was chosen because it contains dense, verifiable technical content - numeric specifications with units, hierarchical product-component relationships, and manufacturer information that can be objectively validated against the source.

Ground truth is derived from manual reading of the source document, not from extraction prompts or LLM outputs. This separation prevents circular validation where the benchmark merely confirms that the extraction prompt was followed rather than that the document content was captured.

## Ground Truth Specifications

| Specification | Value | Unit |
|---|---|---|
| Pressure range | 4-20 | hPa |
| Pressure increment | 0.5 | hPa |
| Weight (without humidifier) | 1.6 | kg |
| Weight (with humidifier) | 2.4 | kg |
| Dimensions (without humidifier) | 220 x 194 x 112 | mm |
| Dimensions (with humidifier) | 313 x 194 x 112 | mm |
| Sound pressure level | < 30 | dB |
| Power supply | 100-240V AC, 50/60Hz | - |
| Operating temperature | 5-30 | C |
| Operating humidity | <= 80% | non-condensing |
| Operating atmospheric pressure | 860-1060 | hPa |
| Max flow at 4 hPa | 70.1 | L/min |
| Max flow at 20 hPa | 73.4 | L/min |

## Scoring Model

The final benchmark score combines two components equally:

- **Deterministic score** (50%): Pass/fail Cypher checks aggregated as a percentage
- **Generative score** (50%): LLM scoring on a 1-5 scale per dimension, normalized to percentage

**Final score** = (deterministic_pct * 0.5) + (generative_avg_normalized * 0.5)

This hybrid approach captures both objective structural requirements (nodes exist, chains are intact, indexes present) and subjective quality characteristics (are specs useful, are relationships meaningful, could a user answer real questions from this graph).

## Dimensions

The benchmark evaluates eight dimensions. Each dimension has a weight reflecting its relative importance to overall graph utility.

### 1. Entity Coverage (15%)

Are the key entities from the source document present in the graph? This checks for the existence of core domain objects - products, manufacturers, accessories, components, and operating modes. A graph missing major entities has fundamental extraction gaps.

**Deterministic checks**:

```cypher
-- Product entity exists (RESmart or CPAP)
MATCH (e:Entity) WHERE e.name =~ '(?i).*(resmart|cpap|auto cpap).*' RETURN count(e) > 0

-- Manufacturer entity exists (BMC)
MATCH (e:Entity) WHERE e.name =~ '(?i).*(bmc|beijing medical|medical equipment).*' RETURN count(e) > 0

-- Humidifier component exists
MATCH (e:Entity) WHERE e.name =~ '(?i).*humidif.*' RETURN count(e) > 0

-- Pressure relief feature exists (SmartFlex/Reslex/EPR)
MATCH (e:Entity) WHERE e.name =~ '(?i).*(smartflex|reslex|epr|pressure relief).*' RETURN count(e) > 0

-- CPAP mode entity exists
MATCH (e:Entity) WHERE e.name =~ '(?i).*(cpap mode|apap|auto.?titrat).*' RETURN count(e) > 0
```

**Pass criteria**: Each query returning true is one pass. 5 checks total.

### 2. Specification Extraction (20%)

This is the most critical dimension. Technical specifications without concrete numeric values, units, and ranges are useless for downstream queries. A graph that says "Pressure Range - a pressure specification" provides no value over the source document itself. The graph must capture that pressure range is 4-20 hPa, weight is 1.6 kg, sound level is less than 30 dB.

**Deterministic checks**:

```cypher
-- Pressure range with numeric values
MATCH (e:Entity) WHERE e.name =~ '(?i).*pressure.*'
AND (e.description =~ '.*4.*20.*' OR e.properties =~ '.*4.*20.*')
RETURN count(e) > 0

-- Sound level with numeric value
MATCH (e:Entity) WHERE e.name =~ '(?i).*(sound|noise|dba|decibel).*'
AND (e.description =~ '.*30.*' OR e.properties =~ '.*30.*')
RETURN count(e) > 0

-- Weight with numeric value
MATCH (e:Entity) WHERE e.name =~ '(?i).*weight.*'
AND (e.description =~ '.*1\\.6.*' OR e.properties =~ '.*1\\.6.*')
RETURN count(e) > 0

-- Dimensions with numeric values
MATCH (e:Entity) WHERE e.name =~ '(?i).*(dimension|size).*'
AND (e.description =~ '.*220.*194.*' OR e.properties =~ '.*220.*194.*')
RETURN count(e) > 0

-- Power supply voltage
MATCH (e:Entity) WHERE e.name =~ '(?i).*(power|voltage|supply).*'
AND (e.description =~ '.*240.*' OR e.properties =~ '.*240.*')
RETURN count(e) > 0

-- Operating temperature range
MATCH (e:Entity) WHERE e.name =~ '(?i).*(temp|operating).*'
AND (e.description =~ '.*5.*30.*' OR e.properties =~ '.*5.*30.*')
RETURN count(e) > 0
```

**Pass criteria**: Each query returning true is one pass. 6 checks total.

### 3. Relationship Accuracy (15%)

Are entities connected with correct relationship types and directionality? The graph should reflect that BMC manufactures the RESmart, the RESmart has specifications, the humidifier is a component of the device, and operating modes are features.

**Deterministic checks**:

```cypher
-- Manufacturer -> Product relationship exists
MATCH (m:Entity)-[r]->(p:Entity)
WHERE m.name =~ '(?i).*(bmc|manufacturer).*'
AND p.name =~ '(?i).*(resmart|cpap).*'
RETURN count(r) > 0

-- Product -> Specification relationship exists
MATCH (p:Entity)-[r]->(s:Entity)
WHERE p.name =~ '(?i).*(resmart|cpap).*'
AND s.name =~ '(?i).*(pressure|weight|dimension|sound|power|temp).*'
RETURN count(r) > 0

-- Product -> Component relationship exists
MATCH (p:Entity)-[r]->(c:Entity)
WHERE p.name =~ '(?i).*(resmart|cpap).*'
AND c.name =~ '(?i).*(humidif|mask|tube|filter).*'
RETURN count(r) > 0

-- Product -> Feature/Mode relationship exists
MATCH (p:Entity)-[r]->(f:Entity)
WHERE p.name =~ '(?i).*(resmart|cpap).*'
AND f.name =~ '(?i).*(cpap|apap|smartflex|ramp|auto).*'
RETURN count(r) > 0
```

**Pass criteria**: Each query returning true is one pass. 4 checks total.

### 4. Dedup Quality (10%)

Entity resolution should merge near-duplicates. The graph should not contain both "BMC" and "BMC Medical" as separate entities, or "Humidifier" and "Built-in Humidifier" as disconnected nodes representing the same concept.

**Deterministic checks**:

```cypher
-- Total entity count is reasonable (not exploded)
MATCH (e:Entity) RETURN count(e) < 300

-- No exact duplicate names
MATCH (a:Entity), (b:Entity)
WHERE a.name = b.name AND id(a) < id(b)
RETURN count(a) = 0

-- Entity type distribution is not fragmented (< 30 unique types)
MATCH (e:Entity) RETURN count(DISTINCT e.type) < 30
```

**Pass criteria**: Each query returning true is one pass. 3 checks total.

### 5. Graph Structure (10%)

Structural integrity checks ensure the document-chunk-entity scaffold is correctly built. This includes Document nodes, Chunk nodes with text content, NEXT_CHUNK chains for reading order, HAS_CHUNK relationships linking documents to chunks, HAS_ENTITY relationships linking chunks to extracted entities, and database indexes for query performance.

**Deterministic checks**:

```cypher
-- Document node exists
MATCH (d:Document) RETURN count(d) > 0

-- Chunk nodes have text content
MATCH (c:Chunk) WHERE c.text IS NOT NULL AND c.text <> '' RETURN count(c) > 0

-- NEXT_CHUNK chain exists
MATCH (c1:Chunk)-[:NEXT_CHUNK]->(c2:Chunk) RETURN count(*) > 0

-- HAS_CHUNK relationships link documents to chunks
MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk) RETURN count(*) > 0

-- HAS_ENTITY relationships link chunks to entities
MATCH (c:Chunk)-[:HAS_ENTITY]->(e:Entity) RETURN count(*) > 0
```

**Pass criteria**: Each query returning true is one pass. 5 checks total.

### 6. Query Answerability (15%)

Can real user questions be answered from the graph? This dimension tests whether the graph supports practical queries that someone reading the manual might ask. Each question has a known answer from the source document.

**Test questions and expected answers**:

1. "What is the pressure range of the RESmart Auto CPAP?" - Expected: 4-20 hPa
2. "Who manufactures the RESmart?" - Expected: BMC Medical / Beijing Medical Equipment
3. "What is the sound level of the device?" - Expected: less than 30 dB
4. "What voltage does the device support?" - Expected: 100-240V AC
5. "What accessories come with the device?" - Expected: mask, tubing, humidifier, filters, power adapter

**Scoring**: Generative only - the LLM evaluates whether a graph traversal starting from relevant entities could produce each answer. Scored 1-5 based on how many questions are answerable with accurate, complete information.

### 7. Type Consistency (10%)

Entity types should be consistent and canonical across the graph. If an ontology was seeded, seeded types should dominate over ad-hoc types. Type fragmentation - where the same conceptual category appears under multiple type labels (e.g., "Therapy" vs "WorkMode" vs "OperatingMode" for the same concept) - reduces graph utility and query predictability.

**Deterministic checks**:

```cypher
-- No single-instance types (types used by only one entity suggest fragmentation)
MATCH (e:Entity)
WITH e.type AS type, count(*) AS cnt
WHERE cnt = 1
RETURN count(type) < 10

-- If ontology was seeded, seeded types represent majority
-- (this check is conditional on seeded extraction)
MATCH (e:Entity)
RETURN count(DISTINCT e.type) < 25
```

**Pass criteria**: Each query returning true is one pass. 2 checks total. Additional generative assessment evaluates whether types are semantically coherent.

### 8. Property Completeness (5%)

Entities should have populated properties with structured key-value pairs, not just free-text descriptions. A specification entity with `properties: {value: "4-20", unit: "hPa", increment: "0.5"}` is far more useful than one with `description: "The pressure range specification for the device"`.

**Deterministic checks**:

```cypher
-- At least 20% of entities have non-null properties
MATCH (e:Entity)
WITH count(e) AS total,
     count(CASE WHEN e.properties IS NOT NULL AND e.properties <> '' AND e.properties <> '{}' THEN 1 END) AS withProps
RETURN toFloat(withProps) / total > 0.2

-- Specification entities specifically have properties
MATCH (e:Entity)
WHERE e.name =~ '(?i).*(pressure|weight|dimension|sound|power|temp).*'
AND e.properties IS NOT NULL AND e.properties <> '' AND e.properties <> '{}'
RETURN count(e) > 0
```

**Pass criteria**: Each query returning true is one pass. 2 checks total.

## Generative Scoring Protocol

For dimensions that benefit from nuanced evaluation (particularly Query Answerability, Type Consistency, and as a supplement to all deterministic dimensions), an LLM scores graph quality on a 1-5 scale.

**Process**:

1. Run dimension-specific Cypher queries to extract relevant graph data (entity lists, relationship patterns, type distributions, property contents)
2. Present the extracted data to the scoring LLM alongside the dimension criteria and ground truth
3. LLM assigns a score from 1 (poor) to 5 (excellent) with written reasoning
4. Scores are normalized to percentage: (score - 1) / 4 * 100

**Scoring criteria across all dimensions**:
- **Completeness** - how much of the expected content is present
- **Accuracy** - is the captured information correct relative to the source document
- **Specificity** - does the graph contain concrete values rather than vague descriptions
- **Utility** - would a downstream query or application benefit from this graph structure

**Model**: Claude Sonnet 4 via Bedrock. Using the same model for scoring and extraction is acceptable here because the benchmark ground truth is derived from the source document, not from extraction prompts. The scoring LLM evaluates whether document facts appear in the graph, not whether the extraction prompt was followed.

## Anti-Overfitting Rules

These rules prevent the benchmark from becoming a test of prompt engineering rather than extraction quality:

- Ground truth is derived from reading the source PDF, not from extraction prompts or system instructions
- Benchmark queries search for document facts (specific numeric values, product names, manufacturer names) not prompt patterns or extraction artifacts
- Generative scoring uses source document facts as the reference standard, not the extraction prompt or ontology definition
- No benchmark check should be passable by prompt engineering alone - passing requires that the actual document content was extracted and structured correctly
- The specification table above is the authoritative reference for all numeric checks

## Versioning

Each benchmark run produces a results file named `BENCHMARK_v<iteration>_<score>.md` containing:

- Run conditions (model, chunk size, concurrency, ontology mode, temperature)
- Graph statistics (entity count, relationship count, chunk count)
- Per-dimension scores with per-check pass/fail detail
- Generative scoring results with LLM reasoning
- Final composite score
- Failure analysis identifying the weakest dimensions
- Improvement plan for the next iteration

## Iteration Workflow

1. Clean Neo4j database (delete all nodes and relationships)
2. Ingest the test document with current configuration
3. Run the full benchmark suite (deterministic + generative)
4. Record results in versioned results file
5. Analyze failures - identify which dimensions lost points and why
6. Plan improvements (config changes, prompt tuning, ontology seeding, post-processing)
7. Implement changes
8. Repeat from step 1

The iteration continues until the composite score meets the target threshold or improvements plateau. Each iteration's results file preserves the full history of what was tried and what effect it had.

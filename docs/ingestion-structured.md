# Structured Data Ingestion

Strategy for building knowledge graphs from JSON/JSONL records using LLM-interpreted schema descriptions.

## Pipeline Overview

```
Records (JSON/JSONL) + Schema description -> LLM mapping -> Deduplicate -> Normalize -> Load
```

1. Read JSON/JSONL records
2. Load the schema description file (markdown, YAML, or plain text)
3. Send records (individually or in batches) to the LLM alongside the schema description
4. LLM interprets field semantics and produces entities and relationships
5. Deduplicate entities across records by deterministic `(type, id)` match
6. Normalize entity names and resolve remaining duplicates
7. Load merged graph into Neo4J

## How It Differs from Unstructured

The reference implementation (Neo4J LLM Graph Builder) has minimal structured data support - it treats everything as unstructured text for LLM extraction. Our approach is different: structured records already have defined fields, so the LLM's job shifts from "find entities in free text" to "interpret what these fields mean and map them to graph structure."

Key differences from unstructured ingestion:
- No chunking - each record (or batch) is a discrete unit
- Schema description replaces the extraction prompt's general instructions
- Entity IDs can be derived deterministically from record fields rather than relying on LLM consistency
- Higher throughput - records are uniform, enabling larger batches per LLM call
- More predictable output - same schema applied uniformly across all records

## Schema Description

The schema description is a human-readable file that explains what each field in the JSON records represents and how it maps to graph structure. The LLM interprets this generatively - it does not need to follow a rigid format.

**Stored in**: `.kg-builder/schemas/`

### What It Should Contain

- What each field represents semantically
- Which fields map to entities (nodes) and what type
- Which fields create relationships and between which entity types
- Which fields become properties on entities rather than separate nodes
- Any special handling (arrays that expand to multiple entities, nested objects, etc.)

### Example: Minimal

```markdown
Each record is an employee. `name` is a Person, `department` is a Department.
The employee works in the department (WORKS_IN relationship).
`skills` is an array - each skill becomes a Skill entity linked by HAS_SKILL.
```

### Example: Detailed

```markdown
## Employee Records

Each JSON record represents an employee in the organization.

**Entities**:
- `name` -> Person entity (use as both name and id basis)
- `department` -> Department entity
- `manager` -> Person entity (same type as name, creates a second Person if different)
- `skills[]` -> one Skill entity per array element

**Relationships**:
- Person WORKS_IN Department (from name -> department)
- Person REPORTS_TO Person (from name -> manager)
- Person HAS_SKILL Skill (from name -> each skill)

**Properties**:
- `start_date` -> property on the WORKS_IN relationship
- `level` -> property on the Person entity
- `salary` -> do not extract (sensitive, exclude from graph)
```

### Example: YAML Format

```yaml
description: Employee directory records
entities:
  name:
    type: Person
    description: Full name of the employee
  department:
    type: Department
  skills:
    type: Skill
    array: true
relationships:
  - from: name
    to: department
    type: WORKS_IN
  - from: name
    to: manager
    type: REPORTS_TO
exclude:
  - salary
  - ssn
```

All three formats are valid. The LLM reads whichever format the user provides and applies it consistently across records.

## LLM Mapping

### Prompt Structure

```
You are a knowledge graph extraction system. Map structured records to graph
entities and relationships according to the schema description below.

Schema description:
{schema_description_content}

[If ontology provided:]
Constrain output to ONLY these entity types: {entity_types}
Constrain output to ONLY these relationship types: {relationship_types}

Rules:
- Each entity must have a deterministic id derived from the record field value
  (lowercase, underscores, type-prefixed, e.g. person_jane_smith)
- Preserve field values as entity names exactly as they appear in the record
- Array fields produce one entity per element
- Fields marked as properties attach to their parent entity, not as separate nodes
- Fields marked for exclusion must be ignored entirely

Records:
{json_records}

Return JSON:
{
  "entities": [{"id": "...", "name": "...", "type": "...", "properties": {}}],
  "relationships": [{"source": "...", "target": "...", "type": "...", "properties": {}}]
}
```

### Record Batching

Structured records are uniform, so multiple records can be sent in a single LLM call. Batch size is a trade-off between throughput and context window limits.

**Recommended batch sizes**:
- Simple records (5-10 fields): 20-50 records per call
- Complex records (nested objects, arrays): 5-10 records per call
- Records with long text fields: treat as hybrid, may need smaller batches

The batch size is auto-adjusted based on estimated token count per record. If a batch exceeds 80% of the configured `chunk_size` token limit, it is split.

### Deterministic Entity IDs

Unlike unstructured extraction where the LLM must invent consistent IDs, structured data allows deterministic ID generation from field values. The LLM is instructed to derive IDs from the actual field content:

- `{"name": "Jane Smith"}` -> `person_jane_smith`
- `{"department": "Engineering"}` -> `department_engineering`

This eliminates the fuzzy matching problem that plagues unstructured extraction. The same field value always produces the same entity ID, ensuring natural deduplication across records.

## Deduplication

### Record-level

Many records reference the same entities (e.g., 50 employees in "Engineering" department). Deduplication before loading:

1. Collect all entities from all records
2. Group by `(type, id)` tuple
3. Merge properties (accumulate unique values for array-like properties)
4. Deduplicate relationships by `(source_id, target_id, type)`

### At Load Time

Same `MERGE`-based strategy as unstructured ingestion. For structured data this is particularly effective because deterministic IDs mean the same entity from different batch runs will merge cleanly.

### Entity Normalization

Even with deterministic IDs, structured data can contain variations of the same entity across records - different spellings, abbreviations, or formatting ("Engineering Dept", "Engineering", "Eng."). A normalization pass catches these.

**Approach**: after deduplication by exact ID, the remaining entity names within each type are compared using LLM-based clustering (same approach as unstructured ingestion). Because structured records produce fewer unique entities per type (departments, skills, etc.), this pass is cheap and highly effective.

Normalized entities store:
- `name`: original field value
- `normalized_name`: canonical form after resolution
- `normalized_score`: confidence of the match
- `normalized_method`: resolution method used

**When normalization is less needed**: if the source data is already clean and consistent (e.g., values from a controlled dropdown or enum), normalization can be skipped. The schema description can indicate this: "department values are from a controlled list - no normalization needed."

## Ontology Interaction

The schema description and ontology serve complementary roles:

- **Schema description**: tells the LLM what the input fields mean and how to map them
- **Ontology** (optional): constrains what entity types and relationship types the output may contain

When both are provided, the schema description guides field interpretation while the ontology acts as a validation filter. If the schema description suggests creating a "Team" entity but the ontology only allows "Department", the LLM should map to the closest allowed type.

When only a schema description is provided (no ontology), the LLM infers entity and relationship types from the schema description itself.

## Graph Structure in Neo4J

```
(:Source {name, format, record_count, processed_at})
  <-[:FROM_SOURCE]- (:Entity:Person {id, name, level, ...})
  <-[:FROM_SOURCE]- (:Entity:Department {id, name, ...})

(:Entity:Person)-[:WORKS_IN {start_date}]->(:Entity:Department)
(:Entity:Person)-[:REPORTS_TO]->(:Entity:Person)
(:Entity:Person)-[:HAS_SKILL]->(:Entity:Skill)
```

Unlike unstructured ingestion, there are no `Chunk` nodes - structured records do not need chunk-level provenance. Instead, a `Source` node tracks the input file metadata and entities link back to it via `FROM_SOURCE`.

## Loading Strategy

Same Cypher batch loading as unstructured ingestion, with one optimization: because entity IDs are deterministic and records are uniform, the loader can pre-sort entities by type and issue type-specific batch `MERGE` operations, reducing label-switching overhead.

**Node creation** (batched by type):
```cypher
UNWIND $batch AS row
MERGE (n:Entity:{type} {id: row.id})
SET n.name = row.name
SET n += row.properties
```

**Relationship creation** (batched by type):
```cypher
UNWIND $batch AS row
MATCH (a:Entity {id: row.source}), (b:Entity {id: row.target})
MERGE (a)-[r:{rel_type}]->(b)
SET r += row.properties
```

## Hybrid Scenario

Some records contain both structured fields and free-text fields (e.g., a product record with a `description` field containing paragraphs of text). In this case:

- Structured fields are mapped according to the schema description as described above
- Free-text fields can optionally be processed through the unstructured extraction pipeline
- The schema description should indicate which fields are free-text: "the `description` field contains unstructured text - extract additional entities and relationships from it"

This is handled by the same LLM call - the schema description simply instructs the LLM to treat certain fields generatively while mapping others deterministically.

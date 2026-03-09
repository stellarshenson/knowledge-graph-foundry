# kg-builder-cli Specification

CLI tool for building knowledge graphs from structured and unstructured data, loading them into Neo4J. Uses LLMs to identify entities and relationships, with optional ontology constraints to control graph structure. Built on the Strands Agents SDK - each CLI command is an autonomous agent with tools for data inspection, graph operations, and interactive user collaboration. Designed as a simpler, CLI-driven alternative to the Neo4J LLM Graph Builder web application.

## Resource Directory

The CLI operates on a `.kg-builder/` directory that lives in the target project (not in the CLI tool's own repository). Any project that wants to build a knowledge graph creates a `.kg-builder/` folder containing all the resources the CLI needs - configuration, Neo4J connection details, ontology definitions, schema descriptions, and extraction outputs.

```
my-project/
  .kg-builder/
    config.yml              # main configuration (Neo4J connection, LLM settings, defaults)
    ontology.yml            # ontology definition (optional)
    schemas/                # schema descriptions for structured data
      employees.md
      products.yml
    extractions/            # extraction output files
      2026-03-09_document.json
      2026-03-09_records.json
    memory/                 # agent memory (data profiles, user preferences, resolution history)
      source_employees.yml
      source_documents.yml
    migrations/             # schema migration history
      2026-03-09_employees_v2.yml
  data/
    raw/
      documents/
      records.jsonl
```

The CLI looks for `.kg-builder/` in the current working directory. All paths in `config.yml` are relative to the project root unless absolute.

## Data Sources

The graph builder accepts two categories of input data, determined automatically by file extension.

### Unstructured Data

Free-form text documents (PDF, TXT, MD, DOCX). The LLM extracts entities and relationships generatively - chunking the text, then interpreting each chunk to produce graph triples.

### Structured Data

JSON or JSONL files containing records that follow a known schema. The schema is described in a separate schema description file (markdown, YAML, or plain text) that the LLM interprets generatively to understand field meanings, entity mappings, and relationship patterns.

The `--schema` option points to this description file. The LLM reads the schema description alongside each record and determines how to map fields to graph entities and relationships. This means the schema description does not need to follow a rigid format - it can be a markdown document explaining what each field represents, a YAML with field descriptions, or any human-readable source that conveys the structure.

```
kg ingest data/records.jsonl --schema .kg-builder/schemas/employees.md
```

**Example schema description** (`.kg-builder/schemas/employees.md`):

```markdown
## Record Schema - Employee Directory

Each JSON record represents an employee entry.

- `name`: full name of the employee (maps to Person entity)
- `department`: department name (maps to Department entity)
- `manager`: name of the direct manager (maps to Person entity, creates REPORTS_TO relationship)
- `skills`: array of technology names (each maps to Skill entity, creates HAS_SKILL relationship)
- `start_date`: ISO date when the employee joined
```

**Example JSONL input**:

```json
{"name": "Jane Smith", "department": "Engineering", "manager": "John Doe", "skills": ["Python", "Neo4J"], "start_date": "2024-01-15"}
```

For structured data, chunking options (`--chunk-size`, `--chunk-overlap`) do not apply. Each JSON record (or batch of records for efficiency) is sent to the LLM as a discrete unit alongside the schema description.

### Schema Inference

When no `--schema` is provided for structured data, the ingest agent infers a schema from a sample of the data. The agent uses its `py-repl` tool to load and inspect the first N records (default 20), analyses field types, cardinality, value distributions, and nesting patterns, then proposes a schema description.

The inference runs in interactive mode - the agent presents its proposed schema to the user and enters a collaborative loop:

1. **Sample** - agent loads N records via `py-repl`, computes field statistics (types, null rates, unique counts, value samples)
2. **Propose** - agent generates a schema description explaining each field's semantics, entity mappings, and relationship patterns
3. **Review** - user reviews the proposal, requests changes ("make `location` a separate entity", "ignore the `internal_id` field", "the `tags` array should create `Topic` entities")
4. **Refine** - agent updates the schema based on feedback, may re-inspect data to validate changes
5. **Confirm** - user approves the schema, agent saves it to `.kg-builder/schemas/`

The saved schema becomes the input for all subsequent ingestion runs against this data source. This means a user can start with zero configuration - point the tool at a JSONL file and the agent builds the schema collaboratively before ingesting.

```
kg ingest data/records.jsonl                    # no --schema triggers inference
kg ingest data/records.jsonl --infer-schema     # explicit inference even if schema exists
```

### Schema Update

Schemas evolve as data sources change - fields are added, renamed, or restructured. The `kg update schema` command handles schema evolution with migration awareness.

When a schema update is triggered (new fields detected, user requests reclassification, or explicit `--update-schema` flag), the update agent:

1. **Diff** - compares the current schema against a fresh sample of the data, identifies new fields, removed fields, type changes, and structural shifts
2. **Impact** - queries the existing graph via `neo4j-mcp` to assess what entities and relationships would be affected by schema changes
3. **Propose migration** - generates a migration plan: new entity types to create, relationships to add or retype, properties to migrate, and any data transformations needed
4. **Interactive review** - presents the migration plan to the user for approval or modification
5. **Execute** - runs the approved migration via `neo4j-driver` (direct Cypher for bulk operations) or re-ingests affected records with the updated schema

The migration plan is saved to `.kg-builder/migrations/` with a timestamp for auditability.

## Agent Architecture

The CLI is built on the Strands Agents SDK. Each command spawns an autonomous agent with a defined set of tools and a system prompt tailored to its workflow. Agents maintain conversational context for interactive operations (schema inference, migration review) and execute multi-step pipelines autonomously for batch operations.

### Agent Tools

Every agent has access to a shared tool registry:

| Tool | Purpose |
|------|---------|
| `py-repl` | Python REPL for data inspection, sampling, statistical analysis, transformation |
| `neo4j-mcp` | MCP server providing graph query, schema inspection, and index management |
| `neo4j-driver` | Direct Neo4J Python driver for bulk Cypher operations, batch loading, transactions |
| `file-ops` | Read/write files in `.kg-builder/` directory (schemas, extractions, ontology, migrations) |

The `neo4j-mcp` tool exposes the graph as a conversational resource - agents can ask questions about the current graph state, inspect node counts, and validate relationships without writing raw Cypher. The `neo4j-driver` tool is used when performance matters - bulk MERGE operations, index creation, and transactional writes that need direct driver access.

### Agent Memory

Each agent has access to persistent memory stored in `.kg-builder/memory/`. Memory operates alongside the ontology buffer as a complementary persistence layer - the buffer tracks schema-level knowledge (entity types, relationship types, coverage scores, variant mappings), while memory tracks operational knowledge accumulated across runs.

Agent memory captures:
- **Data source profiles** - field distributions, quality patterns, anomalies observed in previous runs
- **User preferences** - schema decisions, entity mapping choices, fields marked for exclusion
- **Resolution history** - entity normalization decisions, disambiguation choices, merge/split outcomes
- **Pipeline context** - extraction parameters that worked well for specific data shapes, batch sizes, model performance observations

Memory is consulted at the start of each agent invocation and updated at completion. When the ingest agent encounters a new JSONL file, it checks memory for prior schema inference sessions on similar data. When the update agent proposes a migration, it references previous migration outcomes to calibrate its recommendations. Memory is stored as structured YAML files organized by data source and operation type.

The ontology buffer and memory share a read path but write independently. The buffer is authoritative for type definitions and constraints - memory never overrides buffer decisions. Memory provides contextual hints that influence agent behaviour but do not hard-constrain it.

## CLI Commands

The CLI exposes three entry points corresponding to the primary knowledge graph workflows: ingest, query, and update. Each command is backed by a Strands agent with tools appropriate to its workflow.

### `kg ingest`

Build the knowledge graph from source data. Handles initialization, extraction, loading, and schema inference as a unified workflow.

```
kg ingest <source> [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `<source>` | required | Path to file or directory of documents to process |
| `--schema` | from config | Path to schema description file for structured data |
| `--infer-schema` | `False` | Force schema inference even if schema exists |
| `--ontology` | from config | Path to ontology YAML file (free extraction if omitted) |
| `--model` | from config | LLM model identifier |
| `--chunk-size` | from config | Token chunk size for document splitting (unstructured only) |
| `--chunk-overlap` | from config | Token overlap between chunks (unstructured only) |
| `--concurrency` | from config | Parallel LLM requests |
| `--merge-strategy` | from config | How to handle existing nodes: `merge`, `replace`, `skip` |
| `--batch-size` | from config | Cypher batch size for bulk loading |
| `--extract-only` | `False` | Run extraction without loading into Neo4J |
| `--keep-extractions` | `False` | Save extraction JSON to `.kg-builder/extractions/` |

**Behaviour**:

The ingest agent runs the full pipeline: detect input type, extract entities and relationships, deduplicate, normalize, and load into Neo4J.

- **Initialization**: if `.kg-builder/` does not exist, the agent creates it with default `config.yml`, `schemas/`, `extractions/`, `memory/`, and `migrations/` directories. In interactive mode the agent asks questions about the target graph and generates tailored configuration
- **Input detection**: file extension determines pipeline - `.json`/`.jsonl` -> structured, everything else -> unstructured
- **Schema inference**: for structured data without `--schema`, the agent samples records via `py-repl`, proposes a schema interactively, and saves it to `.kg-builder/schemas/` before proceeding (see Schema Inference section)
- **Ontology buffer**: without `--ontology` the agent runs free extraction, building the ontology progressively. With `--ontology` it starts constrained but refines during processing. The buffer tracks type frequencies, variant mappings, and coverage scores. See `docs/ingestion-unstructured.md` for the full mechanism
- **Extract + load**: by default the agent extracts and loads in a single run. Use `--extract-only` to stop after extraction, or `--keep-extractions` to save intermediate JSON alongside loading

### `kg query`

Query the knowledge graph using natural language or Cypher.

```
kg query [question] [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `[question]` | none | Natural language question (interactive mode if omitted) |
| `--cypher` | `False` | Pass raw Cypher instead of natural language |
| `--format` | `table` | Output format: `table`, `json`, `graph`, `text` |
| `--limit` | `25` | Maximum result rows |

**Behaviour**:

The query agent translates natural language questions to Cypher queries using the current graph schema as context. It queries the graph via `neo4j-mcp`, formats results, and can enter an interactive conversational loop where follow-up questions build on previous context.

- **Schema-aware** - the agent inspects the graph schema (labels, relationship types, property keys) before generating queries, ensuring valid Cypher
- **Dual retrieval** - uses vector index for semantic similarity and fulltext index for keyword matching, choosing the appropriate path based on the question type
- **Interactive mode** - when invoked without a question, enters a conversational loop where the agent maintains context across questions. "Show me all engineers" followed by "what skills do they have?" works as expected
- **Status** - `kg query --status` displays node counts by label, relationship counts by type, and index statistics

### `kg update`

Evolve the knowledge graph - update schemas, run migrations, re-process data, and refine the ontology.

```
kg update <subcommand> [options]
```

#### `kg update schema`

Update an existing schema for structured data.

```
kg update schema <schema-file> [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `<schema-file>` | required | Path to the schema file to update |
| `--source` | from config | Data source to re-sample for schema comparison |
| `--dry-run` | `False` | Show proposed changes without applying |
| `--migrate` | `True` | Generate and execute migration plan for the graph |

The update agent diffs the current schema against fresh data samples, proposes changes interactively, and optionally generates a migration plan for the existing graph. See Schema Update section for the full workflow.

#### `kg update ontology`

Refine the ontology based on accumulated extraction evidence.

```
kg update ontology [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--source` | from config | Re-process source data to gather fresh type evidence |
| `--prune` | `False` | Remove low-frequency types that did not reach confirmation threshold |
| `--merge-variants` | `True` | Apply variant detection to consolidate similar types |

Triggers an ontology refinement pass using the buffer's accumulated frequency and coverage data. Can optionally re-process source data to gather fresh evidence.

#### `kg update graph`

Re-process previously ingested data with updated schema or ontology.

```
kg update graph [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--source` | from config | Data source to re-ingest |
| `--schema` | from config | Updated schema to apply |
| `--incremental` | `True` | Only process records affected by schema changes |
| `--full` | `False` | Re-process all records from scratch |

The update agent uses the migration plan from `kg update schema` to selectively re-process affected records rather than re-ingesting everything. For structural changes (new entity types, relationship retyping), it executes Cypher transformations directly via `neo4j-driver`.

## Configuration

### `.kg-builder/config.yml`

```yaml
# Neo4J connection
neo4j:
  uri: bolt://localhost:7687
  user: neo4j
  password: ${NEO4J_PASSWORD}       # resolved from .env or environment

# LLM settings
llm:
  provider: bedrock                  # bedrock | openai | anthropic
  model: us.anthropic.claude-sonnet-4-20250514
  temperature: 0.0
  region: eu-central-1               # AWS region (bedrock only)
  profile: default                   # AWS profile (bedrock only)

# Extraction defaults
extract:
  chunking_strategy: token            # token | semantic
  chunk_size: 2000                   # token chunk size (unstructured only, token strategy)
  chunk_overlap: 200                 # token overlap between chunks (unstructured only, token strategy)
  concurrency: 4                     # parallel LLM requests
  extraction_mode: hybrid             # entity_relationship | graph_reader | hybrid
  subgraph_splitting: false           # split large schemas into subgraph extractions per chunk
  rolling_context_window: 0           # pass N most recent extractions as context for sequential chunks
  describe_images: false              # run vision model on extracted PDF images
  vision_model: null                  # vision model for image description (e.g., llava:7b, gpt-4o)

# Ontology buffer settings
ontology_buffer:
  seed_from: null                    # ontology seed file in any format (OWL, JSON, MD, TXT, YAML)
  seed_depth: 2                      # max subclass depth to import from OWL
  seed_filter: null                  # restrict OWL import to branch (e.g., "BiologicalEntity")
  refine_every_n_docs: 5             # trigger refinement after N documents
  coverage_threshold: 0.5            # low coverage triggers looser extraction
  min_frequency_to_confirm: 2        # type must appear in N+ documents to be confirmed
  flush_on_complete: true            # write refined ontology to disk after run

# Loading defaults
load:
  merge_strategy: merge              # merge | replace | skip
  batch_size: 500                    # Cypher batch size for bulk loading
  create_indexes: true               # auto-create indexes for entity labels
  validate: true                     # run post-load validation checks (orphan nodes, relationship counts)

# Agent memory
memory:
  enabled: true                      # persist operational knowledge across runs
  max_entries_per_source: 100        # cap memory entries per data source
  ttl_days: 90                       # expire stale memory entries after N days

# Paths (relative to project root)
paths:
  ontology: null                     # path to ontology YAML (free extraction if null)
  schema: null                       # path to schema description for structured data
  memory: .kg-builder/memory/        # agent memory storage directory
  migrations: .kg-builder/migrations/ # schema migration history
```

Neo4J connection details are stored directly in `config.yml`. The password uses `${VAR}` interpolation so it can be kept in `.env` rather than in plaintext, but URI, user, and database name are committed with the config.

**Resolution order** (highest wins):
1. CLI flags (`--chunk-size 4000`)
2. `.kg-builder/config.yml` values
3. Built-in defaults

Secrets use `${VAR_NAME}` syntax and are resolved from `.env` (loaded by `python-dotenv`) or environment variables. The YAML file itself should never contain plaintext secrets.

### `.env` (secrets only)

```env
NEO4J_PASSWORD=secret
AWS_ACCESS_KEY_ID=...               # optional, if not using AWS profile
AWS_SECRET_ACCESS_KEY=...           # optional, if not using AWS profile
```

### Ontology Sources

The ontology buffer accepts input in any format - the only requirement is that the input conveys domain knowledge about entity types, relationships, or graph structure. The system normalizes all inputs to the canonical YAML ontology format before the buffer consumes them.

**Supported input formats**:

| Format | Detection | Normalization method |
|--------|-----------|---------------------|
| OWL/RDF (`.owl`, `.rdf`, `.ttl`) | File extension | Programmatic via owlready2 - classes, properties, hierarchy extracted directly |
| YAML (`.yml`, `.yaml`) | File extension | Validated against canonical schema, passed through if conforming |
| JSON (`.json`) | File extension | LLM interprets structure, maps to canonical YAML |
| Markdown (`.md`) | File extension | LLM interprets prose, extracts entity types, relationships, constraints |
| Plain text (`.txt`) | File extension | LLM interprets free-form description, extracts ontology elements |
| Any other | Fallback | LLM reads content as-is, attempts ontology extraction |

The normalization pipeline ensures that regardless of input format, the buffer always receives a well-defined schema it can formally deconstruct and interpret.

**Source precedence** (highest wins):

1. **Ontology seed** (`ontology_buffer.seed_from`): any file in any supported format. The system detects the format and normalizes accordingly. Read-only input - never modified. **The seed is suggestive, not prescriptive** - it provides starting vocabulary and domain context, but extraction is free to discover types and connections the seed did not anticipate
2. **YAML ontology** (`paths.ontology`): the canonical application schema. If both seed and YAML are provided, the YAML takes precedence for overlapping type definitions
3. **Empty** (free extraction): no seed, no YAML. The buffer starts empty and builds the ontology from scratch

After the run completes, the refined ontology is always flushed as YAML to `.kg-builder/ontology.yml` regardless of the original source format. A markdown description of a medical domain produces the same canonical YAML output as a formal OWL ontology of the same domain. The output is the system's own schema shaped by what the data actually contained.

### Ontology Normalization

All non-YAML, non-OWL inputs pass through an LLM normalization step that converts freeform domain knowledge into the canonical YAML ontology format. This is a structured extraction task - the LLM reads the input and produces a Pydantic-validated ontology definition.

**What the normalizer extracts**:
- Entity types with descriptions and aliases
- Relationship types with source/target constraints
- Property schemas with types and validation rules
- Type hierarchies (parent-child, IS_A relationships)
- Constraints and cardinality hints

**Normalization prompt structure**:

The LLM receives the raw input alongside the canonical YAML schema definition (as a Pydantic model) and instructions to map every identifiable domain concept to the schema. Instructor enforces the output structure with retry on validation failure. The normalizer is conservative - it only emits types and relationships it can confidently identify from the input. Ambiguous concepts are flagged with `confidence: low` for user review.

**Example**: a markdown file describing a healthcare domain -

```markdown
Patients visit hospitals and are treated by doctors. Each patient has a diagnosis
which links to a condition from the ICD-10 catalogue. Doctors specialize in one or
more medical fields. Medications are prescribed for specific conditions.
```

Normalizes to:

```yaml
entity_types:
  - name: Patient
    description: A person receiving medical care
    source: seed_normalized
    confidence: high
  - name: Hospital
    description: A healthcare facility where patients are treated
    source: seed_normalized
    confidence: high
  - name: Doctor
    description: A medical professional who treats patients
    source: seed_normalized
    confidence: high
  - name: Condition
    description: A medical condition or diagnosis from ICD-10
    source: seed_normalized
    confidence: high
  - name: Medication
    description: A pharmaceutical prescribed for conditions
    source: seed_normalized
    confidence: high
  - name: MedicalField
    description: A medical specialty area
    source: seed_normalized
    confidence: medium

relationship_types:
  - name: VISITS
    source: Patient
    target: Hospital
  - name: TREATED_BY
    source: Patient
    target: Doctor
  - name: HAS_DIAGNOSIS
    source: Patient
    target: Condition
  - name: SPECIALIZES_IN
    source: Doctor
    target: MedicalField
  - name: PRESCRIBED_FOR
    source: Medication
    target: Condition
```

After normalization, the system validates that the type hierarchy forms a directed acyclic graph (DAG). Cycle detection is a programmatic topological sort, but resolution is LLM-assisted - the LLM examines the cycle's types and edges, then proposes which edge to remove, reclassify (e.g., IS_A to HAS_PART), or which types to merge. The resolution is presented for user confirmation.

The normalized output is presented to the user for review before being loaded into the buffer. The user can adjust, add, or remove types in the interactive session. Once confirmed, the normalized ontology is saved alongside the original source file for auditability.

### OWL/RDF Import

When the seed is an OWL/RDF file, owlready2 extracts the ontology programmatically without LLM involvement:

| OWL concept | Maps to | Notes |
|-------------|---------|-------|
| `owl:Class` | entity type | Name from class, description from `rdfs:comment` |
| `rdfs:subClassOf` | type hierarchy | Used for prompt context, depth limited by `seed_depth` |
| `owl:ObjectProperty` | relationship type | `rdfs:domain` -> source type, `rdfs:range` -> target type |
| `owl:DatatypeProperty` | property schema | Attached to the entity type from `rdfs:domain` |
| `owl:TransitiveProperty` | relationship flag | Marked for post-load inference via reasoner |
| `owl:disjointWith` | advisory warning | Logged when violated, not enforced - data may bridge OWL boundaries |

Large reference ontologies (NCIt has 170,000+ classes, SNOMED has 350,000+) are not suitable for direct use as extraction constraints. The `seed_depth` and `seed_filter` parameters ensure only a manageable subset is imported.

**The seed is advisory, not binding.** The extraction pipeline treats seed-sourced types as suggestions with higher initial confidence, but the buffer promotes discovered types that appear consistently in the data even without a seed counterpart. The final ontology can contain types and connections the seed never defined.

### Post-Load OWL Reasoning

When an OWL seed is configured, the pipeline can optionally run a post-load reasoning pass using the owlready2 HermiT reasoner. This materializes implicit relationships in Neo4J that were not explicitly extracted:

- **Subclass propagation**: if Rex is a Dog and Dog is subclass of Animal, Rex gets an `INSTANCE_OF` edge to Animal
- **Transitive closure**: if A `REPORTS_TO` B and B `REPORTS_TO` C, infer A `REPORTS_TO` C
- **Consistency checking**: flag entities assigned to disjoint classes

This is configured in `config.yml`:

```yaml
ontology_buffer:
  seed_from: .kg-builder/domain-ontology.owl
  post_load_reasoning: true          # run OWL inference after loading into Neo4J
```

### YAML Ontology Format

YAML file defining allowed entity types, relationship types, and optional property schemas. Default location: `.kg-builder/ontology.yml`.

```yaml
entity_types:
  - name: Person
    description: A human individual
    aliases: ["Individual", "Human", "Employee"]
    extraction_strategy: llm                # llm | regex | hybrid
    properties:
      - name: role
        type: string
      - name: age
        type: integer
        required: false
        min_value: 0
        max_value: 150

  - name: Organization
    description: A company, institution, or group
    aliases: ["Company", "Institution", "Corp"]
    extraction_strategy: hybrid
    properties:
      - name: industry
        type: string
        allowed_values: ["Technology", "Finance", "Healthcare", "Manufacturing"]
      - name: founded_year
        type: integer
        min_value: 1800

  - name: Technology
    description: A tool, framework, or technical concept
    aliases: ["Tool", "Framework", "Software"]
    extraction_strategy: llm

  - name: EmailAddress
    description: An email address extracted from text
    extraction_strategy: regex
    extraction_patterns:
      - "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}"

relationship_types:
  - name: WORKS_AT
    source: Person
    target: Organization

  - name: USES
    source: Organization
    target: Technology

  - name: FOUNDED
    source: Person
    target: Organization
```

**Entity aliases** map alternative surface forms to a canonical type. During extraction the LLM (or regex matcher) recognizes any alias and normalizes it to the parent type name. This reduces type sprawl without requiring the ontology buffer to discover variants at runtime.

**Property validation rules** constrain extracted values at parse time. Supported rules: `min_value`/`max_value` for numeric bounds, `pattern` for regex validation, `allowed_values` for enumerated strings, and `required` flag (defaults to `false`). Entities with properties that fail validation are flagged in the extraction output for review rather than silently dropped.

**Extraction strategy** controls how each entity type is identified. `llm` (default) uses the language model, `regex` uses the `extraction_patterns` list for deterministic matching, and `hybrid` runs regex first then passes candidates to the LLM for classification and property extraction. Regex-only types skip the LLM entirely, reducing cost for high-confidence patterns like email addresses or identifiers.

During extraction, ontology entity types are converted to Pydantic response models. Each entity type becomes a Pydantic class with `Field` descriptions drawn from the ontology, `field_validator` functions for property validation rules (min/max bounds, allowed values, regex patterns), and `json_schema_extra` for few-shot examples. The Instructor library enforces these models against LLM output with automatic retry on validation failure - if the LLM returns a malformed entity, Instructor re-prompts with the validation error until the output conforms or the retry limit is reached. Entity types should use distinct field names (e.g., `medication_name` instead of just `name`) to avoid LLM confusion when multiple types share the same property structure - these disambiguated names are mapped back to canonical property names during loading.

When `--ontology` is provided to `extract`, the LLM prompt is constrained to emit only these types. Entity descriptions and aliases are included in the prompt to guide classification.

### Extraction Output Format

Extraction files are written to `.kg-builder/extractions/` with timestamped filenames.

```json
{
  "metadata": {
    "source": "path/to/document.pdf",
    "model": "us.anthropic.claude-sonnet-4-20250514",
    "ontology": ".kg-builder/ontology.yml",
    "timestamp": "2026-03-09T12:00:00Z",
    "chunk_count": 15
  },
  "entities": [
    {
      "id": "person_john_doe",
      "name": "John Doe",
      "type": "Person",
      "properties": {"role": "CTO"},
      "source_chunks": [0, 3]
    }
  ],
  "relationships": [
    {
      "source": "person_john_doe",
      "target": "org_acme_corp",
      "type": "WORKS_AT",
      "properties": {},
      "source_chunks": [3]
    }
  ],
  "facts": [
    {
      "statement": "John Doe was diagnosed with Type 2 Diabetes on 2024-01-15",
      "source_chunks": [3],
      "triplet": {
        "subject": "person_john_doe",
        "predicate": "DIAGNOSED_WITH",
        "target": "disease_type_2_diabetes"
      }
    }
  ],
  "validation": {
    "orphan_entities": 0,
    "missing_relationships": 2,
    "type_coverage": 0.85
  }
}
```

The `facts` array captures atomic factual statements alongside the entity-relationship graph. Each fact records a natural language statement, the source chunks it was derived from, and a triplet mapping it back to extracted entities. Facts serve as a parallel extraction track - the Graph Reader pattern from Akash Goyal's research shows atomic facts achieve 85% precision at 95% recall, complementing the entity-relationship extraction which trades higher precision for lower recall. During loading, each fact becomes a `Fact` node linked to its subject and target entities, preserving the original statement text for retrieval-augmented generation queries where verbatim source context matters.

## Graph Structure in Neo4J

The load step creates a graph with Document, Chunk, Entity, and Fact node types. Entities carry a `name`, `type`, `description`, and `source_chunk` reference. Relationships between entities are typed edges matching the ontology.

**Dual indexing** ensures both semantic and keyword retrieval paths are available:

- **Vector index** on `Entity.embedding` for semantic similarity search - embeddings are generated during load using the configured LLM provider's embedding model
- **Fulltext index** on `Entity.name` for keyword search - enables exact and fuzzy name lookups without embedding overhead

Both indexes are created automatically when `create_indexes: true` in config. The vector index supports approximate nearest neighbour queries via Neo4J's native vector search, while the fulltext index uses Apache Lucene under the hood for fast text matching.

## Supported Input Formats

| Format | Type | Library |
|--------|------|---------|
| PDF | unstructured | `pymupdf4llm` (structured Markdown with images, tables, layout) |
| TXT / MD | unstructured | built-in |
| DOCX | unstructured | `python-docx` |
| JSON | structured | built-in |
| JSONL | structured | built-in |

## Dependencies (beyond current pyproject.toml)

- `strands-agents` - Strands Agents SDK for agent orchestration, tool registry, and conversational loops
- `strands-agents-tools` - standard tool implementations (py-repl, file operations)
- `neo4j` - Neo4J Python driver (direct driver for bulk operations)
- `boto3` - AWS Bedrock access
- `langchain-text-splitters` - document chunking
- `langchain-aws` - Bedrock LLM integration (or direct `boto3` invoke)
- `pymupdf4llm` - PDF to structured Markdown with layout, tables, and image extraction (built on pymupdf)
- `python-docx` - DOCX parsing
- `pyyaml` - YAML config and ontology parsing
- `owlready2` - OWL/RDF ontology loading and HermiT reasoning
- `instructor` - structured LLM output with Pydantic model enforcement and retry handling
- `pydantic` - entity schema definition, extraction validation, response models
- `chonkie` - semantic chunking (alternative to token-based)
- `langchain-neo4j` - Neo4J graph/vector integration (Neo4jGraph, Neo4jVector, GraphDocument)

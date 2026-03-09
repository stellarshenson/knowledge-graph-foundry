# kg-builder-cli Specification

CLI tool for building knowledge graphs from structured and unstructured data, loading them into Neo4J. Uses LLMs to identify entities and relationships, with optional ontology constraints to control graph structure. Designed as a simpler, CLI-driven alternative to the Neo4J LLM Graph Builder web application.

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

JSON or JSONL files containing records that follow a known schema. The schema is not embedded in the data itself - it is described in a separate schema description file (markdown, YAML, or plain text) that the LLM interprets generatively to understand field meanings, entity mappings, and relationship patterns.

The `--schema` option points to this description file. The LLM reads the schema description alongside each record and determines how to map fields to graph entities and relationships. This means the schema description does not need to follow a rigid format - it can be a markdown document explaining what each field represents, a YAML with field descriptions, or any human-readable source that conveys the structure.

```
kg extract data/records.jsonl --schema .kg-builder/schemas/employees.md
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

## CLI Commands

The CLI is built with typer and exposes a single entry point `kg` with subcommands grouped by workflow stage.

### `kg init`

Initialize the `.kg-builder/` directory and generate a configuration file.

```
kg init [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--interactive` | `False` | LLM-driven Q&A session to build the config generatively |

**Two modes**:

- **Template mode** (default): creates `.kg-builder/` directory and writes a commented `config.yml` template with all available options and sensible defaults. The user fills in or adjusts values manually
- **Interactive mode** (`--interactive`): the LLM asks a series of questions about the user's data, target graph structure, Neo4J setup, and preferred extraction behaviour, then generates a tailored `config.yml` from the answers

Both modes also create the `schemas/` and `extractions/` subdirectories.

### `kg extract`

Extract entities and relationships from source documents using an LLM.

```
kg extract <source> [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--source` | required | Path to file or directory of documents to process |
| `--output` | `.kg-builder/extractions/` | Output path for extracted graph data |
| `--ontology` | from config | Path to ontology YAML file (free extraction if omitted) |
| `--schema` | from config | Path to schema description file for structured data |
| `--model` | from config | LLM model identifier |
| `--chunk-size` | from config | Token chunk size for document splitting (unstructured only) |
| `--chunk-overlap` | from config | Token overlap between chunks (unstructured only) |
| `--concurrency` | from config | Parallel LLM requests |

**Behaviour**:
- Input type detected by file extension: `.json`/`.jsonl` -> structured, everything else -> unstructured
- Without `--ontology`: free extraction - the LLM discovers entity and relationship types, building the ontology progressively via the ontology buffer. The resulting ontology is flushed to `.kg-builder/ontology.yml` at the end of the run
- With `--ontology`: constrained extraction - starts from the provided ontology but refines it during processing. New types discovered with sufficient evidence are proposed for inclusion. The refined ontology is written back to the file
- The ontology buffer tracks type frequencies, variant mappings, and coverage scores across documents. See `docs/ingestion-unstructured.md` for the full buffered ontology mechanism
- `--schema` is required for structured data - provides the human-readable description the LLM uses to interpret record fields as graph entities and relationships
- Unstructured: processes PDF, TXT, MD, and DOCX formats with chunking
- Structured: processes each JSON record (or batch) as a discrete unit, no chunking
- Outputs structured JSON with entities, relationships, and source references

### `kg load`

Load extracted graph data into Neo4J.

```
kg load [input] [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `input` | latest file in `.kg-builder/extractions/` | Path to extraction JSON |
| `--merge-strategy` | from config | How to handle existing nodes: `merge`, `replace`, `skip` |
| `--batch-size` | from config | Cypher batch size for bulk loading |
| `--create-indexes` | from config | Auto-create indexes for entity labels |

**Behaviour**:
- Connects to Neo4J using credentials from config (`${VAR}` resolved from `.env` or environment)
- Creates nodes with properties (name, type, description, source_chunk)
- Creates typed relationships between nodes
- Deduplicates entities by name+type before loading

### `kg pipeline`

Run extract + load as a single pipeline.

```
kg pipeline <source> [options]
```

Accepts all options from `extract` and `load`. Runs extraction then immediately loads results into Neo4J without writing intermediate files to disk (unless `--keep-extractions` is set).

| Option | Default | Description |
|--------|---------|-------------|
| `--keep-extractions` | `False` | Save intermediate extraction JSON to `.kg-builder/extractions/` |

### `kg schema`

Inspect or generate ontology files.

```
kg schema show [ontology-file]
kg schema generate <source> [--output <path>]
```

- `show`: renders the ontology as a table of entity types, relationship types, and constraints. Defaults to `.kg-builder/ontology.yml` if no file specified
- `generate`: uses the LLM to propose an ontology from sample documents, saved as YAML for review and editing. Defaults output to `.kg-builder/ontology.yml`

### `kg status`

Show current Neo4J database statistics.

```
kg status
```

Displays node count by label, relationship count by type, and total graph size.

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
  chunk_size: 2000                   # token chunk size (unstructured only)
  chunk_overlap: 200                 # token overlap between chunks (unstructured only)
  concurrency: 4                     # parallel LLM requests

# Ontology buffer settings
ontology_buffer:
  seed_from: null                    # OWL/RDF file to seed the buffer (optional)
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

# Paths (relative to project root)
paths:
  ontology: null                     # path to ontology YAML (free extraction if null)
  schema: null                       # path to schema description for structured data
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

The ontology buffer can be initialized from three sources, in order of precedence:

1. **OWL/RDF seed** (`ontology_buffer.seed_from`): an existing formal ontology loaded via owlready2. Classes become entity types, object properties become relationship types, data properties become property schemas. The `seed_depth` parameter controls how deep into the class hierarchy to import (default 2), and `seed_filter` restricts import to a specific branch. The OWL file is read-only input - it is never modified. **The OWL seed is suggestive, not prescriptive** - it provides starting vocabulary and domain context, but the extraction is free to discover entity types, relationship types, and connections that the original OWL ontology did not anticipate. The resulting application ontology may diverge significantly from the OWL source
2. **YAML ontology** (`paths.ontology`): the lightweight application schema in our custom format. If both OWL seed and YAML are provided, the YAML takes precedence for any overlapping type definitions - OWL fills in the gaps
3. **Empty** (free extraction): no seed, no YAML. The buffer starts empty and builds the ontology from scratch during extraction

After the run completes, the refined ontology is always flushed as YAML to `.kg-builder/ontology.yml` regardless of the original source. This means an OWL-seeded run produces a YAML ontology as a side effect - informed by the formal ontology but shaped by what the documents actually contained. The output ontology is the system's own schema, not a subset of the OWL input.

### OWL Seed Import

When `seed_from` points to an OWL/RDF file, owlready2 extracts:

| OWL concept | Maps to | Notes |
|-------------|---------|-------|
| `owl:Class` | entity type | Name from class, description from `rdfs:comment` |
| `rdfs:subClassOf` | type hierarchy | Used for prompt context, depth limited by `seed_depth` |
| `owl:ObjectProperty` | relationship type | `rdfs:domain` -> source type, `rdfs:range` -> target type |
| `owl:DatatypeProperty` | property schema | Attached to the entity type from `rdfs:domain` |
| `owl:TransitiveProperty` | relationship flag | Marked for post-load inference via reasoner |
| `owl:disjointWith` | advisory warning | Logged when violated, not enforced - data may bridge OWL boundaries |

Large reference ontologies (NCIt has 170,000+ classes, SNOMED has 350,000+) are not suitable for direct use as extraction constraints. The `seed_depth` and `seed_filter` parameters ensure only a manageable subset is imported. The Dynamic Ontology reference makes this point clearly: reference ontologies are great for standard IDs and relationships, but they're too large and complex to serve as application schemas.

**The OWL seed is advisory, not binding.** The extraction pipeline treats OWL-sourced types as suggestions with higher initial confidence, but the buffer will promote discovered types that appear consistently in the data even if they have no OWL counterpart. This means the final ontology can contain entity types, relationship types, and connection patterns that the OWL source never defined. The OWL gives the system a head start and domain vocabulary - the documents determine the actual schema.

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
    properties:
      - name: role
        type: string

  - name: Organization
    description: A company, institution, or group
    properties:
      - name: industry
        type: string

  - name: Technology
    description: A tool, framework, or technical concept

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

When `--ontology` is provided to `extract`, the LLM prompt is constrained to emit only these types. Entity descriptions are included in the prompt to guide classification.

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
  ]
}
```

## Supported Input Formats

| Format | Type | Library |
|--------|------|---------|
| PDF | unstructured | `pymupdf` or `pdfplumber` |
| TXT / MD | unstructured | built-in |
| DOCX | unstructured | `python-docx` |
| JSON | structured | built-in |
| JSONL | structured | built-in |

## Dependencies (beyond current pyproject.toml)

- `neo4j` - Neo4J Python driver
- `boto3` - AWS Bedrock access
- `langchain-text-splitters` - document chunking
- `langchain-aws` - Bedrock LLM integration (or direct `boto3` invoke)
- `pymupdf` - PDF text extraction
- `python-docx` - DOCX parsing
- `pyyaml` - YAML config and ontology parsing
- `owlready2` - OWL/RDF ontology loading and HermiT reasoning

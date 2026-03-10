# kg-builder-cli

CLI tool for building knowledge graphs from structured and unstructured data into Neo4j. Simpler, CLI-driven alternative to [Neo4j LLM Graph Builder](https://github.com/neo4j-labs/llm-graph-builder) with adaptive ontology evolution and agent-backed architecture.

## Features

- **Adaptive ontology buffer** - evolves during ingestion with frequency tracking, variant detection, and coverage scoring. Free extraction discovers types; constrained extraction refines them
- **Any-format ontology seeding** - OWL, YAML, JSON, markdown, plain text - LLM normalizes any format to canonical schema
- **Structured + unstructured** - PDF, TXT, MD, DOCX (unstructured) and JSON, JSONL (structured) with automatic schema inference
- **Multi-signal entity resolution** - Levenshtein fuzzy matching, embedding similarity (FAISS), Bayesian type inference with LLM escalation for ambiguous cases
- **Fluid schema curing** - two-phase ingestion: fluid accumulation discovers types, curing event freezes the schema, remaining documents load with enforcement
- **Generative curing advisory** - optional LLM layer evaluates metric timelines and domain intent for cure/continue decisions, with graph query tool for ambiguous cases and patience-based early stopping
- **Drift detection** - post-cure monitoring with remap rate tracking, optional re-curing on sustained drift
- **Dual indexing** - vector index (semantic similarity) + fulltext index (keyword lookup) on Neo4j entities
- **Extraction modes** - entity-relationship, atomic facts (Graph Reader), or hybrid at ~2x LLM cost
- **Interactive + batch modes** - user checkpoints for schema review or fully autonomous execution with `--batch`
- **TUI** - textual-based terminal interface with live stats and ontology buffer display
- **Instructor/Pydantic** - structured LLM output enforcement with auto-retry on validation failure

## Install

```bash
make install
```

## Usage

```bash
# Ingest documents into a knowledge graph
kg ingest data/raw/ --ontology ontology.yml

# Free extraction (no ontology seed - discovers types)
kg ingest data/raw/

# Fluid schema curing
kg ingest data/raw/ --fluid

# Batch mode (no interactive checkpoints)
kg ingest data/raw/ --batch

# Initialize .kg-builder/ directory
kg init
```

## Configuration

Configuration uses `.kg-builder/config.yml` with environment variable interpolation from `.env`:

```yaml
neo4j:
  uri: ${NEO4J_URI:bolt://localhost:7687}
  user: ${NEO4J_USERNAME:neo4j}
  password: ${NEO4J_PASSWORD:}

llm:
  provider: bedrock
  model: eu.anthropic.claude-sonnet-4-20250514-v1:0
  temperature: 0.0

extract:
  chunk_size: 2000
  chunk_overlap: 200
  concurrency: 4

curing:
  enabled: false
  generative_curing: false
  generative_patience: 3
  generative_max_tool_calls: 2
```

## Technology Stack

- Python 3.12, uv package manager
- **LLM**: litellm + instructor (structured output)
- **Agents**: Strands Agents SDK
- **CLI/TUI**: typer, textual
- **Parsing**: pymupdf4llm (PDF), python-docx (DOCX)
- **Chunking**: tiktoken, langchain-text-splitters, chonkie (semantic)
- **Graph**: neo4j driver, langchain-neo4j
- **Resolution**: python-Levenshtein, faiss-cpu, numpy
- **Ontology**: owlready2 (OWL/RDF), pydantic (schema validation)

## Makefile Targets

- `make install` - Create environment and install package
- `make test` - Run tests
- `make lint` / `make format` - Check / fix code style
- `make build` - Build distributable wheel
- `make clean` - Remove compiled files and caches

## Project Organization

```
├── kg_builder_cli/
│   ├── cli.py              <- CLI entry points (typer)
│   ├── config/             <- Configuration loading and defaults
│   ├── curing/             <- Fluid schema curing, metrics, drift detection
│   ├── extraction/         <- Parsing, chunking, LLM extraction, entity resolution
│   ├── loading/            <- Batch Cypher loading, indexes, validation
│   ├── ontology/           <- Ontology buffer, OWL import
│   ├── tui/                <- Textual terminal UI
│   └── types/              <- Pydantic data models
├── tests/                  <- pytest test suite
├── docs/
│   ├── DESIGN.md           <- Canonical design document
│   └── DESIGN_ASSUMPTIONS.md <- Design checklist
├── data/
│   ├── raw/                <- Immutable source data
│   ├── interim/            <- Intermediate transforms
│   └── processed/          <- Final datasets
└── .kg-builder/            <- Runtime config, ontology, extractions
```

## References

- [Neo4j LLM Graph Builder](https://github.com/neo4j-labs/llm-graph-builder) - reference implementation for LLM-powered knowledge graph construction from unstructured data
- [CodeGraphContext](https://github.com/CodeGraphContext/CodeGraphContext) - code indexing and graph analysis platform using tree-sitter AST parsing with Neo4j/KuzuDB/FalkorDB backends

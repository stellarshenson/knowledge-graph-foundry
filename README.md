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
  uri: ${NEO4J_URI:bolt://localhost:7687}   # bolt or neo4j+s:// for Aura
  user: ${NEO4J_USERNAME:neo4j}
  password: ${NEO4J_PASSWORD:}

llm:
  provider: bedrock                          # bedrock | openai | anthropic
  model: eu.anthropic.claude-sonnet-4-20250514-v1:0
  temperature: 0.0                           # 0.0 for deterministic extraction
  max_retries: 3                             # instructor retry on validation failure
  timeout: 120                               # seconds per LLM call

extract:
  chunk_size: 2000                           # tokens per chunk
  chunk_overlap: 200                         # overlap between consecutive chunks
  concurrency: 4                             # parallel extraction threads
  extraction_mode: hybrid                    # entity_relationship | graph_reader | hybrid
  resolution_threshold: 0.85                 # Levenshtein threshold for entity resolution
  bayesian_resolution: false                 # Bayesian type inference with exemplar index
  llm_escalation: false                      # LLM fallback for high-entropy type assignment
  use_embeddings: false                      # embedding-based entity resolution (requires model)

curing:
  enabled: false                             # fluid schema curing (two-phase ingestion)
  min_documents: 3                           # minimum docs before curing can trigger
  max_fluid_documents: 20                    # safety net - force-cure at this count
  generative_curing: false                   # LLM-assisted cure/continue decisions
  generative_patience: 0.4                   # fraction of max_fluid_documents as consecutive
                                             # document cure votes to auto-trigger (0.4 * 20 = 8, min 3)
  generative_max_tool_calls: 2              # max graph queries per LLM decision
  drift_remap_threshold: 0.3                # remap rate to signal schema drift
  re_cure_on_drift: false                    # re-enter fluid phase on sustained drift

ontology_buffer:
  seed_from: null                            # path to ontology seed (any format)
  intent: null                               # domain intent for LLM guidance
  refine_every_n_docs: 5                     # buffer refinement interval
  coverage_threshold: 0.5                    # minimum coverage to confirm types
  flush_on_complete: true                    # write final ontology to disk
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
│   ├── KGB_DESIGN.md       <- Canonical design document
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

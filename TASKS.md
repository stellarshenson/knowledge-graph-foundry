# Implementation Tasks

Master task list for kg-builder-cli. Derived from `docs/DESIGN.md`.

---

## Foundation

- [ ] `types/` module - all Pydantic contract models (config, document, extraction, ontology, resolution, loading, pipeline)
- [ ] `config/` module - YAML loader with `${VAR}` interpolation, defaults, CLI override resolution
- [ ] `.kg-builder/` initialization logic - create directory structure on first run

## Infrastructure

- [ ] `tools/neo4j_driver.py` - bulk Cypher operations, batch MERGE, transaction management, deadlock retry
- [ ] `tools/py_repl.py` - Python REPL tool wrapper for code inspection and dynamic parsing
- [ ] `tools/file_ops.py` - read/write `.kg-builder/` directory, YAML serialization

## Ontology

- [ ] `ontology/normalizer.py` - three-tier normalization (py-repl parse -> LLM repair -> full LLM)
- [ ] `ontology/yaml_schema.py` - validate and load YAML ontology against canonical schema
- [ ] `ontology/buffer.py` - in-memory ontology state, TypeSignal accumulation, coverage scoring
- [ ] `ontology/dag.py` - DAG validation, cycle detection on type hierarchies

## Extraction

- [ ] `extraction/parsing.py` - PDF (pymupdf4llm), TXT, MD, DOCX parsers returning TextSegments
- [ ] `extraction/chunking.py` - token-based chunking with overlap, deterministic chunk IDs (SHA1)
- [ ] `extraction/prompts.py` - extraction prompt construction from chunks + ontology state
- [ ] `extraction/unstructured.py` - orchestrate parse -> chunk -> extract -> dedup -> resolve
- [ ] `extraction/dedup.py` - exact (type, id) deduplication across chunks
- [ ] `extraction/resolution.py` - entity resolution: exact match -> embedding similarity -> LLM clustering

## Loading

- [ ] `loading/loader.py` - batch load entities and relationships into Neo4j via parameterized Cypher MERGE
- [ ] `loading/indexes.py` - create structural, vector, and fulltext indexes
- [ ] `loading/validation.py` - post-load validation (orphans, coverage, counts)

## Agents

- [ ] `agents/ingest.py` - ingest agent with Strands SDK, tool registration, interactive/batch mode
- [ ] `agents/query.py` - query agent with text2cypher, dual retrieval routing

## CLI

- [ ] `cli.py` - typer entry points for `kg ingest`, `kg query`, `kg update`, `kg init`

## Testing

- [ ] Unit tests for types, config, chunking, dedup, ontology buffer
- [ ] Integration tests for Neo4j loading (MERGE, indexes, validation)
- [ ] End-to-end test: single CPAP PDF -> parsed -> chunked -> extracted -> loaded -> queryable

## Deferred (post-MVP)

- [ ] `query/` module - text2cypher, retrieval routing, result formatting
- [ ] `update/` module - schema diff, migration plans, ontology refinement
- [ ] `tui/` module - textual three-panel layout
- [ ] `memory/` module - agent memory store with TTL
- [ ] `ontology/owl_import.py` - OWL/RDF import via owlready2
- [ ] `ontology/reasoning.py` - post-load OWL reasoning / Cypher subclass propagation
- [ ] Benchmark instrumentation (`--benchmark` flag)
- [ ] Schema versioning and SchemaVersion node materialization

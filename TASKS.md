# Implementation Tasks

Master task list for kg-builder-cli. Derived from `docs/DESIGN.md`.

---

## Foundation

- [x] `types/` module - all Pydantic contract models (config, document, extraction, ontology, resolution, loading, pipeline)
- [x] `config/` module - YAML loader with `${VAR}` interpolation, defaults, CLI override resolution
- [ ] `.kg-builder/` initialization logic - create directory structure on first run

## Infrastructure

- [ ] `tools/neo4j_driver.py` - bulk Cypher operations, batch MERGE, transaction management, deadlock retry
- [ ] `tools/py_repl.py` - Python REPL tool wrapper for code inspection and dynamic parsing
- [ ] `tools/file_ops.py` - read/write `.kg-builder/` directory, YAML serialization

## Ontology

- [ ] `ontology/normalizer.py` - three-tier normalization (py-repl parse -> LLM repair -> full LLM)
- [ ] `ontology/yaml_schema.py` - validate and load YAML ontology against canonical schema
- [x] `ontology/buffer.py` - in-memory ontology state, TypeSignal accumulation, coverage scoring, YAML flush
- [ ] `ontology/dag.py` - DAG validation, cycle detection on type hierarchies
- [ ] `ontology/owl_import.py` - OWL/RDF import via owlready2
- [ ] `ontology/reasoning.py` - post-load OWL reasoning / Cypher subclass propagation

## Extraction

- [x] `extraction/parsing.py` - PDF (pymupdf4llm), TXT, MD, DOCX parsers returning TextSegments
- [x] `extraction/chunking.py` - token-based chunking with overlap, deterministic chunk IDs (SHA1)
- [x] `extraction/prompts.py` - extraction prompt construction from chunks + ontology state + intent
- [x] `extraction/unstructured.py` - orchestrate parse -> chunk -> extract -> dedup -> resolve -> load (with buffer + resolution)
- [x] `extraction/dedup.py` - exact (type, id) deduplication across chunks
- [x] `extraction/resolution.py` - Levenshtein fuzzy entity resolution with union-find clustering
- [x] `extraction/response_models.py` - Pydantic response models for instructor structured output
- [ ] `extraction/facts.py` - atomic facts extraction (FactNode track)
- [ ] `extraction/structured.py` - structured pipeline (JSON/JSONL/CSV/XLSX)

## Loading

- [x] `loading/loader.py` - batch load with chunk content, NEXT_CHUNK chain, entity nodes, relationships
- [x] `loading/indexes.py` - structural + vector + fulltext indexes (4 total)
- [x] `loading/validation.py` - post-load validation (orphans, counts, type distribution)
- [ ] Schema versioning and SchemaVersion node materialization

## Query

- [ ] `query/` module - text2cypher, retrieval routing, result formatting

## Update

- [ ] `update/` module - schema diff, migration plans, ontology refinement

## Agents

- [ ] `agents/ingest.py` - ingest agent with Strands SDK, tool registration, interactive/batch mode
- [ ] `agents/query.py` - query agent with text2cypher, dual retrieval routing

## CLI

- [x] `cli.py` - typer entry points with TUI callback, ontology buffer integration, `kg ingest`, `kg query` (stub), `kg init`
- [x] `tui/app.py` - textual TUI skeleton (command panel, log panel, status bar)
- [ ] `tui/` - btop-style interactive rich TUI with live stats, graph metrics, pipeline progress

## Memory

- [ ] `memory/` module - agent memory store with TTL, buffer disk persistence/versioning

## Testing

- [x] Unit tests for config, chunking, dedup, prompts, resolution, response models, ontology buffer, graph quality (59 tests, 90% coverage)
- [ ] Integration tests for Neo4j loading (MERGE, indexes, validation)
- [ ] End-to-end test: single CPAP PDF -> parsed -> chunked -> extracted -> loaded -> queryable
- [ ] Query benchmark scorecard - multi-dimensional quality evaluation, comprehensive, no prompt overfitting
- [ ] Benchmark instrumentation (`--benchmark` flag)

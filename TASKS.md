# Implementation Tasks

Master task list for kg-builder-cli. Derived from `docs/KGB_DESIGN.md`.

---

## Foundation

- [x] `types/` module - all Pydantic contract models (config, document, extraction, ontology, resolution, loading, pipeline)
- [x] `config/` module - YAML loader with `${VAR}` interpolation, defaults, CLI override resolution
- [ ] `.kg-builder/` initialization logic - create directory structure on first run

## Ontology

- [x] `ontology/buffer.py` - in-memory ontology state, TypeSignal accumulation, coverage scoring, YAML flush, enriched prompt sections
- [x] `ontology/owl_import.py` - OWL/RDF import via owlready2
- [ ] `ontology/yaml_schema.py` - validate and load YAML ontology against canonical schema
- [ ] `ontology/dag.py` - DAG validation, cycle detection on type hierarchies
- [ ] `ontology/reasoning.py` - post-load OWL reasoning / Cypher subclass propagation

## Extraction

- [x] `extraction/parsing.py` - PDF (pymupdf4llm), TXT, MD, DOCX parsers returning TextSegments
- [x] `extraction/chunking.py` - token-based chunking with overlap, deterministic chunk IDs (SHA1)
- [x] `extraction/prompts.py` - extraction prompt construction from chunks + ontology state + intent, structured properties prompt
- [x] `extraction/unstructured.py` - orchestrate parse -> chunk -> extract -> dedup -> resolve -> load (with buffer + resolution)
- [x] `extraction/dedup.py` - exact (type, id) deduplication with `normalize_entity_ids` cross-document merging
- [x] `extraction/resolution.py` - multi-signal entity resolution (Levenshtein name, type-aware, embedding similarity, cross-type)
- [x] `extraction/deferred_dedup.py` - deferred cross-type dedup buffer with evidence accumulation and LLM escalation (H5f)
- [x] `extraction/response_models.py` - Pydantic response models for instructor structured output
- [x] `extraction/embeddings.py` - Amazon Titan embedding generation for semantic entity resolution
- [ ] `extraction/facts.py` - atomic facts extraction (FactNode track)
- [ ] `extraction/structured.py` - structured pipeline (JSON/JSONL/CSV/XLSX)

## Schema Curing

- [x] `curing/detector.py` - three-condition curing detection (min docs, coverage convergence, type stability) with failsafe
- [x] `curing/accumulator.py` - in-memory ExtractionResult accumulator with consolidation (type enforcement, dedup, resolution)
- [x] `types/config.py` - CuringConfig model with defaults
- [x] `cli.py` - two-phase ingestion loop with `--fluid`/`--no-fluid` and `--cure` flags
- [x] `config/defaults.py` - curing section in DEFAULTS dict
- [x] `ontology/buffer.py` - `type_names()` method for new type tracking

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

## Configuration

- [ ] `config/defaults.py` - split parameters into user-exposed (config.yml) vs expert-only (hardcoded defaults). Document every setting with purpose, value, meaning
- [ ] `config/selftest.py` - system_selftest: verify LLM provider/model configured, embedding model configured, Neo4j reachable, credentials valid. Run before ingestion
- [ ] `config/defaults.py` - multi-provider embedding support (bedrock, openai, sentence-transformers)

## Testing

- [x] Unit tests for config, chunking, dedup, prompts, resolution, response models, ontology buffer, graph quality, embeddings, curing (109 tests, 92% coverage)
- [ ] Integration tests for Neo4j loading (MERGE, indexes, validation)
- [ ] End-to-end test: single CPAP PDF -> parsed -> chunked -> extracted -> loaded -> queryable
- [ ] Query benchmark scorecard - multi-dimensional quality evaluation

## Benchmarks

- [x] Single-document benchmarks (v01-v05) - iterative improvement from 48% to 70%
- [x] Multi-document benchmark v06 - cross-document entity resolution
- [x] Multi-document benchmark v07 - enriched ontology buffer prompts
- [x] Multi-document benchmark v08 - configurable thresholds, 88% score

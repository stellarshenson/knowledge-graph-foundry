# Implementation Changes v00

Gap analysis between `docs/DESIGN.md` (canonical specification) and the current implementation, evaluated from the perspective of the architect who authored the design document.

---

## The Devil

**Role**: Architect and author of DESIGN.md - wants the implementation to faithfully realize the design
**Cares about**: Functional completeness, interface fidelity, production readiness
**Style**: Systematic comparison against the specification, evidence-based
**Default bias**: The design exists for a reason - deviations need justification, not silence
**Triggers**: Silent simplifications that undermine architectural intent, missing error handling, hardcoded values
**Decision**: Approve implementation milestones or flag gaps for correction
**Source**: User-described (architect wanting best implementation)

---

## Concern Catalogue

### Section A - Previously Identified (1-15)

These concerns were identified in the initial analysis. Status updated where fixes were applied.

#### 1. "The loader doesn't call its own post-load steps"

**Likelihood: 8** | **Impact: 5** | **Risk: 40** | **Status: FIXED**

`load_extraction()` now calls `create_indexes()` and `validate_graph()` gated by config flags. Post-load steps wired into the pipeline.

---

#### 2. "boto3 session created per chunk - O(N) session overhead"

**Likelihood: 8** | **Impact: 5** | **Risk: 40** | **Status: FIXED**

Session created once in `ingest_document()`, client passed to `extract_chunk()`. Signature changed to accept `client` parameter.

---

#### 3. "Only Bedrock - provider config is ignored"

**Likelihood: 5** | **Impact: 5** | **Risk: 25** | **Status: OPEN**

`LLMConfig` declares three providers but `extract.py` hardcodes boto3 Bedrock calls. Setting `provider: openai` silently does nothing. Now superseded by concern #35 (litellm replacement).

---

#### 4. "Chunks stored without text content"

**Likelihood: 5** | **Impact: 5** | **Risk: 25** | **Status: OPEN**

`_create_chunk_nodes()` creates `(:Chunk {id: row.id})` with no text, page, or token_count properties. Chunk content lost after loading.

---

#### 5. "Temperature config ignored - hardcoded to 0.0"

**Likelihood: 3** | **Impact: 3** | **Risk: 9** | **Status: FIXED**

`config.llm.temperature` now passed through to `extract_chunk()` and used in `inferenceConfig`.

---

#### 6. "Parsing uses if/elif chain instead of adapter registry"

**Likelihood: 3** | **Impact: 3** | **Risk: 9** | **Status: OPEN**

Design specifies `_PARSERS: dict[str, Callable]` registry. Implementation uses `if suffix == ".pdf"` chain. Works for 4 formats but violates open/closed principle.

---

#### 7. "CLI uses f-strings with loguru instead of {} placeholders"

**Likelihood: 2** | **Impact: 2** | **Risk: 4** | **Status: FIXED**

All 9 f-string logger calls in `cli.py` replaced with `{}` placeholders.

---

#### 8. "ExtractionResult.facts field exists but nothing populates it"

**Likelihood: 5** | **Impact: 3** | **Risk: 15** | **Status: OPEN**

`Fact` model exists, `extraction_mode` config option exists, but extraction never produces facts. The `graph_reader` and `hybrid` modes are not dispatched.

---

#### 9. "No ontology buffer feedback loop"

**Likelihood: 8** | **Impact: 8** | **Risk: 64** | **Status: OPEN**

Architectural centerpiece completely absent. No `ontology/` module, no buffer initialization, no feedback loop, no coverage computation, no refinement. Expanded in concerns 22-31.

---

#### 10. "Entity resolution pipeline completely missing"

**Likelihood: 5** | **Impact: 8** | **Risk: 40** | **Status: OPEN**

Only exact `(type, id)` dedup exists. No fuzzy matching, no embedding similarity, no LLM clustering. `python-Levenshtein` now in dependencies but unused.

---

#### 11. "Validation module opens two separate Neo4j driver connections"

**Likelihood: 3** | **Impact: 2** | **Risk: 6** | **Status: FIXED**

`validate_graph()` now accepts optional `driver` keyword parameter, uses single session.

---

#### 12. "nodes_created and nodes_merged always identical"

**Likelihood: 2** | **Impact: 2** | **Risk: 4** | **Status: OPEN**

Both set to same value. MERGE doesn't report create-vs-match without `ON CREATE SET`.

---

#### 13. "Missing NEXT_CHUNK chain between chunk nodes"

**Likelihood: 3** | **Impact: 3** | **Risk: 9** | **Status: OPEN**

Chunks created as isolated nodes with no ordering relationships.

---

#### 14. "Config defaults hardcode 'kolomolo' AWS profile"

**Likelihood: 3** | **Impact: 3** | **Risk: 9** | **Status: FIXED**

Default profile changed to `None` (boto3 default credential chain).

---

#### 15. "merge_strategy config exists but is never implemented"

**Likelihood: 3** | **Impact: 3** | **Risk: 9** | **Status: OPEN**

Config accepts `merge | replace | skip` but loader always uses MERGE.

---

### Section B - Architecture and CLI (16-21)

#### 16. "No agent layer - CLI calls pipeline functions directly"

**Likelihood: 13** | **Impact: 13** | **Risk: 169**

The design's core premise is that each CLI command spawns a Strands agent with system prompt and tool registry. The agent orchestrates the pipeline, handles interactive checkpoints, and maintains conversational context. The implementation has zero agent involvement - `cli.py` directly imports and calls `ingest_document()` and `load_extraction()` in a loop. No Strands agent instantiation, no system prompt, no tool registry, no interactive/autonomous mode switching. `strands-agents` and `strands-agents-tools` are in pyproject.toml but never imported.

**Response**: Create agent factory module. Start with minimal agent wrapping existing pipeline calls, then add interactive checkpoints.

---

#### 17. "Missing `kg query` command"

**Likelihood: 13** | **Impact: 8** | **Risk: 104**

Stubbed with `logger.warning("Query agent not yet implemented")`. Design specifies full agent-backed query with `--cypher`, `--format` (table/json/graph/text), `--limit`, `--status`, dual retrieval (vector + fulltext), conversational mode.

**Response**: Implement `--status` first (node/relationship counts via Neo4j driver) as quick win. Full query agent follows.

---

#### 18. "Missing `kg update` subcommands entirely"

**Likelihood: 13** | **Impact: 8** | **Risk: 104**

Design specifies `kg update schema`, `kg update ontology`, `kg update graph` - each with distinct option sets. Not even registered as a typer sub-app.

**Response**: Register typer sub-app with three stubbed subcommands matching design signatures.

---

#### 19. "Tool registry not implemented"

**Likelihood: 8** | **Impact: 8** | **Risk: 64**

Design specifies four Strands tools (py-repl, neo4j-mcp, neo4j-driver, file-ops). None exist as registered tools. No `kg_builder_cli/tools/` directory.

**Response**: Define Strands tool wrappers. Extract `_create_neo4j_driver()` and `_create_bedrock_client()` into factory functions.

---

#### 20. "Missing CLI options on `kg ingest`"

**Likelihood: 8** | **Impact: 5** | **Risk: 40**

Design specifies 12 options. Implementation has 6. Missing: `--schema`, `--infer-schema`, `--model`, `--merge-strategy`, `--batch-size`, `--extract-only`, `--keep-extractions`. The `--batch` and `--ontology` flags are accepted but never used.

**Response**: Add missing typer options. Wire `--batch`, `--ontology` into pipeline. Implement `--extract-only` as early return.

---

#### 21. "Config overrides only cover 3 of 12 CLI flags"

**Likelihood: 8** | **Impact: 5** | **Risk: 40**

Only `--chunk-size`, `--chunk-overlap`, `--concurrency` are wired into the overrides dict. `--model`, `--merge-strategy`, `--batch-size` are not injected into config.

**Response**: Extend overrides dict to map all CLI flags to their config paths.

---

### Section C - Ontology System (22-31)

#### 22. "OWL/RDF import pipeline absent"

**Likelihood: 8** | **Impact: 8** | **Risk: 64**

Section 5.3 specifies owlready2 mapping (owl:Class -> entity type, rdfs:subClassOf -> hierarchy, etc.). No `ontology/owl_import.py` exists. `owlready2` now in dependencies but never imported. `seed_from` config field accepts a path but nothing reads the file.

**Response**: Implement `ontology/owl_import.py` - load OWL via owlready2, walk classes/properties, return `OntologyState`.

---

#### 23. "Three-tier normalization pipeline absent"

**Likelihood: 8** | **Impact: 8** | **Risk: 64**

No Tier 1 programmatic parser, no Tier 2 LLM repair, no Tier 3 full LLM interpretation. No format detection dispatcher. `NormDiagnostic` model defined but never populated. A user setting `seed_from: "domain.md"` gets silent no-op.

**Response**: Implement `ontology/normalize.py`. Start with Tier 3 (most general), add Tier 1 (YAML/JSON parse) and Tier 2 (LLM repair).

---

#### 24. "Ontology buffer is frozen snapshot, not working buffer"

**Likelihood: 8** | **Impact: 8** | **Risk: 64**

`OntologyState` is `frozen=True` Pydantic model with no mutation methods. No `OntologyBuffer` class, no `accumulate()`, no `refine()`, no `flush()`. The `ingest_document()` function accepts `OntologyState` and passes it unchanged - zero feedback from extraction.

**Response**: Create `ontology/buffer.py` with mutable `OntologyBuffer` class. Frozen `OntologyState` becomes flush output.

---

#### 25. "TypeSignal never emitted or consumed"

**Likelihood: 8** | **Impact: 5** | **Risk: 40**

Defined in `types/ontology.py` with `type_name`, `frequency`, `source_chunk`, `is_relationship`. Never instantiated anywhere. The schema signal extraction pass (lightweight pre-scan) does not exist.

**Response**: Implement schema signal extraction as separate function. Return `TypeSignal` list for buffer coverage.

---

#### 26. "Refinement triggers configured but never fire"

**Likelihood: 8** | **Impact: 5** | **Risk: 40**

`refine_every_n_docs=5` and `min_frequency_to_confirm=2` are never read. No multi-document orchestration loop counts documents, checks thresholds, or invokes refinement. The feedback loop is unimplemented.

**Response**: Multi-document orchestration must maintain document counter, invoke `buffer.accumulate()`, check triggers, call `buffer.refine()`.

---

#### 27. "TypeDef missing half the design's fields"

**Likelihood: 5** | **Impact: 5** | **Risk: 25**

Design specifies `aliases`, `extraction_strategy`, `extraction_patterns`, `frequency`, `source`, `confidence`, and typed `PropertyDef` with validation rules. Implementation has only `name`, `description`, `properties` (untyped dict), `parent`.

**Response**: Extend `TypeDef` with missing fields. Define `PropertyDef` model.

---

#### 28. "Variant detection has no detection logic"

**Likelihood: 5** | **Impact: 5** | **Risk: 25**

`OntologyState.variants` is an empty dict. No LLM call to detect type variants. `TypeDef` has no `aliases` field. Aliases from YAML seed would be silently dropped.

**Response**: Add `aliases` to `TypeDef`. Implement variant detection in buffer accumulation with fuzzy matching + LLM confirmation.

---

#### 29. "No DAG validation anywhere"

**Likelihood: 5** | **Impact: 5** | **Risk: 25**

Design specifies cycle detection via `graphlib.TopologicalSorter` at three points. No hierarchy validation exists. `TypeDef.parent` can form cycles silently.

**Response**: Add `validate_dag()` function using `graphlib.TopologicalSorter`.

---

#### 30. "Coverage computation measures the wrong thing"

**Likelihood: 5** | **Impact: 5** | **Risk: 25**

Design defines coverage as fraction of extracted types matching buffer entries. `validation.py` computes fraction of types with relationships - a different graph quality metric. `OntologyState.coverage` is always 0.0. `coverage_threshold` config never read.

**Response**: Implement per-document coverage in buffer. Rename post-load metric to avoid confusion.

---

#### 31. "Constrained prompt ignores relationship types and intent scope"

**Likelihood: 5** | **Impact: 5** | **Risk: 25**

`_CONSTRAINED_PROMPT` only constrains entity types. `OntologyState.relationship_types` completely ignored. No source/target constraints reach the LLM. Intent only reaches extraction, not normalization or refinement (design specifies all three).

**Response**: Extend constrained prompt with relationship types and source/target constraints.

---

### Section D - Extraction Pipeline (32-39)

#### 32. "XLSX, CSV, HTML parsers missing"

**Likelihood: 8** | **Impact: 5** | **Risk: 40**

Design lists six format adapters. Only PDF, TXT, MD, DOCX implemented. XLSX (`openpyxl`), CSV (built-in), HTML (`beautifulsoup4`) absent. Pointing tool at directory with `.xlsx` raises `ValueError`.

**Response**: Implement three missing adapters. Add `openpyxl` and `beautifulsoup4` to dependencies.

---

#### 33. "Image description enrichment not implemented"

**Likelihood: 5** | **Impact: 8** | **Risk: 40**

Config has `describe_images: bool` and `vision_model: Optional[str]` but nothing reads them. PDF parser calls `pymupdf4llm.to_markdown()` without `write_images=True`. Charts and diagrams silently dropped.

**Response**: Add `_enrich_images()` function. Pass `write_images=True`, send images to vision model, splice descriptions.

---

#### 34. "Extraction modes not dispatched"

**Likelihood: 8** | **Impact: 8** | **Risk: 64**

Default is `hybrid` but pipeline always runs entity-relationship only. No atomic facts extraction, no `FactNode` creation, no dispatch logic. Users with default config believe they get hybrid but get entity-relationship only.

**Response**: Implement three-mode dispatch or change default to `"entity_relationship"` and raise `NotImplementedError` for others.

---

#### 35. "Raw JSON parsing instead of Instructor + litellm"

**Likelihood: 8** | **Impact: 8** | **Risk: 64**

Design specifies Pydantic response models with Instructor for structured output + automatic retry. Implementation parses raw JSON with three fallback strategies, manually constructs objects from unvalidated dicts. No schema enforcement, no retry on validation failure. Additionally, raw boto3 is used instead of litellm for multi-provider support.

**Response**: Wrap LLM calls with `instructor` + `litellm`. Create Pydantic response models. Eliminates JSON fallback hack and enables all three providers.

---

#### 36. "Semantic chunking not implemented"

**Likelihood: 5** | **Impact: 5** | **Risk: 25**

Config declares `chunking_strategy: Literal["token", "semantic"]` but only token chunking exists. Setting `semantic` silently does nothing. `chonkie` now in dependencies but unused.

**Response**: Implement semantic chunking with `chonkie` or raise `NotImplementedError`.

---

#### 37. "Rolling context window not implemented"

**Likelihood: 5** | **Impact: 5** | **Risk: 25**

Config has `rolling_context_window: int = 0` but chunks are submitted concurrently via ThreadPoolExecutor - no mechanism for sequential context passing. Later chunks that reference earlier entities get no context.

**Response**: When `rolling_context_window > 0`, switch to sequential extraction and prepend prior results.

---

#### 38. "Parent-child chunk hierarchy not implemented"

**Likelihood: 3** | **Impact: 5** | **Risk: 15**

Design describes `parent_child_chunking` with `HAS_CHILD` relationships. Config model has no such fields. No child chunk creation.

**Response**: Add config fields. Implement as post-processing in `chunk_text()`.

---

#### 39. "Cross-document dedup theoretical only"

**Likelihood: 5** | **Impact: 5** | **Risk: 25**

`dedup.py` handles intra-document by `(type, id)`. Cross-document relies on Neo4j MERGE at load time. But `ingest_document()` is called per-file producing independent `ExtractionResult` objects - no aggregation pass exists.

**Response**: Ensure loader uses `MERGE ON (type, id)`. Add aggregation dedup pass for multi-document ingestion.

---

### Section E - Graph Structure and Loading (40-49)

#### 40. "Missing Page/Section/Subsection node types"

**Likelihood: 8** | **Impact: 5** | **Risk: 40**

Design specifies `Page`, `Section`, `Subsection` nodes with `PART_OF`, `NEXT_PAGE` relationships. Loader creates `Chunk` directly linked to `Document` via `HAS_CHUNK`, bypassing page layer. Page-level reconstruction impossible.

**Response**: Add `Page` model. Wire `Document <- PART_OF - Page <- PART_OF - Chunk` chain.

---

#### 41. "Missing OntologyType and SchemaVersion nodes"

**Likelihood: 8** | **Impact: 5** | **Risk: 40**

Design specifies `(:Entity)-[:INSTANCE_OF]->(:OntologyType)` and `(:Entity)-[:CREATED_UNDER]->(:SchemaVersion)`. Loader creates zero `OntologyType` nodes, zero `INSTANCE_OF` edges. Without these, OWL reasoning has no substrate.

**Response**: Materialize buffer confirmed types as `OntologyType` nodes. Create `INSTANCE_OF` edges. Create `SchemaVersion` per load run.

---

#### 42. "Vector index not created"

**Likelihood: 8** | **Impact: 8** | **Risk: 64**

`indexes.py` creates two structural indexes only. Design specifies vector index on `Entity.embedding` (cosine, 1536d). `Entity` model has no `embedding` field. Semantic similarity search, entity resolution, and vector-powered query routing all non-functional.

**Response**: Add `embedding: Optional[list[float]]` to `Entity`. Add `CREATE VECTOR INDEX` statement. Add embedding generation step.

---

#### 43. "Fulltext index not created"

**Likelihood: 8** | **Impact: 5** | **Risk: 40**

`entity_name_idx` is a B-tree index (exact/prefix only). Design specifies fulltext (Lucene-backed) index for fuzzy matching and tokenized search. Query pipeline's fulltext lookup depends on this.

**Response**: Add `CREATE FULLTEXT INDEX` statement to `_INDEXES`.

---

#### 44. "Entity model lacks embedding field"

**Likelihood: 8** | **Impact: 8** | **Risk: 64**

`Entity` has no `embedding` field. No embedding generation step in extraction. Even if vector index existed, nothing to index. Upstream dependency for concerns 42, 10 (tier 3 resolution).

**Response**: Add `embedding` field. Add embedding generation step (call embedding model on name + description).

---

#### 45. "FactNode loading absent"

**Likelihood: 8** | **Impact: 5** | **Risk: 40**

`ExtractionResult.facts` field exists but loader has no `_create_fact_nodes()`. Facts silently dropped. For `graph_reader`/`hybrid` modes, the most valuable output never reaches the graph.

**Response**: Add `_create_fact_nodes` to loader. MERGE with `id`, `text`, `embedding`. Create `HAS_FACT` from chunks.

---

#### 46. "INSTANCE_OF and CREATED_UNDER relationships not created"

**Likelihood: 5** | **Impact: 5** | **Risk: 25**

Entities get dynamic type labels (via APOC) but no explicit `INSTANCE_OF` edges to `OntologyType` nodes. Ontology traversal queries require label-based queries rather than relationship traversal.

**Response**: Create `INSTANCE_OF` edges after entity and `OntologyType` node creation.

---

#### 47. "HAS_CHUNK direction and naming inverted vs design"

**Likelihood: 3** | **Impact: 3** | **Risk: 9**

Design uses `(:Chunk)-[:PART_OF]->(:Document)`. Implementation uses `(:Document)-[:HAS_CHUNK]->(:Chunk)`. Different relationship type AND direction. Query code written against design schema fails.

**Response**: Align implementation with design or update design.

---

#### 48. "Relationship MERGE without APOC uses generic RELATES_TO"

**Likelihood: 5** | **Impact: 5** | **Risk: 25**

Without APOC, fallback uses `MERGE (a)-[r:RELATES_TO {type: row.type}]->(b)`. Queries for typed relationships (`MATCH ()-[:WORKS_AT]->()`) return nothing.

**Response**: Use string-formatted Cypher for relationship types: `MERGE (a)-[r:\`{safe_type}\`]->(b)`.

---

#### 49. "Batch Cypher uses auto-commit transactions"

**Likelihood: 3** | **Impact: 5** | **Risk: 15**

`session.run()` creates auto-commit per batch. If entity creation succeeds but relationship creation fails, graph is inconsistent. No rollback across multi-step loading.

**Response**: Wrap load sequence in explicit transaction or document MERGE idempotency as recovery mechanism.

---

### Section F - Cross-Cutting Concerns (50-54)

#### 50. "Zero real tests exist"

**Likelihood: 13** | **Impact: 8** | **Risk: 104**

`tests/` contains one copier template placeholder. Zero tests for config, chunking, dedup, prompts, extraction, loading. No `conftest.py`, no fixtures, no test documents.

**Response**: Start with highest-value unit tests: config loader, `deduplicate()`, `chunk_text()`, `build_extraction_prompt()`, `_parse_json_response()`.

---

#### 51. "Agent memory system absent"

**Likelihood: 8** | **Impact: 5** | **Risk: 40**

No `kg_builder_cli/memory/` module. `MemoryConfig` defined but unconsumed. `RunReport` model exists but never instantiated. Pipeline recovery (resume from checkpoint) depends on memory that does not exist.

**Response**: Create `memory/store.py` with YAML-backed persistence. Wire into ingest for per-run stats.

---

#### 52. "No retry or backoff on LLM failures"

**Likelihood: 8** | **Impact: 8** | **Risk: 64**

`extract_chunk()` has bare `except Exception` returning empty lists. No exponential backoff, no rate-limit detection (HTTP 429), no fallback model. A single transient timeout silently drops an entire chunk.

**Response**: Add `tenacity` retry with exponential backoff. Or use Instructor's built-in retry. Add `fallback_model` to `LLMConfig`.

---

#### 53. "Neo4J password plaintext risk"

**Likelihood: 5** | **Impact: 8** | **Risk: 40**

`Neo4jConfig.password` is plain `str`. No `SecretStr` validation. Password could be serialized into `RunReport.config_snapshot`. User writing `password: mysecret` in config.yml gets no warning.

**Response**: Use Pydantic `SecretStr`. Exclude password from serialization. Warn when value doesn't look like `\${VAR}` interpolation.

---

#### 54. "Observability limited to logger.info"

**Likelihood: 5** | **Impact: 3** | **Risk: 15**

No structured event emission. `PipelineStats` and `PipelineEvent` models exist but nothing populates them. Token usage discarded from Bedrock response. No timing instrumentation beyond `LoadResult.duration_ms`.

**Response**: Add lightweight `PipelineTracker` class. Extract token usage from Bedrock response. Creates event stream for TUI and run reports.

---

## Scorecard

| # | Concern | Risk | Status | Residual |
|---|---------|------|--------|----------|
| 1 | Loader skips post-load steps | 40 | FIXED | 0.0 |
| 2 | boto3 session per chunk | 40 | FIXED | 0.0 |
| 3 | Provider config ignored | 25 | OPEN | 25.0 |
| 4 | Chunks stored without text | 25 | OPEN | 25.0 |
| 5 | Temperature config ignored | 9 | FIXED | 0.0 |
| 6 | Parser if/elif chain | 9 | OPEN | 9.0 |
| 7 | CLI f-string logging | 4 | FIXED | 0.0 |
| 8 | Facts field always empty | 15 | OPEN | 15.0 |
| 9 | No ontology buffer | 64 | OPEN | 64.0 |
| 10 | No entity resolution | 40 | OPEN | 40.0 |
| 11 | Validation double driver | 6 | FIXED | 0.0 |
| 12 | nodes_created == nodes_merged | 4 | OPEN | 4.0 |
| 13 | Missing NEXT_CHUNK chain | 9 | OPEN | 9.0 |
| 14 | Hardcoded kolomolo profile | 9 | FIXED | 0.0 |
| 15 | merge_strategy not implemented | 9 | OPEN | 9.0 |
| 16 | No agent layer | 169 | OPEN | 169.0 |
| 17 | Missing kg query command | 104 | OPEN | 104.0 |
| 18 | Missing kg update subcommands | 104 | OPEN | 104.0 |
| 19 | Tool registry not implemented | 64 | OPEN | 64.0 |
| 20 | Missing CLI options on kg ingest | 40 | OPEN | 40.0 |
| 21 | Config overrides incomplete | 40 | OPEN | 40.0 |
| 22 | OWL/RDF import absent | 64 | OPEN | 64.0 |
| 23 | Three-tier normalization absent | 64 | OPEN | 64.0 |
| 24 | Ontology buffer is frozen snapshot | 64 | OPEN | 64.0 |
| 25 | TypeSignal never emitted | 40 | OPEN | 40.0 |
| 26 | Refinement triggers never fire | 40 | OPEN | 40.0 |
| 27 | TypeDef missing fields | 25 | OPEN | 25.0 |
| 28 | Variant detection no logic | 25 | OPEN | 25.0 |
| 29 | No DAG validation | 25 | OPEN | 25.0 |
| 30 | Coverage wrong metric | 25 | OPEN | 25.0 |
| 31 | Prompt ignores relationship types | 25 | OPEN | 25.0 |
| 32 | XLSX/CSV/HTML parsers missing | 40 | OPEN | 40.0 |
| 33 | Image description enrichment | 40 | OPEN | 40.0 |
| 34 | Extraction modes not dispatched | 64 | OPEN | 64.0 |
| 35 | Raw JSON instead of Instructor+litellm | 64 | OPEN | 64.0 |
| 36 | Semantic chunking unimplemented | 25 | OPEN | 25.0 |
| 37 | Rolling context window | 25 | OPEN | 25.0 |
| 38 | Parent-child chunk hierarchy | 15 | OPEN | 15.0 |
| 39 | Cross-document dedup theoretical | 25 | OPEN | 25.0 |
| 40 | Missing Page/Section nodes | 40 | OPEN | 40.0 |
| 41 | Missing OntologyType/SchemaVersion | 40 | OPEN | 40.0 |
| 42 | Vector index not created | 64 | OPEN | 64.0 |
| 43 | Fulltext index not created | 40 | OPEN | 40.0 |
| 44 | Entity model lacks embedding | 64 | OPEN | 64.0 |
| 45 | FactNode loading absent | 40 | OPEN | 40.0 |
| 46 | INSTANCE_OF relationships missing | 25 | OPEN | 25.0 |
| 47 | HAS_CHUNK direction inverted | 9 | OPEN | 9.0 |
| 48 | Relationship MERGE without APOC | 25 | OPEN | 25.0 |
| 49 | Auto-commit transactions | 15 | OPEN | 15.0 |
| 50 | Zero real tests | 104 | OPEN | 104.0 |
| 51 | Agent memory absent | 40 | OPEN | 40.0 |
| 52 | No retry/backoff on LLM | 64 | OPEN | 64.0 |
| 53 | Neo4J password plaintext | 40 | OPEN | 40.0 |
| 54 | Observability logger.info only | 15 | OPEN | 15.0 |

**Total risk**: 2,107 | **Residual**: 2,107 - (40+40+9+4+6+9) = **1,999**
**Fixed**: 6 of 54 concerns (11%)
**Open residual**: 1,999

---

## Top 10 Gaps by Risk

1. **#16 - No agent layer** (169) - architectural core unimplemented
2. **#17 - Missing kg query** (104) - primary read path absent
3. **#18 - Missing kg update** (104) - graph evolution absent
4. **#50 - Zero tests** (104) - no quality assurance
5. **#9 - No ontology buffer** (64) - adaptive extraction absent
6. **#22 - OWL import absent** (64) - ontology ingestion absent
7. **#23 - Normalization absent** (64) - seed processing absent
8. **#24 - Buffer frozen** (64) - buffer cannot evolve
9. **#34 - Extraction modes** (64) - default config promises what code cannot deliver
10. **#35 - No Instructor+litellm** (64) - raw JSON parsing, single provider

---

## Priority Correction Groups

### Group A - Quick Wins (done)

Six concerns already fixed: #1, #2, #5, #7, #11, #14.

### Group B - Foundation Layer (address first)

These unblock everything else. Without them, higher-level features have no substrate.

1. **Instructor + litellm integration** (#35, #3, #52): Replace raw boto3 + JSON parsing with `instructor` + `litellm`. Enables multi-provider, structured output, automatic retry. Unblocks extraction quality.
2. **Ontology buffer minimum** (#24, #25, #26): Mutable `OntologyBuffer` with `accumulate()`, `coverage()`, `flush()`. Unblocks adaptive extraction.
3. **Entity embedding generation** (#44, #42): Add embedding field, generate embeddings, create vector index. Unblocks similarity search and resolution tier 3.
4. **Tests** (#50): Config loader, chunking, dedup, prompt construction. Prevents regression during all other work.

### Group C - Essential Features (address next)

5. **Entity resolution tier 2** (#10): Levenshtein within type blocks using `python-Levenshtein`
6. **Store chunk content** (#4, #13): Write text/page/token on chunk nodes, create NEXT_CHUNK chain
7. **Parser registry + missing formats** (#6, #32): Dict-based adapter pattern, add XLSX/CSV/HTML
8. **Graph structure alignment** (#40, #41, #45, #46, #47): Page nodes, OntologyType nodes, FactNode loading, INSTANCE_OF edges, direction fix
9. **Fulltext index** (#43): One-line Cypher, enables query pipeline

### Group D - CLI and Agent Layer

10. **CLI completeness** (#20, #21): Add missing ingest options, wire overrides
11. **Query command** (#17): Implement `--status` (node counts) first, then Text2Cypher
12. **Update command stubs** (#18): Register typer sub-app with three subcommands
13. **Agent orchestration** (#16, #19): Strands agent wrapping, tool registry

### Group E - Advanced Features (address last)

14. **Ontology full pipeline** (#22, #23, #27, #28, #29, #30, #31): OWL import, normalization tiers, TypeDef fields, variant detection, DAG validation, coverage, relationship constraints
15. **Extraction modes** (#34, #8, #33, #36, #37): Dispatch hybrid/graph_reader, atomic facts, image enrichment, semantic chunking, rolling context
16. **Memory and observability** (#51, #54): YAML-backed memory store, PipelineTracker
17. **Security and resilience** (#53, #48, #49): SecretStr, typed relationships, explicit transactions

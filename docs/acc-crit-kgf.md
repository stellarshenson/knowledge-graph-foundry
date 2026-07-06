# Acceptance Criteria - Knowledge Graph Foundry

Consolidated acceptance criteria for the KGF v2 rewrite: a CLI+TUI system that builds a Neo4j knowledge graph from structured and unstructured data and maintains it continuously, with purpose-driven construction, statistical curing, Bayesian resolution and drift detection.

## Contents

- [Foundation](#foundation)
- [LLM Engines](#llm-engines)
- [Ingestion](#ingestion)
- [Schema Seeding](#schema-seeding)
- [Extraction](#extraction)
- [Entity Resolution](#entity-resolution)
- [Ontology Lifecycle](#ontology-lifecycle)
- [Graph Loading](#graph-loading)
- [GraphRAG Optimization](#graphrag-optimization)
- [Drift Detection](#drift-detection)
- [Temporal and Longevity](#temporal-and-longevity)
- [CLI](#cli)
- [TUI](#tui)
- [End-to-End CPAP](#end-to-end-cpap)

## Foundation

- [x] **Settings** - pydantic settings load from config.yml + .env + env vars with that precedence; invalid values fail fast with a clear message
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Neo4j session** - driver factory reads NEO4J_URI/USER/PASSWORD; connection verified with RETURN 1 on first use
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Events** - named blinker signals for document, extraction, resolution, curing, drift and load stages; optional JSONL event log capturing every signal with payload
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **FSM** - six states EMPTY/INITIALIZING/CURING/STABLE/RECURING/FAILED with legal transitions only; state persisted to and restored from the graph metanode
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Edge: metanode absent** - fresh graph resolves to EMPTY and creates the metanode on first ingest
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Edge: config file missing** - defaults apply, warning logged, run proceeds
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Run lease** - graph-resident (:KGFLock) lease claimed atomically before ingest, heartbeated after every document, released on completion or error; TTL stored on the lock governs staleness
  - log: 2026-07-06 criterion added and implemented (v0.1.2)
- [x] **Edge: concurrent ingest** - second ingester fails fast naming the holder, its run id and heartbeat age
  - log: 2026-07-06 criterion added and implemented (v0.1.2)
- [x] **Edge: crashed run** - stale lease (no heartbeat within TTL) is reclaimed by the next ingester; the original run detects the takeover on its next heartbeat and aborts without mutating state
  - log: 2026-07-06 criterion added and implemented (v0.1.2); verified live against neo4j

## LLM Engines

- [x] **Engine protocol** - single interface `complete(messages, response_model)` returning validated Pydantic objects; engine selected by config `llm.engine`
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Frontier engine** - litellm + instructor against Bedrock (default, AWS_PROFILE) and Anthropic/OpenAI keys when configured
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Claude CLI engine** - subprocess `claude -p` with JSON schema instruction; output parsed and validated into the same response models
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Local GPU engine** - OpenAI-compatible endpoint (vLLM) via litellm base_url; model and URL from config
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Retries** - transient failures retry with backoff up to max_retries; validation failures re-prompt once with the error appended
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Edge: malformed JSON from engine** - one repair re-prompt, then raise EngineError carrying raw output
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Edge: engine unavailable** - clear startup error naming the engine and remedy, not a mid-run stack trace
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)

## Ingestion

- [x] **Unstructured readers** - pdf (pymupdf4llm), docx (python-docx), html (beautifulsoup4), md/txt (direct) all produce markdown-ish text with source metadata
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Structured readers** - parquet, csv, tsv, excel, json/jsonl load to records with column names preserved
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Dispatch** - reader chosen by extension; unknown extension raises UnsupportedFormat listing supported ones
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Chunking** - tiktoken token counts, configurable size/overlap, sentence-boundary snapping, deterministic SHA1 chunk ids stable across runs
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Zip and directory input** - a directory or zip expands to its supported files, processed in deterministic (sorted) order
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Edge: empty document** - skipped with warning event, run continues
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Edge: corrupt/password pdf** - error event with file name, file skipped, run continues
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Edge: encrypted or zero-row structured file** - error/warning event, skipped, run continues
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)

## Schema Seeding

- [x] **Purpose** - free-text purpose stored on the metanode and injected into extraction, seed normalization and type clustering prompts
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Freeform seed** - natural-language schema description normalized by LLM into typed ontology (types, properties, relationship types)
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **YAML/JSON seed** - structured seed file parsed directly without LLM
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **OWL seed** - owlready2 parses .owl/.rdf; classes to types, object properties to relationship types, depth-limited
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Seedless** - no seed provided: ontology discovered from data guided by purpose alone
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [ ] **Edge: contradictory seed and purpose** - purpose wins for prioritization, seed types retained; decision logged as event
  - log: 2026-07-06 criterion added
- [x] **Edge: unparseable OWL** - clear error naming the file and parser message, no partial seed applied
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)

## Extraction

- [x] **Entity extraction** - per chunk, LLM returns entities (name, types, description, properties) and relationships (source, target, type, description) validated by Pydantic
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Purpose injection** - purpose and current ontology state included in every extraction prompt
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Structured mapping** - first batch of a new structured source infers a column-to-entity mapping via LLM once; mapping cached and reapplied deterministically to remaining rows
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Embeddings** - Bedrock Titan v2 primary, sentence-transformers MiniLM fallback on first-call failure, single-provider-per-run lock
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Type normalization** - deterministic PascalCase normalization applied to every extracted type before buffering
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Concurrency** - chunk extraction runs with configurable parallelism; failures of single chunks do not abort the document
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Edge: chunk with no entities** - empty result accepted, no retry storm
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Edge: self-referencing or dangling relationship** - dropped with warning event
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)

## Entity Resolution

- [x] **Identity without type** - entity identity keys on normalized name + embedding, never on type; types accumulate as labels
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Bayesian posterior** - odds-form P(same|evidence): name-identity prior x LR_description (Jaccard, floored) x LR_embedding (cosine) x LR_cooccurrence; three zones merge/defer/block with configurable thresholds
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Within-type synonyms** - embedding clustering within type blocks catches non-Levenshtein synonyms (circuit tubing vs connecting tubing)
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Multi-label entities** - dual-role entities carry multiple type labels; never force-merged into one type nor duplicated per type
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Union-find merging** - transitive merges resolve through union-find; merged entity keeps union of properties, longest description, all source provenance
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [ ] **Calibration** - (posterior, outcome) observations collected; isotonic curve fitted and persisted to metanode when observations >= 50; applied on later runs
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 calibrator ported and tested; observation collection not yet wired
- [ ] **Edge: identical names, incompatible evidence** - blocked pair stays separate and emits a decision event with LR values
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 superseded by the v2 identity model - identical names merge structurally as multi-label by design; revisit if homonym splits emerge
- [x] **Edge: embedding unavailable** - LR_embedding neutral (1.0), resolution still functions
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)

## Ontology Lifecycle

- [x] **Fluid buffer** - entities/relationships accumulate in memory during fluid phase; buffer state compressed into graph metanode after every document for resumability
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Per-encounter evolution** - after every document the buffer self-evolves: type frequencies count encounters, emerging types confirm/expire by encounter thresholds
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Stability metrics** - Shannon entropy delta, JSD, Chao1 coverage, Heaps beta computed after every document, decision-free, emitted as events
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Curing decision** - composite criterion (JSD < 0.02 AND Chao1 > 0.95 AND entropy delta < 0.01, all configurable) checked in order converged -> plateau -> cured; force-cure available
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Consolidation** - at cure: one LLM type-clustering pass (purpose-aware), buffer resolved and flushed to Neo4j, ontology written to metanode; exactly one owner per decision, no post-hoc enforcement pass
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Stable-phase resolution** - post-cure documents resolve against the live graph (candidate lookup by name index + vector similarity)
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Edge: resume mid-fluid** - restart restores buffer from metanode cache and continues at the correct document
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Edge: cure criterion never met** - max_fluid_documents forces consolidation with warning event
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)

## Graph Loading

- [x] **Batched upsert** - entities and relationships MERGE in configurable batches; native relationship types via APOC, multi-label nodes via apoc.create.addLabels
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Indexes** - name index, type label indexes and vector index created idempotently at first load
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Provenance** - every entity and relationship carries source document ids and chunk ids
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Metanode** - control node persists FSM state, ontology, purpose, calibration, stability history and fluid cache; readable in one query
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Edge: reload same document** - idempotent, no duplicate nodes or relationships, provenance deduplicated
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [ ] **Edge: neo4j down mid-load** - batch retry with backoff, then FAILED state with resumable checkpoint
  - log: 2026-07-06 criterion added

## GraphRAG Optimization

- [x] **Communities** - GDS Leiden runs over the entity graph; community id written back to nodes; modularity reported
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Community summaries** - LLM summary per community above min size, stored on community nodes for global search
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Vector index** - entity embeddings in a Neo4j vector index; top-k similarity query returns relevant entities
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Quality scorecard** - duplicate-name density, orphan rate, relationship type entropy, modularity, community size distribution computed on demand and persisted per run in reports/
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Edge: graph smaller than GDS minimum** - optimization skips with informative message instead of failing
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)

## Drift Detection

- [x] **Remap rate** - post-cure per-document remap rate tracked; rate > threshold for window consecutive docs raises drift warning event
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Distribution divergence** - post-cure JSD between cured type distribution and rolling window monitored alongside remap rate
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Decision engine** - drift evidence classified into none/warn/recure/rebuild with the evidence attached; recure transitions FSM to RECURING; rebuild is only ever a recommendation
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Edge: single outlier document** - no drift signal from one bad document (window smooths)
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Edge: drift during RECURING** - additional drift signals coalesce, no nested recure
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Fact-drift alarm** - contradiction-rate per window (edges invalidated by supersession) raises a fact_drift verdict distinct from schema drift (R8)
  - log: 2026-07-06 criterion added and implemented (v0.1.2)

## Temporal and Longevity

SOTA-driven redesign for months-long operation (R1): the graph is bi-temporal and non-lossy, so it answers current-versus-historical and keeps an evolution record.

- [x] **Bitemporal edges** - every relationship carries created_at/expired_at (transaction time) and valid_from/valid_to (valid time); loading stamps them, nothing is deleted (R1)
  - log: 2026-07-06 criterion added and implemented (v0.1.2)
- [x] **Contradiction reconciliation** - for functional relationship types, a superseding fact sets the prior edge's valid_to to the new valid_from (invalidate, not delete) (R1)
  - log: 2026-07-06 criterion added and implemented (v0.1.2); live probe HAS_CEO Alice -> Bob
- [x] **Time-aware read** - current_relationships returns valid_to IS NULL edges; relationship_history returns the full ordered timeline; local retrieval context filters to currently-valid (R1)
  - log: 2026-07-06 criterion added and implemented (v0.1.2)
- [x] **Entity versioning** - a content change (longer description or new labels) snapshots the prior entity state to a KGFEntityVersion node via HAD_VERSION; idempotent reloads create no version (R1)
  - log: 2026-07-06 criterion added and implemented (v0.1.2)
- [x] **PPR retrieval** - Personalized PageRank seeded from the vector top-k reaches beyond one hop for multi-hop questions; global/thematic questions route to community summaries (R2/R6)
  - log: 2026-07-06 criterion added and implemented (v0.1.2); live probe reaches a 2-3 hop node
- [x] **Gleaning + split extraction** - a bounded gleaning re-prompt plus separate entity and relation passes raise extraction recall (R3)
  - log: 2026-07-06 criterion added and implemented (v0.1.2)
- [x] **ANN blocking + defer judge** - FAISS top-k blocking above a per-type size keeps resolution sub-quadratic; the 0.4-0.6 defer band routes to an LLM judge when enabled (R4)
  - log: 2026-07-06 criterion added and implemented (v0.1.2)
- [x] **Re-runnable type consolidation** - embed -> block -> LLM-verify replaces the one-shot flat pass; should_recure reopens consolidation on a post-cure type burst (R5)
  - log: 2026-07-06 criterion added and implemented (v0.1.2)
- [x] **Curing and calibration hardening** - Chao1 minimum-sample floor blocks premature curing; TemperatureScaler with a held-out label floor replaces isotonic-on-tiny-sets (R7)
  - log: 2026-07-06 criterion added and implemented (v0.1.2)
- [x] **Transitivity split guard** - a correlation-clustering split pass after union-find breaks snowballed over-merges (R8)
  - log: 2026-07-06 criterion added and implemented (v0.1.2)

## CLI

- [x] **kgf init** - creates project config, verifies Neo4j, stores purpose and optional seed
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **kgf ingest PATH** - ingests file/directory/zip through the full pipeline with progress output and final summary
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **kgf status** - shows FSM state, document/entity/relationship counts, ontology types, stability metrics, drift state
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **kgf optimize** - runs GraphRAG optimization and prints the scorecard
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **kgf query "text"** - answers a question over the graph (vector + graph context to LLM), printing answer and supporting entities
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **kgf wipe** - clears graph and metanode after explicit --yes confirmation
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Exit codes** - 0 success, non-zero on failure with human-readable error on stderr
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Edge: ingest before init** - clear error instructing to run kgf init
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)

## TUI

- [x] **Dashboard** - textual app shows FSM state, live ingestion progress (documents/chunks), entity/relationship counters, current ontology types
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Stability panel** - live JSD/Chao1/entropy-delta sparkline or table during fluid phase, cure indicator
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Drift panel** - post-cure drift signals and decision engine verdict
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Event feed** - scrolling feed of pipeline events (document done, merges, warnings)
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Ingest from TUI** - user can start an ingest of a path from within the TUI and watch it run
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Edge: terminal resize** - layout reflows, no crash
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)
- [x] **Edge: neo4j unreachable at TUI start** - dashboard renders with connection error banner instead of crashing
  - log: 2026-07-06 criterion added
  - log: 2026-07-06 implemented (v0.1.2)

## End-to-End CPAP

- [ ] **Corpus ingest** - all CPAP pdfs ingest end-to-end without manual intervention; purpose "compare CPAP machines"
  - log: 2026-07-06 criterion added
- [ ] **Curing** - ontology cures within max_fluid_documents on the corpus; type count lands in a sane band (8-16)
  - log: 2026-07-06 criterion added
- [ ] **Comparison answerable** - kgf query answers a machine-comparison question (e.g. AirSense 11 vs DreamStation pressure range) with graph-grounded evidence
  - log: 2026-07-06 criterion added
- [ ] **Quality scorecard** - duplicate-name density and orphan rate below configured thresholds on the final graph; scorecard saved to reports/
  - log: 2026-07-06 criterion added
- [ ] **Tests green** - full pytest suite passes without network or live Neo4j (cassettes/mocks); integration marker for live tests
  - log: 2026-07-06 criterion added
- [ ] **Checkpoints** - each completed workstream committed as a separate git checkpoint
  - log: 2026-07-06 criterion added

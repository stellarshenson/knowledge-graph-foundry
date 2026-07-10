# Knowledge Graph Foundry - Design

Knowledge Graph Foundry (KGF) builds a Neo4j knowledge graph from structured and unstructured data and keeps maintaining it as schema evolves and data drifts. It differs from existing graph builders by being data-science driven: every lifecycle decision (when the schema has stabilized, when two entities merge, when the graph needs a rebuild) is made by a measurable statistical signal, not a heuristic. The target operating mode is continuous - weeks to months of ingestion against one living graph, serving a stated purpose.

This document is intentionally short. The v1 post-mortem showed that a 3,300-line spec produced half-unbuilt features, while every scoring improvement came from a hypothesis -> change -> measure loop. KGF v2 specs incrementally against working code; docs/acc-crit-kgf.md is the contract, this file is the map.

## Principles

- **Purpose drives construction** - the user states what the graph is for (free text); that intent is injected into extraction prompts, seed normalization and type clustering. In v1 this single idea moved deterministic quality 87% to 95% and stopped type proliferation cold
- **Statistics own every decision** - schema stability is declared by information-theoretic convergence (JSD < 0.02, Chao1 > 0.95, entropy delta < 0.01); merges are decided by a Bayesian posterior; drift by remap-rate and distribution divergence. Heuristics may feed evidence into these models, never bypass them
- **The graph is the single source of truth** - lifecycle state, ontology, calibration curves and the fluid cache persist in Neo4j itself (control metanode); any session can resume from the graph alone
- **Identity is not type** - entity identity derives from name + embedding; types are mutable multi-label attributes. Dual-role entities (a humidifier is Component and Accessory) are expected structure, not resolution failures. This abandons v1's dominant failure class at the root
- **Pure pipeline, thin shell** - extraction, resolution and curing are pure importable functions on Pydantic models; CLI, TUI and any agent layer are shells over the same pipeline

## Lifecycle

The foundry runs a six-state FSM persisted in the graph: EMPTY -> INITIALIZING -> CURING -> STABLE <-> RECURING, plus FAILED.

1. **Fluid phase** - documents are extracted against an evolving ontology buffer; entities and relationships accumulate in memory (and in a compressed graph-persisted cache); after every document the buffer self-evolves (per-encounter thresholds) and stability metrics update
2. **Curing** - when the composite convergence criterion holds, the type system is clustered and consolidated once, the buffer flushes to Neo4j, and the ontology cures
3. **Stable phase** - further documents extract against the cured ontology and resolve directly against the live graph; stability metrics keep streaming
4. **Drift and rebuild** - post-cure, per-document remap rate and type-distribution divergence are monitored; sustained drift signals either an incremental re-cure (RECURING) or, past a threshold, a recommended rebuild. The decision engine reports evidence; destructive rebuilds require explicit confirmation

## Architecture

```
src/knowledge_graph_foundry/
├── config.py            # paths (scaffold)
├── settings.py          # pydantic settings: neo4j, llm, extraction, curing, drift
├── engines/             # LLM engines: frontier API (litellm), claude -p subprocess, local GPU (OpenAI-compatible)
├── ingest/              # readers: structured (parquet/csv/tsv/excel/json), unstructured (pdf/docx/md/html/txt), chunking
├── ontology/            # seed parsing (freeform/YAML/OWL), ontology buffer, curing metrics + detector, type normalization
├── extraction/          # LLM entity/relationship extraction, prompts, embeddings (Bedrock + local fallback)
├── resolution/          # Bayesian multi-signal entity resolution, calibration, union-find
├── graph/               # Neo4j loader, control metanode, GDS communities, GraphRAG optimization, vector index
├── drift/               # post-cure drift detection, rebuild decision engine
├── events/              # blinker signal catalogue, JSONL event log
├── fsm/                 # lifecycle states and transitions
├── pipeline.py          # orchestrator: wire ingest -> extract -> resolve -> load per lifecycle phase
├── cli.py               # typer CLI: init, ingest, status, optimize, drift, query
└── tui/                 # textual dashboard: progress, graph stats, ontology state, drift signals
```

**LLM engines** - one `Engine` protocol with three implementations: `frontier` (litellm + instructor to Bedrock/Anthropic/OpenAI), `claude-cli` (subprocess `claude -p` with JSON output), `local-gpu` (OpenAI-compatible endpoint, e.g. vLLM). Structured output via instructor where available, JSON-schema prompting elsewhere. Engine choice is config; the pipeline never knows which engine runs.

**GraphRAG optimization** - after load (and on demand): GDS Leiden community detection with community membership written back to nodes, LLM community summaries for global search, vector index over entity embeddings for local search, and graph quality metrics (duplicate-name density, orphan rate, relationship type entropy, community modularity) reported as a scorecard.

**Data flow** - structured records map to entities via a declarative mapping (inferred by LLM once per source schema, then cached and reapplied deterministically); unstructured documents chunk (tiktoken, sentence-snapped, deterministic SHA1 ids) and extract per chunk.

## Development process

- Hybrid benchmark: deterministic checks (duplicate counts, type counts, orphan rate, answerability probes) plus LLM-judge scoring with wide judge context; scorecards versioned per run in reports/
- Every quality change is a hypothesis with a measured before/after; post-mortems land in docs/failure-hypothesis.md
- docs/acc-crit-kgf.md tracks acceptance criteria; docs/defects-kgf.md tracks defects
- Test corpus: CPAP datasheets and manuals (27 PDFs); purpose: "compare CPAP machines"

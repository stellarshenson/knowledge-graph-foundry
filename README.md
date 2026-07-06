# Knowledge Graph Foundry

Knowledge Graph Foundry (KGF) builds a Neo4j knowledge graph from structured and unstructured data and keeps maintaining it as the schema evolves and data drifts. It is data-science driven: schema stability is declared by information-theoretic convergence, entity merges by a Bayesian posterior, and rebuilds by statistical drift evidence - never by heuristics. The target operating mode is continuous: weeks to months of ingestion against one living graph, serving a stated purpose.

- **Purpose-driven construction** - a free-text purpose ("compare CPAP machines") guides extraction, seed normalization and type clustering
- **Fluid-to-cured lifecycle** - documents buffer in memory while the type system is fluid; curing fires when JSD < 0.02, Chao1 coverage > 0.95 and entropy delta < 0.01
- **Bayesian entity resolution** - continuous name-similarity prior times likelihood ratios for description, embedding and co-occurrence evidence; merge / defer / block zones; isotonic calibration
- **Identity decoupled from type** - entity identity derives from the normalized name; types are multi-label attributes, so dual-role entities are one node with several labels
- **Drift detection** - windowed remap-rate and distribution-divergence verdicts (warn / recure / rebuild) on every post-cure document
- **GraphRAG optimization** - GDS Leiden communities with LLM summaries, vector index retrieval, quality scorecards persisted per run
- **Three LLM engines** - frontier API (Bedrock / Anthropic / OpenAI via litellm), local `claude -p` subprocess, local GPU (any OpenAI-compatible endpoint such as vLLM)
- **Resumable by design** - lifecycle state, ontology, calibration and the fluid buffer persist in the graph control metanode; any session resumes from the graph alone

## Quick Start

```bash
make install                      # create .venv and install
docker compose up -d              # Neo4j 5 with APOC + GDS
# set NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD in .env

kgf init "compare CPAP machines"  # store purpose, verify Neo4j
kgf ingest data/raw/manuals/      # file, directory or zip
kgf status                        # lifecycle, counts, stability metrics
kgf optimize                      # communities, summaries, scorecard
kgf query "AirSense 11 vs DreamStation pressure range?"
kgf tui                           # live dashboard
```

Supported inputs: pdf, docx, html, md, txt (unstructured); parquet, csv, tsv, xlsx, json, jsonl (structured - a column mapping is inferred once per source by the LLM, then applied deterministically). Seed schemas: freeform text, YAML/JSON, OWL.

## Architecture

```
src/knowledge_graph_foundry/
├── settings.py       # pydantic settings: neo4j, llm, extraction, curing, drift
├── engines/          # frontier (litellm+instructor), claude-cli, local-gpu
├── ingest/           # format readers, tiktoken chunking with stable ids
├── ontology/         # seeds (freeform/YAML/OWL), fluid buffer, stability metrics, curing
├── extraction/       # purpose-injected extraction, embeddings (Bedrock + CPU fallback)
├── resolution/       # Bayesian posterior, union-find, isotonic calibration
├── graph/            # idempotent loaders, control metanode, GDS communities, scorecard
├── drift.py          # windowed drift verdicts: none / warn / recure / rebuild
├── pipeline.py       # Foundry orchestrator over the lifecycle FSM
├── cli.py            # kgf init/ingest/status/optimize/query/wipe/tui
└── tui/              # Textual dashboard: status, stability, drift, event feed
```

Design details in `docs/DESIGN.md`; acceptance criteria in `docs/acc-crit-kgf.md`; defects in `docs/defects.md`. Lessons distilled from the archived v1 (28 benchmark iterations) in `references/kgf-v1-lessons.md`.

## Development

- `make install` - create environment and install package
- `make test` - run the suite (no network or live Neo4j needed)
- `KGF_INTEGRATION=1 pytest tests/test_graph_integration.py` - live Neo4j integration tests
- `make lint` / `make format` - ruff check / fix

## Project Organization

```
├── data/raw          # immutable source data
├── data/interim      # intermediate transforms
├── data/processed    # final datasets
├── docs              # design, acceptance criteria, defects
├── logs              # run and event logs
├── notebooks         # analysis notebooks
├── references        # v1 lessons and reference material
├── reports           # quality scorecards per run
└── src/knowledge_graph_foundry
```

> **Note**: scaffolded with [copier-data-science](https://github.com/stellarshenson/copier-data-science)

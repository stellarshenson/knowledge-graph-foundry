# Knowledge Graph Foundry

Knowledge Graph Foundry (KGF) builds a Neo4j knowledge graph from documents and keeps maintaining it as the schema evolves and data drifts - a self-auditing graph engine, not a one-shot indexer. Every mechanism in it was measured into shape: schema stability is declared by information-theoretic convergence, entity merges by a calibrated Bayesian posterior, context escalation by a conformal certificate, and rebuilds by statistical drift evidence - never by heuristics.

- **Purpose-driven construction** - a free-text purpose guides extraction, seed normalization and type clustering
- **Fluid-to-cured lifecycle** - documents buffer while the type system is fluid; curing fires on JSD < 0.02, Chao1 coverage > 0.95, entropy delta < 0.01
- **Bayesian entity resolution** - name-similarity prior x likelihood ratios (description, embedding, co-occurrence); merge / defer / block zones; isotonic calibration
- **Identity decoupled from type** - identity derives from the normalized name; types are multi-label attributes, so dual-role entities are one node with several labels
- **Retrieval-first** - dense vector seeding into Personalized PageRank; the work shifts to ingest time so answers come from 1-2 hops
- **Calibrated context escalation** - a CRC-fitted gate on a free retrieval signal recovers full composed recall at ~1/4 of static context cost, with a distribution-free E[miss] <= 0.08 certificate
- **Question channel** - ~7.5 anticipated questions generated per chunk at ingest (doc2query-style), embedded and retrievable
- **Answer cache** - corpus-fingerprint-keyed; invalidates exactly when the graph changes
- **Self-auditing** - per-document coverage certificates, a gap ledger, drift verdicts (warn / recure / rebuild), and a six-metric structural panel (Forman-Ricci curvature is the most sensitive instrument measured)
- **Resumable by design** - lifecycle state, ontology, calibration and buffers persist in a graph control metanode; any session resumes from the graph alone; ingest survives process death and resumes idempotently

## Quick Start

```bash
make install                      # create .venv and install
docker compose up -d              # Neo4j 5 with APOC + GDS
# set NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD in .env

kgf init "compare products across vendor manuals"   # store purpose, verify Neo4j
kgf ingest data/raw/manuals/      # file, directory or zip
kgf status                        # lifecycle, counts, stability metrics
kgf optimize                      # communities, summaries, scorecard
kgf query "AirSense 11 vs DreamStation pressure range?"
kgf tui                           # live dashboard
```

Inputs: pdf, docx, html, md, txt (unstructured); parquet, csv, tsv, xlsx, json, jsonl (structured - column mapping inferred once per source, then applied deterministically). Seed schemas: freeform text, YAML/JSON, OWL. LLM engines: frontier API (Bedrock / Anthropic / OpenAI via litellm), local `claude -p`, or any OpenAI-compatible local endpoint (vLLM).

## Measured State

Current substrate: the 2WikiMultihopQA benchmark ladder (nested rungs of 50 / 200 / 1,000 / 6,118 documents). Numbers below are from the 1,000-document rung and the pinned retrieval harness - reproducible, not aspirational.

| Quantity | Value |
|---|---|
| Graph (1,000 docs) | 6,626 entities, 35,637 relationships, 7,534 question nodes (7.5/chunk) |
| Pure-seed retrieval recall @top_k=16 | 0.854 |
| Composed retrieval frontier | 0.958 (23/24 probes; span windows + proposition seeds, +27.8% context) |
| Gated context cost | ~1/4 of static rendering at full composed recall (conformal certificate E[miss] <= 0.08) |
| Extraction carrier recall (single LLM pass) | 76.8% mean, high run-to-run variance - the dominant known weakness |
| Coverage after guided repair loop | 62.7% -> ~85% (saturates; residual classes registered) |

## How KGF Compares

| Aspect | KGF | HippoRAG-2 | MS GraphRAG | LightRAG | TrustGraph | graphify |
|---|---|---|---|---|---|---|
| Primary goal | long-lived self-auditing KG + retrieval | continual memory for QA | global corpus sensemaking | lightweight dual-level graph RAG | enterprise agent context platform | any folder → navigable graph |
| Graph store | Neo4j, persistent, native rel types | in-memory, rebuilt from index | parquet + vector store | key-value + vector + graph files | Cassandra + Qdrant, RDF/OWL | JSON (+ optional Neo4j push) |
| Ontology / typing | statistically cured dynamic ontology (FSM) | none - untyped phrases | none - flat entities | none | ontology-driven (RDF/OWL) | none - communities stand in |
| Entity resolution | calibrated Bayesian resolver | embedding synonym edges | weak string/embedding match | dedup on names | not a headline feature | name-level merge |
| Retrieval | dense-seeded PPR, 1-2 hops, question channel | phrase+passage PPR | map-reduce over Leiden summaries | dual-level keyword+vector | graph traversal + vector hybrid | BFS/DFS traversal |
| Incremental ingest | continuous, FSM-managed, restart-safe | append | batch reindex (incremental later) | yes | yes | yes (`--update`, `--watch`) |
| Provenance | per-entity source docs/chunks, event log, coverage certificates | none | source refs in summaries | chunk refs | fact-level provenance DAGs | EXTRACTED/INFERRED/AMBIGUOUS labels |
| Self-audit / repair | core thesis: certificates, gap ledger, drift probes, repair-from-source | none | none | none | explainability, not repair | audit labels, no repair loop |
| Temporal / versioning | entity versioning, bitemporal direction | none | none | none | partial (context cores) | none |
| Answer caching | fingerprint-invalidated | none | none | none | context cores (reusable) | none |
| Failure-mode register | yes - `docs/recall-failure-modes.md` | no | no | no | no | no |

One-line positioning: HippoRAG-2 is the retrieval blueprint KGF borrows (fuse inside PPR) without a persistent resolved graph; MS GraphRAG summarizes but cannot resolve identity; LightRAG is the cheap baseline; TrustGraph is a platform play with provenance but no measured self-repair; graphify is widest on inputs, thinnest on identity. KGF's differentiators are the rows nobody else fills: cured ontology, calibrated identity, certificates + repair, versioning, fingerprint caching.

## Strengths and Weaknesses

Strengths (each carries a recorded, reproducible measurement):

- **Identity discipline** - calibrated merge posteriors; the false-merge surface is enumerated and tested, not assumed
- **Context economy** - the escalation gate is a certified context-cost lever (conformal risk control, not a tuned threshold)
- **Operational survival** - ingest, probers and repair loops have each survived server restarts and session deaths with zero recompute (checkpoint + idempotent resume; most recently mid-ingest at doc 966/1,000)
- **Honest instrumentation** - a six-metric structural panel screened from 20 candidates; the 7 metrics that failed to move were retired rather than kept as decoration

Weaknesses (registered, evidenced, owned by open work - full register in `docs/recall-failure-modes.md`, RFM-1..9):

- **Extraction variance is the dominant root cause** - a single LLM pass keeps 76.8% of gold carriers with high run variance; re-rolling the extractor recovers only ~25% of true omissions, so repair-from-source has primacy
- **A perfect repair can still fail retrieval** - the graph can hold the fact while seeding never reaches its carrier (retrieval-hop failure class); coverage and retrieval failures are tracked as distinct classes
- **Answer style depresses extractive metrics** - peer-scored 1,000-doc rung (n=132): EM 0.015 / F1 0.150 / recall@5 0.752 - retrieval healthy, answers verbose rather than extractive (the extractive reader prompt is a known unbuilt harness item); the peer headline awaits the full-scale rung
- **Repair saturates** - guided repair plateaus near ~85% coverage; the residual miss classes are structurally untouchable by the current repair template

## Research Rigor

KGF is measured into shape, not designed and defended: over 500 pre-registered hypotheses (H1-H538) live in an append-only experiments ledger (`docs/experiments/kgf-redesign-experiments.md`), each with acceptance bars written before results and kill criteria so pet ideas can die. Contrarian research deliberately attacks the project's own load-bearing assumptions and has falsified shipped mechanisms (PPR traversal contribution, community summaries on factoid QA, LLM adjudication of NER spans). 173 cited papers are archived with digests in `references/papers/`. Refutations are promoted to the SOTA record as knowledge, not buried.

## Architecture

```
src/knowledge_graph_foundry/
├── settings.py       # pydantic settings: neo4j, llm, extraction, curing, drift
├── engines/          # frontier (litellm+instructor), claude-cli, local-gpu
├── ingest/           # format readers, tiktoken chunking with stable ids
├── ontology/         # seeds (freeform/YAML/OWL), fluid buffer, stability metrics, curing
├── extraction/       # purpose-injected extraction, embeddings (Bedrock + CPU fallback)
├── resolution/       # Bayesian posterior, union-find, isotonic calibration
├── graph/            # idempotent loaders, control metanode, GDS communities, answer cache, scorecard
├── drift.py          # windowed drift verdicts: none / warn / recure / rebuild
├── pipeline.py       # Foundry orchestrator over the lifecycle FSM
├── cli.py            # kgf init/ingest/status/optimize/query/wipe/tui
└── tui/              # Textual dashboard: status, stability, drift, event feed
```

Design in `docs/kgf-sota.md` (the SOTA record) and `docs/sota-promotions.md`; acceptance criteria in `docs/acceptance-criteria/`; defects in `docs/defects/defects.md`; recall failure modes in `docs/recall-failure-modes.md`.

## Development

- `make install` - create environment and install package
- `make test` - run the suite (no network or live Neo4j needed)
- `KGF_INTEGRATION=1 pytest tests/test_graph_integration.py` - live Neo4j integration tests
- `make lint` / `make format` - ruff check / fix

## Project Organization

```
├── config            # pinned per-rung experiment configs (tracked)
├── data/raw          # immutable source data
├── data/interim      # intermediate transforms; data/interim/dumps holds keeper Neo4j dumps + MANIFEST (S3-synced)
├── data/processed    # final datasets
├── docs              # design, acceptance criteria, defects, failure modes, experiments ledger
├── logs              # run and event logs (gitignored)
├── notebooks         # analysis notebooks + pinned measurement instruments (.py)
├── references        # v1 lessons, archived papers with digests
├── reports
│   ├── experiments
│   │   ├── adjudicated   # adjudicated verdict reports (JSON + briefs) cited by the experiments log
│   │   ├── invalid       # quarantined results kept for the record
│   │   └── <round>/      # per-round persistent results (bench/, r45/, ...)
│   └── figures
├── scripts           # infra harnesses (bench, token ledger, serving)
│   └── experiments   # hypothesis/round execution scripts cited by the experiments log
├── tmp               # scratch only - nothing kept (gitignored)
└── src/knowledge_graph_foundry
```

> **Note**: scaffolded with [copier-data-science](https://github.com/stellarshenson/copier-data-science)

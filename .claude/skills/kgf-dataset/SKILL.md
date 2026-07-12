---
name: kgf-dataset
description: KGF benchmark dataset doctrine - which corpus, slice, and Neo4j instance every hypothesis run uses. Consult before ANY ingest, A/B, or benchmark run to pick the correct scale-ladder rung (scout/small/medium/large) and data assets.
---

# KGF Dataset - Benchmark Corpus and Scale Ladder

All hypothesis testing and SOTA maturation runs on the benchmark corpus (2wiki first), on a four-rung scale ladder (user directive 2026-07-12). CPAP-corpus testing is abandoned for now.

## Scale ladder

Route every hypothesis to the cheapest rung that can kill it; escalate survivors up the ladder.

| Rung | Slice | Purpose |
|---|---|---|
| scout | 50 - `data/interim/bench/2wiki-scout-50.json` (head-50 of pilot-200, subset semantics) | smoke/wiring checks, instrument dry-runs, fast engine iteration |
| small | 200 - `data/interim/bench/2wiki-pilot-200.json` | hypothesis screening, cheap A/B kills |
| medium | 1,000 cumulative - `data/interim/bench/2wiki-medium-rows200-999.json` | verdict-grade confirmation, metric-sensitivity + regression work |
| large | 6,118 rows - `data/interim/bench/2wiki-full-rows1000-6118.json` | SOTA maturation + the #59 peer eval - held-out external questions, the honest H371/H372 adjudication |

## Why benchmark-only

- **Held-out questions** - benchmark questions are predefined by the dataset authors, external to ingestion; question generation (passages only) cannot anticipate them - kills the corpus-authored-probe circularity (H371 validity caveat, canonical log 2026-07-12)
- **Scale economics** - 1,000-6,000+ docs stress index growth, latency, and maintenance in ways the 25-doc CPAP corpus cannot
- **Peer numbers** - published GraphRAG / LightRAG / HippoRAG-2 results on the same benches are external reference points

## Corpus assets

- **Raw benchmarks** - `data/external/multihop-qa-benchmarks/`: `2wikimultihopqa.json` + `_corpus.json`, `hotpotqa.json` + `_corpus.json`, `musique.json` + `_corpus.json`, `hotpot_dev_distractor_v1.json`
- **Ladder slices** - `data/interim/bench/` (see table)
- **Rung-boundary dumps** - `tmp/data-dumps/` per `MANIFEST.md`: `20260711-neo4j3-2wiki-small-200` (630M), `20260712-neo4j3-2wiki-medium-1000` (788M), plus R45 repair-state dumps; restore recipe in the manifest
- **Bench results** - `results/bench/` (progressive-probe trajectory, regression ledger)

## Instances

- **neo4j3** (172.19.0.101) - the bench pile; ladder ingests land here
- **neo4j2** - scratch (throwaway experiments; holds the stood-down Phase-3 run-1 CPAP graph until reused)
- **neo4j4** (172.19.0.100) - CPAP production pile, READ-ONLY reference (H365-repaired, carries the r35_prototype question nodes)

## Rules

- DEF-4: `.env NEO4J_URI` silently overrides config targets - verify the connected instance before writing
- Dump + sidecar + manifest row at every rung boundary (neo4j-dumps rule)
- Same max-out GPU feeding config on both arms of any A/B, never changed mid-comparison
- LLM timeout 3600 when the vLLM server is shared across executors

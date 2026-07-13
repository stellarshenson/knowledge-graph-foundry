# Resume Brief - Small-Rung Ingest, R46-H499 Verdict Substrate (ladder rung 2)

Written 2026-07-12 ~19:58Z right after launch. A fresh agent can finish from this file alone. Project root: `/home/lab/workspace/learning/projects/knowledge-graph-foundry` (paths relative). Predecessor artifact: `results/bench-scout-resume-brief.md` (scout rung, COMPLETE - recipes identical).

## Why

H499 question-channel A/B on the scout pile was underpowered (5 eligible questions, OFF 4/5 ON 4/5, zero flips). The small-200 pile is the VERDICT-rung substrate; the coordinator runs the H499 verdict A/B against the LIVE container when this ingest completes.

## State at write time

- NEW throwaway container `user-konrad.jelen-kgf-neo4j-small` (neo4j:5.26.0, GDS+APOC, auth neo4j/kgfoundry, net stellars-tech-ai-workbench_hub_network) UP at **172.19.0.9**
- Config: `config/experiments/config-bench-small.yml` (uri bolt://172.19.0.9:7687, event_log logs/bench-small-events.jsonl)
- `kgf init` DONE with purpose "answer multi-hop questions over an open-domain encyclopedia corpus"; KGFControl VERIFIED on .9 (DEF-4 PASS)
- Ingest RUNNING, detached (setsid nohup, survives session death). Launch pgid 28858, started ~19:58Z. Slice: `data/interim/bench/2wiki-pilot-200.json` (200 passages, superset of scout-50, first title Teutberga). Expected ~2h at ~33 s/passage (scout mean)
- Log: `logs/bench-small-ingest.log`, active run after the `=== SMALL-200 ... ===` marker. Events: `logs/bench-small-events.jsonl`
- Completion signal = `ingested N documents` line (ANSI codes sit between "ingested" and the number - grep for `ingested` + `documents` loosely, or strip codes). NEVER trust process exit (DEF-15: may hang after printing; if hung, `pkill -f "kgf ingest data/interim/bench/2wiki-pilot-200"` and note it)
- Do NOT touch: scout container (UP, post-H499-screen), neo4j2, neo4j3, neo4j4

## Step A - verification (staged, ready)

```bash
.venv/bin/python scripts/bench_small_verify.py
```

Emits JSON: counts (KGFQuestion ~8/chunk all source 'ingest', ANSWERABLE_FROM/ABOUT, index `kgf_question_embeddings` ONLINE), per-passage timing from events, probe "Who was the husband of Teutberga?" with `## Question match:` detection, PASS/FAIL map.

## Step B - rung dump

```bash
docker stop user-konrad.jelen-kgf-neo4j-small
docker create --volumes-from user-konrad.jelen-kgf-neo4j-small --name kgf-small-dumper neo4j:5.26.0 \
  bash -c "mkdir -p /data/_dumps && neo4j-admin database dump neo4j --to-path=/data/_dumps"
docker start user-konrad.jelen-kgf-small-dumper && sleep 20 && docker logs user-konrad.jelen-kgf-small-dumper
docker cp user-konrad.jelen-kgf-small-dumper:/data/_dumps/neo4j.dump \
  tmp/data-dumps/20260712-neo4j-small-2wiki-200.dump
docker rm user-konrad.jelen-kgf-small-dumper
docker start user-konrad.jelen-kgf-neo4j-small    # MUST end UP - H499 verdict A/B runs against it
```

Quirks: socket proxy prefixes names + swallows `docker run` stdout (create/start/logs only); `mkdir -p /data/_dumps` REQUIRED (bit the scout run); bind mounts unwritable for container uid.

Sidecar `tmp/data-dumps/20260712-neo4j-small-2wiki-200.md` + MANIFEST.md row (small rung, R46-H499 verdict substrate, container left UP).

## Step C - report + logs

- `reports/bench-small-ingest-<UTCstamp>.json`: counts, per-passage mean/min/max wall-clock, verification map, probe summary, dump path, anomalies (MUST note "container left UP for H499 verdict A/B")
- `logs/README.md`: entries for bench-small-ingest.log + bench-small-events.jsonl (pattern: the bench-scout entries)

## Final return to coordinator

Counts, per-passage cost, dump path, report path, anomalies. HARD RULES: no git ops, no version changes, no JOURNAL.md edits, no engine-source edits, do not touch other instances.

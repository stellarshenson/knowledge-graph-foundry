# Resume Brief - Scout-Rung Smoke (task #83, retry executor)

Written 2026-07-12 ~19:10Z under a limits warning. A fresh agent can finish the job from this file alone. Project root: `/home/lab/workspace/learning/projects/knowledge-graph-foundry` (all paths relative to it).

## State at write time

- `kgf init` DONE on the throwaway: KGFControl {id:'kgf', purpose:'answer multi-hop questions over an open-domain encyclopedia corpus'} verified present on bolt://172.19.0.8:7687 (DEF-4 PASS - YAML `neo4j.uri` beats .env per `src/knowledge_graph_foundry/settings.py:248`)
- Ingest RUNNING, detached (setsid nohup, survives session death). PIDs at launch: setsid group 8186, children 8188/8189. Started 19:04:53Z, ~8/50 passages done by 19:09Z (~31 s/passage → ETA ~19:30-19:35Z)
- Log: `logs/bench-scout-ingest.log` - the active run starts after the line `=== RETRY 2026-07-12T19:04:52Z scout-50 ingest (post-init) ===` (everything before it is the predecessor's failed run, EXIT_CODE=1)
- Event log: `logs/bench-scout-events.jsonl` (document.started/completed pairs, questions.generated/stored/linked)
- Completion signal = `ingested N documents` line in the log, NEVER process exit (DEF-15: may hang after printing it; if so kill the pid and note it in the report)
- Container: `user-konrad.jelen-kgf-neo4j-scout` (neo4j:5.26.0, 172.19.0.8, /data on anonymous volume). Do NOT touch neo4j2/neo4j3/neo4j4

## Step A - after the "ingested N documents" line appears

Run verification (staged, ready):

```bash
.venv/bin/python scripts/bench_scout_verify.py > /tmp/scout-verify-out.json 2>/tmp/scout-verify-err.log
```

It emits a JSON with: graph counts (nodes/Entity/Chunk/Document/rels/KGFQuestion/source-ingest split/ANSWERABLE_FROM/ABOUT/questions-per-chunk/vector index `kgf_question_embeddings`), per-passage timing from the event log, question-event counts, engine `probe("Who was the husband of Teutberga?")` with `## Question match:` block detection, and PASS/FAIL per item under `verification`. If the process hung post-completion (DEF-15), `pkill -f "kgf ingest data/interim/bench/2wiki-scout-50"` before probing and note it.

## Step B - dump (rung-boundary capture)

```bash
docker stop user-konrad.jelen-kgf-neo4j-scout
docker create --volumes-from user-konrad.jelen-kgf-neo4j-scout --name kgf-scout-dumper neo4j:5.26.0 \
  neo4j-admin database dump neo4j --to-path=/data/_dumps
docker start user-konrad.jelen-kgf-scout-dumper   # socket proxy prefixes the name
docker logs user-konrad.jelen-kgf-scout-dumper    # poll until dump reports done
docker cp user-konrad.jelen-kgf-scout-dumper:/data/_dumps/neo4j.dump \
  tmp/data-dumps/20260712-neo4j-scout-2wiki-50.dump
```

Quirks (feedback_neo4j_dumps): socket proxy prefixes container names with `user-konrad.jelen-` and swallows `docker run` stdout - always create/start/logs, never `docker run`. Bind mounts are unwritable for the container uid - dump inside to /data/_dumps then `docker cp`.

Then write sidecar `tmp/data-dumps/20260712-neo4j-scout-2wiki-50.md` (instance: scout throwaway .8; what: 2wiki scale-ladder SCOUT rung, 50 passages, first H371 question-channel-active bench ingest; pairs with small-200) and append a row to `tmp/data-dumps/MANIFEST.md` following the existing table format.

## Step C - teardown

```bash
docker rm user-konrad.jelen-kgf-scout-dumper
docker rm user-konrad.jelen-kgf-neo4j-scout   # already stopped in Step B
```

## Step D - report

Write `reports/bench-scout-smoke-<UTCstamp>.json` (stamp format like 20260712T193000Z) containing: all counts from Step A, per-passage mean/min/max wall-clock, verification PASS/FAIL map, probe result summary, dump path, anomalies (predecessor init failure + anything new, e.g. DEF-15 hang). Add entries for `bench-scout-ingest.log` and `bench-scout-events.jsonl` to `logs/README.md` if missing.

## Final return to coordinator

PASS/FAIL per verification item, counts, per-passage cost, dump path, report path, anomalies. HARD RULES: no git commit/push/tag, no version changes, no JOURNAL.md edits, no engine-source modifications (question-channel misbehaviour = evidence in report only).

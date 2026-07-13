#!/usr/bin/env bash
# Phase-3 reproducible rebuild on the kgf-neo4j2 scratch (172.19.0.7) - ONE run per invocation.
# Config: config/experiments/config-phase3-rebuild.yml (exact config-apnea.yml copy, URI repointed).
# DEF-15: the driver watches the log for the "ingested N documents" line, never this process.
set -uo pipefail
cd /home/lab/workspace/learning/projects/knowledge-graph-foundry

RUN="$1"
CORPUS="data/external/cpap-datasheets-and-manuals"
CONFIG="config/experiments/config-phase3-rebuild.yml"

until [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8010/v1/models)" = "200" ]; do
  echo "waiting for vLLM health..."; sleep 30
done

echo "=== phase3 neo4j2 rebuild run ${RUN} START $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
rm -f logs/phase3-rebuild-events.jsonl
.venv/bin/kgf wipe --yes --config "$CONFIG" 2>&1
.venv/bin/kgf init "compare CPAP machines" --config "$CONFIG" 2>&1
START=$(date +%s)
.venv/bin/kgf ingest "$CORPUS" --config "$CONFIG" 2>&1
echo "PHASE3_RUN_${RUN}_WALLCLOCK_S=$(( $(date +%s) - START ))"
echo "=== phase3 neo4j2 rebuild run ${RUN} INGEST-EXIT $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

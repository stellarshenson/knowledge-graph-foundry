#!/usr/bin/env bash
# R22-H240(b) union-ingest validation - two sequential scratch arms on neo4j4.
# enum arm (H246 enumerate-then-extract) then mention arm (H258 mention-emission),
# wipe between, measure after each. Detached-compute rule: run via setsid nohup,
# watch logs/h240b-chain.log, results checkpoint to reports/ per arm.
set -euo pipefail
cd /home/lab/workspace/learning/projects/knowledge-graph-foundry

CORPUS="data/external/cpap-datasheets-and-manuals"
LOG="logs/h240b-chain.log"

# vLLM health gate
until [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8010/v1/models)" = "200" ]; do
  echo "waiting for vLLM health..." | tee -a "$LOG"; sleep 30
done

for ARM in enum mention; do
  CONFIG="config/experiments/config-h240b-${ARM}.yml"
  EVENTLOG="logs/h240b-${ARM}-events.jsonl"
  echo "=== H240b arm ${ARM} START $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
  rm -f "$EVENTLOG"
  .venv/bin/kgf wipe --yes --config "$CONFIG" 2>&1 | tee -a "$LOG"
  .venv/bin/kgf init "compare CPAP machines" --config "$CONFIG" 2>&1 | tee -a "$LOG"
  START=$(date +%s)
  .venv/bin/kgf ingest "$CORPUS" --config "$CONFIG" 2>&1 | tee -a "$LOG"
  END=$(date +%s)
  echo "H240B_ARM_${ARM}_WALLCLOCK_S=$((END-START))" | tee -a "$LOG"
  .venv/bin/python scripts/h240b_measure.py "$ARM" 2>&1 | tee -a "$LOG"
  echo "=== H240b arm ${ARM} DONE $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
done

touch logs/h240b-chain.DONE
echo "=== H240b chain COMPLETE $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"

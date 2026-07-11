#!/usr/bin/env bash
# Phase-3 reproducibility rebuild - the composed DEFAULT engine, TWO clean-state runs on neo4j4.
# Same config/experiments/config-phase3.yml both runs; the matching-numbers gate compares entity_id_fingerprint +
# entities + mean_recall across runs (within the H229 model-inherent variance floor).
# Detached-compute rule: launched via setsid nohup, watch logs/phase3-rebuild.log, checkpoint per run.
set -euo pipefail
cd /home/lab/workspace/learning/projects/knowledge-graph-foundry

CORPUS="data/external/cpap-datasheets-and-manuals"
CONFIG="config/experiments/config-phase3.yml"
LOG="logs/phase3-rebuild.log"

# vLLM health gate
until [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8010/v1/models)" = "200" ]; do
  echo "waiting for vLLM health..." | tee -a "$LOG"; sleep 30
done

for RUN in 1 2; do
  echo "=== phase3 rebuild run ${RUN} START $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
  rm -f logs/phase3-rebuild-events.jsonl
  .venv/bin/kgf wipe --yes --config "$CONFIG" 2>&1 | tee -a "$LOG"
  .venv/bin/kgf init "compare CPAP machines" --config "$CONFIG" 2>&1 | tee -a "$LOG"
  START=$(date +%s)
  .venv/bin/kgf ingest "$CORPUS" --config "$CONFIG" 2>&1 | tee -a "$LOG"
  echo "PHASE3_RUN_${RUN}_WALLCLOCK_S=$(( $(date +%s) - START ))" | tee -a "$LOG"
  .venv/bin/python scripts/phase3_measure.py "run${RUN}" 2>&1 | tee -a "$LOG"
  echo "=== phase3 rebuild run ${RUN} DONE $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
done

touch logs/phase3-rebuild.DONE
echo "=== phase3 rebuild COMPLETE $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"

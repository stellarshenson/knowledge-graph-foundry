#!/usr/bin/env bash
# R29 SLOT-1 v2 identity-stack reopen - paired A/B, 2 runs per arm (variance accounting), on neo4j4.
# Supersedes the H241 false-merge-COUNT clause per GAP-1 (no post-hoc renegotiation; this is a NEW decider).
# Pre-registered decider (docs/experiments/kgf-redesign-experiments.md, R29) - v2 promoted to default IFF:
#   C1 recall:    mean_recall(v2) >= mean_recall(v1) - 0.02
#   C2 precision: mean same_as_precision(v2) >= 0.50 AND >= mean same_as_precision(v1)
#   C3 rate:      mean false_merge_rate(v2) <= mean false_merge_rate(v1)   [rate = false/merges]
#   C4 variance:  within-arm run1<->run2 |d recall| <= 0.03 AND |d precision| <= 0.10 (both arms reproducible)
# Run order interleaves arm per run (v1r1, v2r1, v1r2, v2r2) so time-drift balances across the arm comparison.
# Detached-compute rule: launched via setsid nohup; watch logs/r29-chain.log; checkpoint per run to reports/.
# v2 arms load mDeBERTa NLI in-process - launch with CUDA_VISIBLE_DEVICES=0 (idle PRO 4000, off the vLLM card).
set -euo pipefail
cd /home/lab/workspace/learning/projects/knowledge-graph-foundry

CORPUS="data/external/cpap-datasheets-and-manuals"
LOG="logs/r29-chain.log"

# vLLM health gate
until [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8010/v1/models)" = "200" ]; do
  echo "waiting for vLLM health..." | tee -a "$LOG"; sleep 30
done

for RUN in 1 2; do
  for ARM in v1 v2; do
    CONFIG="config/experiments/config-r29-${ARM}.yml"
    echo "=== R29 arm ${ARM} run ${RUN} START $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
    rm -f "logs/r29-${ARM}-events.jsonl"
    .venv/bin/kgf wipe --yes --config "$CONFIG" 2>&1 | tee -a "$LOG"
    .venv/bin/kgf init "compare CPAP machines" --config "$CONFIG" 2>&1 | tee -a "$LOG"
    START=$(date +%s)
    .venv/bin/kgf ingest "$CORPUS" --config "$CONFIG" 2>&1 | tee -a "$LOG"
    echo "R29_${ARM}_RUN${RUN}_WALLCLOCK_S=$(( $(date +%s) - START ))" | tee -a "$LOG"
    .venv/bin/python scripts/experiments/r29_measure.py "${ARM}" "${RUN}" 2>&1 | tee -a "$LOG"
    cp "logs/r29-${ARM}-events.jsonl" "logs/r29-${ARM}-run${RUN}-events.jsonl" 2>/dev/null || true
    echo "=== R29 arm ${ARM} run ${RUN} DONE $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
  done
done

touch logs/r29-chain.DONE
echo "=== R29 CHAIN COMPLETE $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"

#!/usr/bin/env bash
# H241 v2 arm RE-RUN after vLLM outage killed the first v2 attempt (2026-07-08).
# Waits for server health, then wipe -> init -> ingest -> measure.
set -uo pipefail
cd /home/lab/workspace/learning/projects/knowledge-graph-foundry
LOG=logs/h241-ab.log
echo "=== H241 v2 RERUN waiting for vLLM health $(date -u +%H:%M:%SZ) ===" | tee -a "$LOG"
until curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:8010/v1/models | grep -q 200; do sleep 15; done
echo "=== vLLM healthy - starting v2 arm $(date -u +%H:%M:%SZ) ===" | tee -a "$LOG"
bash scripts/h241_arm.sh v2 2>&1 | tee -a "$LOG"
.venv/bin/python scripts/h241_measure.py v2 2>&1 | tee -a "$LOG"
echo "=== H241 v2 RERUN done $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
touch logs/h241-chain.DONE

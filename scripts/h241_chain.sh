#!/usr/bin/env bash
# R15-H241 orchestration chain: wait for the already-running v1 ingest -> measure v1
# (persist recall+stats BEFORE the wipe) -> run v2 arm -> measure v2.
set -uo pipefail
cd /home/lab/workspace/learning/projects/knowledge-graph-foundry
LOG=logs/h241-ab.log
PY=.venv/bin/python

echo "=== H241 CHAIN start $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"

# 1. wait for the running v1 driver to finish
while pgrep -f "h241_arm.sh v1" >/dev/null; do sleep 30; done
echo "=== v1 ingest driver exited $(date -u +%H:%M:%SZ) ===" | tee -a "$LOG"
sleep 5

# 2. measure v1 against its LIVE graph, persist (before any wipe)
$PY scripts/h241_measure.py v1 2>&1 | tee -a "$LOG"

# 3. run the v2 arm (wipes neo4j4, init, ingest)
bash scripts/h241_arm.sh v2 2>&1 | tee -a "$LOG"

# 4. measure v2 against its LIVE graph
$PY scripts/h241_measure.py v2 2>&1 | tee -a "$LOG"

echo "=== H241 CHAIN done $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
touch logs/h241-chain.DONE

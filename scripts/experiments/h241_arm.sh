#!/usr/bin/env bash
# R15-H241 paired identity A/B - one arm (wipe neo4j4 -> init -> ingest 28 docs).
# Usage: scripts/experiments/h241_arm.sh <v1|v2>
# Pins neo4j4 + local gpt-oss-120b engine via config-h241-<arm>.yml (DEF-4/DEF-5).
set -euo pipefail
ARM="$1"
CONFIG="config/experiments/config-h241-${ARM}.yml"
EVENTLOG="logs/h241-${ARM}-events.jsonl"
CORPUS="data/external/cpap-datasheets-and-manuals"
LOG="logs/h241-ab.log"

cd /home/lab/workspace/learning/projects/knowledge-graph-foundry

echo "=== H241 arm ${ARM} START $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
rm -f "$EVENTLOG"                                   # clean event log for a fresh count
.venv/bin/kgf wipe --yes --config "$CONFIG" 2>&1 | tee -a "$LOG"
.venv/bin/kgf init "compare CPAP machines" --config "$CONFIG" 2>&1 | tee -a "$LOG"
START=$(date +%s)
.venv/bin/kgf ingest "$CORPUS" --config "$CONFIG" 2>&1 | tee -a "$LOG"
END=$(date +%s)
echo "=== H241 arm ${ARM} INGEST wall-clock $((END-START))s DONE $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
echo "H241_ARM_${ARM}_WALLCLOCK_S=$((END-START))" | tee -a "$LOG"

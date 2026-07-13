#!/usr/bin/env bash
# One-shot resume launcher after 2026-07-13 server restart (board: BRACE SERVER RESTART).
# Waits for vLLM :8010, then relaunches medium ingest + progressive prober detached.
cd /home/lab/workspace/learning/projects/knowledge-graph-foundry

echo "[resume $(date -u +%FT%TZ)] waiting for vLLM :8010"
until curl -sf http://localhost:8010/v1/models > /dev/null; do sleep 15; done
echo "[resume $(date -u +%FT%TZ)] vLLM up"

setsid nohup .venv/bin/kgf ingest data/interim/bench/2wiki-medium-rows200-999.json \
  --config config/experiments/config-bench-medium.yml --event-log \
  >> logs/bench-medium-ingest.log 2>&1 &
echo "[resume $(date -u +%FT%TZ)] medium ingest relaunched (sid $!)"

sleep 10
setsid nohup .venv/bin/python scripts/bench_progressive_probe.py \
  >> logs/bench-progressive-probe.log 2>&1 &
echo "[resume $(date -u +%FT%TZ)] prober relaunched (sid $!)"

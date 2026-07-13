#!/usr/bin/env bash
# R48/R47 kill-gate chain (greenlit 2026-07-13): Leiden communityId on the
# medium pile, then H514 prunable-mass gate, H515 partition-mask gate,
# H501 retrieval ceiling gate. All FREE offline (no LLM calls).
# Detached; watch logs/r48-r47-gates-20260713.log
set -x
cd /home/lab/workspace/learning/projects/knowledge-graph-foundry

echo "[gates $(date -u +%FT%TZ)] leiden communityId on medium pile"
.venv/bin/python - << 'EOF'
from knowledge_graph_foundry import load_settings
from knowledge_graph_foundry.pipeline import Foundry
from knowledge_graph_foundry.graph.graphrag import detect_communities
st = load_settings("config/experiments/config-bench-medium.yml")
st.event_log = None
with Foundry(st) as f:
    print(detect_communities(f.driver, st.graphrag.community_min_size), flush=True)
EOF

echo "[gates $(date -u +%FT%TZ)] R48-H514 prunable-mass gate"
.venv/bin/python scripts/experiments/r48_h514_gate.py

echo "[gates $(date -u +%FT%TZ)] R48-H515 partition-mask gate"
.venv/bin/python scripts/experiments/r48_h515_mask.py

echo "[gates $(date -u +%FT%TZ)] R47-H501 retrieval ceiling gate"
.venv/bin/python scripts/experiments/r47_h501_ceiling.py

echo "[gates $(date -u +%FT%TZ)] GATES CHAIN COMPLETE"

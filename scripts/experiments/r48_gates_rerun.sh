#!/usr/bin/env bash
# Rerun after Path-vs-str fix: leiden -> H514 -> H515 (H501 runs in the first chain)
set -x
cd /home/lab/workspace/learning/projects/knowledge-graph-foundry
echo "[gates2 $(date -u +%FT%TZ)] leiden communityId on medium pile"
.venv/bin/python - << 'PYEOF'
from pathlib import Path
from knowledge_graph_foundry import load_settings
from knowledge_graph_foundry.pipeline import Foundry
from knowledge_graph_foundry.graph.graphrag import detect_communities
st = load_settings(Path("config/experiments/config-bench-medium.yml"))
st.event_log = None
with Foundry(st) as f:
    print(detect_communities(f.driver, st.graphrag.community_min_size), flush=True)
PYEOF
echo "[gates2 $(date -u +%FT%TZ)] R48-H514 prunable-mass gate"
.venv/bin/python scripts/experiments/r48_h514_gate.py
echo "[gates2 $(date -u +%FT%TZ)] R48-H515 partition-mask gate"
.venv/bin/python scripts/experiments/r48_h515_mask.py
echo "[gates2 $(date -u +%FT%TZ)] GATES2 CHAIN COMPLETE"

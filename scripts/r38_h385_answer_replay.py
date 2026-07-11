"""R38-H385 engine replay (answer side): the engine mints its own gate labels.

Two full-query passes over the 24 benchmark probes through the SHIPPED
``query()`` path (LLM answers on the local engine, post-H363):

  rung-0 arm - escalation_gate False: every probe answers from the base
               render; ``query.answered`` events carry escalated=false
  rung-2 arm - escalation_gate True at prior 2.0 (above the signal range):
               every probe escalates; events carry escalated=true

``fit_gate_from_events`` then harvests the (signal, rung0_covered,
rung2_covered) ledger from the event log and fits the CRC cut - the same
machinery ``optimize()`` consumes. Adjudicated against the offline
instruments:

  - signal match: per-probe seed_top_score vs the H382 ladder signals
  - fit equivalence: fitted theta vs the H383 certificate (0.7644 at
    alpha=0.08, candidate-cut neighbours 0.7565/0.8851)
  - floor discipline: n=24 >= min_labels=12 (below-floor path unit-tested)

Label caveat carried into the verdict: offline outcomes graded gold-in-
CONTEXT (retrieval side); ``_covered`` grades gold-in-ANSWER - paraphrase
loss is part of what this run measures.

Usage: python scripts/r38_h385_answer_replay.py   (GPU: local vLLM :8010)
"""

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import yaml

from knowledge_graph_foundry import enable_event_log, load_settings
from knowledge_graph_foundry.graph.gate_calibration import fit_gate_from_events
from knowledge_graph_foundry.pipeline import Foundry

CONFIG = Path("config/experiments/config-r31-gate.yml")  # local LLM, t3600, neo4j4
PROBES = Path("tests/probes/cpap-probe-set.yml")
EVENTS = Path("logs/r38-h385-answer-events.jsonl")
OFFLINE_LADDER = Path("reports/r37-h382-ladder-arm1-20260710T173529Z.json")
OFFLINE_THETA = 0.7644  # H383 certificate at alpha=0.08
CUT_NEIGHBOURS = [0.7565, 0.7644, 0.8851]  # candidate cuts from the CRC sweep


def main():
    st = load_settings(CONFIG)
    st.graphrag.passages_enabled = True
    st.event_log = str(EVENTS)
    EVENTS.unlink(missing_ok=True)
    enable_event_log(EVENTS)  # the sink is a module global - the CLI wires it, scripts must too

    probes = [p for p in yaml.safe_load(PROBES.read_text()) if p.get("gold_evidence")]
    print(f"probes: {len(probes)}", flush=True)

    with Foundry(st) as f:
        for arm, gate, prior in (("rung0", False, None), ("rung2", True, 2.0)):
            f.settings.graphrag.escalation_gate = gate
            if prior is not None:
                f.settings.graphrag.escalation_threshold_prior = prior
            for p in probes:
                res = f.query(p["question"])
                ans = (res or {}).get("answer") or ""
                print(f"{arm} {p['id']}: {len(ans)} chars", flush=True)

    ledger, record = fit_gate_from_events(EVENTS, probes, min_labels=12)
    print(f"ledger n={len(ledger)} record={record}", flush=True)

    offline = json.loads(OFFLINE_LADDER.read_text())
    sig_by_q = {p["question"]: p["id"] for p in probes}
    signal_diffs = {}
    for row in ledger:
        pid = sig_by_q[row["question"]]
        off_sig = offline["signals"].get(pid)
        signal_diffs[pid] = (
            round(row["signal"], 4),
            off_sig,
            round(abs(row["signal"] - off_sig), 4) if off_sig is not None else None,
        )
    max_diff = max((v[2] for v in signal_diffs.values() if v[2] is not None), default=None)
    theta = record["threshold"] if record else None
    fit_equiv = (
        theta is not None
        and any(abs(theta - c) < 1e-9 for c in CUT_NEIGHBOURS)
    )
    print(f"max signal diff vs offline: {max_diff}", flush=True)
    print(f"fitted theta={theta} vs offline {OFFLINE_THETA} equiv_within_one_cut={fit_equiv}", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/r38-h385-answer-replay-{ts}.json")
    out.write_text(
        json.dumps(
            {
                "hypothesis": "R38-H385 engine replay (answer side, LLM labels)",
                "generated": ts,
                "config": str(CONFIG),
                "events": str(EVENTS),
                "ledger": ledger,
                "record": record,
                "signal_diffs_vs_offline": signal_diffs,
                "max_signal_diff": max_diff,
                "offline_theta": OFFLINE_THETA,
                "fit_equivalent_within_one_cut": fit_equiv,
                "offline_needy": offline["needy"],
                "engine_rung0_uncovered": sorted(
                    sig_by_q[r["question"]] for r in ledger if not r["rung0_covered"]
                ),
            },
            indent=2,
        )
    )
    print(f"\nH385 ANSWER REPLAY COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

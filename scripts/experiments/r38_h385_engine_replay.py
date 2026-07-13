"""R38-H385 engine replay (context side): the SHIPPED gated read path vs its
own poles, measured retrieval-only on the benchmark pile.

Three arms through the engine's `_retrieve_local` (no LLM):
  gate_off - escalation_gate False (the engine's never-escalate pole)
  gated    - escalation_gate True at the shipped prior 0.765 (the H382/H383
             operating point; the pile carries no gate_calibration record so
             the prior applies - the H384 cold-start path, exercised live)
  always   - prior set above the signal range (always-escalate pole)

Passages are built first through the engine's own optimize-path machinery
(bge-m3 on GPU 2 via the passage channel - real embeddings, idempotent
store). This partially discharges the H385 replay-match clause on the
context side and adjudicates the engine's ADDITIVE rung-1 construction vs
the offline arm's displacement union; the LLM answer side rides post-H363.

Grading matches the pinned harness: per-probe share of gold evidence
present in the normalized joined context.
"""

import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, "notebooks")
from h158_measure import _norm, _present  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.extraction.embeddings import (  # noqa: E402
    channel_dimensions,
    embed_channel_texts,
)
from knowledge_graph_foundry.graph.passages import generate_passages  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

URI = "bolt://172.19.0.100:7687"
PROBES = Path("tests/probes/cpap-probe-set.yml")
OFFLINE_ESCALATED = ["P01", "P06", "P08", "P12", "P15", "P22"]  # H382 pooled holdout


def replay(f, probes):
    per, chars, esc = {}, {}, []
    for p in probes:
        lines, _names, cov = f._retrieve_local(p["question"])
        text = _norm(" ".join(lines))
        golds = p["gold_evidence"]
        per[p["id"]] = round(sum(_present(g, text) for g in golds) / len(golds), 4)
        chars[p["id"]] = len(text)
        if cov.get("escalated"):
            esc.append(p["id"])
    return per, chars, sorted(esc)


def main():
    base = load_settings(Path("config/config.yml"))
    st = deepcopy(base)
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = URI, "neo4j", "kgfoundry"
    st.graphrag.passages_enabled = True
    probes = [p for p in yaml.safe_load(PROBES.read_text()) if p.get("gold_evidence")]

    with Foundry(st) as f:
        ch = st.embedding_channels.passages
        created = generate_passages(
            f.driver,
            lambda texts: embed_channel_texts(texts, ch),
            st.graphrag.passage_index_name,
            channel_dimensions(ch),
            ch.provider,
            ch.model,
            span_chars=st.graphrag.passage_span_chars,
        )
        print(f"passages built on pile: {created} new", flush=True)

        arms = {}
        for arm, gate, prior in (
            ("gate_off", False, None),
            ("gated", True, None),  # shipped prior 0.765 - the cold-start path
            ("always", True, 2.0),  # above the signal range: every probe escalates
        ):
            f.settings.graphrag.escalation_gate = gate
            if prior is not None:
                f.settings.graphrag.escalation_threshold_prior = prior
            else:
                f.settings.graphrag.escalation_threshold_prior = (
                    base.graphrag.escalation_threshold_prior
                )
            per, chars, esc = replay(f, probes)
            total = sum(chars.values())
            arms[arm] = {
                "mean_recall": round(sum(per.values()) / len(per), 4),
                "fully_covered": sum(1 for v in per.values() if v == 1.0),
                "escalated": esc,
                "total_chars": total,
                "per_probe": per,
            }
            print(
                f"{arm}: recall={arms[arm]['mean_recall']} "
                f"full={arms[arm]['fully_covered']}/24 esc={len(esc)} chars={total}",
                flush=True,
            )

    off = arms["gate_off"]
    for arm in ("gated", "always"):
        arms[arm]["context_growth"] = round(arms[arm]["total_chars"] / off["total_chars"] - 1, 4)
        regress = [
            p for p, v in arms[arm]["per_probe"].items() if v < off["per_probe"][p]
        ]
        arms[arm]["regressions_vs_gate_off"] = regress
        print(
            f"{arm}: growth={arms[arm]['context_growth']:+.1%} "
            f"regressions={regress or 'none'}",
            flush=True,
        )
    print(
        f"gated escalation set matches offline: "
        f"{arms['gated']['escalated'] == OFFLINE_ESCALATED} "
        f"(engine {arms['gated']['escalated']} vs offline {OFFLINE_ESCALATED})",
        flush=True,
    )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/experiments/adjudicated/r38-h385-engine-replay-{ts}.json")
    out.write_text(
        json.dumps(
            {
                "hypothesis": "R38-H385 engine replay (context side, retrieval-only)",
                "generated": ts,
                "graph_uri": URI,
                "passages_created": created,
                "prior_used": base.graphrag.escalation_threshold_prior,
                "offline_escalated": OFFLINE_ESCALATED,
                "arms": arms,
            },
            indent=2,
        )
    )
    print(f"\nH385 ENGINE REPLAY COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

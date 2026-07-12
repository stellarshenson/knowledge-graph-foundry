"""R44-H468 A/B: relation-type-aware fanout boost, paired per-question.

Frozen pile (1,044 docs). Every eligible benchmark question probed twice -
boost OFF then boost ON - same criterion as the prober (yes/no -> full
gold-title coverage; else answer-in-context). Reports pass->fail and
fail->pass flips plus the named REG-2/REG-3 status. Bar: REG-2 + REG-3 flip
to pass AND zero paired pass->fail flips.

Usage: python scripts/r44_h468_ab.py [boost]
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "notebooks")
from h158_measure import _norm, _present  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

CONFIG = Path("config/experiments/config-bench-pilot.yml")
QUESTIONS = Path("data/external/multihop-qa-benchmarks/2wikimultihopqa.json")
REG_QIDS = {"1dfaa6200bdd11eba7f7acde48001122": "REG-2", "2dc690ba0bdc11eba7f7acde48001122": "REG-3"}
OUT = Path("results/r44")


def gold_titles(q):
    out = []
    for item in q.get("supporting_facts") or []:
        t = item[0] if isinstance(item, (list, tuple)) else item.get("title")
        if t and t not in out:
            out.append(t)
    return out


def load_slices():
    return {
        p.name: [r["title"] for r in json.loads(p.read_text())]
        for p in Path("data/interim/bench").glob("2wiki-*.json")
    }


def score(f, q):
    res = f.probe(q["question"])
    text = _norm(" ".join(res["context_lines"]))
    golds = gold_titles(q)
    cov = sum(bool(_present(t, text)) for t in golds) / len(golds) if golds else None
    aic = bool(_present(q.get("answer", ""), text)) if q.get("answer") else None
    if (q.get("answer") or "").strip().lower() in ("yes", "no"):
        return cov == 1.0
    return bool(aic)


def main():
    boost = float(sys.argv[1]) if len(sys.argv) > 1 else 0.15
    st = load_settings(CONFIG)
    st.event_log = None
    st.graphrag.passages_enabled = True
    questions = json.loads(QUESTIONS.read_text())
    OUT.mkdir(parents=True, exist_ok=True)

    with Foundry(st) as f, f.driver.session() as s:
        names = s.run("MATCH (d:KGFDocument) RETURN d.name AS n").value()
    slices = load_slices()
    titles = set()
    for n in names:
        m = re.search(r"^(.+\.json)#row(\d+)$", n or "")
        if m and slices.get(m.group(1)) and int(m.group(2)) < len(slices[m.group(1)]):
            titles.add(slices[m.group(1)][int(m.group(2))])
    eligible = [q for q in questions if gold_titles(q) and all(t in titles for t in gold_titles(q))]
    print(f"paired A/B over {len(eligible)} eligible questions, boost={boost}", flush=True)

    results = {}
    for arm, b in (("off", 0.0), ("on", boost)):
        st_arm = load_settings(CONFIG)
        st_arm.event_log = None
        st_arm.graphrag.passages_enabled = True
        st_arm.graphrag.fanout_relation_boost = b
        with Foundry(st_arm) as f:
            arm_res = {}
            for i, q in enumerate(eligible):
                qid = q.get("_id") or q.get("id")
                try:
                    arm_res[qid] = score(f, q)
                except Exception as exc:
                    print(f"probe error {qid}: {exc}", flush=True)
                    arm_res[qid] = None
                if (i + 1) % 25 == 0:
                    print(f"  {arm}: {i+1}/{len(eligible)}", flush=True)
            results[arm] = arm_res
        print(f"arm {arm}: {sum(1 for v in arm_res.values() if v)} pass / {len(arm_res)}", flush=True)

    gains = [k for k in results["off"] if results["off"][k] is False and results["on"][k] is True]
    losses = [k for k in results["off"] if results["off"][k] is True and results["on"][k] is False]
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = OUT / f"h468-ab-{ts}.json"
    out_path.write_text(json.dumps({
        "boost": boost, "n": len(eligible),
        "pass_off": sum(1 for v in results["off"].values() if v),
        "pass_on": sum(1 for v in results["on"].values() if v),
        "gains": gains, "losses": losses,
        "reg_status": {tag: {"off": results["off"].get(qid), "on": results["on"].get(qid)} for qid, tag in REG_QIDS.items()},
    }, indent=2))
    print(f"gains={len(gains)} losses={len(losses)}", flush=True)
    for qid, tag in REG_QIDS.items():
        print(f"{tag}: off={results['off'].get(qid)} -> on={results['on'].get(qid)}", flush=True)
    print(f"H468 AB COMPLETE -> {out_path}", flush=True)


if __name__ == "__main__":
    main()

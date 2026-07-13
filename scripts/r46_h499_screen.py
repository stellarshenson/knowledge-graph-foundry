"""R46-H499 screen: held-out question-channel A/B on the scout pile.

Paired per-question comparison on ONE questions-enabled pile - arm OFF
(questions.enabled=false) vs arm ON (true), toggled at retrieval time only,
zero re-ingest. Eligible set = 2wiki benchmark questions whose gold
supporting titles are ALL inside the ingested slice (held-out by
construction: authored by the dataset creators, never seen by ingestion).
Instrument = the progressive prober's scoring verbatim (answer-in-context;
yes/no answers pass on full gold-title coverage instead - REG-1 artifact).

Registered in docs/experiments/kgf-redesign-experiments.md (R46-H499).
Screen is DIRECTIONAL only - verdict rung is small/medium per the bar.

Usage: python scripts/r46_h499_screen.py [config] [questions.json]
Writes: results/bench/r46-h499-screen-<ts>.jsonl + summary to stdout
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "notebooks")
from h158_measure import _norm, _present  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

CONFIG = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    "config/experiments/config-bench-scout.yml"
)
QUESTIONS = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
    "data/external/multihop-qa-benchmarks/2wikimultihopqa.json"
)
OUT_DIR = Path("results/bench")
MAX_ELIGIBLE = int(sys.argv[3]) if len(sys.argv) > 3 else 40  # 0 = all eligible (verdict grade)


def gold_titles(q: dict) -> list[str]:
    sf = q.get("supporting_facts") or []
    titles = []
    for item in sf:
        t = item[0] if isinstance(item, (list, tuple)) else item.get("title")
        if t and t not in titles:
            titles.append(t)
    return titles


def load_slices() -> dict[str, list[str]]:
    return {
        p.name: [r["title"] for r in json.loads(p.read_text())]
        for p in Path("data/interim/bench").glob("2wiki-*.json")
    }


def ingested_titles(f, slices: dict[str, list[str]]) -> set[str]:
    with f.driver.session() as s:
        names = s.run("MATCH (d:KGFDocument) RETURN d.name AS n").value()
    out = set()
    for n in names:
        m = re.search(r"^(.+\.json)#row(\d+)$", n or "")
        if not m:
            continue
        titles = slices.get(m.group(1))
        idx = int(m.group(2))
        if titles and idx < len(titles):
            out.add(titles[idx])
    return out


def score(q: dict, res: dict) -> dict:
    text = _norm(" ".join(res["context_lines"]))
    answer_in_ctx = bool(_present(q.get("answer", ""), text)) if q.get("answer") else None
    golds = gold_titles(q)
    titles_cov = (
        round(sum(bool(_present(t, text)) for t in golds) / len(golds), 3) if golds else None
    )
    yesno = (q.get("answer") or "").strip().lower() in ("yes", "no")
    ok = titles_cov == 1.0 if yesno else bool(answer_in_ctx)
    return {
        "criterion": "gold_titles_full" if yesno else "answer_in_context",
        "answer_in_context": answer_in_ctx,
        "gold_titles_coverage": titles_cov,
        "pass": ok,
    }


def run_arm(enabled: bool, eligible: list[dict], out, run_id: str) -> dict[str, bool]:
    st = load_settings(CONFIG)
    st.event_log = None
    st.questions.enabled = enabled
    arm = "on" if enabled else "off"
    results = {}
    with Foundry(st) as f:
        for q in eligible:
            qid = q.get("_id") or q.get("id") or q["question"][:60]
            t0 = time.monotonic()
            try:
                res = f.probe(q["question"])
            except Exception as exc:
                print(f"probe error arm={arm} {qid}: {exc}", flush=True)
                continue
            rec = {
                "run_id": run_id,
                "arm": arm,
                "id": qid,
                "question": q["question"][:120],
                "probe_wall_s": round(time.monotonic() - t0, 1),
                **score(q, res),
            }
            results[qid] = rec["pass"]
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print(f"arm={arm} {qid} pass={rec['pass']} cov={rec['gold_titles_coverage']}", flush=True)
    return results


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    questions = json.loads(QUESTIONS.read_text())
    st = load_settings(CONFIG)
    st.event_log = None
    with Foundry(st) as f:
        titles = ingested_titles(f, load_slices())
    full = [q for q in questions if gold_titles(q) and all(t in titles for t in gold_titles(q))]
    eligible = full[:MAX_ELIGIBLE] if MAX_ELIGIBLE else full
    print(
        f"r46-h499 screen {run_id}: {len(titles)} ingested titles, "
        f"{len(full)} eligible questions, running {len(eligible)}",
        flush=True,
    )
    if not eligible:
        print("no eligible questions - screen cannot run on this slice", flush=True)
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"r46-h499-screen-{run_id}.jsonl"
    with out_path.open("a") as out:
        off = run_arm(False, eligible, out, run_id)
        on = run_arm(True, eligible, out, run_id)
    both = sorted(set(off) & set(on))
    flips_up = [q for q in both if on[q] and not off[q]]
    flips_down = [q for q in both if off[q] and not on[q]]
    summary = {
        "run_id": run_id,
        "paired_n": len(both),
        "off_pass": sum(off[q] for q in both),
        "on_pass": sum(on[q] for q in both),
        "flips_off_to_on_up": flips_up,
        "REGRESSIONS_on_worse": flips_down,
        "out": str(out_path),
    }
    print("SUMMARY " + json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()

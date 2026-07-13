"""R48-H514 round gate: residual recall-neutral prunable mass after the H382 gate.

For every eligible held-in 2wiki question (gold titles fully ingested), replay
the shipped retrieval (H382 escalation gate ACTIVE in the probe path), then
greedily remove render blocks largest-first while the probe criterion still
passes (answer_in_context; yes/no -> full gold-title coverage, per the prober
instrument). P = prunable token fraction of the passing render. Oracle
hierarchy-aligned prune = the prunable tokens capturable by dropping WHOLE
communities (all blocks of a communityId prunable) - requires communityId on
entities (run gds.leiden first).

Registered: docs/experiments/kgf-redesign-experiments.md R48-H514.
Bars: KILL if median P < 15%; reduction domains OPEN only if median P >= 30%
AND the oracle captures >= half of it.

Usage: python scripts/experiments/r48_h514_gate.py [config] [questions.json] [max]
Writes: reports/experiments/r48/h514-gate-<ts>.json (per-probe rows + summary)
"""

import json
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "notebooks")
sys.path.insert(0, "scripts/experiments")
import tiktoken  # noqa: E402
from h158_measure import _norm, _present  # noqa: E402
from r46_h499_screen import gold_titles, ingested_titles, load_slices  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

CONFIG = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    "config/experiments/config-bench-medium.yml"
)
QUESTIONS = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
    "data/external/multihop-qa-benchmarks/2wikimultihopqa.json"
)
MAX = int(sys.argv[3]) if len(sys.argv) > 3 else 0  # 0 = all eligible

ENC = tiktoken.get_encoding("cl100k_base")
HEADER = re.compile(r"^## (.+?) \(")


def toks(s: str) -> int:
    return len(ENC.encode(s))


def crit_pass(q: dict, blocks: list[str]) -> bool:
    text = _norm(" ".join(blocks))
    golds = gold_titles(q)
    yesno = (q.get("answer") or "").strip().lower() in ("yes", "no")
    if yesno:
        return bool(golds) and all(_present(t, text) for t in golds)
    return bool(_present(q.get("answer", ""), text))


def greedy_prune(q: dict, blocks: list[str]) -> list[int]:
    """Indices of blocks removable (cumulatively, largest-first) without
    breaking the criterion."""
    keep = list(range(len(blocks)))
    removed: list[int] = []
    changed = True
    while changed:
        changed = False
        for i in sorted(keep, key=lambda i: -toks(blocks[i])):
            trial = [blocks[j] for j in keep if j != i]
            if crit_pass(q, trial):
                keep.remove(i)
                removed.append(i)
                changed = True
                break
    return removed


def block_cid(block: str, name_cid: dict[str, str | int]) -> str | int | None:
    m = HEADER.match(block)
    return name_cid.get(_norm(m.group(1))) if m else None


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    questions = json.loads(QUESTIONS.read_text())
    st = load_settings(CONFIG)
    st.event_log = None
    rows = []
    with Foundry(st) as f:
        with f.driver.session() as s:
            name_cid = {
                _norm(r["name"]): r["cid"]
                for r in s.run(
                    "MATCH (e:Entity) WHERE e.communityId IS NOT NULL "
                    "RETURN e.name AS name, e.communityId AS cid"
                )
            }
        if not name_cid:
            print("FATAL: no communityId on entities - run gds.leiden first", flush=True)
            sys.exit(1)
        titles = ingested_titles(f, load_slices())
        full = [
            q for q in questions if gold_titles(q) and all(t in titles for t in gold_titles(q))
        ]
        eligible = full[:MAX] if MAX else full
        print(f"h514 {run_id}: {len(eligible)} eligible probes", flush=True)

        for k, q in enumerate(eligible):
            qid = q.get("_id") or q["question"][:60]
            try:
                res = f.probe(q["question"])
            except Exception as exc:
                print(f"probe error {qid}: {exc}", flush=True)
                continue
            blocks = res["context_lines"]
            total = sum(toks(b) for b in blocks)
            base = crit_pass(q, blocks)
            row = {
                "id": qid,
                "escalated": res["coverage"].get("escalated"),
                "blocks": len(blocks),
                "total_tokens": total,
                "pass": base,
            }
            if base and total:
                removed = greedy_prune(q, blocks)
                pruned_toks = sum(toks(blocks[i]) for i in removed)
                row["prunable_fraction"] = round(pruned_toks / total, 4)
                # oracle: whole communities where EVERY rendered block is prunable
                cids = [block_cid(b, name_cid) for b in blocks]
                removed_set = set(removed)
                prunable_whole = {
                    c
                    for c in set(cids)
                    if c is not None
                    and all(i in removed_set for i, ci in enumerate(cids) if ci == c)
                }
                oracle_toks = sum(
                    toks(blocks[i]) for i in removed if cids[i] in prunable_whole
                )
                row["oracle_capture"] = (
                    round(oracle_toks / pruned_toks, 4) if pruned_toks else None
                )
            rows.append(row)
            print(
                f"[{k+1}/{len(eligible)}] {qid} pass={base} "
                f"P={row.get('prunable_fraction')} oracle={row.get('oracle_capture')}",
                flush=True,
            )

    ps = [r["prunable_fraction"] for r in rows if r.get("prunable_fraction") is not None]
    ocs = [r["oracle_capture"] for r in rows if r.get("oracle_capture") is not None]
    summary = {
        "run_id": run_id,
        "config": str(CONFIG),
        "n_probes": len(rows),
        "n_passing": len(ps),
        "median_prunable_fraction": round(statistics.median(ps), 4) if ps else None,
        "mean_prunable_fraction": round(statistics.fmean(ps), 4) if ps else None,
        "median_oracle_capture": round(statistics.median(ocs), 4) if ocs else None,
        "bars": {"kill_below": 0.15, "open_at": 0.30, "oracle_half": 0.5},
    }
    out = Path("reports/experiments/r48")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"h514-gate-{run_id}.json"
    path.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    print("SUMMARY " + json.dumps(summary), flush=True)
    print(f"WROTE {path}", flush=True)


if __name__ == "__main__":
    main()

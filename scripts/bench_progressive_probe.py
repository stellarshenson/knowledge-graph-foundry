"""Progressive regression prober - runs BESIDE an ingest (user directive
2026-07-11: "progressively probe the queries as we go so that we can see if
there is regression of any kind and register it if it is").

Every cycle: find benchmark questions whose gold supporting titles are ALL
already ingested (eligible set grows as the ingest advances), replay each
through the engine's retrieval (retrieval-only - no LLM, no contention with
the extraction workers), and score answer-in-context + gold-title coverage.
A question that passed in an earlier cycle and fails in a later one is a
REGRESSION - printed loudly and recorded in the trajectory JSONL for
registration.

Usage: python scripts/bench_progressive_probe.py <questions.json> <config.yml>
Writes: reports/experiments/bench/progressive-probe-trajectory.jsonl (append, one record
per question per cycle) - the raw material for the regression ledger.
"""

import argparse
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
from knowledge_graph_foundry.probe import load_manifest, select_manifest  # noqa: E402

DEFAULT_QUESTIONS = Path("data/external/multihop-qa-benchmarks/2wikimultihopqa.json")
DEFAULT_CONFIG = Path("config/experiments/config-bench-pilot.yml")
TRAJECTORY = Path("reports/experiments/bench/progressive-probe-trajectory.jsonl")
CYCLE_S = 600  # probe cadence
MAX_ELIGIBLE = 15  # cap per cycle - probes cost ~2-3 min each under ingest contention


def probe_id(q: dict) -> str:
    """Stable question id used for the trajectory record and manifest match."""
    return q.get("_id") or q.get("id") or q["question"][:60]


def gold_titles(q: dict) -> list[str]:
    # 2wiki/hotpot format: supporting_facts as [title, sent_idx] pairs or
    # {"title": ...}; context/paragraphs carry the same titles
    sf = q.get("supporting_facts") or []
    titles = []
    for item in sf:
        t = item[0] if isinstance(item, (list, tuple)) else item.get("title")
        if t and t not in titles:
            titles.append(t)
    return titles


def load_slices() -> dict[str, list[str]]:
    """Doc name '<file>#rowN' maps to the corpus title via its slice file.
    Re-globbed EVERY cycle - a slice file created after prober start must
    become visible (bug: import-time glob left a live instance blind 2h)."""
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


def seed_memory_from_trajectory() -> set[str]:
    """Rebuild the pass baseline from the persisted trajectory so a prober
    restart cannot erase regression memory (bug: in-memory-only baseline)."""
    passed = set()
    if TRAJECTORY.exists():
        for ln in TRAJECTORY.read_text().splitlines():
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r.get("pass") is True:
                passed.add(r["id"])
    return passed


def main():
    parser = argparse.ArgumentParser(description="progressive regression prober")
    parser.add_argument("questions", nargs="?", default=str(DEFAULT_QUESTIONS))
    parser.add_argument("config", nargs="?", default=str(DEFAULT_CONFIG))
    parser.add_argument(
        "--manifest",
        default=None,
        help="R49-H541 frozen question-manifest file (ids list); overrides "
        "probe.manifest and replaces per-cycle resampling with the fixed set",
    )
    args = parser.parse_args()
    config_path = Path(args.config)

    # single-instance guard: two concurrent probers interleave contradictory
    # doc counts into one trajectory (live-confirmed fault)
    import fcntl

    lock = open("/tmp/kgf-bench-prober.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("another prober instance holds the lock - refusing to start")

    st = load_settings(config_path)
    st.event_log = None
    st.graphrag.passages_enabled = True  # stamped into every record below
    questions = json.loads(Path(args.questions).read_text())
    manifest_path = args.manifest or st.probe.manifest
    manifest_ids = load_manifest(manifest_path) if manifest_path else None
    if manifest_ids is not None:
        print(
            f"frozen manifest {manifest_path}: {len(manifest_ids)} question ids "
            "(H541 paired probes, resampling off)",
            flush=True,
        )
    TRAJECTORY.parent.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    passed_before = seed_memory_from_trajectory()
    regressions_seen: set[str] = set()
    rotate = 0
    print(f"prober run {run_id}: baseline seeded with {len(passed_before)} previously-passing qids", flush=True)

    with Foundry(st) as f:
        while True:
            try:
                titles = ingested_titles(f, load_slices())
            except Exception as exc:
                print(f"cycle skipped - graph unavailable: {exc}", flush=True)
                time.sleep(CYCLE_S)
                continue
            full = [
                q for q in questions
                if gold_titles(q) and all(t in titles for t in gold_titles(q))
            ]
            # R49-H541 frozen manifest: probe the fixed set in manifest order,
            # no resampling. Otherwise round-robin rotation so every eligible
            # question gets probed across cycles (bug: fixed prefix froze
            # surveillance at the first 15)
            if manifest_ids is not None:
                eligible = select_manifest(full, manifest_ids, probe_id)
            elif full:
                rotate %= len(full)
                eligible = (full[rotate:] + full[:rotate])[:MAX_ELIGIBLE]
                rotate += MAX_ELIGIBLE
            else:
                eligible = []
            cycle_ts = datetime.now(timezone.utc).isoformat()
            n_pass = n_fail = 0
            for q in eligible:
                qid = probe_id(q)
                t0 = time.monotonic()
                try:
                    res = f.probe(q["question"])  # public instrumentation surface
                except Exception as exc:
                    print(f"probe error {qid}: {exc}", flush=True)
                    continue
                probe_wall = round(time.monotonic() - t0, 1)
                text = _norm(" ".join(res["context_lines"]))
                answer_in_ctx = bool(_present(q.get("answer", ""), text)) if q.get("answer") else None
                golds = gold_titles(q)
                titles_cov = round(sum(bool(_present(t, text)) for t in golds) / len(golds), 3) if golds else None
                # yes/no answers match incidental tokens (REG-1 artifact) - the
                # comparison class passes on full gold-title coverage instead
                if (q.get("answer") or "").strip().lower() in ("yes", "no"):
                    ok = titles_cov == 1.0
                else:
                    ok = bool(answer_in_ctx)
                n_pass += ok
                n_fail += (not ok)
                rec = {
                    "cycle": cycle_ts,
                    "run_id": run_id,
                    "config": str(config_path),
                    "passages_enabled": True,
                    "criterion": "gold_titles_full" if (q.get("answer") or "").strip().lower() in ("yes", "no") else "answer_in_context",
                    "id": qid,
                    "ingested_titles": len(titles),
                    "eligible_total": len(full),
                    "answer_in_context": answer_in_ctx,
                    "gold_titles_coverage": titles_cov,
                    "pass": ok,
                    "probe_wall_s": probe_wall,
                }
                if ok:
                    passed_before.add(qid)
                elif qid in passed_before and qid not in regressions_seen:
                    regressions_seen.add(qid)
                    rec["REGRESSION"] = True
                    print(
                        f"REGRESSION: {qid} passed earlier, fails at {len(titles)} docs: "
                        f"{q['question'][:90]}",
                        flush=True,
                    )
                with TRAJECTORY.open("a") as fh:
                    fh.write(json.dumps(rec) + "\n")
            print(
                f"PROBE CYCLE {cycle_ts}: {len(titles)} docs ingested, "
                f"{len(eligible)}/{len(full)} eligible probed, {n_pass} pass / {n_fail} fail, "
                f"{len(regressions_seen)} regressions total",
                flush=True,
            )
            time.sleep(CYCLE_S)


if __name__ == "__main__":
    main()

"""#59 QA adapter: run KGF over held-in 2wiki questions, emit an answers JSONL.

Produces one record per eligible question in the bench_score.py schema
({id, question, answer, gold_answers, retrieved_titles, gold_titles}) so the
peer scorer computes EM / F1 + recall@5 against the HotpotQA-standard peer
tables (GraphRAG / LightRAG / HippoRAG-2).

Eligible set = 2wiki questions whose gold supporting titles are ALL inside the
ingested slice (held-in by construction). answer = f.query() (LLM answer over
the graph). retrieved_titles = the render's supporting entities mapped through
their source_documents to slice titles, order-preserved and deduped - a
title-level recall proxy (NOT HippoRAG's passage-ranked recall@5; on a slice
this is a harness shakedown, not the peer headline, which needs the large rung).

Usage: python scripts/bench_answer_kgf.py [config] [questions.json] [max]
Writes: reports/experiments/bench/<stem>-answers-<ts>.jsonl
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time

from knowledge_graph_foundry import load_settings
from knowledge_graph_foundry.pipeline import Foundry

CONFIG = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    "config/experiments/config-bench-small.yml"
)
QUESTIONS = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
    "data/external/multihop-qa-benchmarks/2wikimultihopqa.json"
)
MAX = int(sys.argv[3]) if len(sys.argv) > 3 else 0  # 0 = all eligible
OUT_DIR = Path("reports/experiments/bench")


def gold_titles(q: dict) -> list[str]:
    sf = q.get("supporting_facts") or []
    titles: list[str] = []
    for item in sf:
        t = item[0] if isinstance(item, (list, tuple)) else item.get("title")
        if t and t not in titles:
            titles.append(t)
    return titles


def gold_answers(q: dict) -> list[str]:
    golds = [q["answer"]] if q.get("answer") else []
    for a in q.get("answer_aliases") or q.get("aliases") or []:
        if a and a not in golds:
            golds.append(a)
    return golds


def load_slices() -> dict[str, list[str]]:
    return {
        p.name: [r["title"] for r in json.loads(p.read_text())]
        for p in Path("data/interim/bench").glob("2wiki-*.json")
    }


def docname_to_title(slices: dict[str, list[str]]) -> dict[str, str]:
    """Map every '<file>#rowN' doc name to its slice title."""
    out: dict[str, str] = {}
    for fname, titles in slices.items():
        for i, t in enumerate(titles):
            out[f"{fname}#row{i}"] = t
    return out


def docid_to_title(f, name2title: dict[str, str]) -> dict[str, str]:
    """Entities reference documents by content-hash id (d_...); join through
    KGFDocument.name to the slice title."""
    with f.driver.session() as s:
        rows = s.run("MATCH (x:KGFDocument) RETURN x.id AS id, x.name AS name").data()
    out: dict[str, str] = {}
    for r in rows:
        t = name2title.get(r["name"] or "")
        if r["id"] and t:
            out[r["id"]] = t
    return out


def ingested_titles(f, slices: dict[str, list[str]]) -> set[str]:
    with f.driver.session() as s:
        names = s.run("MATCH (d:KGFDocument) RETURN d.name AS n").value()
    out: set[str] = set()
    for n in names:
        m = re.search(r"^(.+\.json)#row(\d+)$", n or "")
        if not m:
            continue
        titles = slices.get(m.group(1))
        idx = int(m.group(2))
        if titles and idx < len(titles):
            out.add(titles[idx])
    return out


def retrieved_titles(f, names: list[str], docid2title: dict[str, str], k: int = 10) -> list[str]:
    """Supporting entities -> their source_documents (hash ids) -> slice titles, order-preserved."""
    if not names:
        return []
    with f.driver.session() as s:
        rows = s.run(
            "UNWIND $names AS nm MATCH (e:Entity {name: nm}) "
            "RETURN nm AS name, e.source_documents AS docs",
            names=names,
        ).data()
    by_name = {r["name"]: (r["docs"] or []) for r in rows}
    titles: list[str] = []
    for nm in names:  # supporting_names order ~ seed rank
        for doc in by_name.get(nm, []):
            t = docid2title.get(doc)
            if t and t not in titles:
                titles.append(t)
        if len(titles) >= k:
            break
    return titles[:k]


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    questions = json.loads(QUESTIONS.read_text())
    slices = load_slices()
    name2title = docname_to_title(slices)
    st = load_settings(CONFIG)
    st.event_log = None
    with Foundry(st) as f:
        docid2title = docid_to_title(f, name2title)
        titles = ingested_titles(f, slices)
        full = [
            q for q in questions
            if gold_titles(q) and all(t in titles for t in gold_titles(q))
        ]
        eligible = full[:MAX] if MAX else full
        print(
            f"bench-answer {run_id}: {len(titles)} ingested titles, "
            f"{len(full)} eligible, answering {len(eligible)}",
            flush=True,
        )
        if not eligible:
            print("no eligible questions on this slice", flush=True)
            return
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUT_DIR / f"{QUESTIONS.stem}-answers-{run_id}.jsonl"
        with out_path.open("a") as out:
            for i, q in enumerate(eligible):
                qid = q.get("_id") or q.get("id") or q["question"][:60]
                t0 = time.monotonic()
                try:
                    _, names, _ = f._retrieve_local(q["question"])
                    ans = f.query(q["question"])
                except Exception as exc:
                    print(f"error {qid}: {exc}", flush=True)
                    continue
                rec = {
                    "id": qid,
                    "question": q["question"],
                    "answer": ans.get("answer", ""),
                    "gold_answers": gold_answers(q),
                    "gold_titles": gold_titles(q),
                    "retrieved_titles": retrieved_titles(f, names, docid2title),
                    "path": ans.get("path"),
                    "wall_s": round(time.monotonic() - t0, 1),
                }
                out.write(json.dumps(rec) + "\n")
                out.flush()
                print(f"[{i + 1}/{len(eligible)}] {qid} -> {rec['answer'][:60]!r}", flush=True)
    print(f"DONE {out_path}", flush=True)


if __name__ == "__main__":
    main()

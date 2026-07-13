"""R48-H530 sub-question decomposition matched to single-hop question nodes.

2wiki gold evidences ([subject, relation, object] per hop) proxy the gold
sub-questions: each hop becomes "<subject> <relation>?", embedded through the
shipped channel and matched to its nearest KGFQuestion. A hop MATCHES when
the object (the hop answer) is present in the matched question's
ANSWERABLE_FROM chunk text (top-1; top-3 union reported beside). Kill-gate:
coverage < 60% kills. The decomposed context = union of matched questions'
chunks per probe, prober criterion, tokens vs the shipped baseline. The
registered comparator (H528 whole-query routing) was KILLED same day - the
comparison is reported against the shipped baseline instead, deviation noted.

Registered: docs/experiments/kgf-redesign-experiments.md R48-H530.
Usage: python scripts/experiments/r48_h530_decomp.py [config] [questions] [max]
Writes: reports/experiments/r48/h530-decomp-<ts>.json
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, "notebooks")
sys.path.insert(0, "scripts/experiments")
import tiktoken  # noqa: E402
from h158_measure import _present  # noqa: E402
from r46_h499_screen import gold_titles, ingested_titles, load_slices  # noqa: E402
from r48_h514_gate import crit_pass  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.extraction import generate_embeddings  # noqa: E402
from knowledge_graph_foundry.models import Entity  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

CONFIG = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    "config/experiments/config-bench-medium.yml"
)
QUESTIONS = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
    "data/external/multihop-qa-benchmarks/2wikimultihopqa.json"
)
MAX = int(sys.argv[3]) if len(sys.argv) > 3 else 0
ENC = tiktoken.get_encoding("cl100k_base")


def toks(s: str) -> int:
    return len(ENC.encode(s))


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bench = json.loads(QUESTIONS.read_text())
    st = load_settings(CONFIG)
    st.event_log = None
    with Foundry(st) as f:
        with f.driver.session() as s:
            qrows = s.run(
                "MATCH (q:KGFQuestion)-[:ANSWERABLE_FROM]->(c:Chunk) "
                "RETURN q.id AS id, q.text AS text, q.embedding AS emb, "
                "collect(DISTINCT c.text) AS chunks"
            ).data()
        qemb = np.array([r["emb"] for r in qrows], dtype=np.float32)
        qemb /= np.linalg.norm(qemb, axis=1, keepdims=True) + 1e-9
        print(f"h530 {run_id}: {len(qrows)} questions", flush=True)

        titles = ingested_titles(f, load_slices())
        full = [
            q for q in bench
            if gold_titles(q) and all(t in titles for t in gold_titles(q)) and q.get("evidences")
        ]
        eligible = full[:MAX] if MAX else full
        print(f"{len(eligible)} eligible probes with evidences", flush=True)

        hops_total = hops_matched1 = hops_matched3 = 0
        rows = []
        for k, q in enumerate(eligible):
            subqs = [f"{s_} {r_}?" for s_, r_, _ in q["evidences"]]
            objs = [o for _, _, o in q["evidences"]]
            ents = [
                Entity.create(sq[:80], types=["Query"], description=sq) for sq in subqs
            ]
            embs = np.array(
                [e.embedding for e in generate_embeddings(ents, st.embeddings)],
                dtype=np.float32,
            )
            embs /= np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9
            union_chunks: set = set()
            m1 = m3 = 0
            for i, obj in enumerate(objs):
                ranked = np.argsort(-(qemb @ embs[i]))
                top1 = qrows[int(ranked[0])]
                top3 = [qrows[int(j)] for j in ranked[:3]]
                t1 = " ".join(top1["chunks"])
                t3 = " ".join(c for r in top3 for c in r["chunks"])
                m1 += bool(_present(obj, t1))
                m3 += bool(_present(obj, t3))
                union_chunks.update(top1["chunks"])
            hops_total += len(objs)
            hops_matched1 += m1
            hops_matched3 += m3
            chunks = sorted(union_chunks)
            rows.append({
                "id": q.get("_id"),
                "type": q.get("type"),
                "hops": len(objs),
                "hops_matched_top1": m1,
                "pass": crit_pass(q, chunks),
                "tokens": sum(toks(c) for c in chunks),
            })
            if (k + 1) % 20 == 0:
                print(f"[{k+1}/{len(eligible)}] cov1={hops_matched1/hops_total:.3f}",
                      flush=True)

    by_type: dict[str, list] = {}
    for r in rows:
        by_type.setdefault(r["type"], []).append(r)
    summary = {
        "run_id": run_id,
        "config": str(CONFIG),
        "n_probes": len(rows),
        "hops": hops_total,
        "subq_coverage_top1": round(hops_matched1 / hops_total, 4),
        "subq_coverage_top3": round(hops_matched3 / hops_total, 4),
        "decomp_pass_rate": round(sum(r["pass"] for r in rows) / len(rows), 4),
        "decomp_tokens_p50": int(np.median([r["tokens"] for r in rows])),
        "by_type": {
            ty: {"n": len(v), "pass_rate": round(sum(r["pass"] for r in v) / len(v), 4)}
            for ty, v in by_type.items()
        },
        "baseline_reference": {"pass_rate": 0.6515, "tokens_p50": 642,
                               "source": "h516 sweep baseline arm"},
        "deviation": "comparator H528 whole-query routing KILLED same day - compared "
        "to shipped baseline; sub-questions proxied from gold evidence triples",
        "bars": {"killed_coverage_lt": 0.60},
    }
    outdir = Path("reports/experiments/r48")
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"h530-decomp-{run_id}.json"
    path.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    print("SUMMARY " + json.dumps(summary), flush=True)
    print(f"WROTE {path}", flush=True)


if __name__ == "__main__":
    main()

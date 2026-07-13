"""R48-H528 question-cluster routing: pre-shaped context, no PPR, for hot queries.

KMeans over the 7,534 KGFQuestion embeddings (k swept), per-cluster support =
union of member questions' ANSWERABLE_FROM chunk texts. Every eligible probe
is embedded (same entity space the question index lives in), routed to its
nearest centroid, and served the cluster's cached chunk union - criterion is
the prober instrument, tokens counted against a PAIRED baseline probe of the
shipped pipeline. H68 guard runs first per k: NMI(cluster, dominant source
doc of the question) - >= 0.5 KILLS the hypothesis in one pass.

Registered: docs/experiments/kgf-redesign-experiments.md R48-H528.
Bars: CONFIRMED if hot-subset recall >= 0.95 at <= 25% of baseline tokens AND
NMI < 0.4; KILLED if NMI >= 0.5 or hot recall < 0.90 at any budget.

Usage: python scripts/experiments/r48_h528_qcluster.py [config] [questions] [max]
Writes: reports/experiments/r48/h528-qcluster-<ts>.json
"""

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, "notebooks")
sys.path.insert(0, "scripts/experiments")
import tiktoken  # noqa: E402
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
KS = [40, 100, 200]
ENC = tiktoken.get_encoding("cl100k_base")


def toks(s: str) -> int:
    return len(ENC.encode(s))


def main() -> None:
    from sklearn.cluster import KMeans
    from sklearn.metrics import normalized_mutual_info_score

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bench = json.loads(QUESTIONS.read_text())
    st = load_settings(CONFIG)
    st.event_log = None
    with Foundry(st) as f:
        with f.driver.session() as s:
            qrows = s.run(
                "MATCH (q:KGFQuestion)-[:ANSWERABLE_FROM]->(c:Chunk)-[:PART_OF]->(d:KGFDocument) "
                "RETURN q.id AS id, q.embedding AS emb, "
                "collect(DISTINCT c.text) AS chunks, collect(DISTINCT d.name) AS docs"
            ).data()
        print(f"h528 {run_id}: {len(qrows)} questions with chunk provenance", flush=True)
        emb = np.array([r["emb"] for r in qrows], dtype=np.float32)
        emb /= np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9
        dom_doc = [Counter(r["docs"]).most_common(1)[0][0] for r in qrows]

        titles = ingested_titles(f, load_slices())
        full = [
            q for q in bench if gold_titles(q) and all(t in titles for t in gold_titles(q))
        ]
        eligible = full[:MAX] if MAX else full
        print(f"{len(eligible)} eligible probes", flush=True)

        # paired baseline + probe embeddings, computed once
        probes = []
        for k, q in enumerate(eligible):
            pe = Entity.create(q["question"][:80], types=["Query"], description=q["question"])
            qv = np.array(generate_embeddings([pe], st.embeddings)[0].embedding,
                          dtype=np.float32)
            qv /= np.linalg.norm(qv) + 1e-9
            res = f.probe(q["question"])
            probes.append({
                "q": q,
                "qv": qv,
                "base_pass": crit_pass(q, res["context_lines"]),
                "base_tokens": sum(toks(b) for b in res["context_lines"]),
            })
            if (k + 1) % 20 == 0:
                print(f"[{k+1}/{len(eligible)}] baselined", flush=True)

    results = []
    for K in KS:
        km = KMeans(n_clusters=K, n_init=4, random_state=42).fit(emb)
        labels = km.labels_
        nmi = normalized_mutual_info_score(labels, dom_doc)
        cluster_chunks: dict[int, set] = defaultdict(set)
        for lab, r in zip(labels, qrows):
            cluster_chunks[lab].update(r["chunks"])
        cents = km.cluster_centers_ / (
            np.linalg.norm(km.cluster_centers_, axis=1, keepdims=True) + 1e-9
        )
        rows = []
        for p in probes:
            sims = cents @ p["qv"]
            lab = int(np.argmax(sims))
            chunks = sorted(cluster_chunks[lab])
            rows.append({
                "cos": float(sims[lab]),
                "pass": crit_pass(p["q"], chunks),
                "tokens": sum(toks(c) for c in chunks),
                "base_pass": p["base_pass"],
                "base_tokens": p["base_tokens"],
            })
        # hot-subset curve: threshold at cosine percentiles
        curve = []
        coss = sorted((r["cos"] for r in rows), reverse=True)
        for frac in (0.25, 0.35, 0.45, 0.55, 0.75, 1.0):
            cut = coss[min(len(coss) - 1, int(frac * len(coss)) - 1)]
            hot = [r for r in rows if r["cos"] >= cut]
            curve.append({
                "coverage": round(len(hot) / len(rows), 3),
                "threshold": round(cut, 4),
                "hot_recall": round(sum(r["pass"] for r in hot) / len(hot), 4) if hot else None,
                "hot_base_recall": round(
                    sum(r["base_pass"] for r in hot) / len(hot), 4
                ) if hot else None,
                "token_fraction": round(
                    sum(r["tokens"] for r in hot) / max(1, sum(r["base_tokens"] for r in hot)), 3
                ) if hot else None,
            })
        results.append({
            "k": K,
            "nmi_cluster_doc": round(float(nmi), 4),
            "curve": curve,
            "all_recall": round(sum(r["pass"] for r in rows) / len(rows), 4),
            "base_recall": round(sum(r["base_pass"] for r in rows) / len(rows), 4),
        })
        print(f"k={K} NMI={nmi:.4f} all_recall={results[-1]['all_recall']} "
              f"base={results[-1]['base_recall']}", flush=True)

    out = {
        "run_id": run_id,
        "config": str(CONFIG),
        "n_questions": len(qrows),
        "n_probes": len(probes),
        "results": results,
        "bars": {"confirmed": "hot recall >= 0.95 at <= 0.25 tokens AND NMI < 0.4",
                 "killed": "NMI >= 0.5 OR hot recall < 0.90"},
    }
    outdir = Path("reports/experiments/r48")
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"h528-qcluster-{run_id}.json"
    path.write_text(json.dumps(out, indent=1))
    print("SUMMARY " + json.dumps({k: v for k, v in out.items() if k != "results"}), flush=True)
    for r in results:
        print(json.dumps(r), flush=True)
    print(f"WROTE {path}", flush=True)


if __name__ == "__main__":
    main()

"""R48-H515 safety gate: partition-restricted PPR severs multi-hop gold.

Offline, no LLM. Exports the live-relation Entity adjacency (SIMILAR_TO and
closed relations excluded, matching the engine's PPR projection minus Chunk
nodes - chunks carry no communityId; deviation recorded in the report). For
every eligible question: dense top-16 seeds via the shipped vector index, then
(a) cross-community gold fraction - do the gold-title carrier entities sit in
a different communityId than the top seed; (b) scipy personalized PageRank,
full graph vs transition matrix masked to the top seed's community, gold
carrier recall in top-N each way.

Registered: docs/experiments/kgf-redesign-experiments.md R48-H515.
Bars: community-scoped retrieval FALSIFIED if cross-community gold > 15% AND
masked recall < full recall at the 0.854-equivalent margin; lever also closes
if gold fraction < 5% AND masked == full (no savings available either way).

Usage: python scripts/experiments/r48_h515_mask.py [config] [questions.json] [max]
Writes: reports/experiments/r48/h515-mask-<ts>.json
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix

sys.path.insert(0, "notebooks")
sys.path.insert(0, "scripts/experiments")
from h158_measure import _norm  # noqa: E402
from r46_h499_screen import gold_titles, ingested_titles, load_slices  # noqa: E402

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
DAMPING = 0.85
ITERS = 50


def ppr(adj: csr_matrix, seed_idx: list[int], mask: np.ndarray | None = None) -> np.ndarray:
    """Power-iteration personalized PageRank; mask (bool per node) restricts
    the walk to masked-True nodes (transition rows/cols zeroed outside)."""
    n = adj.shape[0]
    if mask is not None:
        keepd = np.where(mask, 1.0, 0.0)
        adj = adj.multiply(keepd[:, None]).multiply(keepd[None, :]).tocsr()
        seed_idx = [i for i in seed_idx if mask[i]]
    if not seed_idx:
        return np.zeros(n)
    out = np.asarray(adj.sum(axis=1)).ravel()
    out[out == 0] = 1.0
    p = np.zeros(n)
    p[seed_idx] = 1.0 / len(seed_idx)
    r = p.copy()
    for _ in range(ITERS):
        r = (1 - DAMPING) * p + DAMPING * (adj.T @ (r / out))
    return r


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    questions = json.loads(QUESTIONS.read_text())
    st = load_settings(CONFIG)
    st.event_log = None
    top_k = st.graphrag.top_k
    top_n = st.graphrag.ppr_top_n
    rows = []
    with Foundry(st) as f:
        with f.driver.session() as s:
            ents = s.run(
                "MATCH (e:Entity) RETURN e.id AS id, e.name AS name, e.communityId AS cid"
            ).data()
            edges = s.run(
                "MATCH (a:Entity)-[r]-(b:Entity) WHERE r.valid_to IS NULL "
                "AND type(r) <> 'SIMILAR_TO' RETURN a.id AS a, b.id AS b"
            ).data()
        idx = {e["id"]: i for i, e in enumerate(ents)}
        cid = np.array([e["cid"] if e["cid"] is not None else -1 for e in ents])
        if (cid == -1).all():
            print("FATAL: no communityId - run gds.leiden first", flush=True)
            sys.exit(1)
        name_row = {_norm(e["name"]): idx[e["id"]] for e in ents if e.get("name")}
        n = len(ents)
        ij = np.array(
            [[idx[e["a"]], idx[e["b"]]] for e in edges if e["a"] in idx and e["b"] in idx]
        )
        adj = csr_matrix(
            (np.ones(len(ij)), (ij[:, 0], ij[:, 1])), shape=(n, n)
        )
        adj = ((adj + adj.T) > 0).astype(float).tocsr()
        print(f"h515 {run_id}: {n} entities, {adj.nnz} undirected edge slots, "
              f"{len(set(cid[cid >= 0]))} communities", flush=True)

        titles = ingested_titles(f, load_slices())
        full = [
            q for q in questions if gold_titles(q) and all(t in titles for t in gold_titles(q))
        ]
        eligible = full[:MAX] if MAX else full
        print(f"{len(eligible)} eligible questions", flush=True)

        from knowledge_graph_foundry.graph.graphrag import vector_query  # noqa: E402

        for k, q in enumerate(eligible):
            qid = q.get("_id") or q["question"][:60]
            golds = [name_row[t] for t in (_norm(t) for t in gold_titles(q)) if t in name_row]
            if not golds:
                rows.append({"id": qid, "skipped": "no gold carrier entity matched"})
                continue
            probe = Entity.create(q["question"][:80], types=["Query"], description=q["question"])
            qv = generate_embeddings([probe], st.embeddings)[0].embedding
            seeds = vector_query(f.driver, qv, st.graphrag.vector_index_name, top_k=top_k)
            seed_rows = [idx[s["id"]] for s in seeds if s["id"] in idx]
            if not seed_rows:
                rows.append({"id": qid, "skipped": "no seeds"})
                continue
            top_cid = int(cid[seed_rows[0]])
            cross = any(int(cid[g]) != top_cid for g in golds)

            full_r = ppr(adj, seed_rows)
            mask = cid == top_cid
            masked_r = ppr(adj, seed_rows, mask=mask)
            full_top = set(np.argsort(-full_r)[:top_n]) | set(seed_rows)
            masked_top = set(np.argsort(-masked_r)[:top_n]) | {
                i for i in seed_rows if mask[i]
            }
            row = {
                "id": qid,
                "gold_carriers": len(golds),
                "top_seed_cid": top_cid,
                "cross_community_gold": cross,
                "gold_in_full_ppr": all(g in full_top for g in golds),
                "gold_in_masked_ppr": all(g in masked_top for g in golds),
                "gold_in_dense_seeds": all(g in set(seed_rows) for g in golds),
            }
            rows.append(row)
            print(f"[{k+1}/{len(eligible)}] {qid} cross={cross} "
                  f"full={row['gold_in_full_ppr']} masked={row['gold_in_masked_ppr']}",
                  flush=True)

    scored = [r for r in rows if "skipped" not in r]
    summary = {
        "run_id": run_id,
        "config": str(CONFIG),
        "n": len(scored),
        "n_skipped": len(rows) - len(scored),
        "cross_community_gold_fraction": round(
            sum(r["cross_community_gold"] for r in scored) / len(scored), 4
        ) if scored else None,
        "full_ppr_gold_recall": round(
            sum(r["gold_in_full_ppr"] for r in scored) / len(scored), 4
        ) if scored else None,
        "masked_ppr_gold_recall": round(
            sum(r["gold_in_masked_ppr"] for r in scored) / len(scored), 4
        ) if scored else None,
        "dense_seed_gold_recall": round(
            sum(r["gold_in_dense_seeds"] for r in scored) / len(scored), 4
        ) if scored else None,
        "deviation": "offline scipy PPR over Entity-only live-rel adjacency; "
        "engine projection also carries Chunk nodes (no communityId)",
        "bars": {"cross_gt": 0.15, "negligible_lt": 0.05},
    }
    out = Path("reports/experiments/r48")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"h515-mask-{run_id}.json"
    path.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    print("SUMMARY " + json.dumps(summary), flush=True)
    print(f"WROTE {path}", flush=True)


if __name__ == "__main__":
    main()

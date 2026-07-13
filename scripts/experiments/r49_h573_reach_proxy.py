"""R49-H573: seed-rank margin beats PPR-mass as the cheap reachability proxy.

Executes the H479 carry-forward. Of three offline structural columns, which best
predicts ACTUAL query-time probe reachability?
  1. seed-rank margin  - query-personalized PPR RANK of the gold carrier relative
     to the ppr_top_n cutoff (margin = ppr_top_n - rank; scale-free across queries).
  2. seed-hop-distance - shortest unweighted graph hops from any dense seed to the
     gold carrier (BFS over the same live-rel Entity adjacency); reachability score
     = -hops (unreachable -> -inf).
  3. PPR-mass floor    - the raw personalized-PageRank MASS at the gold carrier
     (magnitude, not rank).

Ground truth (PRIMARY) = the ACTUAL end-to-end probe outcome: the h499 screen OFF
arm pass/fail (reports/experiments/bench/r46-h499-screen-20260713T072044Z.jsonl,
132 probes, 85 pass / 47 fail). Chosen because it is the real query-time reachability
the proxies must foresee, and it is independent of the offline PPR from which the
proxies are derived (non-circular). Per-carrier proxies roll up to the probe via the
BOTTLENECK carrier (a probe passes only if its hardest carrier is reachable):
min ppr-mass, min rank-margin, max hop-distance. SECONDARY ground truth reported for
robustness = per-carrier gold-in-dense-16 (H501 dense_hit convention).

AUC by rank statistics (Mann-Whitney; ties = 0.5) - no sklearn dependency.

Bars (registered): CONFIRMED seed-rank AUC >= 0.80 and PPR-mass lower by >= 0.10 (or
PPR-mass near-degenerate); KILLED if PPR-mass AUC >= seed-rank AUC.

Deviation: offline scipy PPR/BFS over Entity-only live-rel adjacency (h515 convention).

Usage: python scripts/experiments/r49_h573_reach_proxy.py [config] [questions.json] [max]
Writes: reports/experiments/r49/h573-reach-proxy-<ts>.json
"""

import json
import sys
from collections import deque
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
SCREEN = Path("reports/experiments/bench/r46-h499-screen-20260713T072044Z.jsonl")
DAMPING = 0.85
ITERS = 50
NO_PATH = 99  # hop distance when the carrier is unreachable from every seed


def ppr(adj, seed_idx, out):
    n = adj.shape[0]
    if not seed_idx:
        return np.zeros(n)
    p = np.zeros(n)
    p[seed_idx] = 1.0 / len(seed_idx)
    r = p.copy()
    for _ in range(ITERS):
        r = (1 - DAMPING) * p + DAMPING * (adj.T @ (r / out))
    return r


def bfs_hops(adj_rows, seed_idx, target, cap=6):
    """Shortest unweighted hops from any seed to target; cap-bounded BFS."""
    if target in seed_idx:
        return 0
    seen = set(seed_idx)
    frontier = deque((s, 0) for s in seed_idx)
    while frontier:
        node, d = frontier.popleft()
        if d >= cap:
            continue
        for nb in adj_rows[node]:
            if nb == target:
                return d + 1
            if nb not in seen:
                seen.add(nb)
                frontier.append((nb, d + 1))
    return NO_PATH


def auc(scores, labels):
    """AUC via Mann-Whitney U; higher score should mean positive label."""
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return None
    wins = 0.0
    for a in pos:
        for b in neg:
            wins += 1.0 if a > b else 0.5 if a == b else 0.0
    return round(wins / (len(pos) * len(neg)), 4)


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    questions = json.loads(QUESTIONS.read_text())
    byid = {q.get("_id"): q for q in questions}
    off = {json.loads(l)["id"]: json.loads(l)["pass"]
           for l in SCREEN.read_text().splitlines()
           if l.strip() and json.loads(l)["arm"] == "off"}
    st = load_settings(CONFIG)
    st.event_log = None
    top_k = st.graphrag.top_k
    top_n = st.graphrag.ppr_top_n

    with Foundry(st) as f:
        from knowledge_graph_foundry.graph.graphrag import vector_query  # noqa: E402
        with f.driver.session() as s:
            ents = s.run("MATCH (e:Entity) RETURN e.id AS id, e.name AS name").data()
            edges = s.run(
                "MATCH (a:Entity)-[r]-(b:Entity) WHERE r.valid_to IS NULL "
                "AND type(r) <> 'SIMILAR_TO' RETURN a.id AS a, b.id AS b"
            ).data()
        idx = {e["id"]: i for i, e in enumerate(ents)}
        name_row = {_norm(e["name"]): idx[e["id"]] for e in ents if e.get("name")}
        n = len(ents)
        ij = np.array([[idx[e["a"]], idx[e["b"]]] for e in edges
                       if e["a"] in idx and e["b"] in idx])
        adj = csr_matrix((np.ones(len(ij)), (ij[:, 0], ij[:, 1])), shape=(n, n))
        adj = ((adj + adj.T) > 0).astype(float).tocsr()
        out = np.asarray(adj.sum(axis=1)).ravel()
        out[out == 0] = 1.0
        adj_rows = {i: adj.indices[adj.indptr[i]:adj.indptr[i + 1]].tolist() for i in range(n)}
        print(f"h573 {run_id}: {n} entities, {adj.nnz} edge slots", flush=True)

        titles = ingested_titles(f, load_slices())
        eligible = [byid[i] for i in off if i in byid
                    and gold_titles(byid[i]) and all(t in titles for t in gold_titles(byid[i]))]
        eligible = eligible[:MAX] if MAX else eligible
        print(f"{len(eligible)} eligible probes", flush=True)

        carrier_rows = []  # per (probe, carrier)
        for k, q in enumerate(eligible):
            qid = q.get("_id")
            golds = [(t, name_row[_norm(t)]) for t in gold_titles(q) if _norm(t) in name_row]
            if not golds:
                continue
            probe = Entity.create(q["question"][:80], types=["Query"], description=q["question"])
            qv = generate_embeddings([probe], st.embeddings)[0].embedding
            seeds = vector_query(f.driver, qv, st.graphrag.vector_index_name, top_k=top_k)
            seed_rows = [idx[x["id"]] for x in seeds if x["id"] in idx]
            r = ppr(adj, seed_rows, out)
            order = np.argsort(-r)
            rank_of = {int(node): i for i, node in enumerate(order)}
            seed_set = set(seed_rows)
            for t, crow in golds:
                rank = rank_of[crow]
                carrier_rows.append({
                    "probe": qid, "carrier": t,
                    "rank_margin": int(top_n - rank),        # higher = deeper inside cutoff
                    "ppr_mass": float(r[crow]),               # raw mass
                    "hop_distance": int(bfs_hops(adj_rows, seed_rows, crow)),
                    "dense_hit": bool(crow in seed_set),      # secondary per-carrier truth
                    "off_pass": bool(off.get(qid)),
                })
            print(f"[{k+1}/{len(eligible)}] {qid[:12]} pass={off.get(qid)} "
                  f"carriers={len(golds)}", flush=True)

    # --- per-probe bottleneck rollup --------------------------------------
    by_probe = {}
    for r in carrier_rows:
        by_probe.setdefault(r["probe"], []).append(r)
    probe_rows = []
    for qid, rs in by_probe.items():
        probe_rows.append({
            "probe": qid,
            "rank_margin": min(r["rank_margin"] for r in rs),        # worst carrier
            "neg_hop": -max(r["hop_distance"] for r in rs),           # worst carrier
            "ppr_mass": min(r["ppr_mass"] for r in rs),               # worst carrier
            "off_pass": rs[0]["off_pass"],
        })

    y = [r["off_pass"] for r in probe_rows]
    auc_probe = {
        "seed_rank_margin": auc([r["rank_margin"] for r in probe_rows], y),
        "seed_hop_distance": auc([r["neg_hop"] for r in probe_rows], y),
        "ppr_mass_floor": auc([r["ppr_mass"] for r in probe_rows], y),
    }
    # secondary: per-carrier vs dense_hit
    yc = [r["dense_hit"] for r in carrier_rows]
    auc_carrier = {
        "seed_rank_margin": auc([r["rank_margin"] for r in carrier_rows], yc),
        "seed_hop_distance": auc([-r["hop_distance"] for r in carrier_rows], yc),
        "ppr_mass_floor": auc([r["ppr_mass"] for r in carrier_rows], yc),
    }

    sr = auc_probe["seed_rank_margin"]
    pm = auc_probe["ppr_mass_floor"]
    clauses = {
        "seed_rank_auc_ge_0.80": bool(sr is not None and sr >= 0.80),
        "ppr_mass_lower_by_0.10_or_degenerate": bool(
            sr is not None and pm is not None and (sr - pm >= 0.10 or pm <= 0.55)),
        "ppr_mass_not_ge_seed_rank": bool(sr is not None and pm is not None and pm < sr),
    }
    if sr is None or pm is None:
        verdict = "INCONCLUSIVE"
    elif pm >= sr:
        verdict = "KILLED"
    elif sr >= 0.80 and (sr - pm >= 0.10 or pm <= 0.55):
        verdict = "CONFIRMED"
    else:
        verdict = "INDETERMINATE"

    summary = {
        "run_id": run_id, "config": str(CONFIG),
        "n_probes": len(probe_rows), "n_carriers": len(carrier_rows),
        "off_pass": int(sum(y)), "off_fail": int(len(y) - sum(y)),
        "ground_truth_primary": "h499 OFF-arm probe pass/fail (bottleneck rollup)",
        "auc_per_proxy": auc_probe,
        "auc_per_carrier_vs_dense_hit_secondary": auc_carrier,
        "clauses": clauses, "proposed_verdict": verdict,
        "deviation": "offline scipy PPR/BFS over Entity-only live-rel adjacency (h515 "
        "convention); rank-margin = ppr_top_n - PPR rank; hop cap 6 (unreachable=99)",
        "bars": {"seed_rank_ge": 0.80, "mass_margin": 0.10},
    }
    outdir = Path("reports/experiments/r49")
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"h573-reach-proxy-{run_id}.json"
    path.write_text(json.dumps(
        {"summary": summary, "probe_rows": probe_rows, "carrier_rows": carrier_rows}, indent=1))
    print("SUMMARY " + json.dumps(summary), flush=True)
    print(f"WROTE {path}", flush=True)


if __name__ == "__main__":
    main()

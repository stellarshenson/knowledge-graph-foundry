"""R58-H652 Query-node reset - a query pseudo-node walked as an additional PPR source.

Mechanism: add a query pseudo-node wired to (linked max-gap anchors u dense seeds).
Walk PPR with an ASYMMETRIC reset distribution (HippoRAG-2 discipline): SMALL reset
mass eps (~0.05) on the query node, (1-eps) on the original PPR seeds. The query
node's star topology makes the anchor/seed union internally 2-hop connected, so PPR
mass reaches bridge carriers within 2 hops of the union that the anchor-only reset
under-weights. The region is still PPR-top15 capped (the BASELINE cap rule) so this
isolates the query-node lever from H651's cap widening.

INVALID BY CONSTRUCTION (H597 fuse-add kill) if the query node is injected into the
SEED slots with seed-equal mass. Here it receives eps reset mass only, never a seed
slot - guarded explicitly.

FREE offline replay on the frozen 132 OFF-arm probes. Reuses the r58_h651 build().
Population = the 110 dense-missed carrier rows (atlas dense_hit=False). Attribution
vs H651 mandatory (overlap census of recovered carriers).

Writes:
  reports/experiments/r58/h652-query-node-<ts>.json + .md
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix

ROOT = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry")
sys.path.insert(0, str(ROOT / "scripts/experiments"))

import r47_h582_embedder_swap as H          # noqa: E402
import r58_h651_region_cap as H651          # noqa: E402

OUT = ROOT / "reports/experiments/r58"
PPR_TOP_N = 15
DAMPING, ITERS = H.DAMPING, H.ITERS
EPS_SWEEP = [0.02, 0.05, 0.10]
EPS_OPERATING = 0.05
JOIN_VERSION = H651.JOIN_VERSION


def aug_ppr(adj, out_deg, n, ppr_seeds, qnbrs, eps):
    """PPR on the graph augmented with a query node (index n) wired to qnbrs.
    Reset: eps on query node, (1-eps) uniform on ppr_seeds. Returns r over 0..n-1."""
    if not qnbrs:
        # degenerate: fall back to plain PPR from ppr_seeds
        return H.ppr(adj, out_deg, ppr_seeds, n)
    co = adj.tocoo()
    rows = list(co.row)
    cols = list(co.col)
    data = list(co.data)
    for s in qnbrs:
        rows += [n, s]
        cols += [s, n]
        data += [1.0, 1.0]
    A = coo_matrix((data, (rows, cols)), shape=(n + 1, n + 1)).tocsr()
    od = np.asarray(A.sum(axis=1)).ravel()
    od[od == 0] = 1.0
    p = np.zeros(n + 1)
    if ppr_seeds:
        p[ppr_seeds] = (1.0 - eps) / len(ppr_seeds)
    p[n] = eps
    r = p.copy()
    for _ in range(ITERS):
        r = (1 - DAMPING) * p + DAMPING * (A.T @ (r / od))
    return r[:n]


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731
    ckpt = OUT / f"h652-query-node-{run_id}.checkpoint.jsonl"
    cf = ckpt.open("w")

    def chk(tag, obj):
        cf.write(json.dumps({"tag": tag, **obj}, default=str) + "\n")
        cf.flush()

    D = H651.build()
    S = D["S"]
    n = D["n"]
    adj, out_deg = D["adj"], D["out_deg"]
    off_ids = D["off_ids"]
    dense_seeds = D["dense_seeds"]
    anchors_maxgap = D["anchors_maxgap"]
    reset_region = D["reset_region"]
    reset_region_wide = D["reset_region_wide"]
    atlas_rows = D["atlas_rows"]

    # GUARD: query node gets reset mass, never a seed slot (H597 fuse-add fence)
    guard = ("query node index=n receives eps reset mass; ppr_seeds slots are the "
             "ORIGINAL anchors/dense-seeds only - the query node is NEVER appended to "
             "ppr_seeds. Verified by construction in aug_ppr().")
    chk("h597_guard", {"note": guard})

    # ---- population: 110 dense-missed carrier rows -------------------------
    miss_rows = [r for r in atlas_rows if not r["dense"]["dense_hit"]]
    miss_node_rows = [r for r in miss_rows if r["eff_idx"] is not None]  # recoverable pool
    n_absent = len(miss_rows) - len(miss_node_rows)
    log(f"miss population: {len(miss_rows)} dense-missed rows "
        f"({len(miss_node_rows)} with node, {n_absent} absent-no-node)")

    # baseline-walk & H651 recovery over the 110 (by node membership)
    def recovers(region_of, rows):
        s = set()
        for r in rows:
            eff = r["eff_idx"]
            if eff is not None and eff in region_of[r["probe"]]:
                s.add((r["probe"], r["carrier"]))
        return s

    base_walk_set = recovers(reset_region, miss_rows)
    h651_set = recovers(reset_region_wide, miss_rows)
    log(f"baseline walk recovers {len(base_walk_set)}/110 ; H651 recovers {len(h651_set)}/110")

    # ---- H652 region per eps ----------------------------------------------
    def build_query_regions(eps):
        region_q = {}
        for pid in off_ids:
            anc = anchors_maxgap.get(pid, set())
            ds = dense_seeds[pid]
            ppr_seeds = list(anc) if anc else list(ds)
            qnbrs = sorted(set(anc) | set(ds))          # query node wired to anchors u seeds
            r = aug_ppr(adj, out_deg, n, ppr_seeds, qnbrs, eps)
            top15 = set(np.argsort(-r)[:PPR_TOP_N].tolist())
            region_q[pid] = top15 | set(ppr_seeds) | ds  # BASELINE cap rule (top15), not widened
        return region_q

    # regression surface: ALL carrier rows the baseline walk recovers (hit set protection)
    all_node_rows = [r for r in atlas_rows if r["eff_idx"] is not None]
    base_all_recov = recovers(reset_region, all_node_rows)

    sweep = {}
    for eps in EPS_SWEEP:
        region_q = build_query_regions(eps)
        h652_set = recovers(region_q, miss_rows)
        # paired vs baseline walk on the 110
        gained = h652_set - base_walk_set
        lost = base_walk_set - h652_set
        net = len(gained) - len(lost)
        # non-redundancy vs H651 (carriers H652 recovers that H651 does not)
        nonredundant = h652_set - h651_set
        # regression on the full recovered (hit) set
        q_all_recov = recovers(region_q, all_node_rows)
        hit_regressions = base_all_recov - q_all_recov
        sweep[str(eps)] = {
            "recovered_of_110": len(h652_set),
            "gained_vs_base_walk": sorted(gained),
            "lost_vs_base_walk": sorted(lost),
            "net_vs_base_walk": net,
            "nonredundant_vs_h651": sorted(nonredundant),
            "n_nonredundant_vs_h651": len(nonredundant),
            "hit_set_regressions": sorted(hit_regressions),
            "n_hit_set_regressions": len(hit_regressions),
        }
        log(f"eps={eps}: recov {len(h652_set)}/110 net {net:+d} "
            f"nonredundant_vs_h651 {len(nonredundant)} hit-regr {len(hit_regressions)}")
        chk("eps", {"eps": eps, **sweep[str(eps)]})

    op = sweep[str(EPS_OPERATING)]
    net_op = op["net_vs_base_walk"]
    nonredun_op = op["n_nonredundant_vs_h651"]
    regr_op = op["n_hit_set_regressions"]

    if net_op >= 5 and regr_op == 0 and nonredun_op >= 2:
        verdict = "CONFIRMED"
    elif net_op <= 0 or nonredun_op == 0:
        verdict = "KILLED"
    else:
        verdict = "INDETERMINATE"

    # composition census vs H651
    composition = {
        "h651_recovers_of_110": sorted(h651_set),
        "n_h651": len(h651_set),
        "h652_op_recovers_of_110": sorted(recovers(build_query_regions(EPS_OPERATING), miss_rows)),
        "overlap_h651_h652_op": sorted(h651_set & recovers(build_query_regions(EPS_OPERATING), miss_rows)),
        "h652_only_op": op["nonredundant_vs_h651"],
    }

    summ = {
        "hypothesis": "R58-H652", "run_id": run_id, "join_version": JOIN_VERSION,
        "substrate": ("medium 2wiki frozen H582 cache (6,626 entities); FREE numpy/scipy, "
                      "no GPU/LLM/Neo4j/net; reuses r58_h651 build()"),
        "substrate_caveat": "frozen 6,626-entity cache, not the 7,575 live re-ingest",
        "h597_fuse_add_guard": guard,
        "mechanism": ("query pseudo-node (index n) wired to (maxgap anchors u dense seeds); "
                      "asymmetric reset eps on the query node, (1-eps) on original ppr_seeds; "
                      "region = PPR-top15 cap (baseline rule) to isolate from H651"),
        "population": {"dense_missed_rows": len(miss_rows),
                       "with_node_recoverable": len(miss_node_rows),
                       "absent_no_node": n_absent},
        "baseline_walk_recovers_of_110": len(base_walk_set),
        "h651_recovers_of_110": len(h651_set),
        "eps_sweep": sweep,
        "operating_point": {"eps": EPS_OPERATING, **op},
        "composition_vs_h651": composition,
        "verdict_recommendation": verdict,
        "bar": ("CONFIRMED if net >= +5 carriers paired (vs baseline walk) with zero hit-set "
                "regressions AND non-redundant with H651 (adds >=2 carriers H651 does not); "
                "KILLED at net <= 0 or full redundancy"),
        "caveats": [
            "recovery = carrier node inside the region (walk-level reachability); render/EM not "
            "simulated (FREE). Paired against baseline-walk recovery on the same 110 rows.",
            "the 12 absent-no-node carriers are unrecoverable by any walk (extraction defect).",
            "frozen 6,626-entity substrate, not the 7,575 live re-ingest.",
        ],
        "artifacts": {"json": str(OUT / f"h652-query-node-{run_id}.json"),
                      "brief": str(OUT / f"h652-query-node-{run_id}.md"),
                      "checkpoint": str(ckpt),
                      "script": "scripts/experiments/r58_h652_query_node.py"},
    }
    (OUT / f"h652-query-node-{run_id}.json").write_text(json.dumps(summ, indent=1, default=str))

    brief = f"""# R58-H652 query-node reset - brief

**Verdict recommendation: {verdict}**  (run {run_id}, join {JOIN_VERSION})

Mechanism: query pseudo-node wired to (maxgap anchors u dense seeds), asymmetric reset
mass eps on the query node ((1-eps) on original seeds), PPR-top15 baseline cap (isolates
from H651's cap widening). H597 fuse-add guard: query node is reset mass, never a seed slot.

## Population
- 110 dense-missed carrier rows; {len(miss_node_rows)} with a node, {n_absent} absent-no-node
- baseline walk recovers {len(base_walk_set)}/110 ; H651 recovers {len(h651_set)}/110

## Operating point eps={EPS_OPERATING} (JUDGED)
- recovered: {op['recovered_of_110']}/110
- **net vs baseline walk: {net_op:+d}** (gained {len(op['gained_vs_base_walk'])}, lost {len(op['lost_vs_base_walk'])})
- **non-redundant vs H651: {nonredun_op}** carriers H651 does not recover
- **hit-set regressions: {regr_op}**
- bar: net >= +5 AND zero regressions AND non-redundant >= 2

## eps sweep (net vs base walk / non-redundant vs H651 / hit-regr)
""" + "\n".join(
        f"- eps={e}: recov {sweep[str(e)]['recovered_of_110']}/110, "
        f"net {sweep[str(e)]['net_vs_base_walk']:+d}, "
        f"nonredundant {sweep[str(e)]['n_nonredundant_vs_h651']}, "
        f"hit-regr {sweep[str(e)]['n_hit_set_regressions']}"
        for e in EPS_SWEEP
    ) + f"""

## Composition vs H651
- H651 recovers {len(h651_set)}/110; H652@{EPS_OPERATING} overlaps on
  {len(composition['overlap_h651_h652_op'])}; H652-only: {composition['h652_only_op']}

## Caveats
- walk-level reachability recovery (render/EM not simulated, FREE); paired on the same 110 rows.
- frozen 6,626-entity substrate, not the 7,575 live re-ingest.
"""
    (OUT / f"h652-query-node-{run_id}.md").write_text(brief)
    cf.close()
    log(f"\nVERDICT {verdict} | net@{EPS_OPERATING} {net_op:+d} | "
        f"nonredundant {nonredun_op} | hit-regr {regr_op}")
    log(f"wrote {OUT}/h652-query-node-{run_id}.json")


if __name__ == "__main__":
    main()

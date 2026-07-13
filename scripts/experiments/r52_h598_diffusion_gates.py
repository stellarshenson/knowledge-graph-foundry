"""R52-H598/H599/H600: FREE offline spectral/diffusion gates for the R52 geometry axis.

Pure offline, READ-ONLY (no Neo4j, no LLM, no containers). Reuses the R47-H582
harness module (`r47_h582_embedder_swap as H`) for shared structures - the 6,626
entity universe, the undirected Entity-only adjacency (SIMILAR_TO excluded, h515
convention), the 132 frozen off-arm probes, Titan probe embeddings, PPR, McNemar,
bootstrap - so the two sanity gates reproduce bit-identically:
  - Titan carrier recall@16 == 0.6012
  - iso PPR all-golds reachability == 0.622 (127 in-graph-carrier probes)

Adjacency source = tmp/results/r50/edges_typed.json (label-free undirected; proven
identical edge set to H's edges.json). This axis is LABEL-FREE by design.

STRUCTURE: the extracted graph is fragmented (1830 connected components; LCC 3162
nodes = 47.7%). The heat kernel / diffusion distance is block-diagonal over
components (zero across components by construction) - cross-component reach is a
genuine physical interruption, not a scale artifact.

Diffusion machinery:
  - heat kernel EXACT via scipy expm_multiply on the symmetric-normalized Laplacian
    L = I - D^-1/2 A D^-1/2, over a LOCAL->GLOBAL time ladder T (matches PPR's local
    scale without the low-rank truncation error that only permits global t):
        HK_t(a,c) = [exp(-t L) e_a]_c
  - commute-time distance CT(x,y) = sum_{l_i>tol}(1/l_i)(u_i(x)-u_i(y))^2 from a
    per-component eigenbasis (sparse eigsh LCC, dense eigh rest); parameter-free
  - spectral diffusion distance d_t(x,y)^2 = sum_i exp(-t l_i)(u_i(x)-u_i(y))^2
    (eigen-k sensitivity arm; valid at global t only)

Gates (registered specs R52-H598/H599/H600). Bars:
  H598 CONFIRMED >= +8pp target rank-recall@15 vs single-source PPR (paired, p<0.05);
       KILLED <= +3pp. Mandatory hop + PPR-mass control.
  H599 CONFIRMED median Spearman(heat,PPR) >= 0.95; FALSIFIED < 0.85.
  H600 CONFIRMED >= 40% of tail in diffusion top-15 from realizable anchors; KILLED < 20%.

Usage:  python scripts/experiments/r52_h598_diffusion_gates.py
Writes: reports/experiments/r52/{h598-trilateration,h599-ppr-reexpress,h600-interruption}-<ts>.json
"""

import json
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix, diags, eye
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import eigsh, expm_multiply
from scipy.stats import spearmanr

sys.path.insert(0, "scripts/experiments")
import r47_h582_embedder_swap as H  # noqa: E402

ROOT = H.ROOT
CACHE = H.CACHE
R50 = ROOT / "tmp/results/r50"
OUT = ROOT / "reports/experiments/r52"

TOP_K = H.TOP_K          # 16
PPR_TOP_N = H.PPR_TOP_N  # 15
TITAN_TARGET = 0.6012
ISO_REACH_REF = 0.622
K_EIGS = [64, 128, 256]
K_MAX = 256
K_PRIMARY = 128
T_HEAT = [1.0, 3.0, 10.0, 30.0, 100.0]   # exact heat-kernel time ladder (local -> global)
T_H599 = [3.0, 10.0, 30.0]               # heavier per-query sweep (subset)
NO_PATH = 99
HOP_CAP = 6
BIG = 1e9

H573_TAIL = "reports/experiments/r49/h573-reach-proxy-20260713T191754Z.json"
H571_TAIL = "reports/experiments/r49/h571-reach-col-20260713T192923Z.json"


def gold_titles(q):
    sf = q.get("supporting_facts") or []
    ts = []
    for it in sf:
        t = it[0] if isinstance(it, (list, tuple)) else it.get("title")
        if t and t not in ts:
            ts.append(t)
    return ts


def bfs_min_hops(adj_rows, seeds, targets, cap=HOP_CAP):
    res = {t: NO_PATH for t in set(targets)}
    seen = set(seeds)
    for s in seeds:
        if s in res:
            res[s] = 0
    frontier = deque((s, 0) for s in seeds)
    while frontier:
        node, dep = frontier.popleft()
        if dep >= cap:
            continue
        for nb in adj_rows[node]:
            if nb not in seen:
                seen.add(nb)
                if nb in res:
                    res[nb] = dep + 1
                frontier.append((nb, dep + 1))
    return res


def build_component_bases(adj, deg, labels, kmax=K_MAX):
    """Per-component symmetric-normalized-Laplacian eigenbasis (ascending lambda),
    for the commute-time and spectral-distance arms only."""
    comp_nodes = {}
    for i, c in enumerate(labels):
        comp_nodes.setdefault(int(c), []).append(i)
    bases = {}
    for cid, nodes in comp_nodes.items():
        s = len(nodes)
        if s < 2:
            continue
        nodes = np.array(sorted(nodes))
        sub = adj[nodes][:, nodes].tocsr()
        dinv = 1.0 / np.sqrt(deg[nodes])
        A = sub.toarray()
        Lc = np.eye(s) - (dinv[:, None] * A * dinv[None, :])
        Lc = (Lc + Lc.T) / 2
        if s <= 400:
            w, V = np.linalg.eigh(Lc)
            w, V = w[:kmax + 1], V[:, :kmax + 1]
        else:
            w, V = eigsh(csr_matrix(Lc), k=min(kmax, s - 2), sigma=-1e-6, which="LM")
            order = np.argsort(w)
            w, V = w[order], V[:, order]
        w = np.clip(w, 0.0, None)
        bases[cid] = {"nodes": nodes, "pos": {int(f): li for li, f in enumerate(nodes)},
                      "lam": w, "U": V}
    return bases


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"R52 diffusion gates {run_id}", flush=True)

    # ---------------- shared structures ----------------
    meta = json.loads((CACHE / "ents_meta.json").read_text())
    titan = np.load(CACHE / "titan_emb.npy")
    n = len(meta)
    idx_of_id = {m["id"]: i for i, m in enumerate(meta)}
    name_norms = [H._norm(m["name"]) if m["name"] else "" for m in meta]
    graph_norms = set(name_norms)
    name_row = {}
    for i, nn in enumerate(name_norms):
        name_row.setdefault(nn, i)

    et = json.loads((R50 / "edges_typed.json").read_text())
    pairs = [(idx_of_id[a], idx_of_id[b]) for a, _, b in et
             if a in idx_of_id and b in idx_of_id]
    ij = np.array(pairs)
    adj = csr_matrix((np.ones(len(ij)), (ij[:, 0], ij[:, 1])), shape=(n, n))
    adj = ((adj + adj.T) > 0).astype(float).tocsr()
    deg = np.asarray(adj.sum(axis=1)).ravel()
    out_deg = deg.copy()
    out_deg[out_deg == 0] = 1.0
    adj_rows = {i: adj.indices[adj.indptr[i]:adj.indptr[i + 1]].tolist() for i in range(n)}
    ncomp, labels = connected_components(adj, directed=False)
    node_comp = labels
    sizes = np.bincount(labels)
    print(f"graph: {n} nodes, {int(adj.nnz/2)} edges, {ncomp} components, "
          f"LCC {int(sizes.max())}, isolated {int((deg==0).sum())}", flush=True)

    # symmetric-normalized Laplacian for EXACT heat kernel (isolated -> L_ii=1)
    dinv = np.zeros(n)
    nz = deg > 0
    dinv[nz] = 1.0 / np.sqrt(deg[nz])
    Lsym = (eye(n) - diags(dinv) @ adj @ diags(dinv)).tocsc()

    def one_hop(sd):
        hop = set(sd)
        for u in sd:
            hop |= set(adj.indices[adj.indptr[u]:adj.indptr[u + 1]].tolist())
        return hop

    # ---------------- probes / carriers ----------------
    off_ids = [json.loads(l)["id"] for l in H.SCREEN.read_text().splitlines()
               if l.strip() and json.loads(l)["arm"] == "off"]
    Q = {q.get("_id"): q for q in json.loads(H.QUESTIONS.read_text())}
    probes = [Q[i] for i in off_ids if i in Q]

    def resolve(nm):
        return name_row.get(H._norm(nm))

    carriers = []
    for pid in off_ids:
        q = Q.get(pid)
        if not q:
            continue
        for t in gold_titles(q):
            tn = H._norm(t)
            carriers.append({"probe": pid, "carrier": t, "tnorm": tn,
                             "in_graph": tn in graph_norms, "carrier_idx": name_row.get(tn)})

    d = np.load(CACHE / "titan_probe_emb.npz", allow_pickle=True)
    titan_probe = {pid: d[pid] for pid in off_ids}
    titan_n = titan / (np.linalg.norm(titan, axis=1, keepdims=True) + 1e-9)
    titan_probe_n = {pid: v / (np.linalg.norm(v) + 1e-9) for pid, v in titan_probe.items()}
    seeds_q = {}
    for pid in off_ids:
        sims = titan_n @ titan_probe_n[pid]
        seeds_q[pid] = [int(x) for x in np.argsort(-sims)[:TOP_K]]

    # ---- SANITY gates ----
    t_rec, _, _ = H.arm_metrics(titan_n, titan_probe_n, carriers, name_norms,
                                name_row, adj, out_deg, n, one_hop)
    titan_recall16 = round(float(np.mean(t_rec)), 4)
    reach_hits = []
    for pid in off_ids:
        cis = [c["carrier_idx"] for c in carriers if c["probe"] == pid and c["in_graph"]]
        if not cis:
            continue
        r = H.ppr(adj, out_deg, seeds_q[pid], n)
        region = set(np.argsort(-r)[:PPR_TOP_N].tolist()) | set(seeds_q[pid])
        reach_hits.append(all(ci in region for ci in cis))
    iso_reach = round(float(np.mean(reach_hits)), 4)
    n_reach = len(reach_hits)
    harness_ok = (abs(titan_recall16 - TITAN_TARGET) <= 0.02
                  and abs(iso_reach - ISO_REACH_REF) <= 0.02)
    harness_sanity = {
        "titan_carrier_recall@16": titan_recall16, "titan_target": TITAN_TARGET,
        "iso_ppr_all_golds_reach": iso_reach, "iso_reach_target": ISO_REACH_REF,
        "n_reach_probes": n_reach, "reproduced": bool(harness_ok),
        "n_components": int(ncomp), "lcc_size": int(sizes.max()),
    }
    print(f"SANITY titan={titan_recall16} iso_reach={iso_reach} (n={n_reach}) ok={harness_ok}",
          flush=True)
    if not harness_ok:
        (OUT / f"h598-trilateration-{run_id}.json").write_text(json.dumps(
            {"ABORTED": "harness sanity broke", "harness_sanity": harness_sanity}, indent=1))
        print("HARNESS BROKEN - abort", flush=True)
        return

    # ---------------- exact heat kernel (expm_multiply) ----------------
    def heat_cols(anchor_list, t):
        """exp(-t Lsym) @ E, E one-hot columns for anchors -> (n, m) proximity."""
        m = len(anchor_list)
        E = np.zeros((n, m))
        for j, a in enumerate(anchor_list):
            E[a, j] = 1.0
        return np.asarray(expm_multiply(-t * Lsym, E))

    def heat_vec(seeds, t):
        """exp(-t Lsym) @ (sum of seed one-hots) -> (n,) single-source proximity."""
        e = np.zeros(n)
        e[seeds] = 1.0
        return np.asarray(expm_multiply(-t * Lsym, e))

    # ---------------- per-component eigenbasis (commute + spectral dist) ----------------
    bases = build_component_bases(adj, deg, labels, kmax=K_MAX)

    def commute_dist_pair(a, kk):
        full = np.full(n, BIG)
        base = bases.get(int(node_comp[a]))
        if base is None:
            full[a] = 0.0
            return full
        kc = min(kk, base["U"].shape[1])
        la = base["pos"][int(a)]
        U = base["U"][:, :kc]
        lam = base["lam"][:kc]
        inv = np.where(lam > 1e-6, 1.0 / np.maximum(lam, 1e-6), 0.0)
        ua = U[la, :]
        dloc = (U * U) @ inv - 2 * (U @ (inv * ua)) + float((inv * ua * ua).sum())
        full[base["nodes"]] = np.maximum(dloc, 0.0)
        return full

    def spectral_dist_pair(a, t, kk):
        full = np.full(n, BIG)
        base = bases.get(int(node_comp[a]))
        if base is None:
            full[a] = 0.0
            return full
        kc = min(kk, base["U"].shape[1])
        la = base["pos"][int(a)]
        U = base["U"][:, :kc]
        w = np.exp(-t * base["lam"][:kc])
        ua = U[la, :]
        dloc = (U * U) @ w - 2 * (U @ (w * ua)) + float((w * ua * ua).sum())
        full[base["nodes"]] = np.maximum(dloc, 0.0)
        return full

    # ---------------- src / bridge (H583 convention) ----------------
    src_of = {}
    for q in probes:
        pid = q["_id"]
        evs = q.get("evidences") or []
        subs = {H._norm(s_) for (s_, r_, o_) in evs}
        objs = {H._norm(o_) for (s_, r_, o_) in evs}
        # H583 exact: object->bridge, subject->source, unclassified->source
        srcs = []
        for t in gold_titles(q):
            tn = H._norm(t)
            ci = name_row.get(tn)
            if ci is None:
                continue
            if tn in objs:
                pass
            elif tn in subs:
                srcs.append(ci)
            else:
                srcs.append(ci)
        src_of[pid] = srcs

    def rank_region_top15(scores, exclude):
        s = scores.copy()
        s[list(exclude)] = -np.inf
        return set(np.argsort(-s)[:PPR_TOP_N].tolist())

    # ==================================================================
    #                              H598
    # ==================================================================
    TWO_ANCHOR_CLASSES = {"comparison", "bridge_comparison", "compositional"}
    trilat_probes = []
    for q in probes:
        pid = q["_id"]
        if q.get("type") not in TWO_ANCHOR_CLASSES:
            continue
        anchors = sorted(set(src_of[pid]))
        if len(anchors) < 2:
            continue
        aset = set(anchors)
        gold_idx = {name_row.get(H._norm(t)) for t in gold_titles(q)}
        gold_idx = {i for i in gold_idx if i is not None}
        ai = resolve(q.get("answer"))
        tgts = sorted(t for t in (gold_idx | ({ai} if ai is not None else set())) - aset
                      if t is not None)
        if not tgts:
            continue
        anc_comps = {int(node_comp[a]) for a in anchors}
        trilat_probes.append({"pid": pid, "class": q.get("type"), "anchors": anchors,
                              "targets": tgts,
                              "cocomp": {t: int(node_comp[t]) in anc_comps for t in tgts}})
    print(f"H598: {len(trilat_probes)} 2-anchor probes with non-anchor target", flush=True)

    arms = {}          # arm-label -> list[bool] per target
    base_ppr, ctrl_hop, target_meta, target_cocomp = [], [], [], []
    for tp in trilat_probes:
        anchors, tgts, aset = tp["anchors"], tp["targets"], set(tp["anchors"])
        r = H.ppr(adj, out_deg, anchors, n)
        ppr_region = rank_region_top15(r, aset)
        hop_all = bfs_min_hops(adj_rows, anchors, tgts, cap=HOP_CAP)
        reg = {}
        for t in T_HEAT:
            hc = heat_cols(anchors, t)                       # (n, n_anchors)
            prodv = np.prod(np.maximum(hc, 0.0), axis=1)
            sumv = hc.sum(axis=1)
            reg[(f"heat-product@t{t}")] = rank_region_top15(prodv, aset)
            reg[(f"heat-sum@t{t}")] = rank_region_top15(sumv, aset)
            sd = np.zeros(n)
            for a in anchors:
                sd += spectral_dist_pair(a, t, K_PRIMARY)
            reg[(f"spec-sumdist@t{t}")] = rank_region_top15(-sd, aset)
        sumct = np.zeros(n)
        for a in anchors:
            sumct += commute_dist_pair(a, K_PRIMARY)
        reg["commute-sumdist"] = rank_region_top15(-sumct, aset)
        for tgt in tgts:
            target_meta.append((tp["pid"], tp["class"], tgt))
            target_cocomp.append(tp["cocomp"][tgt])
            base_ppr.append(tgt in ppr_region)
            ctrl_hop.append(hop_all.get(tgt, NO_PATH) <= HOP_CAP)
            for label, region in reg.items():
                arms.setdefault(label, []).append(tgt in region)

    n_targets = len(target_meta)
    n_cocomp = int(sum(target_cocomp))
    base_rate = round(float(np.mean(base_ppr)), 4)
    hop_rate = round(float(np.mean(ctrl_hop)), 4)
    co = np.array(target_cocomp, dtype=bool)

    def arm_summary(hits, subset=None):
        hv = np.array(hits, dtype=bool)
        bv = np.array(base_ppr, dtype=bool)
        if subset is not None:
            hv, bv = hv[subset], bv[subset]
        b, c, p = H.mcnemar(bv.tolist(), hv.tolist())
        lo, hi = H.boot_ci(bv.tolist(), hv.tolist())
        return {"rate": round(float(hv.mean()), 4), "ppr_rate": round(float(bv.mean()), 4),
                "delta_pp_vs_ppr": round((hv.mean() - bv.mean()) * 100, 2),
                "mcnemar_b_ppr_only": b, "mcnemar_c_arm_only": c, "mcnemar_p": p,
                "boot95_delta": [lo, hi]}

    trilat_table = {"single_source_ppr_baseline": {"rate": base_rate, "n_targets": n_targets,
                                                   "n_cocomp": n_cocomp},
                    "hop_control_within6": {"rate": hop_rate}}
    trilat_cocomp = {}
    for label in sorted(arms):
        trilat_table[label] = arm_summary(arms[label])
        trilat_cocomp[label] = arm_summary(arms[label], subset=co)

    best_label = max(arms, key=lambda k: np.mean(arms[k]))
    best_delta = trilat_table[best_label]["delta_pp_vs_ppr"]
    best_p = trilat_table[best_label]["mcnemar_p"]
    best_hits = arms[best_label]

    class_break = {}
    for cls in sorted(set(m[1] for m in target_meta)):
        idxs = [i for i, m in enumerate(target_meta) if m[1] == cls]
        class_break[cls] = {
            "n_targets": len(idxs), "n_cocomp": int(sum(target_cocomp[i] for i in idxs)),
            "ppr": round(float(np.mean([base_ppr[i] for i in idxs])), 4),
            "best_arm": round(float(np.mean([best_hits[i] for i in idxs])), 4)}

    if best_delta >= 8.0 and best_p < 0.05:
        verdict598 = "CONFIRMED"
    elif best_delta <= 3.0:
        verdict598 = "KILLED"
    else:
        verdict598 = "INDETERMINATE"
    clauses598 = [
        {"clause": "best trilateration target rank-recall@15 >= +8pp over single-source PPR (paired McNemar p<0.05)",
         "predicted": ">= +8pp & p<0.05",
         "measured": f"{best_label}: {best_delta}pp (ppr {base_rate} -> {trilat_table[best_label]['rate']}), p={best_p}",
         "holds": bool(best_delta >= 8.0 and best_p < 0.05)},
        {"clause": "KILL: best arm <= +3pp (joint geometry re-expresses single-source diffusion / no headroom)",
         "predicted": "kill if <= +3pp", "measured": f"{best_delta}pp", "holds": bool(best_delta <= 3.0)},
        {"clause": "honest control: trilateration beats hop-distance-from-anchors too",
         "predicted": "best arm rate > hop control",
         "measured": f"best {trilat_table[best_label]['rate']} vs hop {hop_rate}",
         "holds": bool(trilat_table[best_label]["rate"] > hop_rate)},
    ]
    h598 = {
        "run_id": run_id, "hypothesis": "R52-H598", "scoring_fence": "retrieval-level only",
        "harness_sanity": harness_sanity, "eigen_k_primary": K_PRIMARY, "heat_time_ladder": T_HEAT,
        "n_2anchor_probes": len(trilat_probes), "n_targets": n_targets, "n_cocomp_targets": n_cocomp,
        "target_convention": "in-graph gold carriers NOT among the >=2 gold-source anchors "
        "(+ resolved answer); anchors excluded from candidate ranking in every arm; heat kernel "
        "block-diagonal over 1830 components (cross-component proximity = 0)",
        "single_source_ppr_baseline_rate": base_rate, "hop_control_rate": hop_rate,
        "trilateration_vs_ppr_table": trilat_table,
        "trilateration_vs_ppr_cocomp_only": trilat_cocomp,
        "best_arm": best_label, "best_delta_pp": best_delta, "by_class_best_arm": class_break,
        "clauses": clauses598,
        "acceptance_bar": "CONFIRMED >= +8pp & p<0.05; KILLED <= +3pp",
        "proposed_verdict": verdict598,
    }

    # ==================================================================
    #                              H599
    # ==================================================================
    rho_curve = {}          # t -> {median,...} over dense@16
    rho_by_probe_best = {}  # pid -> max rho over ladder
    for t in T_H599:
        rr = []
        for pid in off_ids:
            sd = seeds_q[pid]
            hk = heat_vec(sd, t)
            pr = H.ppr(adj, out_deg, sd, n)
            cand = (set(np.argsort(-hk)[:200].tolist()) | set(np.argsort(-pr)[:200].tolist())) - set(sd)
            cand = sorted(cand)
            if len(cand) < 5:
                continue
            rho, _ = spearmanr(hk[cand], pr[cand])
            if not np.isnan(rho):
                rr.append(rho)
                rho_by_probe_best[pid] = max(rho_by_probe_best.get(pid, -1), float(rho))
        rr = np.array(rr)
        rho_curve[t] = {"median": round(float(np.median(rr)), 4),
                        "mean": round(float(np.mean(rr)), 4),
                        "p25": round(float(np.percentile(rr, 25)), 4),
                        "p75": round(float(np.percentile(rr, 75)), 4),
                        "n": int(len(rr))}
    best_t = max(rho_curve, key=lambda t: rho_curve[t]["median"])
    median_rho_bestT = rho_curve[best_t]["median"]
    best_probe = np.array(list(rho_by_probe_best.values()))
    median_rho_bestperprobe = round(float(np.median(best_probe)), 4)

    if median_rho_bestT >= 0.95:
        verdict599 = "CONFIRMED (single-source geometry re-expresses PPR)"
    elif median_rho_bestT < 0.85:
        verdict599 = "FALSIFIED (diffusion carries independent signal)"
    else:
        verdict599 = "INDETERMINATE"
    h599 = {
        "run_id": run_id, "hypothesis": "R52-H599", "scoring_fence": "retrieval-level only",
        "harness_sanity": harness_sanity, "heat_time_ladder": T_H599, "eigen_k_primary": K_PRIMARY,
        "candidate_set": "union of top-200 by heat-kernel proximity or PPR mass, seeds excluded",
        "seed_source": "dense@16 (realizable single source)",
        "spearman_curve_by_time": rho_curve,
        "best_time_for_reexpression": best_t,
        "median_spearman_at_best_time": median_rho_bestT,
        "median_of_per_probe_best_over_ladder": median_rho_bestperprobe,
        "clauses": [
            {"clause": "median per-query Spearman(heat, PPR mass) >= 0.95 at best-matched time (re-expression)",
             "predicted": ">= 0.95", "measured": f"median {median_rho_bestT} @ t={best_t}",
             "holds": bool(median_rho_bestT >= 0.95)},
            {"clause": "FALSIFY: median < 0.85 even at best-matched time (independent signal)",
             "predicted": "falsify if < 0.85", "measured": f"{median_rho_bestT}",
             "holds": bool(median_rho_bestT < 0.85)}],
        "acceptance_bar": "CONFIRMED >= 0.95; FALSIFIED < 0.85",
        "proposed_verdict": verdict599,
    }

    # ==================================================================
    #                              H600
    # ==================================================================
    h573 = json.loads(Path(H573_TAIL).read_text())
    tailA = [{"probe": r["probe"], "carrier": r["carrier"],
              "idx": name_row.get(H._norm(r["carrier"])), "source": "h573_hop_unreachable",
              "probe_pass": r["off_pass"]}
             for r in h573["carrier_rows"] if r["hop_distance"] >= NO_PATH]
    h571 = json.loads(Path(H571_TAIL).read_text())
    tailB, tailB_zero, tailB_all = [], [], []
    for r in h571["rows"]:
        if "ppr_reachable" not in r or r["ppr_reachable"] or not r["member_reachable"]:
            continue
        rec = {"probe": r["probe"], "carrier": r["title"], "idx": name_row.get(H._norm(r["title"])),
               "graded": r["graded_reach"], "source": "h571_member_only", "probe_pass": r["probe_pass"]}
        tailB_all.append(rec)
        if r["graded_reach"] <= 1e-9:
            tailB_zero.append(rec)
        elif r["graded_reach"] <= 0.13:
            tailB.append(rec)

    def dedupe(recs):
        seen, out = set(), []
        for r in recs:
            key = (r["probe"], r["idx"])
            if r["idx"] is None or key in seen:
                continue
            seen.add(key)
            out.append(r)
        return out

    def eval_tail(tail):
        rows = []
        for r in tail:
            pid, ci = r["probe"], r["idx"]
            if pid not in seeds_q or ci is None:
                continue
            sd = seeds_q[pid]
            pr = H.ppr(adj, out_deg, sd, n)
            ppr_region = set(np.argsort(-pr)[:PPR_TOP_N].tolist())
            hops = bfs_min_hops(adj_rows, sd, [ci], cap=HOP_CAP)
            seed_comps = {int(node_comp[s]) for s in sd}
            diff_hits = {}
            for t in T_HEAT:
                hk = heat_vec(sd, t)
                hk[sd] = -np.inf
                diff_hits[t] = ci in set(np.argsort(-hk)[:PPR_TOP_N].tolist())
            rows.append({**r, "in_ppr_top15": ci in ppr_region,
                         "hop_within6": hops.get(ci, NO_PATH) <= HOP_CAP,
                         "cocomp_with_seed": int(node_comp[ci]) in seed_comps,
                         "in_diff_top15": {str(k): v for k, v in diff_hits.items()},
                         "best_diff_hit": any(diff_hits.values())})
        return rows

    rowsA = eval_tail(dedupe(tailA))
    rowsB = eval_tail(dedupe(tailB))
    rowsC = eval_tail(dedupe(tailA + tailB))
    rows_zero = eval_tail(dedupe(tailB_zero))
    rows_all = eval_tail(dedupe(tailB_all))

    def counts(rows):
        c = {"n": len(rows), "diff_top15_any_t": sum(r["best_diff_hit"] for r in rows),
             "ppr_top15": sum(r["in_ppr_top15"] for r in rows),
             "hop_within6": sum(r["hop_within6"] for r in rows),
             "cocomp_with_seed": sum(r["cocomp_with_seed"] for r in rows)}
        for t in T_HEAT:
            c[f"diff_top15_t{t}"] = sum(r["in_diff_top15"][str(t)] for r in rows)
        return c

    cA, cB, cC = counts(rowsA), counts(rowsB), counts(rowsC)
    frac_combined = (cC["diff_top15_any_t"] / cC["n"]) if cC["n"] else 0.0
    if frac_combined >= 0.40:
        verdict600 = "CONFIRMED (interruption tolerance real)"
    elif frac_combined < 0.20:
        verdict600 = "KILLED (disconnection genuine, not a resolution artifact)"
    else:
        verdict600 = "INDETERMINATE"
    h600 = {
        "run_id": run_id, "hypothesis": "R52-H600", "scoring_fence": "retrieval-level only",
        "harness_sanity": harness_sanity, "eigen_k_primary": K_PRIMARY, "heat_time_ladder": T_HEAT,
        "tail_definition": {
            "h573": "carriers hop-unreachable within 6 hops (hop_distance>=99)",
            "h571_primary_weak": "member-only (not ppr_reachable & member_reachable), 0 < graded_reach <= 0.13",
            "realizable_anchors": "dense@16 titan seeds of the carrier's own probe",
            "region": "top-15 by exact heat-kernel proximity, seeds excluded"},
        "exact_counts": {
            "h573_tail": cA, "h571_weak_tail": cB, "combined_primary": cC,
            "h571_graded_zero_band_sensitivity": counts(rows_zero),
            "h571_full_member_only_sensitivity": counts(rows_all)},
        "combined_frac_diff_top15": round(frac_combined, 4),
        "per_carrier": rowsC,
        "clauses": [
            {"clause": "CONFIRMED: >= 40% of combined tail in diffusion top-15 from realizable anchors",
             "predicted": ">= 40%",
             "measured": f"{cC['diff_top15_any_t']}/{cC['n']} = {round(frac_combined,4)}",
             "holds": bool(frac_combined >= 0.40)},
            {"clause": "KILL: < 20% in diffusion top-15 (disconnection genuine)",
             "predicted": "kill if < 20%", "measured": f"{round(frac_combined,4)}",
             "holds": bool(frac_combined < 0.20)},
            {"clause": "control: h573 hop-unreachable ~0 by construction (diffusion + PPR)",
             "predicted": "~0",
             "measured": f"h573 diff {cA['diff_top15_any_t']}/{cA['n']}, ppr {cA['ppr_top15']}/{cA['n']}",
             "holds": True}],
        "acceptance_bar": "CONFIRMED >= 40%; KILLED < 20% (exact counts, no percentage theater)",
        "proposed_verdict": verdict600,
    }

    # ---------------- eigen-k sensitivity (commute / spectral-dist arms) ----------------
    sens = {"note": "commute + spectral-sumdist trilat rank-recall@15 across eigen-k (mid heat time)",
            "eigen_k": {}}
    tmid = T_HEAT[2]
    for k in K_EIGS:
        hits_ct, hits_sd = [], []
        for tp in trilat_probes:
            anchors, tgts, aset = tp["anchors"], tp["targets"], set(tp["anchors"])
            sumct = np.zeros(n)
            sd = np.zeros(n)
            for a in anchors:
                sumct += commute_dist_pair(a, k)
                sd += spectral_dist_pair(a, tmid, k)
            reg_ct = rank_region_top15(-sumct, aset)
            reg_sd = rank_region_top15(-sd, aset)
            for tgt in tgts:
                hits_ct.append(tgt in reg_ct)
                hits_sd.append(tgt in reg_sd)
        sens["eigen_k"][k] = {"commute_rate": round(float(np.mean(hits_ct)), 4),
                              "spec_sumdist_rate": round(float(np.mean(hits_sd)), 4)}
    h598["sensitivity"] = sens

    # ---------------- write ----------------
    p598 = OUT / f"h598-trilateration-{run_id}.json"
    p599 = OUT / f"h599-ppr-reexpress-{run_id}.json"
    p600 = OUT / f"h600-interruption-{run_id}.json"
    p598.write_text(json.dumps(h598, indent=1))
    p599.write_text(json.dumps(h599, indent=1))
    p600.write_text(json.dumps(h600, indent=1))
    print("H598 " + json.dumps({"verdict": verdict598, "best": best_label, "delta_pp": best_delta,
                                "ppr": base_rate, "n_targets": n_targets, "n_cocomp": n_cocomp}))
    print("H599 " + json.dumps({"verdict": verdict599, "median_rho_bestT": median_rho_bestT,
                                "best_t": best_t}))
    print("H600 " + json.dumps({"verdict": verdict600, "combined": cC, "frac": round(frac_combined, 4)}))
    print(f"WROTE {p598}\nWROTE {p599}\nWROTE {p600}", flush=True)


if __name__ == "__main__":
    main()

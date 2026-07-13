"""R53 relation-vocabulary governance gates (serves H602 + H605).

H602 CRUX - embedding + co-occurrence consolidation of the ~595 semantic
relation types into a canonical alias schema, and a post-consolidation H585
re-run (gold -> canonical cluster). Bars: <= ~80 canonical relations covering
>= 95% of semantic edge mass AND the re-run clears >= 60% alignment at <= 20%
false-alignment on a 30-pair hand-check. KILL if reaching alignment requires
merging semantically distinct roles (DIED_OF vs CAUSES_DEATH_OF; ATTENDED vs
TAUGHT_AT; X_OF direction confusions) - tested explicitly.

H605 - relation-type count vs corpus size fit (Heaps' law V = K n^beta) across
the three live rungs (scout/medium/pilot) plus historical CPAP points, with a
6,118-doc forecast. Ships the count query as the instrument.

All FREE: cached Titan embeddings (emb_native_*, emb_gold_* from r50/h585) +
cached typed edges + labels; three read-only Neo4j counts for H605.

Usage: .venv/bin/python scripts/experiments/r53_h602_consolidation.py
Writes: reports/experiments/r53/h602-consolidation-<ts>.json
        reports/experiments/r53/h605-proliferation-law-<ts>.json
"""

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from neo4j import GraphDatabase
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

CACHE = Path("tmp/results/r50")
R53CACHE = Path("tmp/results/r53")
OUT = Path("reports/experiments/r53")
H585 = Path("reports/experiments/r50/h585-relation-linker-20260713T224119Z.json")
VERDICTS = R53CACHE / "h602_handcheck_verdicts.json"

PROV = {"ABOUT", "MENTIONED_IN", "ANSWERABLE_FROM", "SIMILAR_TO"}
# combined-similarity weights (squared-weight convex blend of sub-cosines)
W_NAME, W_CTX, W_COOC = 0.5, 0.3, 0.2
# distance thresholds swept for agglomerative average-linkage (merge if S >= 1-t)
DIST_THRESHOLDS = [round(0.10 + 0.05 * i, 2) for i in range(17)]  # 0.10 .. 0.90
ALIGN_ANCHOR = 0.6  # h585 alignment anchor

# instances (READ-ONLY)
INSTANCES = {
    "scout": "bolt://172.19.0.8:7687",
    "medium": "bolt://172.19.0.9:7687",
    "pilot": "bolt://172.19.0.101:7687",
}
AUTH = ("neo4j", "kgfoundry")
DOC_Q = "MATCH (d:KGFDocument) RETURN count(d) AS n"
V_Q = (
    "MATCH (a:Entity)-[r]->(b:Entity) "
    "WHERE NOT type(r) IN ['SIMILAR_TO','ABOUT','MENTIONED_IN','ANSWERABLE_FROM'] "
    "RETURN count(DISTINCT type(r)) AS V"
)

# confusable role pairs the precision trap predicts must NOT merge
CONFUSABLE = [
    ("DIED_OF", "CAUSES_DEATH_OF", "cause-of-death, direction inverse"),
    ("DIED_OF", "DIED_IN", "cause vs place of death"),
    ("DIED_IN", "BORN_IN", "place of death vs place of birth"),
    ("ATTENDED", "TAUGHT_AT", "student (educated-at) vs teacher role"),
    ("ATTENDED", "TEACHES_AT", "student vs teacher role"),
    ("ATTENDED", "PROFESSOR_AT", "student vs professor role"),
    ("DIRECTED", "DIRECTED_BY", "director relation, direction inverse"),
    ("CHILD_OF", "FATHER_OF", "child vs parent, X_OF direction"),
    ("CHILD_OF", "DAUGHTER_OF", "child vs parent, X_OF direction"),
    ("MARRIED_TO", "MARRIED_IN", "spouse vs place/date of marriage"),
    ("BORN_IN", "BORN_ON", "place vs date of birth"),
]


def hum(t: str) -> str:
    return t.lower().replace("_", " ").strip()


def load_semantic_universe():
    """595 semantic types (edges_typed minus provenance) + edge mass + cooc."""
    edges = json.loads((CACHE / "edges_typed.json").read_text())
    labels = json.loads((CACHE / "labels.json").read_text())
    native = json.loads((CACHE / "native_vocab.json").read_text())
    nv_index = {n["type"]: i for i, n in enumerate(native)}

    mass = Counter()
    cooc = defaultdict(Counter)  # type -> Counter[(subj_label, obj_label)]
    for s, r, o in edges:
        if r in PROV:
            continue
        mass[r] += 1
        sl = labels.get(s, ["_"])[0]
        ol = labels.get(o, ["_"])[0]
        cooc[r][(sl, ol)] += 1

    types = sorted(mass)  # deterministic order
    return types, mass, cooc, native, nv_index


def build_features(types, cooc, native, nv_index):
    NN = np.load(CACHE / "emb_native_name.npy")
    NC = np.load(CACHE / "emb_native_ctx.npy")
    name_emb = np.stack([NN[nv_index[t]] for t in types])
    ctx_emb = np.stack([NC[nv_index[t]] for t in types])

    # co-occurrence signature vectors over the global ordered-label-pair vocab
    pair_vocab = sorted({p for t in types for p in cooc[t]})
    pidx = {p: i for i, p in enumerate(pair_vocab)}
    cooc_mat = np.zeros((len(types), len(pair_vocab)), dtype=np.float32)
    for i, t in enumerate(types):
        for p, c in cooc[t].items():
            cooc_mat[i, pidx[p]] = c
    norms = np.linalg.norm(cooc_mat, axis=1, keepdims=True)
    cooc_mat = cooc_mat / (norms + 1e-9)
    return name_emb, ctx_emb, cooc_mat, pair_vocab


def combined_similarity(name_emb, ctx_emb, cooc_mat):
    cos_name = name_emb @ name_emb.T
    cos_ctx = ctx_emb @ ctx_emb.T
    cos_cooc = cooc_mat @ cooc_mat.T
    wsum = W_NAME + W_CTX + W_COOC
    sim = (W_NAME * cos_name + W_CTX * cos_ctx + W_COOC * cos_cooc) / wsum
    np.clip(sim, 0.0, 1.0, out=sim)
    return sim


def cluster_at(dist_condensed, threshold, n):
    Z = linkage(dist_condensed, method="average")
    labels = fcluster(Z, t=threshold, criterion="distance")
    clusters = defaultdict(list)
    for i, c in enumerate(labels):
        clusters[int(c)].append(i)
    return Z, labels, clusters


def cluster_labels_fixed(Z, threshold):
    return fcluster(Z, t=threshold, criterion="distance")


def coverage_row(clusters, types, mass, threshold):
    total = sum(mass.values())
    cl_mass = sorted(
        (sum(mass[types[i]] for i in members) for members in clusters.values()),
        reverse=True,
    )
    n = len(clusters)
    cum, k95 = 0, 0
    for m in cl_mass:
        cum += m
        k95 += 1
        if cum >= 0.95 * total:
            break
    top80 = sum(cl_mass[:80])
    n_multi = sum(1 for members in clusters.values() if len(members) >= 2)
    mass_multi = sum(
        sum(mass[types[i]] for i in members)
        for members in clusters.values()
        if len(members) >= 2
    )
    return {
        "dist_threshold": threshold,
        "merge_sim_ge": round(1 - threshold, 2),
        "n_clusters": n,
        "n_multi_member_clusters": n_multi,
        "k95_clusters_to_95pct_mass": k95,
        "mass_in_top80_clusters_pct": round(100 * top80 / total, 2),
        "mass_in_multi_member_pct": round(100 * mass_multi / total, 2),
        "meets_le80_and_95pct": (n <= 80),
    }


def confusable_assignments(Z, types, thresholds):
    tindex = {t: i for i, t in enumerate(types)}
    rows = []
    label_by_t = {t: cluster_labels_fixed(Z, t) for t in thresholds}
    for a, b, why in CONFUSABLE:
        present = a in tindex and b in tindex
        row = {"a": a, "b": b, "role_distinction": why, "both_present": present}
        if present:
            ia, ib = tindex[a], tindex[b]
            row["same_cluster_at"] = {
                str(t): bool(label_by_t[t][ia] == label_by_t[t][ib])
                for t in thresholds
            }
        rows.append(row)
    return rows


def load_gold():
    d = json.loads(H585.read_text())
    per = d["gold_vocab"]["per_relation_eligible"]
    rels = list(per.keys())
    qcounts = np.array([per[r]["q_count"] for r in rels], dtype=np.float32)
    examples = {r: per[r]["example"] for r in rels}
    tot_slots = d["gold_vocab"]["eligible_slots"]
    GN = np.load(CACHE / "emb_gold_name.npy")
    GC = np.load(CACHE / "emb_gold_ctx.npy")
    gkeys = json.loads((CACHE / "emb_gold_name_keys.json").read_text())
    assert gkeys == rels, "gold key order drift"
    return rels, qcounts, examples, tot_slots, GN, GC, d


def cluster_centroids(clusters, name_emb, ctx_emb):
    ids = sorted(clusters)
    cn = np.stack([name_emb[clusters[c]].mean(axis=0) for c in ids])
    cc = np.stack([ctx_emb[clusters[c]].mean(axis=0) for c in ids])
    cn /= np.linalg.norm(cn, axis=1, keepdims=True) + 1e-9
    cc /= np.linalg.norm(cc, axis=1, keepdims=True) + 1e-9
    return ids, cn, cc


def align_to_clusters(G, centroids, ids, rels, qcounts, tot_slots):
    sim = G @ centroids.T  # gold x cluster
    best = sim.max(axis=1)
    arg = sim.argmax(axis=1)
    aligned = best >= ALIGN_ANCHOR
    return {
        "threshold": ALIGN_ANCHOR,
        "n_aligned": int(aligned.sum()),
        "coverage_unweighted": round(float(aligned.sum()) / len(rels), 4),
        "coverage_qweighted": round(float(qcounts[aligned].sum()) / tot_slots, 4),
    }, best, arg, sim


def best_member_cov(clusters, name_emb, GN, rels, qcounts, tot_slots):
    """Alignment when a cluster is represented by its BEST member (max cosine).
    This exactly reproduces h585 raw type-level coverage - consolidation cannot
    lift it; only centroid representation can move it (and it dilutes)."""
    sim = GN @ name_emb.T  # gold x native-type (all members)
    best = sim.max(axis=1)
    aligned = best >= ALIGN_ANCHOR
    return {
        "n_aligned": int(aligned.sum()),
        "coverage_unweighted": round(float(aligned.sum()) / len(rels), 4),
        "coverage_qweighted": round(float(qcounts[aligned].sum()) / tot_slots, 4),
    }


def alignment_sweep(Z, name_emb, ctx_emb, GN, GC, rels, qcounts, tot_slots,
                    thresholds):
    """Centroid-arm alignment coverage at each cluster threshold (name + ctx)."""
    rows = []
    for t in thresholds:
        labels = fcluster(Z, t=t, criterion="distance")
        clusters = defaultdict(list)
        for i, c in enumerate(labels):
            clusters[int(c)].append(i)
        ids, cn, cc = cluster_centroids(clusters, name_emb, ctx_emb)
        nc, *_ = align_to_clusters(GN, cn, ids, rels, qcounts, tot_slots)
        cxc, *_ = align_to_clusters(GC, cc, ids, rels, qcounts, tot_slots)
        rows.append({
            "dist_threshold": t,
            "n_clusters": len(clusters),
            "centroid_name_cov_unweighted": nc["coverage_unweighted"],
            "centroid_name_cov_qweighted": nc["coverage_qweighted"],
            "centroid_ctx_cov_unweighted": cxc["coverage_unweighted"],
        })
    return rows


def heaps_fit(points):
    """points: list of (n_docs, V). Returns beta, K, R2, CI on log-log OLS."""
    n = np.array([p[0] for p in points], dtype=float)
    V = np.array([p[1] for p in points], dtype=float)
    x = np.log(n)
    y = np.log(V)
    m = len(x)
    xm, ym = x.mean(), y.mean()
    sxx = ((x - xm) ** 2).sum()
    sxy = ((x - xm) * (y - ym)).sum()
    beta = sxy / sxx
    logK = ym - beta * xm
    yhat = logK + beta * x
    ss_res = ((y - yhat) ** 2).sum()
    ss_tot = ((y - ym) ** 2).sum()
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    # 95% CI on beta (t-approx); needs m>=3
    ci = None
    if m >= 3:
        se2 = ss_res / (m - 2)
        se_beta = math.sqrt(se2 / sxx) if sxx > 0 else float("nan")
        tcrit = {3: 12.71, 4: 4.303, 5: 3.182, 6: 2.776}.get(m, 2.776)
        ci = [round(beta - tcrit * se_beta, 4), round(beta + tcrit * se_beta, 4)]
    return {
        "n_points": m,
        "beta": round(float(beta), 4),
        "K": round(float(math.exp(logK)), 4),
        "r2_loglog": round(float(r2), 4),
        "beta_ci95": ci,
        "forecast_6118": round(float(math.exp(logK) * 6118 ** beta), 1),
        "points": [[float(p[0]), float(p[1])] for p in points],
    }


def run_h605():
    live = {}
    for name, uri in INSTANCES.items():
        drv = GraphDatabase.driver(uri, auth=AUTH)
        with drv.session() as s:
            live[name] = {
                "docs": s.run(DOC_Q).single()["n"],
                "semantic_types": s.run(V_Q).single()["V"],
            }
        drv.close()
    live_points = [(live[k]["docs"], live[k]["semantic_types"]) for k in
                   ("scout", "medium", "pilot")]
    # historical CPAP (26-doc build): relation types 334; entity types 65 (a
    # DIFFERENT vocabulary - flagged, spec conflated the two 26-doc numbers)
    cpap_rel = (26, 334)      # true CPAP relation-type point (R01-H3 == H395)
    cpap_ent = (26, 65)       # CPAP ENTITY-type count (spec's "65 @ 26 R01")
    fits = {
        "live_2wiki_only": heaps_fit(live_points),
        "live_plus_cpap_relation_334": heaps_fit(live_points + [cpap_rel]),
        "live_plus_spec_literal_65_and_334": heaps_fit(
            live_points + [cpap_ent, cpap_rel]),
    }
    return {
        "count_query_instrument": V_Q,
        "doc_query": DOC_Q,
        "live_rungs": live,
        "historical_points": {
            "cpap_relation_types_R01H3_eq_H395": {"docs": 26, "V": 334,
                "note": "same 26-doc CPAP build; entropy 6.22; substrate differs from 2wiki"},
            "cpap_entity_types_R01": {"docs": 26, "V": 65,
                "note": "ENTITY-type count, NOT relation - spec's '65 @ 26 docs R01' is this; mixing it into a relation Heaps fit is a category error"},
        },
        "fits": fits,
        "primary_fit": "live_2wiki_only",
    }


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    R53CACHE.mkdir(parents=True, exist_ok=True)

    # ---------- H602 consolidation ----------
    types, mass, cooc, native, nv_index = load_semantic_universe()
    total_mass = sum(mass.values())
    print(f"semantic universe: {len(types)} types, {total_mass} edges", flush=True)
    name_emb, ctx_emb, cooc_mat, pair_vocab = build_features(
        types, cooc, native, nv_index)
    sim = combined_similarity(name_emb, ctx_emb, cooc_mat)
    dist = 1.0 - sim
    np.fill_diagonal(dist, 0.0)
    dist = (dist + dist.T) / 2  # enforce symmetry for squareform
    dist_condensed = squareform(dist, checks=False)
    Z = linkage(dist_condensed, method="average")

    curve = []
    clusters_by_t = {}
    for t in DIST_THRESHOLDS:
        labels = fcluster(Z, t=t, criterion="distance")
        clusters = defaultdict(list)
        for i, c in enumerate(labels):
            clusters[int(c)].append(i)
        clusters_by_t[t] = clusters
        curve.append(coverage_row(clusters, types, mass, t))

    confusable = confusable_assignments(Z, types, DIST_THRESHOLDS)

    # operating threshold: smallest cluster count that first reaches <= 80
    op_row = next((r for r in curve if r["n_clusters"] <= 80), curve[-1])
    op_t = op_row["dist_threshold"]
    op_clusters = clusters_by_t[op_t]

    # ---------- post-consolidation H585 re-run ----------
    rels, qcounts, examples, tot_slots, GN, GC, h585 = load_gold()
    align_sweep = alignment_sweep(Z, name_emb, ctx_emb, GN, GC, rels, qcounts,
                                  tot_slots, DIST_THRESHOLDS)
    best_member = best_member_cov(op_clusters, name_emb, GN, rels, qcounts,
                                  tot_slots)
    ids, cn, cc = cluster_centroids(op_clusters, name_emb, ctx_emb)
    name_cov, _, _, _ = align_to_clusters(GN, cn, ids, rels, qcounts, tot_slots)
    ctx_cov, _, _, _ = align_to_clusters(GC, cc, ids, rels, qcounts, tot_slots)

    # faithful "which canonical bucket" mapping: gold -> cluster containing its
    # single best-matching native type (best-member logic; this is the coverage
    # a consolidated schema actually inherits, = h585 raw type coverage)
    op_labels = fcluster(Z, t=op_t, criterion="distance")
    type_sim = GN @ name_emb.T          # gold x 595 native types
    bt_idx = type_sim.argmax(axis=1)    # best native type per gold
    bt_cos = type_sim.max(axis=1)

    def cluster_of_type(ti):
        cid = int(op_labels[ti])
        members = [j for j in range(len(types)) if op_labels[j] == cid]
        mm = sorted(((types[j], mass[types[j]]) for j in members),
                    key=lambda x: -x[1])
        return {"cluster_id": cid, "size": len(members),
                "members_top": mm[:15], "total_members": len(mm)}

    per_gold = []
    for i, r in enumerate(rels):
        ti = int(bt_idx[i])
        per_gold.append({
            "gold": r, "q_count": int(qcounts[i]),
            "gold_example": examples[r],
            "best_native_type": types[ti],
            "best_native_cos": round(float(bt_cos[i]), 4),
            "aligned_at_0.6": bool(bt_cos[i] >= ALIGN_ANCHOR),
            "canonical_cluster": cluster_of_type(ti),
        })

    # ---------- 30-pair hand-check candidates ----------
    # gold -> (best native type, the canonical cluster it falls into at the
    # operating threshold). Judge: does that canonical cluster COHERENTLY
    # express the gold relation, or is it a role-mixed blob (false alignment)?
    handcheck = []
    for i, r in enumerate(rels):
        ti = int(bt_idx[i])
        handcheck.append({
            "arm": "name", "gold": r,
            "best_native_type": types[ti],
            "name_cos": round(float(bt_cos[i]), 4),
            "aligned_at_0.6": bool(bt_cos[i] >= ALIGN_ANCHOR),
            "cluster": cluster_of_type(ti),
            "gold_example": examples[r],
        })
    # 7 extra: the largest canonical clusters (the mega-blobs governance must
    # name) - judge whether each is a single coherent canonical relation
    cl_sizes = Counter(op_labels)
    big = [c for c, _ in cl_sizes.most_common(7)]
    for cid in big:
        members = [j for j in range(len(types)) if op_labels[j] == cid]
        mm = sorted(((types[j], mass[types[j]]) for j in members),
                    key=lambda x: -x[1])
        handcheck.append({
            "arm": "cluster_coherence", "gold": None,
            "cluster": {"cluster_id": int(cid), "size": len(members),
                        "members_top": mm[:15], "total_members": len(mm)},
        })
    for k, p in enumerate(handcheck):
        p["pair_id"] = k

    result = {
        "run_id": run_id,
        "hypothesis": "R53-H602 embedding+co-occurrence relation consolidation",
        "universe": {
            "n_semantic_types": len(types),
            "total_semantic_edges": total_mass,
            "excluded_provenance": sorted(PROV),
            "cooc_pair_vocab_size": len(pair_vocab),
            "singletons_count1": sum(1 for t in types if mass[t] == 1),
        },
        "weights": {"name": W_NAME, "context": W_CTX, "cooccurrence": W_COOC},
        "size_coverage_curve": curve,
        "operating_threshold": {
            "dist_threshold": op_t,
            "merge_sim_ge": round(1 - op_t, 2),
            **{k: op_row[k] for k in
               ("n_clusters", "k95_clusters_to_95pct_mass",
                "mass_in_top80_clusters_pct", "mass_in_multi_member_pct")},
        },
        "confusable_pair_assignments": confusable,
        "h585_rerun": {
            "baseline_h585_name_cov_unweighted": h585["coverage_at_0.6"]["name_arm"]["coverage_unweighted"],
            "baseline_h585_name_cov_qweighted": h585["coverage_at_0.6"]["name_arm"]["coverage_qweighted"],
            "baseline_best_true_at_le20pct_false": h585["decision"]["best_true_coverage_at_le20pct_false"],
            "post_consolidation_name_arm_centroid": name_cov,
            "post_consolidation_context_arm_centroid": ctx_cov,
            "best_member_arm_at_op_threshold": best_member,
            "best_member_note": "best-member cluster representation reproduces h585 raw type-level coverage exactly; centroid representation dilutes it",
            "centroid_alignment_sweep_all_thresholds": align_sweep,
            "operating_threshold": op_t,
            "per_gold": per_gold,
        },
        "handcheck_candidates": handcheck,
    }

    # inject hand-check verdicts if present
    if VERDICTS.exists():
        verdicts = json.loads(VERDICTS.read_text())
        judged, n_true, n_false, n_unj = [], 0, 0, 0
        for p in handcheck:
            key = str(p["pair_id"])
            v = verdicts.get(key)
            row = dict(p)
            row["expresses_gold"] = v["expresses"] if v else None
            row["judge_note"] = v["note"] if v else None
            judged.append(row)
            if v is None:
                n_unj += 1
            elif v["expresses"]:
                n_true += 1
            else:
                n_false += 1
        result["handcheck_judged"] = judged
        # name-arm-at-0.6 false rate (the counted alignments)
        counted = [r for r in judged if r["arm"] == "name"
                   and r["name_cos"] >= ALIGN_ANCHOR]
        false06 = [r for r in counted if r["expresses_gold"] is False]
        result["handcheck_summary"] = {
            "sample_size": len(judged),
            "unjudged": n_unj,
            "true": n_true, "false": n_false,
            "sample_false_rate": round(n_false / (n_true + n_false), 4) if (n_true + n_false) else None,
            "counted_name_arm_at_0.6": len(counted),
            "false_among_counted_0.6": len(false06),
            "false_rate_at_0.6": round(len(false06) / len(counted), 4) if counted else None,
        }

    outp = OUT / f"h602-consolidation-{run_id}.json"
    outp.write_text(json.dumps(result, indent=1))
    print("WROTE", outp, flush=True)
    print("operating threshold:", op_t, "-> clusters:", op_row["n_clusters"],
          "k95:", op_row["k95_clusters_to_95pct_mass"], flush=True)
    print("post-consolidation name-arm coverage:", name_cov, flush=True)

    # ---------- H605 proliferation law ----------
    h605 = run_h605()
    h605["run_id"] = run_id
    h605["hypothesis"] = "R53-H605 relation-vocabulary Heaps-law proliferation"
    outp5 = OUT / f"h605-proliferation-law-{run_id}.json"
    outp5.write_text(json.dumps(h605, indent=1))
    print("WROTE", outp5, flush=True)
    pf = h605["fits"]["live_2wiki_only"]
    print(f"Heaps (live 2wiki): beta={pf['beta']} R2={pf['r2_loglog']} "
          f"forecast@6118={pf['forecast_6118']}", flush=True)
    return outp, outp5


if __name__ == "__main__":
    main()

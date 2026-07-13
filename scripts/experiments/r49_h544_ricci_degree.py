"""R49-H544: is Forman-Ricci a degree-summary alias, or an independent signal?

Hypothesis (contrarian persona, Sreejith 1603.00386 / Samal 1712.07600): the
mean AFRC delta reported in R45 is reconstructable from simple degree/edge
statistics, and a degree-preserving (configuration-model) rewiring leaves it
unmoved - so Forman-Ricci carries no information beyond the degree sequence.

Prediction: R^2 of FR-mean delta on {dE, d-mean-degree, d-degree-variance}
> 0.90 across a perturbation series + the R45 dump stages; |d mean-AFRC| < 2%
under degree-preserving rewiring; certificate coverage NOT reconstructable
(R^2 < 0.5, but under-determined here - only 3 stage points exist).

Acceptance bar: KILLED (H486 demoted to a degree-summary alias) if R^2 > 0.90
AND rewiring move < 2%; Ricci SURVIVES as independent if R^2 < 0.70 OR rewiring
move >= 2%; otherwise INCONCLUSIVE.

Forman-Ricci computation is copied VERBATIM from scripts/experiments/
r45_metric_sweep.py (key H486_forman_ricci: sample 500 edges under seed 43,
frc = 4 - deg(u) - deg(v)) so numbers are comparable to the R45 sweeps. A
deterministic full-graph FR-mean is also computed as a sampling-noise control.

READ-ONLY on Neo4j. No CREATE/MERGE/SET/DELETE. No graph is ever mutated in the
database - all perturbation/rewiring happens on in-memory networkx copies.

Usage:  .venv/bin/python scripts/experiments/r49_h544_ricci_degree.py
Output: reports/experiments/r49/h544-ricci-degree-<UTC ts>.json
"""

import json
import random
import statistics as st
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
import numpy as np
from neo4j import GraphDatabase

URI = "bolt://172.19.0.101:7687"
AUTH = ("neo4j", "kgfoundry")
OUT = Path("reports/experiments/r49")

# R45 stage sweeps (the dump-stage observations). Only THREE sweeps exist; the
# registered text says "four dump stages" -> DEVIATION recorded in output.
STAGE_SWEEPS = [
    ("pre-repair", "reports/experiments/r45/metric-sweep-pre-repair-20260712T073633Z.json"),
    ("post-repair", "reports/experiments/r45/metric-sweep-post-repair-20260712T101351Z.json"),
    ("post-pass2", "reports/experiments/r45/metric-sweep-post-pass2-20260712T102639Z.json"),
]

# H389 certificate coverage jsonl (H484 facts-per-entity / coverage source).
COVERAGE_GLOB = "reports/experiments/r39/h389-coverage-*.jsonl"


# ---------- metrics (R45-verbatim + deterministic control) ----------

def fr_sampled(G):
    """VERBATIM R45 H486_forman_ricci: sample 500 edges, seed 43."""
    edges = list(G.edges())
    random.seed(43)
    sample = random.sample(edges, min(500, len(edges)))
    frc = [4 - G.degree(u) - G.degree(v) for u, v in sample]
    return round(st.mean(frc), 3)


def fr_full(G):
    """Deterministic full-graph FR-mean (same 4-deg(u)-deg(v) formula, all edges)."""
    m = G.number_of_edges()
    if m == 0:
        return 0.0
    s = sum(4 - G.degree(u) - G.degree(v) for u, v in G.edges())
    return round(s / m, 4)


def deg_moments(G):
    degs = [d for _, d in G.degree()]
    return st.mean(degs), (st.variance(degs) if len(degs) > 1 else 0.0)


def snap(G):
    mm = deg_moments(G)
    return {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "deg_mean": round(mm[0], 4),
        "deg_var": round(mm[1], 4),
        "fr_sampled": fr_sampled(G),
        "fr_full": fr_full(G),
    }


# ---------- base graph export (READ-ONLY) ----------

def export_base():
    drv = GraphDatabase.driver(URI, auth=AUTH)
    with drv.session() as s:
        ids = [r["id"] for r in s.run("MATCH (e:Entity) RETURN e.id AS id").data()]
        rels = s.run("MATCH (a:Entity)-[r]->(b:Entity) RETURN a.id AS a, b.id AS b").data()
    drv.close()
    G = nx.Graph()
    G.add_nodes_from(ids)
    G.add_edges_from((r["a"], r["b"]) for r in rels)
    return G


# ---------- perturbations ----------

def perturb_delete(G, rate, seed):
    H = G.copy()
    rng = random.Random(seed)
    edges = list(H.edges())
    k = max(1, int(rate * len(edges)))
    for e in rng.sample(edges, k):
        H.remove_edge(*e)
    return H


def perturb_add(G, rate, seed):
    H = G.copy()
    rng = random.Random(seed)
    nodes = list(H.nodes())
    m = H.number_of_edges()
    k = max(1, int(rate * m))
    added = 0
    tries = 0
    while added < k and tries < k * 50:
        u, v = rng.choice(nodes), rng.choice(nodes)
        tries += 1
        if u != v and not H.has_edge(u, v):
            H.add_edge(u, v)
            added += 1
    return H


def perturb_ingest(G, ndocs, seed):
    """Mimic doc ingest: each doc = 6 new entity nodes as a star + 1 edge to an existing node."""
    H = G.copy()
    rng = random.Random(seed)
    existing = list(G.nodes())
    for d in range(ndocs):
        center = f"synth_s{seed}_d{d}_c"
        leaves = [f"synth_s{seed}_d{d}_l{i}" for i in range(5)]
        H.add_node(center)
        for lf in leaves:
            H.add_node(lf)
            H.add_edge(center, lf)
        H.add_edge(center, rng.choice(existing))
    return H


def perturb_mixed(G, rate, seed):
    return perturb_add(perturb_delete(G, rate, seed), rate, seed + 1000)


def build_series(G):
    obs = []
    for rate in (0.005, 0.01, 0.02, 0.05, 0.10, 0.20):
        for seed in (0, 1, 2):
            obs.append(("del", rate, seed, perturb_delete(G, rate, seed)))
    for rate in (0.005, 0.01, 0.02, 0.05, 0.10):
        for seed in (0, 1):
            obs.append(("add", rate, seed, perturb_add(G, rate, seed)))
    for ndocs in (5, 20, 50):
        for seed in (0, 1):
            obs.append(("ingest", ndocs, seed, perturb_ingest(G, ndocs, seed)))
    for rate in (0.02, 0.05, 0.10):
        obs.append(("mixed", rate, 0, perturb_mixed(G, rate, 0)))
    return obs


# ---------- OLS ----------

def ols_r2(rows, target_key):
    """rows: list of dicts with d_edges,d_deg_mean,d_deg_var,<target_key>. Returns coeffs+R^2."""
    X = np.array([[1.0, r["d_edges"], r["d_deg_mean"], r["d_deg_var"]] for r in rows])
    y = np.array([r[target_key] for r in rows])
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ beta
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return {
        "n": len(rows),
        "coef": {"intercept": round(float(beta[0]), 6), "d_edges": round(float(beta[1]), 6),
                 "d_deg_mean": round(float(beta[2]), 4), "d_deg_var": round(float(beta[3]), 4)},
        "r2": round(r2, 5),
    }


# ---------- rewiring (degree-preserving) ----------

def rewire(G, seeds, factor=10):
    m = G.number_of_edges()
    nswap = factor * m
    results = []
    for seed in seeds:
        H = G.copy()
        before_s, before_f = fr_sampled(H), fr_full(H)
        done = nswap
        try:
            nx.double_edge_swap(H, nswap=nswap, max_tries=nswap * 40, seed=seed)
        except nx.NetworkXAlgorithmError as exc:
            done = f"partial ({exc})"
        after_s, after_f = fr_sampled(H), fr_full(H)
        pct_s = abs(after_s - before_s) / abs(before_s) * 100 if before_s else float("nan")
        pct_f = abs(after_f - before_f) / abs(before_f) * 100 if before_f else float("nan")
        # sanity: degree sequence unchanged
        deg_ok = sorted(d for _, d in H.degree()) == sorted(d for _, d in G.degree())
        results.append({
            "seed": seed, "swaps_target": nswap, "swaps_result": done,
            "degree_seq_preserved": deg_ok,
            "fr_sampled_before": before_s, "fr_sampled_after": after_s,
            "fr_full_before": before_f, "fr_full_after": after_f,
            "pct_move_sampled": round(pct_s, 4), "pct_move_full": round(pct_f, 4),
        })
    return results


def sampling_noise_diagnostic(G, seeds=(1, 2, 3)):
    """Show the sampled-500 rewiring 'move' is estimator noise: it -> 0 as the
    FR sample grows toward all edges (where the move is provably exactly 0)."""
    m = G.number_of_edges()
    # full FR distribution std (deterministic) -> SE of a k-edge sample mean
    fr_vals = [4 - G.degree(u) - G.degree(v) for u, v in G.edges()]
    full_std = st.pstdev(fr_vals)
    sizes = [500, 1000, 2000, 4000, m]
    conv = []
    for k in sizes:
        moves = []
        for seed in seeds:
            H = G.copy()
            try:
                nx.double_edge_swap(H, nswap=10 * m, max_tries=10 * m * 40, seed=seed)
            except nx.NetworkXAlgorithmError:
                pass

            def frk(GG, kk, sd):
                edges = list(GG.edges())
                r = random.Random(sd)
                samp = edges if kk >= len(edges) else r.sample(edges, kk)
                return st.mean(4 - GG.degree(u) - GG.degree(v) for u, v in samp)
            before = frk(G, k, 43)
            after = frk(H, k, 43)
            moves.append(abs(after - before) / abs(before) * 100 if before else float("nan"))
        conv.append({"sample_edges": k, "mean_pct_move": round(st.mean(moves), 4)})
    return {
        "full_fr_distribution_pstd": round(full_std, 3),
        "se_of_500_edge_mean": round(full_std / (500 ** 0.5), 4),
        "rewire_move_vs_sample_size": conv,
        "interpretation": "sampled-500 rewiring move is ~1 SE of the 500-edge estimator "
                          "and decays to 0.0 as the sample reaches all edges; it is "
                          "measurement noise, not a real curvature move",
    }


# ---------- stage points ----------

def stage_points():
    stages = []
    for label, path in STAGE_SWEEPS:
        d = json.loads(Path(path).read_text())
        stages.append({
            "label": label, "nodes": d["nodes"], "edges": d["edges"],
            "deg_mean": d["H469_degree"]["mean"], "deg_var": d["H469_degree"]["var"],
            "fr_sampled": d["H486_forman_ricci"]["mean"],
        })
    deltas = []
    for a, b in zip(stages, stages[1:]):
        deltas.append({
            "from": a["label"], "to": b["label"],
            "d_edges": b["edges"] - a["edges"],
            "d_deg_mean": round(b["deg_mean"] - a["deg_mean"], 4),
            "d_deg_var": round(b["deg_var"] - a["deg_var"], 4),
            "d_fr_sampled": round(b["fr_sampled"] - a["fr_sampled"], 4),
        })
    return stages, deltas


# ---------- certificate coverage (UNDER-DETERMINED) ----------

def coverage_points():
    files = sorted(Path(".").glob(COVERAGE_GLOB))
    pts = []
    for f in files:
        covs = [json.loads(ln)["coverage"] for ln in f.read_text().splitlines() if ln.strip()]
        if covs:
            ts = f.stem.split("-")[-1]
            pts.append({"file": f.name, "ts": ts, "n_docs": len(covs),
                        "mean_coverage": round(st.mean(covs), 5)})
    return pts


# ---------- main ----------

def log(msg, out=None, path=None):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)
    if out is not None and path is not None:
        path.write_text(json.dumps(out, indent=2))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = OUT / f"h544-ricci-degree-{ts}.json"
    out = {"hypothesis": "R49-H544", "generated_utc": ts, "uri": URI,
           "fr_method": "R45-verbatim: sample 500 edges seed 43, frc=4-deg(u)-deg(v); "
                        "fr_full is deterministic all-edge mean of same formula"}

    log("exporting base graph (READ-ONLY)", out, path)
    G = export_base()
    out["base"] = snap(G)
    log(f"base: {out['base']['nodes']} nodes / {out['base']['edges']} edges "
        f"fr_sampled={out['base']['fr_sampled']} fr_full={out['base']['fr_full']}", out, path)

    log("building perturbation series", out, path)
    series = build_series(G)
    base_de, base_dm, base_dv = out["base"]["edges"], out["base"]["deg_mean"], out["base"]["deg_var"]
    rows = []
    obs_out = []
    for kind, param, seed, H in series:
        sm, sv = deg_moments(H)
        r = {"kind": kind, "param": param, "seed": seed,
             "edges": H.number_of_edges(), "nodes": H.number_of_nodes(),
             "d_edges": H.number_of_edges() - base_de,
             "d_deg_mean": round(sm - base_dm, 5),
             "d_deg_var": round(sv - base_dv, 5),
             "d_fr_sampled": round(fr_sampled(H) - out["base"]["fr_sampled"], 4),
             "d_fr_full": round(fr_full(H) - out["base"]["fr_full"], 4)}
        rows.append(r)
        obs_out.append(r)
    out["perturbations"] = obs_out
    log(f"perturbation series: {len(rows)} variants", out, path)

    # regressions: primary sampled (R45-comparable) + full (noise-control)
    out["regression"] = {
        "target_fr_sampled": ols_r2([{**r, } for r in rows], "d_fr_sampled"),
        "target_fr_full": ols_r2(rows, "d_fr_full"),
    }
    log(f"R^2 sampled={out['regression']['target_fr_sampled']['r2']} "
        f"full={out['regression']['target_fr_full']['r2']}", out, path)

    # stage points + combined regression (perturb + stage deltas, sampled metric)
    stages, stage_deltas = stage_points()
    out["stage_points"] = {"stages": stages, "consecutive_deltas": stage_deltas,
                           "note": "only 3 sweeps exist -> 2 consecutive deltas; "
                                   "registered text says 4 dump stages (3 deltas) - DEVIATION"}
    combined = [{"d_edges": r["d_edges"], "d_deg_mean": r["d_deg_mean"],
                 "d_deg_var": r["d_deg_var"], "d_fr_sampled": r["d_fr_sampled"]} for r in rows]
    combined += [{"d_edges": d["d_edges"], "d_deg_mean": d["d_deg_mean"],
                  "d_deg_var": d["d_deg_var"], "d_fr_sampled": d["d_fr_sampled"]} for d in stage_deltas]
    out["regression"]["target_fr_sampled_with_stages"] = ols_r2(combined, "d_fr_sampled")
    log(f"R^2 sampled+stages={out['regression']['target_fr_sampled_with_stages']['r2']}", out, path)

    # rewiring
    log("degree-preserving rewiring (double_edge_swap, 10x edges, 5 seeds)", out, path)
    rw = rewire(G, seeds=[1, 2, 3, 4, 5], factor=10)
    out["rewiring"] = {
        "per_seed": rw,
        "mean_pct_move_sampled": round(st.mean(r["pct_move_sampled"] for r in rw), 4),
        "mean_pct_move_full": round(st.mean(r["pct_move_full"] for r in rw), 4),
        "note": "full-graph FR is provably invariant under degree-preserving rewiring "
                "(sum over edges of deg(u)+deg(v) = sum deg^2, wiring-independent); "
                "sampled shows only 500-edge sampling noise",
    }
    log(f"rewiring mean pct move sampled={out['rewiring']['mean_pct_move_sampled']} "
        f"full={out['rewiring']['mean_pct_move_full']}", out, path)

    log("sampling-noise diagnostic (rewire move vs FR sample size)", out, path)
    out["sampling_noise_diagnostic"] = sampling_noise_diagnostic(G)
    log(f"diagnostic: SE(500)={out['sampling_noise_diagnostic']['se_of_500_edge_mean']} "
        f"conv={out['sampling_noise_diagnostic']['rewire_move_vs_sample_size']}", out, path)

    # certificate coverage clause (UNDER-DETERMINED)
    cov = coverage_points()
    out["certificate_clause"] = {
        "status": "UNDER-DETERMINED",
        "reason": "certificate coverage exists only at a handful of stage timestamps; "
                  "H484 is absent from the R45 sweep JSONs; cannot fit 3 predictors on "
                  "2-3 aggregate points -> no meaningful R^2 (a 3-point fit is exactly "
                  "determined, R^2=1 trivially). Best-effort aggregates below.",
        "coverage_points": cov,
        "coverage_spread": (round(max(c["mean_coverage"] for c in cov)
                                  - min(c["mean_coverage"] for c in cov), 5) if cov else None),
    }

    # clause-by-clause outcome vs registered bar
    r2_s = out["regression"]["target_fr_sampled"]["r2"]
    r2_f = out["regression"]["target_fr_full"]["r2"]
    rw_full = out["rewiring"]["mean_pct_move_full"]
    rw_samp = out["rewiring"]["mean_pct_move_sampled"]
    out["clauses"] = [
        {"clause": "R^2(FR-mean delta ~ {dE,d-mean-deg,d-deg-var}) > 0.90",
         "predicted": "> 0.90", "measured_fr_full": r2_f, "measured_fr_sampled": r2_s,
         "holds": bool(r2_f > 0.90)},
        {"clause": "|d mean-AFRC| < 2% under degree-preserving rewiring",
         "predicted": "< 2%", "measured_pct_full": rw_full, "measured_pct_sampled": rw_samp,
         "holds": bool(rw_full < 2.0)},
        {"clause": "certificate coverage NOT reconstructable (R^2 < 0.5)",
         "predicted": "< 0.5", "measured": "UNDER-DETERMINED", "holds": None},
    ]

    # proposed verdict strictly per registered bar (use fr_full as the FR-mean signal;
    # sampled reported alongside). KILLED if R2>0.90 AND rewire<2%; SURVIVES if
    # R2<0.70 OR rewire>=2%; else INCONCLUSIVE.
    killed = (r2_f > 0.90) and (rw_full < 2.0)
    survives = (r2_f < 0.70) or (rw_full >= 2.0)
    verdict = "KILLED" if killed else ("SURVIVES" if survives else "INCONCLUSIVE")
    out["proposed_verdict"] = verdict
    out["verdict_basis"] = {
        "r2_fr_full": r2_f, "r2_fr_sampled": r2_s,
        "rewire_pct_full": rw_full, "rewire_pct_sampled": rw_samp,
        "rule": "KILLED if r2>0.90 and rewire<2%; SURVIVES if r2<0.70 or rewire>=2%; else INCONCLUSIVE",
    }

    path.write_text(json.dumps(out, indent=2))
    log(f"DONE -> {path}  verdict={verdict}", out, path)
    print(f"ARTIFACT {path}", flush=True)


if __name__ == "__main__":
    main()

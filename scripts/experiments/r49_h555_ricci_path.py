"""R49-H555/H556/H557: min-Forman (degree-bottleneck) on the seed->carrier path.

RE-PRICED per H544 KILLED (2026-07-13): the shipped Forman-Ricci has NO triangle
term, so edge-Forman is FR(u,v) = 4 - deg(u) - deg(v) (the H486 convention,
scripts/experiments/r45_metric_sweep.py:127). min-Forman over the shortest-path
edges from the dense seed set to the gold answer-carrier is therefore a LOCAL
DEGREE-BOTTLENECK instrument (the path's single highest-summed-degree edge), NOT
a curvature. Everything below is labeled honestly as degree-bottleneck.

Three hypotheses, one offline read-only pass (Neo4j MATCH/RETURN only; Bedrock
Titan only to embed the probe questions, exactly H573's seed path):
  H555 - per-probe min-Forman separates FAIL from PASS (AUC >= 0.68; fail median
         >= 0.5 pooled-SD more negative, Mann-Whitney p < 0.05).
  H556 - attribution control: min-Forman does NOT out-predict a logistic model on
         {shortest-path hop-count, min node-degree on path}; earns its seat only
         at delta-AUC >= 0.05, p < 0.05 (LR chi2). Reports feature correlation
         between min-Forman and min-node-degree.
  H557 - orthogonality: among certificate-covered probes min-Forman separates
         FAIL from PASS AND survives conditioning on cert coverage
         (partial Spearman(min-Forman, fail | cert) <= -0.25, p < 0.05).

CONVENTIONS reused verbatim:
  - Adjacency: (a:Entity)-[r]-(b:Entity) WHERE type(r) <> 'SIMILAR_TO' (H515;
    valid_to absent on this graph, not filtered). Symmetrized + deduped. deg =
    distinct-neighbor count in THIS graph (same graph the BFS walks) = the degree
    functional in FR.
  - Seeds: dense top-16 per probe question via vector_query over
    kgf_entity_embeddings (bit-identical to H573).
  - Carrier resolution: gold title -> entity via exact _norm name-match (H571/H573).
  - Path: multi-source unweighted BFS from the seed set to the carrier
    (= shortest of the per-seed shortest paths), cap 6 hops. min-Forman = min over
    path edges of 4-deg(u)-deg(v); min-node-degree = min over path nodes of deg.
  - Bottleneck rollup (H573): per-probe feature = worst carrier per feature
    (neg_hop=-max hop; min-Forman=min; min-node-degree=min).
  - Unreachable-within-6 carrier: sentinel worse than any real value, uniformly
    (neg_hop -99; min-Forman min_real-1; min-node-degree 0). 0-hop carrier (carrier
    IS a seed, no path edge): min-Forman BEST sentinel max_real+1; min-node-degree
    = deg(carrier).
  - Ground truth: h499 OFF-arm probe pass/fail (85 pass / 47 fail over 132;
    eligible-and-resolvable subset here).
  - Cert coverage: reports/experiments/r49/h545-cert-*.jsonl, per-doc; probe
    coverage = min over its gold docs (bottleneck); covered = >= pile median (0.6).

Usage: python scripts/experiments/r49_h555_ricci_path.py [config] [questions.json] [max]
Writes: reports/experiments/r49/h555-557-ricci-path-<ts>.json  (serves all three
        registered artifact names h555-ricci-path / h556-ricci-control /
        h557-ricci-ortho - one combined file, cross-referenced).
READ-ONLY on Neo4j.
"""

import json
import re
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import stats
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, "notebooks")
sys.path.insert(0, "scripts/experiments")
from h158_measure import _norm  # noqa: E402
from r46_h499_screen import gold_titles, ingested_titles, load_slices  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.extraction import generate_embeddings  # noqa: E402
from knowledge_graph_foundry.models import Entity  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

CONFIG = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    "config/experiments/config-bench-medium.yml")
QUESTIONS = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
    "data/external/multihop-qa-benchmarks/2wikimultihopqa.json")
MAX = int(sys.argv[3]) if len(sys.argv) > 3 else 0
SCREEN = Path("reports/experiments/bench/r46-h499-screen-20260713T072044Z.jsonl")
CERT = Path("reports/experiments/r49/h545-cert-20260713T175512Z.jsonl")
H573 = Path("reports/experiments/r49/h573-reach-proxy-20260713T191754Z.json")
OUT = Path("reports/experiments/r49")
CAP = 6
NO_HOP = 99


def bfs_path(adj_rows, seed_set, target, cap=CAP):
    """Shortest unweighted path (node list, seed..target) from any seed; cap-bounded.

    Returns [target] for a 0-hop carrier, None if unreachable within cap.
    """
    if target in seed_set:
        return [target]
    parent = {}
    seen = set(seed_set)
    frontier = deque((s, 0) for s in seed_set)
    while frontier:
        node, d = frontier.popleft()
        if d >= cap:
            continue
        for nb in adj_rows[node]:
            if nb in seen:
                continue
            seen.add(nb)
            parent[nb] = node
            if nb == target:
                path = [nb]
                while path[-1] in parent:
                    path.append(parent[path[-1]])
                return list(reversed(path))
            frontier.append((nb, d + 1))
    return None


def auc(scores, labels):
    """AUC via Mann-Whitney U (ties=0.5); higher score => positive label (pass)."""
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return None
    wins = sum(1.0 if a > b else 0.5 if a == b else 0.0 for a in pos for b in neg)
    return round(wins / (len(pos) * len(neg)), 4)


def llf(y, p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return float(np.sum(y * np.log(p) + (1 - y) * np.log(1 - p)))


def fit_lr(X, y):
    Xs = (X - X.mean(0)) / (X.std(0) + 1e-9)
    m = LogisticRegression(penalty=None, solver="lbfgs", max_iter=2000)
    m.fit(Xs, y)
    return m.predict_proba(Xs)[:, 1], Xs, m


def loo_auc(X, y):
    """Leave-one-out predicted probabilities -> AUC (robustness for delta-AUC)."""
    n = len(y)
    pred = np.zeros(n)
    for i in range(n):
        mask = np.arange(n) != i
        Xtr, ytr = X[mask], y[mask]
        mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
        m = LogisticRegression(penalty=None, solver="lbfgs", max_iter=2000)
        m.fit((Xtr - mu) / sd, ytr)
        pred[i] = m.predict_proba(((X[i] - mu) / sd).reshape(1, -1))[0, 1]
    return auc(list(pred), list(y.astype(bool)))


def partial_spearman(x, y, z):
    """Partial Spearman(x, y | z): Spearman on ranks, partial via residual corr."""
    rx = stats.rankdata(x)
    ry = stats.rankdata(y)
    rz = stats.rankdata(z)
    rxy = np.corrcoef(rx, ry)[0, 1]
    rxz = np.corrcoef(rx, rz)[0, 1]
    ryz = np.corrcoef(ry, rz)[0, 1]
    denom = np.sqrt((1 - rxz ** 2) * (1 - ryz ** 2))
    if denom == 0:
        return None, None
    r = (rxy - rxz * ryz) / denom
    n = len(x)
    df = n - 3
    if df <= 0 or abs(r) >= 1:
        return float(r), None
    t = r * np.sqrt(df / (1 - r ** 2))
    p = 2 * stats.t.sf(abs(t), df)
    return float(r), float(p)


def sep_sd(vals_fail, vals_pass):
    """(pass mean - fail mean) / pooled SD, and median gap in pooled-SD units."""
    a, b = np.asarray(vals_fail, float), np.asarray(vals_pass, float)
    if len(a) < 2 or len(b) < 2:
        return None, None, None
    sp = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1))
                 / (len(a) + len(b) - 2))
    if sp == 0:
        return None, None, None
    mean_sd = (b.mean() - a.mean()) / sp
    med_sd = (np.median(b) - np.median(a)) / sp
    return float(mean_sd), float(med_sd), float(sp)


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    st = load_settings(CONFIG)
    st.event_log = None
    top_k = st.graphrag.top_k
    questions = json.loads(QUESTIONS.read_text())
    byid = {q.get("_id"): q for q in questions}
    off = {json.loads(l)["id"]: json.loads(l)["pass"]
           for l in SCREEN.read_text().splitlines()
           if l.strip() and json.loads(l)["arm"] == "off"}

    # title -> cert coverage (parse cert `name` via slices; graph-independent)
    slices = load_slices()
    title_cov = {}
    for line in CERT.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("coverage") is None:
            continue
        m = re.match(r"^(.+\.json)#row(\d+)$", r.get("name", "") or "")
        if m and slices.get(m.group(1)) and int(m.group(2)) < len(slices[m.group(1)]):
            title_cov[slices[m.group(1)][int(m.group(2))]] = r["coverage"]
    cov_vals = sorted(title_cov.values())
    cov_median = float(np.median(cov_vals)) if cov_vals else 0.6

    with Foundry(st) as f:
        from knowledge_graph_foundry.graph.graphrag import vector_query  # noqa: E402
        with f.driver.session() as s:
            ents = s.run("MATCH (e:Entity) RETURN e.id AS id, e.name AS name").data()
            edges = s.run(
                "MATCH (a:Entity)-[r]-(b:Entity) WHERE type(r) <> 'SIMILAR_TO' "
                "RETURN a.id AS a, b.id AS b").data()
        idx = {e["id"]: i for i, e in enumerate(ents)}
        name_row = {_norm(e["name"]): idx[e["id"]] for e in ents if e.get("name")}
        n = len(ents)
        # symmetrized + deduped adjacency (H515); deg = distinct neighbors
        adj_set = [set() for _ in range(n)]
        for e in edges:
            if e["a"] in idx and e["b"] in idx:
                a, b = idx[e["a"]], idx[e["b"]]
                if a != b:
                    adj_set[a].add(b)
                    adj_set[b].add(a)
        adj_rows = [list(s) for s in adj_set]
        deg = np.array([len(s) for s in adj_set], dtype=np.int64)
        print(f"h555 {run_id}: {n} entities, {int(deg.sum() // 2)} undirected edges",
              flush=True)

        titles = ingested_titles(f, load_slices())
        eligible = [byid[i] for i in off if i in byid and gold_titles(byid[i])
                    and all(t in titles for t in gold_titles(byid[i]))]
        eligible = eligible[:MAX] if MAX else eligible
        print(f"{len(eligible)} eligible probes", flush=True)

        carrier_rows = []
        for k, q in enumerate(eligible):
            qid = q.get("_id")
            golds = [(t, name_row[_norm(t)]) for t in gold_titles(q)
                     if _norm(t) in name_row]
            if not golds:
                continue
            probe = Entity.create(q["question"][:80], types=["Query"],
                                  description=q["question"])
            qv = generate_embeddings([probe], st.embeddings)[0].embedding
            seeds = vector_query(f.driver, qv, st.graphrag.vector_index_name, top_k=top_k)
            seed_rows = [idx[x["id"]] for x in seeds if x["id"] in idx]
            seed_set = set(seed_rows)
            for t, crow in golds:
                path = bfs_path(adj_rows, seed_set, crow)
                if path is None:
                    rec = {"reachable": False, "hop": None,
                           "min_forman_real": None, "min_deg_real": None}
                elif len(path) == 1:  # 0-hop, carrier is a seed
                    rec = {"reachable": True, "hop": 0,
                           "min_forman_real": None,  # best sentinel filled later
                           "min_deg_real": int(deg[crow]), "zero_hop": True}
                else:
                    fmn = min(4 - int(deg[path[i]]) - int(deg[path[i + 1]])
                              for i in range(len(path) - 1))
                    dmn = min(int(deg[v]) for v in path)
                    rec = {"reachable": True, "hop": len(path) - 1,
                           "min_forman_real": fmn, "min_deg_real": dmn}
                rec.update({"probe": qid, "carrier": t,
                            "off_pass": bool(off.get(qid)),
                            "carrier_cov": title_cov.get(t)})
                carrier_rows.append(rec)
            print(f"[{k+1}/{len(eligible)}] {qid[:12]} pass={off.get(qid)} "
                  f"carriers={len(golds)}", flush=True)

    # --- sentinels (worse/better than any real value) ---------------------
    real_forman = [r["min_forman_real"] for r in carrier_rows
                   if r.get("min_forman_real") is not None]
    F_BEST = max(real_forman) + 1
    F_WORST = min(real_forman) - 1
    DEG_WORST = 0
    for r in carrier_rows:
        if not r["reachable"]:
            r["hop_f"], r["min_forman"], r["min_deg"] = NO_HOP, F_WORST, DEG_WORST
        elif r.get("zero_hop"):
            r["hop_f"], r["min_forman"], r["min_deg"] = 0, F_BEST, r["min_deg_real"]
        else:
            r["hop_f"] = r["hop"]
            r["min_forman"] = r["min_forman_real"]
            r["min_deg"] = r["min_deg_real"]

    # --- per-probe bottleneck rollup (worst carrier per feature, H573) ----
    by_probe = {}
    for r in carrier_rows:
        by_probe.setdefault(r["probe"], []).append(r)
    probe_rows = []
    for qid, rs in by_probe.items():
        covs = [c["carrier_cov"] for c in rs if c["carrier_cov"] is not None]
        probe_rows.append({
            "probe": qid,
            "neg_hop": -max(r["hop_f"] for r in rs),
            "min_forman": min(r["min_forman"] for r in rs),
            "min_deg": min(r["min_deg"] for r in rs),
            "off_pass": rs[0]["off_pass"],
            "n_carriers": len(rs),
            "cert_cov": min(covs) if len(covs) == len(rs) and covs else None,
            "any_unreachable": any(not r["reachable"] for r in rs),
        })

    y = np.array([1 if r["off_pass"] else 0 for r in probe_rows])
    yb = [bool(v) for v in y]
    forman = np.array([r["min_forman"] for r in probe_rows], float)
    neg_hop = np.array([r["neg_hop"] for r in probe_rows], float)
    min_deg = np.array([r["min_deg"] for r in probe_rows], float)

    # ================= H555 =================
    auc_forman = auc(list(forman), yb)          # higher forman => pass
    auc_neghop = auc(list(neg_hop), yb)          # cross-check vs H573 (0.6809)
    auc_mindeg = auc(list(min_deg), yb)
    disc_forman = round(max(auc_forman, 1 - auc_forman), 4) if auc_forman else None
    ff = forman[y == 0]
    fp = forman[y == 1]
    mean_sd, med_sd, pooled_sd = sep_sd(ff, fp)
    mw = stats.mannwhitneyu(fp, ff, alternative="two-sided")
    h555_c = [
        {"clause": "AUC >= 0.68 (min-Forman predicts pass; fail more negative)",
         "predicted": ">=0.68", "measured": auc_forman, "holds": bool(auc_forman is not None and auc_forman >= 0.68)},
        {"clause": "fail median >= 0.5 pooled-SD more negative than pass",
         "predicted": "med gap >= 0.5 SD", "measured": None if med_sd is None else round(med_sd, 3),
         "holds": bool(med_sd is not None and med_sd >= 0.5)},
        {"clause": "Mann-Whitney fail vs pass p < 0.05",
         "predicted": "p<0.05", "measured": round(float(mw.pvalue), 4), "holds": bool(mw.pvalue < 0.05)},
    ]
    if auc_forman is None:
        v555 = "INCONCLUSIVE"
    elif auc_forman >= 0.68 and med_sd is not None and med_sd >= 0.5 and mw.pvalue < 0.05:
        v555 = "CONFIRMED"
    elif auc_forman <= 0.60 or mw.pvalue > 0.10:
        v555 = "KILLED"
    else:
        v555 = "INDETERMINATE"

    # ================= H556 =================
    Xb = np.column_stack([neg_hop, min_deg])
    Xf = np.column_stack([neg_hop, min_deg, forman])
    pb, _, _ = fit_lr(Xb, y)
    pf, _, _ = fit_lr(Xf, y)
    auc_base = auc(list(pb), yb)
    auc_full = auc(list(pf), yb)
    d_auc = round(auc_full - auc_base, 4)
    chi2 = 2 * (llf(y, pf) - llf(y, pb))
    p_lr = float(stats.chi2.sf(max(chi2, 0.0), 1))
    d_auc_loo = round(loo_auc(Xf, y) - loo_auc(Xb, y), 4)
    r_pear = float(np.corrcoef(forman, min_deg)[0, 1])
    r_spear = float(stats.spearmanr(forman, min_deg).statistic)
    r_forman_hop = float(stats.spearmanr(forman, neg_hop).statistic)
    h556_c = [
        {"clause": "Forman earns seat iff delta-AUC >= 0.05 AND LR p < 0.05",
         "predicted": "delta-AUC>=0.05 & p<0.05", "measured": f"delta-AUC={d_auc} (LOO {d_auc_loo}), LR p={round(p_lr,4)}",
         "holds": bool(d_auc >= 0.05 and p_lr < 0.05)},
        {"clause": "redundant (retire) if delta-AUC < 0.03",
         "predicted": "delta-AUC<0.03", "measured": d_auc, "holds": bool(d_auc < 0.03)},
    ]
    if d_auc >= 0.05 and p_lr < 0.05:
        v556 = "CONFIRMED_CURVATURE_EARNS_SEAT"
    elif d_auc < 0.03:
        v556 = "CONFIRMED_REDUNDANT_RETIRE"
    else:
        v556 = "INDETERMINATE"

    # ================= H557 =================
    cov_rows = [r for r in probe_rows if r["cert_cov"] is not None]
    covered = [r for r in cov_rows if r["cert_cov"] >= cov_median]
    cov_fail = [r for r in covered if not r["off_pass"]]
    cov_pass = [r for r in covered if r["off_pass"]]
    cf = [r["min_forman"] for r in cov_fail]
    cp = [r["min_forman"] for r in cov_pass]
    c_mean_sd, c_med_sd, _ = sep_sd(cf, cp) if cf and cp else (None, None, None)
    cmw = stats.mannwhitneyu(cp, cf, alternative="two-sided") if len(cf) >= 2 and len(cp) >= 2 else None
    # partial Spearman over all cert-resolved probes: (min-Forman, fail | cert)
    xf = np.array([r["min_forman"] for r in cov_rows], float)
    yfail = np.array([0 if r["off_pass"] else 1 for r in cov_rows], float)
    zc = np.array([r["cert_cov"] for r in cov_rows], float)
    pr, pr_p = partial_spearman(xf, yfail, zc)
    n_cov_fail = len(cov_fail)
    escalate = n_cov_fail < 15
    h557_c = [
        {"clause": "covered-subset separation >= 0.5 SD (p<0.05)",
         "predicted": ">=0.5 SD, p<0.05",
         "measured": (f"mean {None if c_mean_sd is None else round(c_mean_sd,3)} SD / "
                      f"med {None if c_med_sd is None else round(c_med_sd,3)} SD, "
                      f"MW p={None if cmw is None else round(float(cmw.pvalue),4)}"),
         "holds": bool(c_med_sd is not None and abs(c_med_sd) >= 0.5 and cmw is not None and cmw.pvalue < 0.05)},
        {"clause": "partial Spearman(min-Forman, fail | cert) <= -0.25, p<0.05",
         "predicted": "<=-0.25, p<0.05",
         "measured": f"r={None if pr is None else round(pr,3)}, p={None if pr_p is None else round(pr_p,4)}",
         "holds": bool(pr is not None and pr <= -0.25 and pr_p is not None and pr_p < 0.05)},
        {"clause": "covered-and-failing n >= 15 (else ESCALATE)",
         "predicted": ">=15", "measured": n_cov_fail, "holds": bool(not escalate)},
    ]
    both_hold = h557_c[0]["holds"] and h557_c[1]["holds"]
    if escalate:
        v557 = "ESCALATE_LARGE_RUNG"
    elif both_hold:
        v557 = "CONFIRMED"
    elif pr is None or pr_p is None or pr_p >= 0.05:
        v557 = "KILLED"
    else:
        v557 = "INDETERMINATE"

    # --- H573 cross-check: my -max(hop) should match H573 neg_hop ----------
    xcheck = None
    if H573.exists():
        h = {r["probe"]: r["neg_hop"] for r in json.loads(H573.read_text())["probe_rows"]}
        common = [r for r in probe_rows if r["probe"] in h]
        agree = sum(1 for r in common if r["neg_hop"] == h[r["probe"]])
        xcheck = {"n_common": len(common), "neg_hop_agree": agree,
                  "agree_frac": round(agree / len(common), 4) if common else None}

    summary = {
        "run_id": run_id, "config": str(CONFIG),
        "instrument": "min-Forman = min over seed->carrier shortest-path edges of "
        "4-deg(u)-deg(v) (H486 convention; NO triangle term => local DEGREE-BOTTLENECK, "
        "not curvature). deg = distinct-neighbor count in the undirected SIMILAR_TO-"
        "excluded Entity adjacency (H515), same graph the BFS walks.",
        "seed_path": "dense top-16 via vector_query over kgf_entity_embeddings, "
        "Bedrock Titan probe embeddings (H573-identical)",
        "rollup": "per-probe worst carrier per feature (neg_hop=-max hop, min-Forman=min, "
        "min-deg=min); unreachable-within-6 sentinel neg_hop=-99 / Forman=min_real-1 / "
        "deg=0; 0-hop carrier Forman=max_real+1 / deg=deg(carrier)",
        "n_probes": len(probe_rows), "n_carriers": len(carrier_rows),
        "off_pass": int(y.sum()), "off_fail": int(len(y) - y.sum()),
        "n_unreachable_carriers": int(sum(1 for r in carrier_rows if not r["reachable"])),
        "n_zero_hop_carriers": int(sum(1 for r in carrier_rows if r.get("zero_hop"))),
        "sentinels": {"F_BEST": F_BEST, "F_WORST": F_WORST, "DEG_WORST": DEG_WORST, "NO_HOP": NO_HOP},
        "cert_median_threshold": round(cov_median, 4),
        "h573_neg_hop_crosscheck": xcheck,
        "H555": {"auc_min_forman_pass_oriented": auc_forman,
                 "auc_discriminative": disc_forman,
                 "auc_neg_hop_crosscheck": auc_neghop,
                 "auc_min_deg": auc_mindeg,
                 "fail_median_forman": float(np.median(ff)), "pass_median_forman": float(np.median(fp)),
                 "median_gap_pooled_sd": None if med_sd is None else round(med_sd, 3),
                 "mean_gap_pooled_sd": None if mean_sd is None else round(mean_sd, 3),
                 "pooled_sd": None if pooled_sd is None else round(pooled_sd, 3),
                 "mannwhitney_p": round(float(mw.pvalue), 5),
                 "clauses": h555_c, "proposed_verdict": v555},
        "H556": {"auc_base_hop_deg": auc_base, "auc_full_plus_forman": auc_full,
                 "delta_auc_insample": d_auc, "delta_auc_loo": d_auc_loo,
                 "lr_chi2": round(float(chi2), 4), "lr_p": round(p_lr, 5),
                 "corr_forman_mindeg_pearson": round(r_pear, 4),
                 "corr_forman_mindeg_spearman": round(r_spear, 4),
                 "corr_forman_neghop_spearman": round(r_forman_hop, 4),
                 "clauses": h556_c, "proposed_verdict": v556},
        "H557": {"n_cert_resolved_probes": len(cov_rows), "n_covered": len(covered),
                 "n_covered_fail": n_cov_fail, "n_covered_pass": len(cov_pass),
                 "covered_sep_mean_sd": None if c_mean_sd is None else round(c_mean_sd, 3),
                 "covered_sep_median_sd": None if c_med_sd is None else round(c_med_sd, 3),
                 "covered_mannwhitney_p": None if cmw is None else round(float(cmw.pvalue), 4),
                 "partial_spearman_forman_fail_given_cert": None if pr is None else round(pr, 4),
                 "partial_spearman_p": None if pr_p is None else round(pr_p, 5),
                 "escalate": escalate, "clauses": h557_c, "proposed_verdict": v557},
    }

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"h555-557-ricci-path-{run_id}.json"
    path.write_text(json.dumps(
        {"summary": summary, "probe_rows": probe_rows, "carrier_rows": carrier_rows}, indent=1))
    print("SUMMARY " + json.dumps(summary), flush=True)
    print(f"WROTE {path}", flush=True)


if __name__ == "__main__":
    main()

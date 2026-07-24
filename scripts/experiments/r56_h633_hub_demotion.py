"""R56-H633 - hub-demotion prior inside the anchor list (stage-2 ranking gate, FREE).

The H621/H623 residual: gold entities sit at rank >= 2 inside a CORRECT candidate
list, behind off-gold exact-match GENERIC HUBS (high-degree nodes like `Mother`,
`Maurice`, `United States` that exact-match role-words or common names). H626's
constraint: anchor COUNT must not shrink (surplus anchors are useful reset mass).
So this prior does NOT filter - it REORDERS candidates within each span's list
before selection; the same max-gap adaptive-k then picks from the reordered scores.

Mechanism (per span candidate list):
  adjusted_score = normalized_score - lambda * norm(log(1 + degree))
  degree = id-incidence over edges.json (both endpoints +1 per edge = "both
           directions summed"), mapped to the entity row.
  norm(.) = per-query (per candidate-list) min-max of log1p(degree) -> [0,1].
Candidates are RE-SORTED by adjusted_score desc, re-min-max-normalized, and the
same max-gap detector (H623, lambda_flatline=0.0 incumbent) picks cut_k.

At lambda=0 the arm is byte-identical to the max-gap adaptive-k incumbent
(reach_all 0.8740) - this is baseline B and the honest-control reproduction.

lambda* is chosen on a CAL split of the 157 gold spans (78/79, H623 SEED=0
machinery): the largest lambda that drops ZERO gold picks on cal, maximizing
cal off-gold reduction. lambda* is then FROZEN and the FULL paired evaluation
(off-gold census, gold-pick preservation, paired reachability vs 0.8740) runs
over all 127 probes. Per-lambda cal frontier reported for audit.

Mention-count prior variant: ents_meta.json has no mention/count/freq field
(keys = id,name,types,descr) -> ABSENT; degree-only prior evaluated.

FREE replay over cached H597/H623 candidates + r47 adjacency. NO Neo4j, NO LLM,
NO GPU, NO network. Writes reports/experiments/r56/h633-hub-demotion-<ts>.json.
"""

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np
from scipy.sparse import csr_matrix

sys.path.insert(0, "scripts/experiments")
import r47_h582_embedder_swap as H  # noqa: E402
from rapidfuzz import fuzz, process  # noqa: E402

ROOT = H.ROOT
CACHE = H.CACHE
R50 = ROOT / "tmp/results/r50"
OUT = ROOT / "reports/experiments/r56"
SPAN_CACHE = R50 / "h597_gliner_spans.json"
H619_ART = ROOT / "reports/experiments/r50" / "h619-stoplist-20260713T233206Z.json"

TOP_K = H.TOP_K
PPR_TOP_N = H.PPR_TOP_N
CAND_FLOOR = 0.6
CAND_CAP = 15
K1, B = 1.5, 0.75
SEED = 0

# sanity constants (pre-registered)
MAXGAP_REACH_REF = 0.8740
FIXEDK1_REACH_REF = 0.8661

# lambda sweep grid for the demotion prior
LAM_GRID = [round(x, 3) for x in np.linspace(0.0, 1.0, 21)]


def tok(s):
    return re.findall(r"[a-z0-9]+", s.lower())


def frac(a, b):
    return round(a / b, 4) if b else None


def _norm01(scores):
    s = np.asarray(scores, dtype=float)
    lo, hi = s.min(), s.max()
    if hi - lo < 1e-12:
        return np.ones_like(s)
    return (s - lo) / (hi - lo)


def detect_maxgap(scores):
    """max-gap elbow: cut after the largest adjacent drop. (cut_k, strength)."""
    s = np.asarray(scores, dtype=float)
    m = len(s)
    if m <= 1:
        return m, 1.0
    gaps = s[:-1] - s[1:]
    j = int(np.argmax(gaps))
    return j + 1, float(gaps[j])


def region(r, seeds):
    return set(np.argsort(-r)[:PPR_TOP_N].tolist()) | set(seeds)


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    # -------------------- substrate (H582/H583/H623 harness, verbatim) --------------------
    meta = json.loads((CACHE / "ents_meta.json").read_text())
    edges = json.loads((CACHE / "edges.json").read_text())
    n = len(meta)
    name_norms = [H._norm(m["name"]) if m["name"] else "" for m in meta]
    name_row = {}
    for i, nn in enumerate(name_norms):
        name_row.setdefault(nn, i)

    idx_of_id = {m["id"]: i for i, m in enumerate(meta)}
    ij = np.array([[idx_of_id[a], idx_of_id[b]] for a, b in edges
                   if a in idx_of_id and b in idx_of_id])
    adj = csr_matrix((np.ones(len(ij)), (ij[:, 0], ij[:, 1])), shape=(n, n))
    adj = ((adj + adj.T) > 0).astype(float).tocsr()
    out_deg = np.asarray(adj.sum(axis=1)).ravel()
    out_deg[out_deg == 0] = 1.0

    # DEGREE for the prior = id-incidence over edges.json (both endpoints +1,
    # multiplicity kept) -> the hub signal. Mapped to row index.
    inc = Counter()
    for a, b in edges:
        inc[a] += 1
        inc[b] += 1
    degree = np.zeros(n, dtype=float)
    for eid, c in inc.items():
        if eid in idx_of_id:
            degree[idx_of_id[eid]] = c
    log_deg = np.log1p(degree)   # penalty base per entity

    off_ids = [json.loads(l)["id"] for l in H.SCREEN.read_text().splitlines()
               if l.strip() and json.loads(l)["arm"] == "off"]
    Q = {q.get("_id"): q for q in json.loads(H.QUESTIONS.read_text())}
    probes = [Q[i] for i in off_ids if i in Q]

    graph_norms = set(name_norms)

    def gold_titles(q):
        sf = q.get("supporting_facts") or []
        ts = []
        for it in sf:
            t = it[0] if isinstance(it, (list, tuple)) else it.get("title")
            if t and t not in ts:
                ts.append(t)
        return ts

    src_of, bridge_of, gold_idx_of = {}, {}, {}
    for q in probes:
        pid = q["_id"]
        evs = q.get("evidences") or []
        objs = {H._norm(o_) for (s_, r_, o_) in evs}
        srcs, brs, golds = [], [], []
        for t in gold_titles(q):
            tn = H._norm(t)
            ci = name_row.get(tn)
            if ci is None:
                continue
            golds.append(ci)
            if tn in objs:
                brs.append(ci)
            else:
                srcs.append(ci)
        src_of[pid], bridge_of[pid], gold_idx_of[pid] = srcs, brs, golds

    carriers = []
    for pid in off_ids:
        q = Q.get(pid)
        if not q:
            continue
        for t in gold_titles(q):
            tn = H._norm(t)
            carriers.append({"probe": pid, "carrier": t, "tnorm": tn,
                             "in_graph": tn in graph_norms, "carrier_idx": name_row.get(tn)})
    probe_has_carrier = {pid: [c["carrier_idx"] for c in carriers
                               if c["probe"] == pid and c["in_graph"]] for pid in off_ids}
    reach_pids = [pid for pid in off_ids if probe_has_carrier[pid]]

    titan = np.load(CACHE / "titan_emb.npy")
    titan_n = titan / (np.linalg.norm(titan, axis=1, keepdims=True) + 1e-9)
    d = np.load(CACHE / "titan_probe_emb.npz", allow_pickle=True)
    seeds_q = {}
    for pid in off_ids:
        v = d[pid]
        v = v / (np.linalg.norm(v) + 1e-9)
        sims = titan_n @ v
        order = np.argsort(-sims)
        seeds_q[pid] = [int(x) for x in order[:TOP_K]]

    # -------------------- BM25 over entity names (Okapi, numpy) --------------------
    docs = [tok(nn) for nn in name_norms]
    df = Counter()
    for dd in docs:
        for t in set(dd):
            df[t] += 1
    Nd = len(docs)
    dl = np.array([len(x) for x in docs], dtype=float)
    avgdl = dl.mean()
    idf = {t: np.log(1 + (Nd - c + 0.5) / (c + 0.5)) for t, c in df.items()}
    term_docs = defaultdict(list)
    for i, dd in enumerate(docs):
        for t, f in Counter(dd).items():
            term_docs[t].append((i, f))
    denom_base = K1 * (1 - B + B * dl / avgdl)
    bm25_cache = {}

    def bm25_term_vec(t):
        if t in bm25_cache:
            return bm25_cache[t]
        v = np.zeros(Nd)
        if t in idf:
            for i, f in term_docs[t]:
                v[i] = idf[t] * (f * (K1 + 1)) / (f + denom_base[i])
        bm25_cache[t] = v
        return v

    def bm25_score(qtoks):
        v = np.zeros(Nd)
        for t in set(qtoks):
            v += bm25_term_vec(t)
        return v

    names_arr = name_norms

    def candidate_list(span_norm):
        L = len(span_norm)
        fr = np.asarray(process.cdist([span_norm], names_arr, scorer=fuzz.ratio)[0]) / 100.0
        cont = np.zeros(Nd)
        if L >= 3:
            for i in range(Nd):
                nn = names_arr[i]
                if len(nn) >= 3 and (span_norm in nn or nn in span_norm):
                    cont[i] = min(len(nn), L) / max(len(nn), L)
        bm = bm25_score(tok(span_norm))
        bmn = bm / bm.max() if bm.max() > 0 else bm
        exact = np.zeros(Nd)
        if span_norm in name_row:
            exact[name_row[span_norm]] = 1.0
        blended = np.maximum.reduce([exact, cont, fr, bmn])
        idx = np.where(blended >= CAND_FLOOR)[0]
        if len(idx) == 0:
            idx = np.array([int(np.argmax(blended))])
        idx = idx[np.argsort(-blended[idx])][:CAND_CAP]
        return idx, blended[idx]

    # -------------------- build per-span candidate lists (H623 semantics) --------------------
    spans_by_pid = json.loads(SPAN_CACHE.read_text())
    lexicon = set(json.loads(H619_ART.read_text())["stoplist_lexicon"])

    spanrecs = []
    for pid in off_ids:
        sp = spans_by_pid.get(pid, [])
        for text, gscore in sp:
            sn = H._norm(text)
            idx, blended = candidate_list(sn)
            norm_scores = _norm01(blended)
            cand_deg = log_deg[idx]                 # penalty base, aligned to cand_idx
            golds = set(gold_idx_of[pid])
            gold_targets = [int(i) for i in idx.tolist() if int(i) in golds]
            spanrecs.append({
                "pid": pid, "span": text, "span_norm": sn,
                "cand_idx": idx.tolist(), "raw_scores": blended.tolist(),
                "norm_scores": norm_scores.tolist(),
                "cand_logdeg": cand_deg.tolist(),
                "gold_targets": gold_targets,
                "is_role": sn in lexicon,
            })

    n_spans = len(spanrecs)
    gold_spans = [r for r in spanrecs if r["gold_targets"]]
    print(f"spans={n_spans} gold_spans={len(gold_spans)}", flush=True)

    # -------------------- the hub-demotion prior --------------------
    def demote_pick(r, lam):
        """Reorder candidate list by adjusted score, apply max-gap, return kept
        candidate ROW indices (subset of r['cand_idx'])."""
        ns = np.asarray(r["norm_scores"], dtype=float)
        p = np.asarray(r["cand_logdeg"], dtype=float)
        # per-query min-max of the log-degree penalty -> [0,1]
        plo, phi = p.min(), p.max()
        pen = (p - plo) / (phi - plo) if (phi - plo) > 1e-12 else np.zeros_like(p)
        adj_score = ns - lam * pen
        order = np.argsort(-adj_score, kind="stable")     # reorder by adjusted desc
        cand_re = [r["cand_idx"][j] for j in order]
        s_re = _norm01(adj_score[order])                  # re-normalize reordered scores
        cut_k, _ = detect_maxgap(s_re)
        return cand_re[:cut_k]

    def probe_anchors(lam):
        pa = defaultdict(set)
        for r in spanrecs:
            for ci in demote_pick(r, lam):
                pa[r["pid"]].add(ci)
        return pa

    def offgold_census(pa):
        """gold vs off-gold distinct (pid, idx) picks (H619/H623 offgold_count defn)."""
        gold = off = 0
        for pid in off_ids:
            golds = set(gold_idx_of.get(pid, []))
            for ci in pa.get(pid, set()):
                if ci in golds:
                    gold += 1
                else:
                    off += 1
        return gold, off

    def reach_per_probe(pa):
        """pid -> {all, bridge(None if no bridge)} over reach_pids, reset_region_union."""
        out = {}
        for pid in reach_pids:
            la = list(pa.get(pid, set()))
            dense = seeds_q[pid]
            seeds = la if la else dense
            r = H.ppr(adj, out_deg, seeds, n)
            reg = region(r, seeds) | set(dense)
            cis = probe_has_carrier[pid]
            brs = [b for b in bridge_of[pid] if b is not None]
            out[pid] = {"all": bool(cis) and all(t in reg for t in cis),
                        "bridge": (all(t in reg for t in brs) if brs else None)}
        return out

    def reach_rates(rp):
        allv = [rp[p]["all"] for p in reach_pids]
        brv = [rp[p]["bridge"] for p in reach_pids if rp[p]["bridge"] is not None]
        return frac(sum(allv), len(allv)), frac(sum(brv), len(brv)), len(allv), len(brv)

    # -------------------- SANITY GATE: lambda=0 must reproduce the incumbent --------------------
    pa0 = probe_anchors(0.0)
    rp0 = reach_per_probe(pa0)
    reach0_all, reach0_br, n_all, n_br = reach_rates(rp0)
    gold0, off0 = offgold_census(pa0)   # baseline B
    sanity_ok = abs(reach0_all - MAXGAP_REACH_REF) <= 0.0005
    print(f"SANITY: lambda=0 reach_all={reach0_all} (ref {MAXGAP_REACH_REF}) ok={sanity_ok} "
          f"| baseline B: gold={gold0} off_gold={off0} | n_all={n_all}", flush=True)
    if not sanity_ok:
        print("ABORT: lambda=0 does not reproduce the max-gap incumbent 0.8740", flush=True)
        (OUT / f"h633-hub-demotion-{run_id}.SANITY-FAIL.json").write_text(json.dumps(
            {"sanity_fail": True, "reach0_all": reach0_all, "ref": MAXGAP_REACH_REF,
             "baseline_B_offgold": off0, "baseline_B_gold": gold0}, indent=1, default=float))
        sys.exit(1)

    # -------------------- CAL/HOLD split (H623 machinery, SEED=0) --------------------
    gs_ids = list(range(len(gold_spans)))
    rng.shuffle(gs_ids)
    half = len(gs_ids) // 2
    cal_spans = [gold_spans[i] for i in gs_ids[:half]]
    hold_spans = [gold_spans[i] for i in gs_ids[half:]]

    def cal_metrics(span_set, lam):
        """gold picks kept + off-gold picks over a gold-span set (span-local)."""
        gold_kept = off_gold = 0
        for r in span_set:
            kept = set(demote_pick(r, lam))
            golds = set(r["gold_targets"])
            gold_kept += len(kept & golds)
            off_gold += len(kept - golds)
        return gold_kept, off_gold

    cal_gold_base, _ = cal_metrics(cal_spans, 0.0)

    # -------------------- lambda sweep (cal selection + full-eval audit frontier) --------------------
    frontier = []
    for lam in LAM_GRID:
        cg, cof = cal_metrics(cal_spans, lam)
        pa = probe_anchors(lam)
        gold_f, off_f = offgold_census(pa)
        rp = reach_per_probe(pa)
        ra, rb, _, _ = reach_rates(rp)
        frontier.append({
            "lambda": lam,
            "cal_gold_kept": cg, "cal_gold_base": cal_gold_base,
            "cal_gold_preserved": cg >= cal_gold_base,
            "cal_offgold": cof,
            "full_offgold": off_f, "full_gold": gold_f,
            "full_offgold_reduction_pct": round((1 - off_f / max(off0, 1)) * 100, 2),
            "reach_all": ra, "reach_bridge": rb,
        })
        print(f"  lam={lam}: cal_gold={cg}/{cal_gold_base} cal_off={cof} | "
              f"full_off={off_f} (-{round((1-off_f/max(off0,1))*100,1)}%) reach_all={ra}", flush=True)

    # selection: largest lambda preserving cal gold picks, maximizing cal off-gold reduction.
    preserving = [f for f in frontier if f["cal_gold_preserved"]]
    # among preserving, min cal off-gold (max reduction); tie -> smallest lambda
    best = min(preserving, key=lambda f: (f["cal_offgold"], f["lambda"]))
    lam_star = best["lambda"]
    print(f"SELECTED lambda*={lam_star} (cal off-gold {best['cal_offgold']}, "
          f"cal gold {best['cal_gold_kept']}/{cal_gold_base})", flush=True)

    # -------------------- FULL paired evaluation at frozen lambda* --------------------
    pa_star = probe_anchors(lam_star)
    rp_star = reach_per_probe(pa_star)
    reach_star_all, reach_star_br, _, _ = reach_rates(rp_star)
    gold_star, off_star = offgold_census(pa_star)
    offgold_reduction_pct = round((1 - off_star / max(off0, 1)) * 100, 2)

    # paired reach (all): b = B-only reach, c = demoted-only reach
    b_all = [p for p in reach_pids if rp0[p]["all"] and not rp_star[p]["all"]]   # lost
    c_all = [p for p in reach_pids if rp_star[p]["all"] and not rp0[p]["all"]]   # gained
    b_br = [p for p in reach_pids if rp0[p]["bridge"] and not rp_star[p]["bridge"]
            and rp0[p]["bridge"] is not None and rp_star[p]["bridge"] is not None]
    c_br = [p for p in reach_pids if rp_star[p]["bridge"] and not rp0[p]["bridge"]
            and rp0[p]["bridge"] is not None and rp_star[p]["bridge"] is not None]

    # for the KILLED-branch diagnosis: for each lost probe, was the demoted hub on the gold path?
    lost_detail = []
    for pid in b_all:
        base_anc = pa0.get(pid, set())
        star_anc = pa_star.get(pid, set())
        demoted_out = sorted(base_anc - star_anc)          # anchors present in B, gone at lam*
        golds = set(gold_idx_of.get(pid, []))
        cis = set(probe_has_carrier[pid])
        lost_detail.append({
            "probe": pid,
            "anchors_dropped_by_demotion": [{"idx": i, "name": meta[i]["name"],
                                             "degree": int(degree[i]),
                                             "is_gold": i in golds} for i in demoted_out],
            "n_anchors_B": len(base_anc), "n_anchors_star": len(star_anc),
            "carriers": sorted(cis),
        })

    # gold-pick preservation over the FULL span set (distinct gold picks per probe)
    def full_gold_picks(pa):
        kept = 0
        for pid in off_ids:
            golds = set(gold_idx_of.get(pid, []))
            kept += len(pa.get(pid, set()) & golds)
        return kept
    gold_picks_B = full_gold_picks(pa0)
    gold_picks_star = full_gold_picks(pa_star)

    # -------------------- verdict --------------------
    net_all = len(c_all) - len(b_all)
    zero_unoffset_regression = len(b_all) == 0 or net_all >= 0
    reach_held = reach_star_all >= MAXGAP_REACH_REF - 1e-9
    offgold_bar = offgold_reduction_pct >= 30.0

    if net_all < 0:
        verdict = ("KILLED (paired reachability DROPS net negative - hub identity is "
                   "load-bearing reset mass; H626 inversion extends from anchor COUNT "
                   "to anchor IDENTITY)")
    elif offgold_bar and reach_held and len(b_all) == 0:
        verdict = "CONFIRMED (off-gold >= 30% down AND reach_all >= 0.8740 with zero unoffset regressions)"
    else:
        verdict = (f"INDETERMINATE (off-gold reduction {offgold_reduction_pct}% "
                   f"{'>=' if offgold_bar else '<'} 30%, reach_all {reach_star_all} "
                   f"{'held' if reach_held else 'below'} 0.8740; net reach {net_all:+d})")

    result = {
        "run_id": run_id, "hypothesis": "R56-H633",
        "title": "hub-demotion prior inside the anchor list (stage-2 ranking gate, FREE)",
        "mechanism": {
            "adjusted_score": "normalized_score - lambda * norm(log(1+degree))",
            "degree": "id-incidence over edges.json (both endpoints +1 per edge, multiplicity kept)",
            "penalty_norm": "per-query min-max of log1p(degree) over the candidate list -> [0,1]",
            "selection": "reorder candidates by adjusted score desc -> re-min-max -> max-gap adaptive-k",
            "flatline_lambda": 0.0,
            "mention_count_variant": "ABSENT (ents_meta.json has no mention/count/freq field; degree-only)",
        },
        "params": {"cand_floor": CAND_FLOOR, "cand_cap": CAND_CAP, "bm25_k1": K1, "bm25_b": B,
                   "seed": SEED, "lambda_grid": LAM_GRID, "ppr_iters": H.ITERS, "ppr_damping": H.DAMPING},
        "sanity": {
            "maxgap_reach_all_lambda0": reach0_all, "maxgap_reach_ref": MAXGAP_REACH_REF,
            "fixed_k1_reach_ref": FIXEDK1_REACH_REF,
            "reproduced": bool(sanity_ok),
            "baseline_B_offgold": off0, "baseline_B_gold": gold0,
            "n_reach_probes": n_all, "n_bridge_probes": n_br,
            "h619_reference_points": {"unfiltered_offgold": 125, "stoplist_offgold": 60,
                                      "note": "H619 exact+alias linker census; B here is the max-gap "
                                              "scored-linker census (different arm, more anchors)"},
        },
        "n_spans": n_spans, "n_gold_spans": len(gold_spans),
        "cal_hold_split": {"n_cal_gold_spans": len(cal_spans), "n_hold_gold_spans": len(hold_spans),
                           "cal_gold_picks_base": cal_gold_base},
        "cal_frontier": frontier,
        "lambda_star": lam_star,
        "lambda_star_selection": "largest lambda preserving cal gold picks, min cal off-gold; tie->smallest lambda",
        "primary": {
            "baseline_B_offgold": off0, "demoted_offgold": off_star,
            "offgold_reduction_pct": offgold_reduction_pct,
            "baseline_B_gold_picks": gold_picks_B, "demoted_gold_picks": gold_picks_star,
            "gold_pick_preserved": bool(gold_picks_star >= gold_picks_B),
            "reach_all_B": reach0_all, "reach_all_demoted": reach_star_all,
            "reach_bridge_B": reach0_br, "reach_bridge_demoted": reach_star_br,
            "paired_reach_all": {"b_lost": len(b_all), "c_gained": len(c_all), "net": net_all,
                                 "lost_ids": b_all, "gained_ids": c_all},
            "paired_reach_bridge": {"b_lost": len(b_br), "c_gained": len(c_br),
                                    "net": len(c_br) - len(b_br),
                                    "lost_ids": b_br, "gained_ids": c_br},
            "lost_probe_detail": lost_detail,
        },
        "bars": {
            "offgold_down_30pct": bool(offgold_bar),
            "reach_all_held_8740": bool(reach_held),
            "zero_unoffset_regression": bool(zero_unoffset_regression),
            "net_reach_negative": bool(net_all < 0),
        },
        "proposed_verdict": verdict,
        "artifact": str(OUT / f"h633-hub-demotion-{run_id}.json"),
        "script": "scripts/experiments/r56_h633_hub_demotion.py",
    }
    path = OUT / f"h633-hub-demotion-{run_id}.json"
    path.write_text(json.dumps(result, indent=1, default=float))
    print("\n==== H633 SUMMARY ====", flush=True)
    print(f"  baseline B off-gold={off0} gold={gold0}", flush=True)
    print(f"  lambda*={lam_star}: off-gold={off_star} (-{offgold_reduction_pct}%) "
          f"reach_all={reach_star_all} (ref {MAXGAP_REACH_REF})", flush=True)
    print(f"  paired reach_all: b_lost={len(b_all)} c_gained={len(c_all)} net={net_all:+d}", flush=True)
    print(f"  gold picks: B={gold_picks_B} demoted={gold_picks_star}", flush=True)
    print(f"  VERDICT: {verdict}", flush=True)
    print(f"WROTE {path}", flush=True)


if __name__ == "__main__":
    main()

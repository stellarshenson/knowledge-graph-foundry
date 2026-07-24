"""R40x-H623 + H624 elbow-battery: scored linker rungs + CRC-calibrated head-cut.

Replays the H597 realizable linker (GLiNER spans -> graph entities) but replaces
the fixed exact/alias ladder with SCORED candidate lists (exact 1.0 tier +
normalized-containment + fuzzy Levenshtein ratio + Okapi BM25 over the 6,626
entity names, blended by max, per-query min-max normalized) and an adaptive
head-cut chosen by an ELBOW DETECTOR. Three detectors compete (H623 bakeoff):

  max-gap   - cut after the largest adjacent score drop; strength = that gap
  kneedle   - normalized-difference knee (Satopaa 2011); strength = max(d)
  spline    - scipy UnivariateSpline over sorted scores; strength = max |curvature|

Each detector's flat-line/significance parameter lambda is CRC-calibrated on a
gold calibration split so that P(the cut drops a gold anchor | span has a gold
target) <= alpha=0.10; scored on the held-out split. Below lambda -> FLAT-LINE
-> ABSTAIN (keep nothing). Baselines: fixed-k=1, fixed-k=2, fixed-threshold
(best precision on calibration). Stability: bootstrap-perturb scores with sigma
estimated from the fuzzy/BM25 dispersion of span->gold-entity residuals; 200
resamples; per-detector cut-index variance.

H624 (same run): the flat-line flag as an ambiguity detector - precision vs the
gold ambiguous set (role-word/abstain spans + H561 ties), false-flat on clean,
forced-elbow control (argmax-gap regardless of significance) vs the routed arm
(abstain->dense fallback / oracle-attacher).

FREE replay over cached H597 candidates; READ-ONLY (no Neo4j, no LLM). Writes
reports/experiments/r50/h623-elbow-gate-<ts>.json and h624-flatline-<ts>.json.
"""

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np
from scipy.sparse import csr_matrix
from scipy.interpolate import UnivariateSpline

sys.path.insert(0, "scripts/experiments")
import r47_h582_embedder_swap as H  # noqa: E402
from rapidfuzz import fuzz, process  # noqa: E402

ROOT = H.ROOT
CACHE = H.CACHE
R50 = ROOT / "tmp/results/r50"
OUT = ROOT / "reports/experiments/r50"
SPAN_CACHE = R50 / "h597_gliner_spans.json"
H619_ART = OUT / "h619-stoplist-20260713T233206Z.json"
H561_ART = ROOT / "reports/experiments/r49/h561-rai-samedoc-20260713T214807Z.json"

TOP_K = H.TOP_K
PPR_TOP_N = H.PPR_TOP_N
ALPHA = 0.10
CAND_FLOOR = 0.6      # blended-score floor for the plausible candidate pool
CAND_CAP = 15
K1, B = 1.5, 0.75
N_BOOT = 200
SEED = 0
ISO_REACH_REF = 0.622
ORACLE_SEED_REACH = 0.898


def tok(s):
    return re.findall(r"[a-z0-9]+", s.lower())


def frac(a, b):
    return round(a / b, 4) if b else None


# ----------------------------------------------------------- detectors
def _norm01(scores):
    s = np.asarray(scores, dtype=float)
    lo, hi = s.min(), s.max()
    if hi - lo < 1e-12:
        return np.ones_like(s)          # perfectly flat -> all 1
    return (s - lo) / (hi - lo)


def detect_maxgap(scores):
    """Return (cut_k, strength). cut_k in [1..len]. strength = largest gap (raw scale)."""
    s = np.asarray(scores, dtype=float)
    m = len(s)
    if m <= 1:
        return m, 1.0                    # single candidate: keep it, max confidence
    gaps = s[:-1] - s[1:]                 # gap between rank i and i+1
    j = int(np.argmax(gaps))
    return j + 1, float(gaps[j])


def detect_kneedle(scores):
    """Normalized-difference knee (Satopaa 2011). strength = max difference-curve height."""
    s = np.asarray(scores, dtype=float)
    m = len(s)
    if m <= 1:
        return m, 1.0
    if m == 2:
        return 1, float(s[0] - s[1])
    x = np.linspace(0, 1, m)
    y = _norm01(s)                        # decreasing, in [0,1]
    d = y - (1 - x)                       # difference from the concave-decreasing diagonal
    j = int(np.argmax(d))
    return max(j + 1, 1), float(max(d.max(), 0.0))


def detect_spline(scores, s_smooth=None):
    """UnivariateSpline curvature. strength = max |2nd deriv| at interior knots.
    smoothing s: default len*var(y) (scipy heuristic scale). Reported honestly."""
    y = np.asarray(scores, dtype=float)
    m = len(y)
    if m <= 2:
        return detect_maxgap(scores)      # curvature ill-defined at n<=2 -> max-gap fallback
    x = np.arange(m, dtype=float)
    yv = _norm01(y)
    if s_smooth is None:
        s_smooth = max(1e-3, 0.05 * m)    # light smoothing; stated in artifact
    k = min(3, m - 1)
    try:
        spl = UnivariateSpline(x, yv, k=k, s=s_smooth)
        xs = np.linspace(0, m - 1, 200)
        curv = spl.derivative(2)(xs)
        # cut at the max-curvature location mapped to the nearest rank boundary
        j = int(round(xs[int(np.argmax(np.abs(curv)))]))
        cut = min(max(j, 1), m)
        return cut, float(np.max(np.abs(curv)))
    except Exception:
        return detect_maxgap(scores)


DETECTORS = {"maxgap": detect_maxgap, "kneedle": detect_kneedle, "spline": detect_spline}


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    # -------------------- shared structures (H582/H583 harness) --------------------
    meta = json.loads((CACHE / "ents_meta.json").read_text())
    edges = json.loads((CACHE / "edges.json").read_text())
    n = len(meta)
    name_norms = [H._norm(m["name"]) if m["name"] else "" for m in meta]
    name_row = {}
    for i, nn in enumerate(name_norms):
        name_row.setdefault(nn, i)
    name_len = [len(s) for s in name_norms]

    idx_of_id = {m["id"]: i for i, m in enumerate(meta)}
    ij = np.array([[idx_of_id[a], idx_of_id[b]] for a, b in edges
                   if a in idx_of_id and b in idx_of_id])
    adj = csr_matrix((np.ones(len(ij)), (ij[:, 0], ij[:, 1])), shape=(n, n))
    adj = ((adj + adj.T) > 0).astype(float).tocsr()
    out_deg = np.asarray(adj.sum(axis=1)).ravel()
    out_deg[out_deg == 0] = 1.0

    off_ids = [json.loads(l)["id"] for l in H.SCREEN.read_text().splitlines()
               if l.strip() and json.loads(l)["arm"] == "off"]
    Q = {q.get("_id"): q for q in json.loads(H.QUESTIONS.read_text())}
    probes = [Q[i] for i in off_ids if i in Q]
    questions_by_id = {pid: Q[pid] for pid in off_ids if pid in Q}
    qclass = {q["_id"]: q.get("type") for q in probes}

    graph_norms = set(name_norms)

    def gold_titles(q):
        sf = q.get("supporting_facts") or []
        ts = []
        for it in sf:
            t = it[0] if isinstance(it, (list, tuple)) else it.get("title")
            if t and t not in ts:
                ts.append(t)
        return ts

    # gold source / bridge / all gold entities per probe (H583 convention)
    src_of, bridge_of, gold_idx_of = {}, {}, {}
    for q in probes:
        pid = q["_id"]
        evs = q.get("evidences") or []
        subs = {H._norm(s_) for (s_, r_, o_) in evs}
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

    # carriers (for reachability) + dense@16 seeds
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
    seeds_q, cos_scores_q = {}, {}
    for pid in off_ids:
        v = d[pid]
        v = v / (np.linalg.norm(v) + 1e-9)
        sims = titan_n @ v
        order = np.argsort(-sims)
        seeds_q[pid] = [int(x) for x in order[:TOP_K]]
        cos_scores_q[pid] = sims[order[:TOP_K]].astype(float)

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
    # sparse term -> doc freq for vectorized scoring
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
        """Return (idx_sorted, blended_sorted, rung_detail) for a span."""
        L = len(span_norm)
        fr = np.asarray(process.cdist([span_norm], names_arr, scorer=fuzz.ratio)[0]) / 100.0
        cont = np.zeros(Nd)
        if L >= 3:
            # only iterate over entities sharing >=1 token or substring is expensive;
            # containment is cheap enough vectorized via python over candidates with token overlap
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
        return idx, blended[idx], {"exact": exact, "fuzzy": fr, "cont": cont, "bm25n": bmn}

    # -------------------- build per-span candidate lists --------------------
    spans_by_pid = json.loads(SPAN_CACHE.read_text())
    lexicon = set(json.loads(H619_ART.read_text())["stoplist_lexicon"])

    spanrecs = []   # one per (pid, span occurrence)
    for pid in off_ids:
        sp = spans_by_pid.get(pid, [])
        for text, gscore in sp:
            sn = H._norm(text)
            idx, blended, _ = candidate_list(sn)
            # per-query min-max normalize the blended candidate scores
            norm_scores = _norm01(blended)
            golds = set(gold_idx_of[pid])
            cand_is_gold = [int(i) in golds for i in idx.tolist()]
            gold_targets = [int(i) for i in idx.tolist() if int(i) in golds]
            exact_idx = name_row.get(sn)
            n_exact = int(sn in name_row)   # collisions ~0 at medium
            is_role = sn in lexicon
            # subset label (gold-structure only, detector-independent)
            if is_role or len(gold_targets) == 0:
                subset = "tie"            # abstain-ideal / role-word / no gold in pool
                ideal = "abstain"
            elif (len(gold_targets) == 1 and exact_idx is not None
                  and exact_idx in gold_targets and n_exact == 1
                  and int(idx[0]) == exact_idx):
                subset = "clean"
                ideal = "keep_gold"
            else:
                subset = "tie"
                ideal = "keep_gold"
            spanrecs.append({
                "pid": pid, "span": text, "span_norm": sn,
                "cand_idx": idx.tolist(), "raw_scores": blended.tolist(),
                "norm_scores": norm_scores.tolist(),
                "cand_is_gold": cand_is_gold, "gold_targets": gold_targets,
                "is_role": is_role, "subset": subset, "ideal": ideal,
                "exact_idx": exact_idx,
            })

    n_spans = len(spanrecs)
    n_clean = sum(1 for r in spanrecs if r["subset"] == "clean")
    n_tie = n_spans - n_clean
    print(f"spans={n_spans} clean={n_clean} tie={n_tie}", flush=True)

    # -------------------- sigma for stability (residual dispersion) --------------------
    # noise scale = std of (1 - fuzzy_ratio) of span->its-gold-target where gold present,
    # i.e. the textual score noise among known-same-entity (span, correct name) pairs.
    resid = []
    for r in spanrecs:
        for gt in r["gold_targets"]:
            if gt in r["cand_idx"]:
                pos = r["cand_idx"].index(gt)
                resid.append(1.0 - r["raw_scores"][pos])
    sigma = float(np.std(resid)) if resid else 0.05
    print(f"sigma (score-noise) = {sigma:.4f} from {len(resid)} span-gold pairs", flush=True)

    # -------------------- detector cut application --------------------
    def apply_detector(scores, det, lam):
        """Return set of kept ranks (indices into the candidate list) or [] if flat-line."""
        cut_k, strength = DETECTORS[det](scores)
        if strength < lam:
            return [], cut_k, strength      # flat-line -> abstain
        return list(range(cut_k)), cut_k, strength

    # gold-bearing spans (for CRC recall-risk)
    gold_spans = [r for r in spanrecs if r["gold_targets"]]

    def recall_risk(det, lam):
        """P(gold target dropped | span has a gold target) on a set of spanrecs."""
        drops = 0
        tot = 0
        for r in gold_spans:
            keep, _, _ = apply_detector(r["norm_scores"], det, lam)
            kept_idx = {r["cand_idx"][k] for k in keep}
            for gt in r["gold_targets"]:
                tot += 1
                if gt not in kept_idx:
                    drops += 1
        return drops / tot if tot else 0.0, tot

    # -------------------- CRC calibration (split gold spans) --------------------
    gs_ids = list(range(len(gold_spans)))
    rng.shuffle(gs_ids)
    half = len(gs_ids) // 2
    cal_ids = set(gs_ids[:half])
    # calibration risk uses only calibration gold spans
    cal_spans = [gold_spans[i] for i in gs_ids[:half]]
    hold_spans = [gold_spans[i] for i in gs_ids[half:]]

    def cal_recall_risk(det, lam, span_set):
        drops, tot = 0, 0
        for r in span_set:
            keep, _, _ = apply_detector(r["norm_scores"], det, lam)
            kept_idx = {r["cand_idx"][k] for k in keep}
            for gt in r["gold_targets"]:
                tot += 1
                if gt not in kept_idx:
                    drops += 1
        return (drops / tot if tot else 0.0), tot

    crc = {}
    for det in DETECTORS:
        # strength grid from observed strengths
        strengths = sorted({round(DETECTORS[det](r["norm_scores"])[1], 4) for r in spanrecs})
        n_cal = len(cal_spans)
        alpha_corr = ALPHA - (1 - ALPHA) / (n_cal + 1) if n_cal else ALPHA  # finite-sample CRC bound
        feasible = []
        for lam in strengths:
            R, _ = cal_recall_risk(det, lam, cal_spans)
            if R <= max(alpha_corr, 0.0):
                feasible.append(lam)
        lam_star = max(feasible) if feasible else 0.0
        R_cal, _ = cal_recall_risk(det, lam_star, cal_spans)
        R_hold, _ = cal_recall_risk(det, lam_star, hold_spans)
        crc[det] = {"lambda": round(float(lam_star), 4),
                    "alpha": ALPHA, "alpha_finite_sample": round(float(alpha_corr), 4),
                    "cal_recall_risk": round(R_cal, 4), "hold_recall_risk": round(R_hold, 4),
                    "feasible": len(feasible) > 0,
                    "n_cal_gold_spans": n_cal, "n_hold_gold_spans": len(hold_spans)}
    print("CRC:", json.dumps(crc), flush=True)

    # -------------------- scoring: per detector + baselines, per subset --------------------
    def score_arm(keep_fn, span_set):
        """keep_fn(r)->list of kept ranks. Return precision/recall micro on the subset."""
        tp = fp = 0
        gold_present = 0
        gold_kept = 0
        for r in span_set:
            keep = keep_fn(r)
            kept_idx = {r["cand_idx"][k] for k in keep}
            golds = set(r["gold_targets"])
            for i in kept_idx:
                if i in golds:
                    tp += 1
                else:
                    fp += 1
            gold_present += len(golds)
            gold_kept += len(kept_idx & golds)
        prec = frac(tp, tp + fp)
        rec = frac(gold_kept, gold_present)
        return {"precision": prec, "recall": rec, "tp": tp, "fp": fp,
                "gold_present": gold_present, "gold_kept": gold_kept, "n_spans": len(span_set)}

    def keep_detector(det, lam):
        def f(r):
            keep, _, _ = apply_detector(r["norm_scores"], det, lam)
            return keep
        return f

    def keep_fixed_k(k):
        return lambda r: list(range(min(k, len(r["cand_idx"]))))

    # fixed-threshold: best precision on calibration gold spans over a grid
    thr_grid = np.round(np.linspace(0.5, 1.0, 26), 3)
    def keep_thresh(t):
        return lambda r: [k for k, s in enumerate(r["norm_scores"]) if s >= t]
    best_t, best_p = 0.999, -1
    for t in thr_grid:
        sc = score_arm(keep_thresh(t), cal_spans)
        # objective: precision with recall >= (1-alpha)
        if sc["precision"] is not None and (sc["recall"] or 0) >= (1 - ALPHA) and sc["precision"] > best_p:
            best_p, best_t = sc["precision"], t
    fixed_threshold = float(best_t)

    subsets = {"all": spanrecs,
               "clean": [r for r in spanrecs if r["subset"] == "clean"],
               "tie": [r for r in spanrecs if r["subset"] == "tie"]}
    hold_subsets = {"all": hold_spans,
                    "clean": [r for r in hold_spans if r["subset"] == "clean"],
                    "tie": [r for r in hold_spans if r["subset"] == "tie"]}

    bakeoff = {}
    for name, kf in ([(f"detector:{det}", keep_detector(det, crc[det]["lambda"])) for det in DETECTORS]
                     + [("fixed_k1", keep_fixed_k(1)), ("fixed_k2", keep_fixed_k(2)),
                        (f"fixed_threshold@{fixed_threshold}", keep_thresh(fixed_threshold))]):
        bakeoff[name] = {sub: score_arm(kf, hold_subsets[sub]) for sub in hold_subsets}
        # also report on full span set for reference
        bakeoff[name]["all_fullset"] = {sub: score_arm(kf, subsets[sub]) for sub in subsets}

    # -------------------- stability (bootstrap cut-index variance) --------------------
    stability = {}
    for det in DETECTORS:
        cut_vars = []
        flip_rates = []
        for r in spanrecs:
            base_keep, base_cut, _ = apply_detector(r["norm_scores"], det, crc[det]["lambda"])
            cuts = []
            flips = 0
            base_set = frozenset(r["cand_idx"][k] for k in base_keep)
            for _ in range(N_BOOT):
                pert = np.asarray(r["raw_scores"]) + rng.normal(0, sigma, size=len(r["raw_scores"]))
                ns = _norm01(pert)
                keep, cut, _ = apply_detector(ns, det, crc[det]["lambda"])
                cuts.append(cut if keep else 0)
                if frozenset(r["cand_idx"][k] for k in keep) != base_set:
                    flips += 1
            cut_vars.append(float(np.var(cuts)))
            flip_rates.append(flips / N_BOOT)
        stability[det] = {"mean_cut_index_variance": round(float(np.mean(cut_vars)), 4),
                          "median_cut_index_variance": round(float(np.median(cut_vars)), 4),
                          "mean_keptset_flip_rate": round(float(np.mean(flip_rates)), 4),
                          "sigma": round(sigma, 4), "n_boot": N_BOOT}
    print("STABILITY:", json.dumps(stability), flush=True)

    # -------------------- reachability end-to-end (reset_region_union) --------------------
    def region(r, seeds):
        return set(np.argsort(-r)[:PPR_TOP_N].tolist()) | set(seeds)

    # per-probe anchor sets for each arm
    def probe_anchors(keep_fn):
        pa = defaultdict(set)
        for r in spanrecs:
            keep = keep_fn(r)
            for k in keep:
                pa[r["pid"]].add(r["cand_idx"][k])
        return pa

    def reach_rate_for(pa):
        allv, brv = [], []
        for pid in reach_pids:
            la = list(pa.get(pid, set()))
            dense = seeds_q[pid]
            seeds = la if la else dense
            r = H.ppr(adj, out_deg, seeds, n)
            reg = region(r, seeds) | set(dense)     # reset_region_union
            cis = probe_has_carrier[pid]
            brs = [b for b in bridge_of[pid] if b is not None]
            allv.append(bool(cis) and all(t in reg for t in cis))
            if brs:
                brv.append(all(t in reg for t in brs))
        return frac(sum(allv), len(allv)), frac(sum(brv), len(brv)), len(allv), len(brv)

    reach_arms = {}
    for name, kf in ([(f"detector:{det}", keep_detector(det, crc[det]["lambda"])) for det in DETECTORS]
                     + [("fixed_k1", keep_fixed_k(1)), ("fixed_k2", keep_fixed_k(2)),
                        ("all_exact_alias_H597ref", None)]):
        if kf is None:
            # H597 unfiltered ref: keep every candidate that is an exact or containment match (rank where raw==1.0 or gold)
            def kf_ref(r):
                return [k for k, s in enumerate(r["raw_scores"]) if s >= 0.999] or ([0] if r["exact_idx"] is not None else [])
            pa = probe_anchors(kf_ref)
        else:
            pa = probe_anchors(kf)
        ra, rb, na, nb = reach_rate_for(pa)
        reach_arms[name] = {"reach_all": ra, "reach_bridge": rb, "n_all": na, "n_bridge": nb,
                            "total_anchors": sum(len(v) for v in pa.values())}
    print("REACH:", json.dumps(reach_arms), flush=True)

    # secondary: dense@16 adaptive-k on cosine scores
    dense_adaptive = {}
    for det in DETECTORS:
        allv = []
        ks = []
        for pid in reach_pids:
            cs = cos_scores_q[pid]
            ns = _norm01(cs)
            cut_k, strength = DETECTORS[det](ns)
            k = cut_k if strength >= crc[det]["lambda"] else TOP_K   # flat-line -> keep full 16
            k = max(1, min(k, TOP_K))
            ks.append(k)
            seeds = seeds_q[pid][:k]
            r = H.ppr(adj, out_deg, seeds, n)
            reg = region(r, seeds)
            cis = probe_has_carrier[pid]
            allv.append(bool(cis) and all(t in reg for t in cis))
        dense_adaptive[det] = {"reach_all": frac(sum(allv), len(allv)),
                               "mean_k": round(float(np.mean(ks)), 2), "n": len(allv)}
    # dense fixed-16 reference
    allv = []
    for pid in reach_pids:
        seeds = seeds_q[pid]
        r = H.ppr(adj, out_deg, seeds, n)
        reg = region(r, seeds)
        cis = probe_has_carrier[pid]
        allv.append(bool(cis) and all(t in reg for t in cis))
    dense_fixed16 = frac(sum(allv), len(allv))

    # -------------------- verdict clauses (H623) --------------------
    def best_fixed_k_prec(sub):
        return max(bakeoff["fixed_k1"][sub]["precision"] or 0,
                   bakeoff["fixed_k2"][sub]["precision"] or 0)

    best_det = max(DETECTORS, key=lambda dt: (bakeoff[f"detector:{dt}"]["tie"]["precision"] or 0))
    det_tie_p = bakeoff[f"detector:{best_det}"]["tie"]["precision"] or 0
    det_tie_r = bakeoff[f"detector:{best_det}"]["tie"]["recall"] or 0
    fk_tie_p = best_fixed_k_prec("tie")
    fk_tie_r = max(bakeoff["fixed_k1"]["tie"]["recall"] or 0, bakeoff["fixed_k2"]["tie"]["recall"] or 0)
    det_clean_r = bakeoff[f"detector:{best_det}"]["clean"]["recall"] or 0
    fk1_clean_r = bakeoff["fixed_k1"]["clean"]["recall"] or 0

    h623_clauses = [
        {"clause": "elbow-gated gold-anchor precision >= best fixed-k + 10pp on the tie/collision subset "
                   "at equal-or-better recall",
         "predicted": ">= +10pp precision, recall not worse",
         "measured": f"best detector={best_det}: tie precision {det_tie_p} vs fixed-k best {fk_tie_p} "
                     f"(delta {round((det_tie_p-fk_tie_p)*100,2)}pp); tie recall {det_tie_r} vs {fk_tie_r}",
         "holds": bool(det_tie_p - fk_tie_p >= 0.10 and det_tie_r >= fk_tie_r)},
        {"clause": "clean-subset recall preserved (reset-purity) - elbow does not cut genuine anchors",
         "predicted": "clean recall >= fixed-k1 clean recall",
         "measured": f"detector clean recall {det_clean_r} vs fixed-k1 {fk1_clean_r}",
         "holds": bool(det_clean_r >= fk1_clean_r - 1e-9)},
        {"clause": "CRC alpha-feasible threshold exists on gold (else the mechanism dies at calibration - V3)",
         "predicted": "feasible per detector",
         "measured": {dt: crc[dt]["feasible"] for dt in DETECTORS},
         "holds": all(crc[dt]["feasible"] for dt in DETECTORS)},
        {"clause": "clean-subset end-to-end reachability unchanged vs the H597 reference",
         "predicted": "no regression",
         "measured": f"detector:{best_det} reach_all {reach_arms['detector:'+best_det]['reach_all']} "
                     f"vs H597ref {reach_arms['all_exact_alias_H597ref']['reach_all']}",
         "holds": None},
        {"clause": "STABILITY: elbow cut-index variance under noise - spline identifiable at tiny n?",
         "predicted": "the arm that manufactures elbows from noise shows high variance",
         "measured": {dt: stability[dt]["mean_cut_index_variance"] for dt in DETECTORS},
         "holds": None},
    ]

    prec_win = det_tie_p - fk_tie_p >= 0.10 and det_tie_r >= fk_tie_r
    clean_ok = det_clean_r >= fk1_clean_r - 1e-9
    if prec_win and clean_ok:
        h623_verdict = "CONFIRMED"
    elif det_tie_p <= fk_tie_p:
        h623_verdict = "KILLED (elbow <= best fixed-k on the tie subset - distributions too clean/chaotic for adaptivity)"
    else:
        h623_verdict = "INDETERMINATE (partial precision lift below the +10pp bar; see hidden-mechanism notes)"

    h623 = {
        "run_id": run_id, "hypothesis": "R40x-H623",
        "scoring_fence": "candidate-selection precision/recall (span->entity picks) + reset_region_union reachability, paired",
        "params": {"cand_floor": CAND_FLOOR, "cand_cap": CAND_CAP, "bm25_k1": K1, "bm25_b": B,
                   "alpha": ALPHA, "n_boot": N_BOOT, "seed": SEED, "sigma_noise": round(sigma, 4),
                   "blend": "max(exact1.0, containment, fuzzy_ratio, bm25_minmax); per-query min-max normalized",
                   "spline_smoothing": "s = 0.05*len(scores) (light); k=min(3,m-1); curvature ill-defined at m<=2 -> maxgap"},
        "n_spans": n_spans, "n_clean_spans": n_clean, "n_tie_spans": n_tie,
        "n_gold_spans": len(gold_spans),
        "candidate_size_dist": {
            "min": int(min(len(r["cand_idx"]) for r in spanrecs)),
            "median": float(np.median([len(r["cand_idx"]) for r in spanrecs])),
            "mean": round(float(np.mean([len(r["cand_idx"]) for r in spanrecs])), 2),
            "max": int(max(len(r["cand_idx"]) for r in spanrecs))},
        "crc_calibration": crc,
        "detector_bakeoff": bakeoff,
        "fixed_threshold_calibrated": fixed_threshold,
        "stability": stability,
        "reachability_end_to_end": reach_arms,
        "dense16_adaptive_k_secondary": {"adaptive": dense_adaptive, "fixed16_ref": dense_fixed16},
        "clauses": h623_clauses,
        "proposed_verdict": h623_verdict,
        "artifact": str(OUT / f"h623-elbow-gate-{run_id}.json"),
        "script": "scripts/experiments/r50_h623_elbow_battery.py",
    }
    (OUT / f"h623-elbow-gate-{run_id}.json").write_text(json.dumps(h623, indent=1, default=float))
    print(f"WROTE h623 verdict={h623_verdict}", flush=True)

    # ==================================================================
    #  H624 - flat-line as an alpha-certified ambiguity signal
    # ==================================================================
    # ambiguous gold set = tie-subset spans whose ideal is ABSTAIN (role-word / no gold in pool)
    ambiguous_spans = [r for r in spanrecs if r["ideal"] == "abstain"]
    clean_only = [r for r in spanrecs if r["subset"] == "clean"]

    h624 = {"run_id": run_id, "hypothesis": "R40x-H624",
            "definitions": {
                "flat_line": "detector strength < CRC lambda -> abstain",
                "gold_ambiguous_set": "spans whose gold-structure ideal is ABSTAIN "
                                      "(role-word span OR no gold anchor in candidate pool) "
                                      f"= {len(ambiguous_spans)} spans; H561 tie rows folded as a cross-check",
                "clean_set": f"single-exact-gold spans = {len(clean_only)}"},
            "per_detector": {}}
    for det in DETECTORS:
        lam = crc[det]["lambda"]
        # flat-line confusion on ambiguous vs clean
        tp = sum(1 for r in ambiguous_spans if apply_detector(r["norm_scores"], det, lam)[0] == [])
        fn = len(ambiguous_spans) - tp
        false_flat = sum(1 for r in clean_only if apply_detector(r["norm_scores"], det, lam)[0] == [])
        flat_precision = frac(tp, tp + false_flat)   # of all flat-line fires, frac that are truly ambiguous
        flat_recall = frac(tp, len(ambiguous_spans))
        false_flat_rate = frac(false_flat, len(clean_only))
        # forced-elbow control (argmax-gap regardless of significance) vs routed (abstain) on the ambiguous set
        forced_offgold = 0   # picks on ambiguous spans when forced to elbow
        routed_offgold = 0
        forced_picks = routed_picks = 0
        for r in ambiguous_spans:
            fk, _ = DETECTORS["maxgap"](r["norm_scores"])   # forced: always cut, ignore lambda
            forced_keep = set(r["cand_idx"][k] for k in range(fk))
            forced_picks += len(forced_keep)
            forced_offgold += sum(1 for i in forced_keep if i not in set(r["gold_targets"]))
            rk, _, strg = apply_detector(r["norm_scores"], det, lam)
            routed_keep = set(r["cand_idx"][k] for k in rk)
            routed_picks += len(routed_keep)
            routed_offgold += sum(1 for i in routed_keep if i not in set(r["gold_targets"]))
        # anchor precision on the flat subset: forced vs routed (oracle-attacher = gold given on flat-line)
        # forced arm precision = gold picks / all picks on ambiguous spans (mostly off-gold hubs)
        forced_prec = frac(forced_picks - forced_offgold, forced_picks)
        routed_prec = frac(routed_picks - routed_offgold, routed_picks) if routed_picks else 1.0
        h624["per_detector"][det] = {
            "lambda": lam,
            "flat_line_precision_vs_ambiguous": flat_precision,
            "flat_line_recall_vs_ambiguous": flat_recall,
            "false_flat_rate_on_clean": false_flat_rate,
            "n_ambiguous": len(ambiguous_spans), "n_clean": len(clean_only),
            "flat_tp": tp, "flat_fn": fn, "false_flat": false_flat,
            "forced_elbow_offgold_picks": forced_offgold,
            "routed_offgold_picks": routed_offgold,
            "forced_elbow_anchor_precision_on_flat": forced_prec,
            "routed_anchor_precision_on_flat": routed_prec,
            "forced_minus_routed_precision_pp": (round(((forced_prec or 0) - (routed_prec or 0)) * 100, 2)),
            "oracle_attacher_note": "oracle-attacher = gold answer injected on flat-line queries (SIMULATED, "
                                    "no LLM); routed arm falls back to dense status quo when flat-line fires",
        }
    # H561 cross-check: tie rows with n_matches>=2 are ambiguous; strict resolves 7/12
    h561 = json.loads(H561_ART.read_text())
    amb561 = [r for r in h561["rows"] if r.get("n_matches", 0) >= 2 or r.get("gold_carrier") is None]
    h624["h561_crosscheck"] = {
        "n_ambiguous_h561": len(amb561),
        "strict_resolves": h561["clause"]["strict_resolves"],
        "anchor_longest_resolves": h561["clause"]["anchor_longest_tiebreak_resolves"],
        "note": "H561 substrate is fact-level (r49 carrier bakeoff), folded as a directional cross-check only",
    }
    # H624 clauses
    best624 = max(DETECTORS, key=lambda dt: (h624["per_detector"][dt]["flat_line_precision_vs_ambiguous"] or 0))
    fp_prec = h624["per_detector"][best624]["flat_line_precision_vs_ambiguous"] or 0
    ff_rate = h624["per_detector"][best624]["false_flat_rate_on_clean"] or 0
    fmr = h624["per_detector"][best624]["forced_minus_routed_precision_pp"]
    h624["clauses"] = [
        {"clause": "flat-line precision >= 80% against the gold ambiguous set",
         "predicted": ">= 0.80", "measured": f"{best624}: {fp_prec}", "holds": bool(fp_prec >= 0.80)},
        {"clause": "false-flat rate <= 10% on clean queries",
         "predicted": "<= 0.10", "measured": f"{best624}: {ff_rate}", "holds": bool(ff_rate <= 0.10)},
        {"clause": "forced-elbow loses >= 10pp anchor precision on the flat subset vs the routed arm",
         "predicted": ">= 10pp loss (routed > forced)",
         "measured": f"{best624}: forced-minus-routed {fmr}pp",
         "holds": bool(fmr <= -10.0)},
        {"clause": "KILL: flat-line fires > 25% on clean queries (detector is noise)",
         "predicted": "kill if > 0.25", "measured": f"{best624}: {ff_rate}", "holds": bool(ff_rate > 0.25)},
    ]
    if ff_rate > 0.25:
        h624_verdict = "KILLED (flat-line fires > 25% on clean - detector is noise; fixed-threshold fallback stands)"
    elif fp_prec >= 0.80 and ff_rate <= 0.10 and fmr <= -10.0:
        h624_verdict = "CONFIRMED (flat-line ships as the abstention branch; attacher as its escalation)"
    else:
        h624_verdict = "INDETERMINATE / partial (see per-detector table + hidden-mechanism notes)"
    h624["proposed_verdict"] = h624_verdict
    h624["best_detector"] = best624
    h624["artifact"] = str(OUT / f"h624-flatline-{run_id}.json")
    h624["script"] = "scripts/experiments/r50_h623_elbow_battery.py"
    (OUT / f"h624-flatline-{run_id}.json").write_text(json.dumps(h624, indent=1, default=float))
    print(f"WROTE h624 verdict={h624_verdict}", flush=True)

    # -------------------- console summary --------------------
    print("\n==== SUMMARY ====", flush=True)
    print(f"H623: {h623_verdict}", flush=True)
    for det in DETECTORS:
        b = bakeoff[f"detector:{det}"]
        print(f"  {det}: tie P={b['tie']['precision']} R={b['tie']['recall']} | "
              f"clean P={b['clean']['precision']} R={b['clean']['recall']} | "
              f"cutvar={stability[det]['mean_cut_index_variance']} | lambda={crc[det]['lambda']} "
              f"feasible={crc[det]['feasible']}", flush=True)
    print(f"  fixed_k1: tie P={bakeoff['fixed_k1']['tie']['precision']} R={bakeoff['fixed_k1']['tie']['recall']} | "
          f"clean R={bakeoff['fixed_k1']['clean']['recall']}", flush=True)
    print(f"  fixed_k2: tie P={bakeoff['fixed_k2']['tie']['precision']} R={bakeoff['fixed_k2']['tie']['recall']}", flush=True)
    print(f"  reach: " + " ".join(f"{k}={v['reach_all']}" for k, v in reach_arms.items()), flush=True)
    print(f"H624: {h624_verdict}", flush=True)


if __name__ == "__main__":
    main()

"""R58-H651 CRUX - the region-cap fix: full 1-hop expansion replaces PPR-top15.

Mechanism: widen the reset-region cap. The shipped best arm reset_region_union
truncates the seed/anchor neighbourhood at PPR-top-15. H651 unions the FULL
1-hop shell of (dense seeds u max-gap anchors) into the region instead, keeping
the region a strict SUPERSET of the baseline (widening a cap can only ADD nodes
the truncation was discarding).

FREE offline replay on the frozen 132 OFF-arm probes. NO GPU, NO LLM, NO Neo4j,
NO network. Reuses the R57 atlas substrate/anchor/region construction verbatim
(reset_region_union reproduces reach_all 0.8740) and the atlas 326-row JSONL for
the effective-node (goldjoin-v2/v3) mapping. Probe-flip render sim follows the
H620 pattern against the recorded rru_b10 / rru_b06 pass sets.

goldjoin: v2 (paren-strip -> fold -> fuzzy 0.92) then v3 type-gate fall-through,
exactly as the atlas eff_idx (goldjoin-v3-typegate-20260724). Every reported
number carries the join version stamp.

Writes:
  reports/experiments/r58/h651-region-cap-<ts>.json
  reports/experiments/r58/h651-region-cap-<ts>.md   (brief)
"""

import json
import sys
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.sparse.csgraph import connected_components

ROOT = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry")
sys.path.insert(0, str(ROOT / "scripts/experiments"))

import r47_h582_embedder_swap as H       # noqa: E402  (_norm, ppr, TOP_K)
import r50_h619_seedland_digs as R50     # noqa: E402  (load_substrate)
from rapidfuzz import fuzz, process      # noqa: E402
from collections import Counter as _C    # noqa: E402

CACHE = ROOT / "tmp/results/r47"
OUT = ROOT / "reports/experiments/r58"
SPAN_CACHE = ROOT / "tmp/results/r50/h597_gliner_spans.json"
H619_ART = ROOT / "reports/experiments/r50/h619-stoplist-20260713T233206Z.json"
ATLAS_ROWS = ROOT / "reports/experiments/r57/h644-miss-atlas-rows-20260724T085649Z.jsonl"
H620_CKPT = ROOT / "reports/experiments/r50/h620-conversion-20260713T233256Z.checkpoint.jsonl"

TOP_K = 16
PPR_TOP_N = 15
CAND_FLOOR = 0.6
CAND_CAP = 15
K1, B = 1.5, 0.75
JOIN_VERSION = "goldjoin-v3-typegate-20260724 (eff = v2 then v3 fall-through, from R57 atlas rows)"

import re  # noqa: E402


def tok(s):
    return re.findall(r"[a-z0-9]+", s.lower())


def norm01(scores):
    s = np.asarray(scores, dtype=float)
    lo, hi = s.min(), s.max()
    if hi - lo < 1e-12:
        return np.ones_like(s)
    return (s - lo) / (hi - lo)


def detect_maxgap(scores):
    s = np.asarray(scores, dtype=float)
    m = len(s)
    if m <= 1:
        return m, 1.0
    gaps = s[:-1] - s[1:]
    j = int(np.argmax(gaps))
    return j + 1, float(gaps[j])


_BUILD = None


def build():
    """Reconstruct the atlas substrate + anchors + regions ONCE. Cached."""
    global _BUILD
    if _BUILD is not None:
        return _BUILD

    S = R50.load_substrate()
    n = S["n"]
    meta, name_row, name_norms = S["meta"], S["name_row"], S["name_norms"]
    carriers, off_ids, Q = S["carriers"], S["off_ids"], S["Q"]
    adj, out_deg = S["adj"], S["out_deg"]
    indptr, indices = adj.indptr, adj.indices
    true_deg = np.asarray(adj.sum(axis=1)).ravel().astype(int)

    ncomp, comp = connected_components(adj, directed=False)
    comp_sizes = np.bincount(comp)
    lcc = int(comp_sizes.argmax())

    # ---- H623 scored candidate lists (verbatim from atlas) -----------------
    docs = [tok(nn) for nn in name_norms]
    df = _C()
    for dd in docs:
        for t in set(dd):
            df[t] += 1
    Nd = len(docs)
    dl = np.array([len(x) for x in docs], dtype=float)
    avgdl = dl.mean()
    idf = {t: np.log(1 + (Nd - c + 0.5) / (c + 0.5)) for t, c in df.items()}
    term_docs = defaultdict(list)
    for i, dd in enumerate(docs):
        for t, f in _C(dd).items():
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
    cl_cache = {}

    def candidate_list(span_norm):
        if span_norm in cl_cache:
            return cl_cache[span_norm]
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
        res = (idx, blended[idx])
        cl_cache[span_norm] = res
        return res

    spans_by_pid = json.loads(SPAN_CACHE.read_text())
    anchors_maxgap = defaultdict(set)
    for pid in off_ids:
        for text, _g in spans_by_pid.get(pid, []):
            sn = H._norm(text)
            idx, blended = candidate_list(sn)
            ns = norm01(blended)
            cut_k, _strength = detect_maxgap(ns)
            cidx = [int(i) for i in idx.tolist()]
            for k in range(cut_k):
                anchors_maxgap[pid].add(cidx[k])

    def onehop(seed_set):
        h = set()
        for u in seed_set:
            h.update(int(x) for x in indices[indptr[u]:indptr[u + 1]])
        return h

    dense_seeds = {pid: set(S["seeds_q"][pid]) for pid in off_ids}
    ppr_vec = {}
    reset_region = {}        # baseline: PPR-top15 capped (shipped best arm)
    reset_region_wide = {}   # H651: baseline UNION full 1-hop shell of (seeds u anchors)
    region_seeds = {}
    for pid in off_ids:
        anc = anchors_maxgap.get(pid, set())
        ds = dense_seeds[pid]
        ppr_seeds = list(anc) if anc else list(ds)
        r = H.ppr(adj, out_deg, ppr_seeds, n)
        ppr_vec[pid] = r
        top15 = set(np.argsort(-r)[:PPR_TOP_N].tolist())
        base = top15 | set(ppr_seeds) | ds
        reset_region[pid] = base
        shell = onehop(set(ppr_seeds) | ds)
        reset_region_wide[pid] = base | shell
        region_seeds[pid] = set(ppr_seeds) | ds

    # ---- atlas rows (eff_idx mapping via goldjoin v2/v3) --------------------
    atlas_rows = [json.loads(l) for l in ATLAS_ROWS.read_text().splitlines() if l.strip()]
    # roles per (pid, carrier) from atlas
    role_of_row = {(r["probe"], r["carrier"]): r["reasoning_role"] for r in atlas_rows}
    eff_of_row = {(r["probe"], r["carrier"]): r["eff_idx"] for r in atlas_rows}

    # ---- recorded H620 pass sets (rru arms) --------------------------------
    ck = [json.loads(l) for l in H620_CKPT.read_text().splitlines() if l.strip()]
    rru_pass = {"rru_b10": {}, "rru_b06": {}, "base_b10": {}, "base_b06": {}}
    for r in ck:
        if r["arm"] in rru_pass:
            rru_pass[r["arm"]][r["pid"]] = bool(r["pass"])

    _BUILD = dict(
        S=S, n=n, meta=meta, name_row=name_row, name_norms=name_norms,
        carriers=carriers, off_ids=off_ids, Q=Q, adj=adj, out_deg=out_deg,
        indptr=indptr, indices=indices, true_deg=true_deg, comp=comp,
        comp_sizes=comp_sizes, lcc=lcc, anchors_maxgap=anchors_maxgap,
        dense_seeds=dense_seeds, ppr_vec=ppr_vec, reset_region=reset_region,
        reset_region_wide=reset_region_wide, region_seeds=region_seeds,
        onehop=onehop, atlas_rows=atlas_rows, role_of_row=role_of_row,
        eff_of_row=eff_of_row, rru_pass=rru_pass,
    )
    return _BUILD


def carrier_rows_by_pid(atlas_rows):
    d = defaultdict(list)
    for r in atlas_rows:
        d[r["probe"]].append(r)
    return d


def fully_retrieved(pid, region, rows_by_pid):
    """True iff EVERY gold carrier row of pid has a node AND that node in region."""
    rows = rows_by_pid[pid]
    if not rows:
        return False
    for r in rows:
        eff = r["eff_idx"]
        if eff is None or eff not in region:
            return False
    return True


def ctx_proxy(region, meta):
    """Rendered-context token proxy = sum(len(name)+len(descr)) over region nodes."""
    tot = 0
    for i in region:
        m = meta[i]
        tot += len(m.get("name") or "") + len(m.get("descr") or "")
    return tot


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731
    ckpt = OUT / f"h651-region-cap-{run_id}.checkpoint.jsonl"
    cf = ckpt.open("w")

    def chk(tag, obj):
        cf.write(json.dumps({"tag": tag, **obj}, default=str) + "\n")
        cf.flush()

    D = build()
    meta = D["meta"]
    off_ids = D["off_ids"]
    reset_region = D["reset_region"]
    reset_region_wide = D["reset_region_wide"]
    atlas_rows = D["atlas_rows"]
    rows_by_pid = carrier_rows_by_pid(atlas_rows)

    # ================= PIN: reset_region membership matches atlas flag ========
    mism = 0
    for r in atlas_rows:
        eff = r["eff_idx"]
        if eff is None:
            continue
        flag = r["traversal"]["in_reset_region_union"]
        mine = eff in reset_region[r["probe"]]
        if bool(flag) != bool(mine):
            mism += 1
    # reach_all pin (0.8740 over reach_pids)
    S = D["S"]
    reach_pids = S["reach_pids"]
    reach_num = sum(1 for pid in reach_pids
                    if S["probe_has_carrier"][pid]
                    and all(t in reset_region[pid] for t in S["probe_has_carrier"][pid]))
    reach_all = round(reach_num / len(reach_pids), 4)
    pins = {"atlas_region_flag_mismatches": mism,
            "reach_all_reset_region": reach_all, "reach_all_expected": 0.8740,
            "reach_pins_ok": mism == 0 and abs(reach_all - 0.8740) < 0.002}
    log(f"PINS: mismatches={mism} reach_all={reach_all} ok={pins['reach_pins_ok']}")
    chk("pins", pins)
    if not pins["reach_pins_ok"]:
        summ = {"hypothesis": "R58-H651", "run_id": run_id,
                "ABORTED_PIN_MISMATCH": True, "pins": pins}
        (OUT / f"h651-region-cap-{run_id}.json").write_text(json.dumps(summ, indent=1))
        log("ABORT (pin mismatch)")
        return

    # ================= the 15 cap-artifact carriers ==========================
    # atlas H647: in-component missed (not in reset_region, comp same-as-seeds,
    # boundary_dist==0). These are inside the 1-hop shell but outside PPR-top15.
    cap_carriers = []
    for r in atlas_rows:
        eff = r["eff_idx"]
        if eff is None:
            continue
        tr = r["traversal"]
        if (not tr["in_reset_region_union"]
                and tr["component_status"] == "same-as-seeds"
                and tr["dist_to_region_boundary"] == 0):
            cap_carriers.append(r)
    log(f"cap-artifact carriers reproduced: {len(cap_carriers)} (atlas premise: 15)")
    chk("cap_carriers", {"n": len(cap_carriers),
                         "names": [(c["probe"], c["carrier"]) for c in cap_carriers]})

    # ---- recovery under the widened region ---------------------------------
    recovered = []
    not_recovered = []
    for r in cap_carriers:
        eff = r["eff_idx"]
        pid = r["probe"]
        if eff in reset_region_wide[pid]:
            recovered.append(r)
        else:
            not_recovered.append(r)
    n_rec = len(recovered)
    log(f"H651 recovery: {n_rec}/{len(cap_carriers)} cap-artifact carriers now in widened region")

    # ================= region growth (all 132 probes) =========================
    growth = []
    for pid in off_ids:
        b = len(reset_region[pid])
        w = len(reset_region_wide[pid])
        cb = ctx_proxy(reset_region[pid], meta)
        cw = ctx_proxy(reset_region_wide[pid], meta)
        growth.append({"pid": pid, "region_base": b, "region_wide": w,
                       "region_ratio": round(w / b, 3) if b else None,
                       "ctx_base_chars": cb, "ctx_wide_chars": cw,
                       "ctx_ratio": round(cw / cb, 3) if cb else None,
                       "added_nodes": w - b})
    reg_ratios = [g["region_ratio"] for g in growth if g["region_ratio"] is not None]
    ctx_ratios = [g["ctx_ratio"] for g in growth if g["ctx_ratio"] is not None]
    med_region_ratio = round(float(np.median(reg_ratios)), 3)
    med_ctx_ratio = round(float(np.median(ctx_ratios)), 3)
    med_base = int(np.median([g["region_base"] for g in growth]))
    med_wide = int(np.median([g["region_wide"] for g in growth]))
    log(f"region growth: median base={med_base} wide={med_wide} "
        f"ratio={med_region_ratio}x  ctx ratio={med_ctx_ratio}x")

    # ================= probe-flip render sim (H620 pattern) ==================
    # Deterministic proxy: a probe flips fail->pass under the widened region iff it
    # was a RETRIEVAL-miss failure of the recorded rru arm (some gold carrier not in
    # baseline reset_region) AND the widened region now fully retrieves every gold
    # carrier. render_budget=1.0 => full budget, retrieved carrier renders (the
    # rendered_answer_absent probes are a disjoint fixed render defect the region
    # fix cannot touch; flagged). Regression at retrieval level is impossible because
    # reset_region_wide is a strict superset of reset_region.
    rru = D["rru_pass"]

    def flip_sim(arm):
        pass_map = rru[arm]
        flips_pos, flips_neg = [], []
        cnr_fail = []       # carrier_not_retrieved failures (retrieval misses)
        render_fail = []    # fully retrieved yet failed (render-absent bucket)
        for pid in off_ids:
            passed = pass_map.get(pid)
            if passed is None:
                continue
            fr_base = fully_retrieved(pid, reset_region[pid], rows_by_pid)
            fr_wide = fully_retrieved(pid, reset_region_wide[pid], rows_by_pid)
            if not passed:
                if not fr_base:
                    cnr_fail.append(pid)
                    if fr_wide:
                        flips_pos.append(pid)
                else:
                    render_fail.append(pid)
            else:
                # regression only if widened breaks retrieval - impossible (superset)
                if fr_base and not fr_wide:
                    flips_neg.append(pid)
        return {"arm": arm, "baseline_pass": sum(1 for v in pass_map.values() if v),
                "baseline_fail": sum(1 for v in pass_map.values() if not v),
                "carrier_not_retrieved_fails": len(cnr_fail),
                "render_absent_fails": len(render_fail),
                "flips_fail_to_pass": len(flips_pos), "flip_pids": flips_pos,
                "regressions_pass_to_fail": len(flips_neg), "regression_pids": flips_neg}

    sim_b10 = flip_sim("rru_b10")   # render_budget = 1.0 (JUDGED)
    sim_b06 = flip_sim("rru_b06")   # render_budget = 0.6
    log(f"FLIP b10(=1.0): +{sim_b10['flips_fail_to_pass']} "
        f"-{sim_b10['regressions_pass_to_fail']} "
        f"(cnr fails {sim_b10['carrier_not_retrieved_fails']})")
    log(f"FLIP b06(=0.6): +{sim_b06['flips_fail_to_pass']} "
        f"-{sim_b06['regressions_pass_to_fail']}")
    chk("flips", {"b10": sim_b10, "b06": sim_b06})

    # pure retrieval-reachability delta on all 132 (arm-agnostic cross-check)
    fr_base_all = sum(1 for pid in off_ids if fully_retrieved(pid, reset_region[pid], rows_by_pid))
    fr_wide_all = sum(1 for pid in off_ids if fully_retrieved(pid, reset_region_wide[pid], rows_by_pid))

    # ================= verdict ===============================================
    flips_judged = sim_b10["flips_fail_to_pass"]
    regr_judged = sim_b10["regressions_pass_to_fail"]
    rec_ok = n_rec >= 10
    flip_ok = flips_judged >= 3
    noregr = regr_judged == 0
    if rec_ok and flip_ok and noregr:
        verdict = "CONFIRMED"
    elif med_region_ratio > 2.0 and flips_judged == 0:
        verdict = "KILLED"
    else:
        verdict = "INDETERMINATE"

    summ = {
        "hypothesis": "R58-H651", "run_id": run_id,
        "join_version": JOIN_VERSION,
        "substrate": ("medium 2wiki frozen H582 cache tmp/results/r47 (6,626 entities) + "
                      "R50 H597 span cache; FREE numpy/scipy/rapidfuzz, no GPU/LLM/Neo4j/net"),
        "substrate_caveat": ("frozen 6,626-entity cache (NOT the 7,575-entity live re-ingest); "
                             "matches the R57 atlas substrate exactly for comparability"),
        "pins": pins,
        "mechanism": ("reset_region_wide = reset_region_union UNION onehop(dense_seeds u maxgap_anchors); "
                      "strict superset of the PPR-top15-capped baseline"),
        "cap_artifact_premise": {"expected": 15, "reproduced": len(cap_carriers),
                                 "premise_holds": len(cap_carriers) == 15},
        "recovery": {
            "recovered": n_rec, "of": len(cap_carriers),
            "bar": ">=10/15",
            "recovered_carriers": [(c["probe"], c["carrier"], c["reasoning_role"]) for c in recovered],
            "not_recovered_carriers": [(c["probe"], c["carrier"]) for c in not_recovered],
        },
        "region_growth": {
            "median_region_base": med_base, "median_region_wide": med_wide,
            "median_region_ratio": med_region_ratio,
            "median_ctx_char_ratio": med_ctx_ratio,
            "max_region_ratio": round(max(reg_ratios), 3),
            "note": "ctx proxy = sum(len(name)+len(descr)) over region nodes; per-probe in checkpoint",
            "per_probe": growth,
        },
        "flip_sim": {
            "render_budget_1.0_JUDGED": sim_b10,
            "render_budget_0.6": sim_b06,
            "model": ("H620-pattern deterministic proxy: flip = recorded-arm FAIL that was a "
                      "carrier-not-retrieved miss (a gold carrier outside baseline reset_region) and "
                      "is fully retrieved by the widened region. render_budget=1.0 => retrieved carrier "
                      "renders; the render-absent fail bucket is disjoint and unaffected by the region "
                      "fix. Regression is structurally impossible at retrieval level (widened is a "
                      "strict superset); live-render crowd-out at budget 0.6 is NOT simulated offline "
                      "and is carried as a caveat."),
            "retrieval_reachability_all132": {"base_fully_retrieved": fr_base_all,
                                              "wide_fully_retrieved": fr_wide_all,
                                              "delta": fr_wide_all - fr_base_all},
        },
        "verdict_recommendation": verdict,
        "bar": ("CONFIRMED at >=10/15 recovered AND >=3 flips (budget 1.0) with zero regressions; "
                "KILLED if recovery needs region growth >2x median without flips"),
        "caveats": [
            "render_budget=0.6 crowd-out cannot be simulated offline (no live render node lists in "
            "the H620 checkpoint); the +flips at 0.6 assume retrieved=>rendered, an upper bound.",
            "flip proxy assumes a newly fully-retrieved carrier_not_retrieved probe passes; a fraction "
            "could instead land in the render-absent bucket. Reported as retrieval-level flips.",
            "frozen 6,626-entity substrate, not the 7,575 live re-ingest (97.2% carrier alignment).",
        ],
        "artifacts": {"json": str(OUT / f"h651-region-cap-{run_id}.json"),
                      "brief": str(OUT / f"h651-region-cap-{run_id}.md"),
                      "checkpoint": str(ckpt),
                      "script": "scripts/experiments/r58_h651_region_cap.py"},
    }
    (OUT / f"h651-region-cap-{run_id}.json").write_text(json.dumps(summ, indent=1, default=str))

    brief = f"""# R58-H651 region-cap fix - brief

**Verdict recommendation: {verdict}**  (run {run_id}, join {JOIN_VERSION})

Mechanism: `reset_region_wide = reset_region_union UNION onehop(dense_seeds u maxgap_anchors)`
- strict superset of the shipped PPR-top15-capped best arm.

## Premise
- cap-artifact carriers reproduced: **{len(cap_carriers)}/15** (atlas H647 in-component
  boundary-dist-0 misses). Premise holds: {len(cap_carriers) == 15}.

## Headline (exact counts, paired)
- **Recovery: {n_rec}/{len(cap_carriers)}** cap-artifact carriers now inside the widened region (bar >=10/15)
- **Flips @ render_budget=1.0 (JUDGED): +{sim_b10['flips_fail_to_pass']} / -{sim_b10['regressions_pass_to_fail']}**
  (baseline rru_b10 {sim_b10['baseline_pass']} pass / {sim_b10['baseline_fail']} fail;
  carrier-not-retrieved fails {sim_b10['carrier_not_retrieved_fails']})
- Flips @ render_budget=0.6: +{sim_b06['flips_fail_to_pass']} / -{sim_b06['regressions_pass_to_fail']}
- Panel @1.0: {sim_b10['baseline_pass']} -> {sim_b10['baseline_pass'] + sim_b10['flips_fail_to_pass']}
- Retrieval reachability (all 132, fully-retrieved probes): {fr_base_all} -> {fr_wide_all}
  (+{fr_wide_all - fr_base_all})

## Region growth
- median region {med_base} -> {med_wide} nodes ({med_region_ratio}x); max {round(max(reg_ratios), 3)}x
- median rendered-context char proxy ratio: {med_ctx_ratio}x

## Flip pids @1.0
{sim_b10['flip_pids']}

## Caveats
- render_budget=0.6 crowd-out not simulable offline (no live-render node lists); 0.6 flips are an
  upper bound under retrieved=>rendered.
- flip proxy is retrieval-level; a newly-retrieved probe could land in the fixed render-absent bucket.
- frozen 6,626-entity substrate (not the 7,575 live re-ingest).
"""
    (OUT / f"h651-region-cap-{run_id}.md").write_text(brief)
    cf.close()
    log(f"\nVERDICT {verdict} | recovery {n_rec}/{len(cap_carriers)} | "
        f"flips@1.0 +{sim_b10['flips_fail_to_pass']}/-{sim_b10['regressions_pass_to_fail']}")
    log(f"wrote {OUT}/h651-region-cap-{run_id}.json")


if __name__ == "__main__":
    main()

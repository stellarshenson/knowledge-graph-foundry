"""R54-H628 - does H627 pooled-index seed landing CONVERT to reachability + flips?

The money question separated from H627: H627 showed pooled top-16 lifts carrier
recall@16 0.6012 -> 0.7147 (alpha 0.6, meanpool r1). Is that a REACH gain (new
carriers become region-reachable, probes flip) or a RANKING gain inside the
already-reachable region (a dashboard number)? H627's own mechanism note says the
latter (recovered_beyond_base_region = 0 on every arm), so the NULL is the live
alternative and this gate measures it.

FREE offline replay. NO GPU/LLM/Neo4j/net. Reuses the r58_h651 build() substrate
(anchors, dense seeds, atlas eff_idx gold join, recorded H620 rru pass maps,
onehop). Adds pooled seeds = top-16 of the alpha-0.6 meanpool-r1 smoothed score
(the shipped H627 operating point) and rebuilds the reset region from them.

MANDATORY SUBSTRATE RULE (R58-H651, 2026-07-24): the shipped region is now the
WIDENED region = seeds u anchors u FULL 1-hop shell u PPR-top15. Every arm runs on
BOTH the narrow (PPR-top15-capped) region and the widened region; the widened
region is the primary arm.

anchor-reset is the incumbent seeding mechanism. Each seed source {dense, pooled}
runs standalone (anchors OFF) and composed with anchor-reset (anchors ON) x
{narrow, wide}. The flip sim reference is the recorded rru_b10 arm (dense + anchor
+ narrow, budget 1.0) exactly as H651; net flips of a pooled arm are measured
against that fixed recorded panel with regressions counted (pooled changes seeds,
so a dropped carrier is a real pass->fail).

Writes:
  reports/experiments/r54/h628-pooled-conversion-<ts>.json + .md brief
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix

ROOT = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry")
sys.path.insert(0, str(ROOT / "scripts/experiments"))

import r47_h582_embedder_swap as H       # noqa: E402  (_norm, ppr, TOP_K)
import r50_h619_seedland_digs as R50     # noqa: E402  (load_substrate)
import r58_h651_region_cap as H651       # noqa: E402  (build: anchors/atlas/rru_pass)

OUT = ROOT / "reports/experiments/r54"
TOP_K = 16
PPR_TOP_N = 15
ALPHA = 0.6                              # H627 shipped operating point (meanpool r1)
JOIN_VERSION = "goldjoin-v3-typegate-20260724 (eff = v2 then v3 fall-through, R57 atlas rows)"
BASE_RECALL_PIN = 0.6012                 # H582/H627 dense@16 r0 carrier recall
POOL_RECALL_PIN = 0.7147                 # H627 meanpool alpha 0.6 r0 carrier recall
RESET_REACH_PIN = 0.8740                 # H651 reset_region reach_all


def pooled_scores(S, alpha):
    """meanpool-r1 smoothed node index (H627), returns Z (unit rows) and Ahat build."""
    adj, out_deg, n = S["adj"], S["out_deg"], S["n"]
    titan_n = S["titan_n"]
    Ahat = csr_matrix((1.0 / out_deg, (np.arange(n), np.arange(n))), shape=(n, n)) @ adj
    A1 = Ahat @ titan_n
    z = (1 - alpha) * titan_n + alpha * A1
    nz = np.linalg.norm(z, axis=1, keepdims=True)
    nz[nz == 0] = 1.0
    return z / nz


def topk(scores, k):
    sd = np.argpartition(-scores, k)[:k]
    return set(int(x) for x in sd[np.argsort(-scores[sd])])


def carrier_recall(S, seeds_by_pid):
    """r0 join carrier recall@16 over ALL carriers (H627 convention)."""
    name_norms = S["name_norms"]
    hits = []
    for c in S["carriers"]:
        seed_norms = {name_norms[i] for i in seeds_by_pid[c["probe"]]}
        hits.append(1 if c["tnorm"] in seed_norms else 0)
    return round(float(np.mean(hits)), 4), hits


def build_region(pid, seed_set, use_anchors, widen, D):
    anc = D["anchors_maxgap"].get(pid, set())
    ppr_seeds = list(anc) if (use_anchors and anc) else list(seed_set)
    r = H.ppr(D["adj"], D["out_deg"], ppr_seeds, D["n"])
    top15 = set(int(x) for x in np.argsort(-r)[:PPR_TOP_N])
    base = top15 | set(int(x) for x in ppr_seeds) | set(int(x) for x in seed_set)
    if widen:
        base |= D["onehop"](set(int(x) for x in ppr_seeds) | set(int(x) for x in seed_set))
    return base


def reach_all(S, region_by_pid):
    """name_row / probe_has_carrier reach_all over reach_pids (the 0.8740 metric)."""
    rp = S["reach_pids"]
    num = sum(1 for pid in rp
              if S["probe_has_carrier"][pid]
              and all(t in region_by_pid[pid] for t in S["probe_has_carrier"][pid]))
    return round(num / len(rp), 4), num, len(rp)


def fully_retrieved(pid, region, rows_by_pid):
    rows = rows_by_pid[pid]
    if not rows:
        return False
    for r in rows:
        eff = r["eff_idx"]
        if eff is None or eff not in region:
            return False
    return True


def fr_count(off_ids, region_by_pid, rows_by_pid):
    return sum(1 for pid in off_ids if fully_retrieved(pid, region_by_pid[pid], rows_by_pid))


def flip_sim(off_ids, region_by_pid, ref_region_by_pid, ref_pass, rows_by_pid):
    """Recorded-arm flip proxy (H651 pattern), generalised to allow regressions.

    ref_pass  = recorded rru_b10 pass map (dense+anchor+narrow, budget 1.0).
    ref_region= narrow reset_region (dense+anchor) that PRODUCED the recorded arm.
    region    = the candidate arm's region.
    flip+  : recorded FAIL, carrier-not-retrieved under ref (not fr_ref), fr_arm True.
    flip-  : recorded PASS, fr_ref True, fr_arm False (arm dropped a gold carrier).
    """
    flips_pos, flips_neg, cnr = [], [], []
    for pid in off_ids:
        passed = ref_pass.get(pid)
        if passed is None:
            continue
        fr_ref = fully_retrieved(pid, ref_region_by_pid[pid], rows_by_pid)
        fr_arm = fully_retrieved(pid, region_by_pid[pid], rows_by_pid)
        if not passed:
            if not fr_ref:
                cnr.append(pid)
                if fr_arm:
                    flips_pos.append(pid)
        else:
            if fr_ref and not fr_arm:
                flips_neg.append(pid)
    return {"flips_fail_to_pass": len(flips_pos), "flip_pids": flips_pos,
            "regressions_pass_to_fail": len(flips_neg), "regression_pids": flips_neg,
            "net": len(flips_pos) - len(flips_neg),
            "carrier_not_retrieved_ref": len(cnr)}


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731
    ckpt = OUT / f"h628-pooled-conversion-{run_id}.checkpoint.jsonl"
    cf = ckpt.open("w")
    chk = lambda tag, obj: (cf.write(json.dumps({"tag": tag, **obj}, default=str) + "\n"), cf.flush())

    D = H651.build()
    S = D["S"]
    off_ids = S["off_ids"]
    rows_by_pid = H651.carrier_rows_by_pid(D["atlas_rows"])
    ref_pass = D["rru_pass"]["rru_b10"]

    # ---- pooled seeds (H627 meanpool alpha 0.6) ----------------------------
    Z = pooled_scores(S, ALPHA)
    dense_seeds = {pid: set(S["seeds_q"][pid]) for pid in off_ids}
    pooled_seeds = {pid: topk(Z @ S["titan_probe_n"][pid], TOP_K) for pid in off_ids}

    # ---- PIN: carrier recall@16 base + pooled --------------------------------
    base_recall, _ = carrier_recall(S, {pid: dense_seeds[pid] for pid in off_ids})
    pool_recall, _ = carrier_recall(S, pooled_seeds)
    reset_reach, _, _ = reach_all(S, D["reset_region"])
    pins = {"base_recall@16": base_recall, "base_pin": BASE_RECALL_PIN,
            "pooled_recall@16": pool_recall, "pooled_pin": POOL_RECALL_PIN,
            "reset_region_reach_all": reset_reach, "reset_pin": RESET_REACH_PIN,
            "ok": (abs(base_recall - BASE_RECALL_PIN) < 0.01
                   and abs(pool_recall - POOL_RECALL_PIN) < 0.01
                   and abs(reset_reach - RESET_REACH_PIN) < 0.002)}
    log(f"PINS base={base_recall} pooled={pool_recall} reset_reach={reset_reach} ok={pins['ok']}")
    chk("pins", pins)
    if not pins["ok"]:
        (OUT / f"h628-pooled-conversion-{run_id}.json").write_text(
            json.dumps({"hypothesis": "R54-H628", "run_id": run_id,
                        "ABORTED_PIN_MISMATCH": True, "pins": pins}, indent=1))
        log("ABORT (pin mismatch)")
        return

    # ---- build every region arm --------------------------------------------
    seed_srcs = {"dense": dense_seeds, "pooled": pooled_seeds}
    regions = {}   # (src, anchors, widen) -> {pid: set}
    for src, seeds in seed_srcs.items():
        for use_anc in (False, True):
            for widen in (False, True):
                key = (src, use_anc, widen)
                regions[key] = {pid: build_region(pid, seeds[pid], use_anc, widen, D)
                                for pid in off_ids}

    # incumbent narrow reset_region == build_region(dense, anchors, narrow); verify
    inc_narrow = regions[("dense", True, False)]
    reset_match = all(inc_narrow[pid] == D["reset_region"][pid] for pid in off_ids)
    wide_match = all(regions[("dense", True, True)][pid] == D["reset_region_wide"][pid]
                     for pid in off_ids)
    chk("region_reconstruction", {"narrow_matches_reset_region": reset_match,
                                  "wide_matches_reset_region_wide": wide_match})
    log(f"region reconstruction: narrow={reset_match} wide={wide_match}")

    # reference region for the flip sim = narrow dense+anchor reset_region
    ref_region = D["reset_region"]

    # ---- metrics per arm ----------------------------------------------------
    arms = {}
    for key, reg in regions.items():
        src, use_anc, widen = key
        ra, ra_num, ra_den = reach_all(S, reg)
        frc = fr_count(off_ids, reg, rows_by_pid)
        seeds = seed_srcs[src]
        rec16, _ = carrier_recall(S, seeds)
        flips = flip_sim(off_ids, reg, ref_region, ref_pass, rows_by_pid)
        name = f"{src}|anchors={'on' if use_anc else 'off'}|{'wide' if widen else 'narrow'}"
        arms[name] = {"seed_source": src, "anchors": use_anc, "widen": widen,
                      "carrier_recall@16": rec16,
                      "reach_all": ra, "reach_all_num": ra_num, "reach_all_den": ra_den,
                      "fully_retrieved_132": frc,
                      "flip_vs_recorded_rru_b10": flips,
                      "panel_pass_est": 112 + flips["net"]}
        chk("arm", {"name": name, **{k: v for k, v in arms[name].items()
                                     if k != "flip_vs_recorded_rru_b10"},
                    "flips": flips})
        log(f"  {name:38s} rec16={rec16:.4f} reach_all={ra:.4f} fr132={frc:3d} "
            f"flips +{flips['flips_fail_to_pass']}/-{flips['regressions_pass_to_fail']} "
            f"net={flips['net']:+d}")

    # ---- overlap: pooled recoveries already inside the widened region? -------
    # carriers landed by pooled top16 not by dense top16, and whether each is
    # already reachable under dense+anchor+wide (the incumbent shipped region).
    name_norms = S["name_norms"]
    dense_inc_wide = regions[("dense", True, True)]
    pooled_landed_new = []
    pooled_new_already_reachable = 0
    for c in S["carriers"]:
        pid = c["probe"]
        ci = c.get("carrier_idx")
        in_p = c["tnorm"] in {name_norms[i] for i in pooled_seeds[pid]}
        in_d = c["tnorm"] in {name_norms[i] for i in dense_seeds[pid]}
        if in_p and not in_d and ci is not None:
            pooled_landed_new.append((pid, c["tnorm"]))
            if ci in dense_inc_wide[pid]:
                pooled_new_already_reachable += 1
    overlap = {"pooled_top16_new_carriers": len(pooled_landed_new),
               "already_reachable_in_dense_anchor_wide": pooled_new_already_reachable,
               "pct_already_reachable": round(
                   100 * pooled_new_already_reachable / max(len(pooled_landed_new), 1), 1)}
    chk("overlap", overlap)
    log(f"pooled-new carriers {overlap['pooled_top16_new_carriers']}, "
        f"already reachable in incumbent-wide {overlap['already_reachable_in_dense_anchor_wide']} "
        f"({overlap['pct_already_reachable']}%)")

    # ---- verdict: primary = pooled vs dense, both anchor+wide ---------------
    def A(src, anc, widen):
        return arms[f"{src}|anchors={'on' if anc else 'off'}|{'wide' if widen else 'narrow'}"]

    def compare(pooled_arm, dense_arm, label):
        d_reach = round(100 * (pooled_arm["reach_all"] - dense_arm["reach_all"]), 2)
        d_fr = pooled_arm["fully_retrieved_132"] - dense_arm["fully_retrieved_132"]
        net_over = pooled_arm["flip_vs_recorded_rru_b10"]["net"] - \
            dense_arm["flip_vs_recorded_rru_b10"]["net"]
        return {"label": label, "reach_all_delta_pp": d_reach,
                "fully_retrieved_delta": d_fr,
                "net_flips_pooled_over_dense": net_over,
                "pooled_reach": pooled_arm["reach_all"], "dense_reach": dense_arm["reach_all"],
                "pooled_net_flips": pooled_arm["flip_vs_recorded_rru_b10"]["net"],
                "dense_net_flips": dense_arm["flip_vs_recorded_rru_b10"]["net"]}

    cmp_wide_anchor = compare(A("pooled", True, True), A("dense", True, True),
                              "pooled vs dense, anchors ON, WIDE (primary, shipped region)")
    cmp_narrow_anchor = compare(A("pooled", True, False), A("dense", True, False),
                                "pooled vs dense, anchors ON, narrow")
    cmp_wide_standalone = compare(A("pooled", False, True), A("dense", False, True),
                                  "pooled vs dense, anchors OFF, WIDE (standalone)")
    cmp_narrow_standalone = compare(A("pooled", False, False), A("dense", False, False),
                                    "pooled vs dense, anchors OFF, narrow (standalone)")

    # registered bar on the primary (anchors ON, wide): reach delta >= +3pts AND net flips > 0
    prim = cmp_wide_anchor
    reach_ok = prim["reach_all_delta_pp"] >= 3.0
    flips_ok = prim["net_flips_pooled_over_dense"] > 0
    if reach_ok and flips_ok:
        verdict = "CONFIRMED"
    elif prim["net_flips_pooled_over_dense"] == 0 and abs(prim["reach_all_delta_pp"]) < 1.0:
        verdict = "KILLED"
    else:
        verdict = "INDETERMINATE"

    summ = {
        "hypothesis": "R54-H628", "run_id": run_id, "join_version": JOIN_VERSION,
        "alpha_meanpool_r1": ALPHA,
        "substrate": ("medium 2wiki frozen H582 cache tmp/results/r47 (6,626 entities) + "
                      "R50 H597 span cache; FREE numpy/scipy, no GPU/LLM/Neo4j/net"),
        "substrate_caveat": ("frozen 6,626-entity cache (NOT the 7,575-entity live re-ingest); "
                             "matches the R57 atlas + H651 substrate for comparability"),
        "pins": pins,
        "region_reconstruction": {"narrow_matches_reset_region": reset_match,
                                  "wide_matches_reset_region_wide": wide_match},
        "flip_reference": ("recorded H620 rru_b10 pass map (dense+anchor+narrow region, "
                           "render_budget=1.0); ref region = narrow reset_region"),
        "arms": arms,
        "overlap_pooled_new_vs_incumbent_wide": overlap,
        "comparisons": {
            "primary_anchors_on_wide": cmp_wide_anchor,
            "anchors_on_narrow": cmp_narrow_anchor,
            "standalone_wide": cmp_wide_standalone,
            "standalone_narrow": cmp_narrow_standalone,
        },
        "registered_bar": ("reachability delta >= +3pts AND non-zero net flips at render_budget=1.0; "
                           "KILLED at zero net flips AND flat reachability"),
        "verdict_recommendation": verdict,
        "caveats": [
            "flip sim is deterministic retrieval-level proxy vs the recorded rru_b10 arm (H651 pattern); "
            "a newly-retrieved probe could still land in the fixed render-absent bucket - reported as "
            "retrieval-level net flips, not a live re-render.",
            "pooled seeds change the region, so regressions ARE possible and are counted (unlike H651 "
            "where the widened region was a strict superset).",
            "render_budget 1.0 is the judged arm; crowd-out at 0.6 is not simulated offline.",
            "frozen 6,626-entity substrate, not the 7,575 live re-ingest.",
        ],
        "artifacts": {"json": str(OUT / f"h628-pooled-conversion-{run_id}.json"),
                      "brief": str(OUT / f"h628-pooled-conversion-{run_id}.md"),
                      "checkpoint": str(ckpt),
                      "script": "scripts/experiments/r54_h628_pooled_conversion.py"},
    }
    (OUT / f"h628-pooled-conversion-{run_id}.json").write_text(json.dumps(summ, indent=1, default=str))

    brief = f"""# R54-H628 pooled-index conversion - brief

**Verdict recommendation: {verdict}**  (run {run_id}, join {JOIN_VERSION})

Question: does H627's pooled seed-landing gain (carrier recall@16 {base_recall} -> {pool_recall}
at alpha {ALPHA}) CONVERT to reachability and probe flips, or is it a ranking-only dashboard number?

## Pins (reproduced)
- dense carrier recall@16 {base_recall} (pin {BASE_RECALL_PIN}); pooled {pool_recall} (pin {POOL_RECALL_PIN})
- reset_region reach_all {reset_reach} (pin {RESET_REACH_PIN})
- narrow region == reset_region: {reset_match}; wide == reset_region_wide: {wide_match}

## Primary comparison - pooled vs dense, anchors ON, WIDE region (the shipped region)
- reach_all delta **{prim['reach_all_delta_pp']:+.2f}pp** (pooled {prim['pooled_reach']} vs dense {prim['dense_reach']})
- fully-retrieved(132) delta **{cmp_wide_anchor['fully_retrieved_delta']:+d}**
- net flips pooled over dense (vs recorded rru_b10): **{prim['net_flips_pooled_over_dense']:+d}**
- registered bar: reach delta >= +3pp AND net flips > 0 -> reach_ok={reach_ok} flips_ok={flips_ok}

## All four comparisons (pooled minus dense)
| setting | reach_all delta | fully-ret delta | net flips (pooled-dense) |
|---|---|---|---|
| anchors ON, wide (primary) | {cmp_wide_anchor['reach_all_delta_pp']:+.2f}pp | {cmp_wide_anchor['fully_retrieved_delta']:+d} | {cmp_wide_anchor['net_flips_pooled_over_dense']:+d} |
| anchors ON, narrow | {cmp_narrow_anchor['reach_all_delta_pp']:+.2f}pp | {cmp_narrow_anchor['fully_retrieved_delta']:+d} | {cmp_narrow_anchor['net_flips_pooled_over_dense']:+d} |
| anchors OFF, wide | {cmp_wide_standalone['reach_all_delta_pp']:+.2f}pp | {cmp_wide_standalone['fully_retrieved_delta']:+d} | {cmp_wide_standalone['net_flips_pooled_over_dense']:+d} |
| anchors OFF, narrow | {cmp_narrow_standalone['reach_all_delta_pp']:+.2f}pp | {cmp_narrow_standalone['fully_retrieved_delta']:+d} | {cmp_narrow_standalone['net_flips_pooled_over_dense']:+d} |

## Why (the H627 scope limit, measured)
- pooled top-16 lands **{overlap['pooled_top16_new_carriers']}** carriers dense top-16 misses;
  **{overlap['already_reachable_in_dense_anchor_wide']}** ({overlap['pct_already_reachable']}%) were ALREADY
  reachable inside the incumbent dense+anchor+wide region - so the landing gain is a RANKING move
  inside the reachable region, not a reach gain.

## Per-arm table
| arm | rec@16 | reach_all | fr(132) | flips +/- | net |
|---|---|---|---|---|---|
""" + "\n".join(
        f"| {n} | {a['carrier_recall@16']:.4f} | {a['reach_all']:.4f} | {a['fully_retrieved_132']} | "
        f"+{a['flip_vs_recorded_rru_b10']['flips_fail_to_pass']}/"
        f"-{a['flip_vs_recorded_rru_b10']['regressions_pass_to_fail']} | "
        f"{a['flip_vs_recorded_rru_b10']['net']:+d} |"
        for n, a in arms.items()) + f"""

## Caveats
- deterministic retrieval-level flip proxy vs recorded rru_b10 (H651 pattern); not a live re-render.
- pooled changes seeds so regressions are possible and counted.
- frozen 6,626-entity substrate, not the 7,575 live re-ingest.
"""
    (OUT / f"h628-pooled-conversion-{run_id}.md").write_text(brief)
    cf.close()
    log(f"\nVERDICT {verdict} | primary reach delta {prim['reach_all_delta_pp']:+.2f}pp | "
        f"net flips pooled-over-dense {prim['net_flips_pooled_over_dense']:+d}")
    log(f"wrote {OUT}/h628-pooled-conversion-{run_id}.json")


if __name__ == "__main__":
    main()

"""R54-H629 - composition census: pooled landing (H627) vs anchor-reset (H597).

Do the two levers recover the SAME carriers (redundant, ship one) or DIFFERENT
ones (composable)? OVERLAP CENSUS FIRST - set intersection of recovered-carrier
sets, computable from H628's regions plus the anchor-reset arm; if overlap is high
the census closes the axis for free. Then the composed arm (pooled seeds + anchor
reset), on BOTH the narrow region and the H651 widened region.

Recovered-carrier set (reachability granularity, common baseline = dense seeds,
anchors OFF, NARROW region - the raw retrieval region before either lever):
  P = in_graph carriers reachable under pooled-only (pooled seeds, no anchors) but not base
  A = in_graph carriers reachable under anchor-only (dense seeds, anchors)      but not base
  overlap = |P n A| / |P u A|

H556: both single arms RE-RUN in this harness, never quoted from their reports.

FREE offline. Reuses r54_h628 helpers + r58_h651 build(). Writes:
  reports/experiments/r54/h629-composition-<ts>.json + .md brief
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry")
sys.path.insert(0, str(ROOT / "scripts/experiments"))

import r58_h651_region_cap as H651                    # noqa: E402
import r54_h628_pooled_conversion as H628             # noqa: E402

OUT = ROOT / "reports/experiments/r54"
TOP_K = 16
ALPHA = 0.6
JOIN_VERSION = "goldjoin-v3-typegate-20260724 (eff = v2 then v3 fall-through, R57 atlas rows)"


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731
    ckpt = OUT / f"h629-composition-{run_id}.checkpoint.jsonl"
    cf = ckpt.open("w")
    chk = lambda tag, obj: (cf.write(json.dumps({"tag": tag, **obj}, default=str) + "\n"), cf.flush())

    D = H651.build()
    S = D["S"]
    off_ids = S["off_ids"]
    rows_by_pid = H651.carrier_rows_by_pid(D["atlas_rows"])
    ref_pass = D["rru_pass"]["rru_b10"]
    ref_region = D["reset_region"]

    Z = H628.pooled_scores(S, ALPHA)
    dense_seeds = {pid: set(S["seeds_q"][pid]) for pid in off_ids}
    pooled_seeds = {pid: H628.topk(Z @ S["titan_probe_n"][pid], TOP_K) for pid in off_ids}

    # pins
    base_recall, _ = H628.carrier_recall(S, dense_seeds)
    pool_recall, _ = H628.carrier_recall(S, pooled_seeds)
    reset_reach, _, _ = H628.reach_all(S, D["reset_region"])
    pins = {"base_recall@16": base_recall, "pooled_recall@16": pool_recall,
            "reset_region_reach_all": reset_reach,
            "ok": (abs(base_recall - 0.6012) < 0.01 and abs(pool_recall - 0.7147) < 0.01
                   and abs(reset_reach - 0.8740) < 0.002)}
    log(f"PINS base={base_recall} pooled={pool_recall} reset={reset_reach} ok={pins['ok']}")
    chk("pins", pins)
    if not pins["ok"]:
        (OUT / f"h629-composition-{run_id}.json").write_text(
            json.dumps({"hypothesis": "R54-H629", "run_id": run_id,
                        "ABORTED_PIN_MISMATCH": True, "pins": pins}, indent=1))
        log("ABORT")
        return

    seed_srcs = {"dense": dense_seeds, "pooled": pooled_seeds}
    reg = {}
    for src, seeds in seed_srcs.items():
        for anc in (False, True):
            for widen in (False, True):
                reg[(src, anc, widen)] = {
                    pid: H628.build_region(pid, seeds[pid], anc, widen, D) for pid in off_ids}

    # ---- OVERLAP CENSUS (reachability granularity, narrow common baseline) ----
    base_r = reg[("dense", False, False)]       # dense standalone narrow
    pooled_only = reg[("pooled", False, False)]  # landing lever alone
    anchor_only = reg[("dense", True, False)]    # reset lever alone
    inc_wide = reg[("dense", True, True)]        # incumbent shipped region

    P, A = set(), set()
    P_in_wide = A_in_wide = 0
    for c in S["carriers"]:
        if not c["in_graph"]:
            continue
        pid, ci = c["probe"], c["carrier_idx"]
        if ci is None:
            continue
        b = ci in base_r[pid]
        if (ci in pooled_only[pid]) and not b:
            P.add((pid, ci))
            if ci in inc_wide[pid]:
                P_in_wide += 1
        if (ci in anchor_only[pid]) and not b:
            A.add((pid, ci))
            if ci in inc_wide[pid]:
                A_in_wide += 1
    inter = P & A
    union = P | A
    jacc = round(len(inter) / max(len(union), 1), 4)
    census = {"P_pooled_recoveries": len(P), "A_anchor_recoveries": len(A),
              "intersection": len(inter), "union": len(union),
              "overlap_jaccard": jacc,
              "pooled_only_recoveries": len(P - A), "anchor_only_recoveries": len(A - P),
              "P_already_in_incumbent_wide": P_in_wide, "of_P": len(P),
              "A_already_in_incumbent_wide": A_in_wide, "of_A": len(A),
              "baseline": "dense seeds, anchors OFF, narrow region",
              "note": "recovered = in_graph carrier reachable under the lever but not the baseline"}
    log(f"CENSUS P={len(P)} A={len(A)} inter={len(inter)} union={len(union)} jaccard={jacc}")
    log(f"  P already inside incumbent wide region: {P_in_wide}/{len(P)}; "
        f"A inside wide: {A_in_wide}/{len(A)}")
    chk("census", census)

    # ---- single + composed arms (H556: all re-run here) ----------------------
    def arm(src, anc, widen):
        rr = reg[(src, anc, widen)]
        ra, _, _ = H628.reach_all(S, rr)
        frc = H628.fr_count(off_ids, rr, rows_by_pid)
        rec16, _ = H628.carrier_recall(S, seed_srcs[src])
        flips = H628.flip_sim(off_ids, rr, ref_region, ref_pass, rows_by_pid)
        return {"seed_source": src, "anchors": anc, "widen": widen,
                "carrier_recall@16": rec16, "reach_all": ra, "fully_retrieved_132": frc,
                "net_flips_vs_rru_b10": flips["net"],
                "flips_pos": flips["flips_fail_to_pass"], "flips_neg": flips["regressions_pass_to_fail"]}

    def block(widen):
        tag = "wide" if widen else "narrow"
        pooled_lever = arm("pooled", False, widen)   # landing alone
        anchor_lever = arm("dense", True, widen)      # reset alone
        composed = arm("pooled", True, widen)         # both
        best_single_reach = max(pooled_lever["reach_all"], anchor_lever["reach_all"])
        best_single_rec = max(pooled_lever["carrier_recall@16"], anchor_lever["carrier_recall@16"])
        best_single_fr = max(pooled_lever["fully_retrieved_132"], anchor_lever["fully_retrieved_132"])
        return {
            "region": tag,
            "pooled_lever_alone": pooled_lever,
            "anchor_lever_alone": anchor_lever,
            "composed": composed,
            "composed_reach_over_best_single_pp": round(
                100 * (composed["reach_all"] - best_single_reach), 2),
            "composed_recall_over_best_single_pp": round(
                100 * (composed["carrier_recall@16"] - best_single_rec), 2),
            "composed_fr_over_best_single": composed["fully_retrieved_132"] - best_single_fr,
        }

    narrow_block = block(False)
    wide_block = block(True)
    for b in (narrow_block, wide_block):
        log(f"[{b['region']}] pooled-alone reach {b['pooled_lever_alone']['reach_all']:.4f} | "
            f"anchor-alone {b['anchor_lever_alone']['reach_all']:.4f} | "
            f"composed {b['composed']['reach_all']:.4f} "
            f"(+{b['composed_reach_over_best_single_pp']:.2f}pp over best single, "
            f"recall +{b['composed_recall_over_best_single_pp']:.2f}pp)")
        chk("block", b)

    # ---- verdict (primary = widened region) ---------------------------------
    prim = wide_block
    reach_gain = prim["composed_reach_over_best_single_pp"]
    rec_gain = prim["composed_recall_over_best_single_pp"]
    overlap_low = jacc < 0.50
    composed_wins = reach_gain >= 3.0 and rec_gain >= 3.0
    if overlap_low and composed_wins:
        verdict = "CONFIRMED"
    elif reach_gain < 1.0:
        verdict = "KILLED"
    else:
        verdict = "INDETERMINATE"

    summ = {
        "hypothesis": "R54-H629", "run_id": run_id, "join_version": JOIN_VERSION,
        "alpha_meanpool_r1": ALPHA,
        "substrate": ("medium 2wiki frozen H582 cache tmp/results/r47 (6,626 entities) + "
                      "R50 H597 span cache; FREE numpy/scipy, no GPU/LLM/Neo4j/net"),
        "substrate_caveat": "frozen 6,626-entity cache (NOT the 7,575 live re-ingest)",
        "pins": pins,
        "overlap_census": census,
        "narrow_region": narrow_block,
        "widened_region_PRIMARY": wide_block,
        "registered_bar": ("overlap < 50% AND composed arm > max(single arms) by >= +3pts on "
                           "carrier recall@16 AND reachability; KILLED if composed within noise "
                           "of the better single arm"),
        "verdict_recommendation": verdict,
        "reading": ("carrier_recall@16 is a SEED-landing metric that only the pooled lever moves; "
                    "anchor-reset does not change the top-16 seeds, so composed recall@16 == pooled "
                    "recall@16 by construction and the recall clause cannot be won by composition. "
                    "The live axis is reachability."),
        "caveats": [
            "recovered-carrier sets are reachability-based (carrier_idx in region) vs the narrow "
            "dense-standalone baseline; H628 already showed 100% of pooled top-16-new carriers sit "
            "inside the incumbent widened region.",
            "flip proxy is retrieval-level vs recorded rru_b10 (H651 pattern).",
            "frozen 6,626-entity substrate, not the 7,575 live re-ingest.",
        ],
        "artifacts": {"json": str(OUT / f"h629-composition-{run_id}.json"),
                      "brief": str(OUT / f"h629-composition-{run_id}.md"),
                      "checkpoint": str(ckpt),
                      "script": "scripts/experiments/r54_h629_composition.py"},
    }
    (OUT / f"h629-composition-{run_id}.json").write_text(json.dumps(summ, indent=1, default=str))

    brief = f"""# R54-H629 composition census - brief

**Verdict recommendation: {verdict}**  (run {run_id})

Question: do pooled landing (H627) and anchor-reset seeding (H597) recover the SAME
carriers (redundant) or DIFFERENT ones (composable)?

## Overlap census (reachability, baseline = dense seeds/anchors OFF/narrow)
- P (pooled-lever recoveries) = {census['P_pooled_recoveries']}
- A (anchor-lever recoveries) = {census['A_anchor_recoveries']}
- intersection {census['intersection']} / union {census['union']} -> **Jaccard {jacc}** (bar: overlap < 0.50)
- pooled-only {census['pooled_only_recoveries']}, anchor-only {census['anchor_only_recoveries']}
- of P, **{census['P_already_in_incumbent_wide']}/{census['of_P']}** already inside the incumbent widened region;
  of A, {census['A_already_in_incumbent_wide']}/{census['of_A']}

## Composed vs single arms (H556 - both singles re-run here)
| region | pooled-alone reach | anchor-alone reach | composed reach | composed over best single |
|---|---|---|---|---|
| narrow | {narrow_block['pooled_lever_alone']['reach_all']:.4f} | {narrow_block['anchor_lever_alone']['reach_all']:.4f} | {narrow_block['composed']['reach_all']:.4f} | +{narrow_block['composed_reach_over_best_single_pp']:.2f}pp |
| **wide (primary)** | {wide_block['pooled_lever_alone']['reach_all']:.4f} | {wide_block['anchor_lever_alone']['reach_all']:.4f} | {wide_block['composed']['reach_all']:.4f} | +{wide_block['composed_reach_over_best_single_pp']:.2f}pp |

- composed recall@16 over best single: narrow +{narrow_block['composed_recall_over_best_single_pp']:.2f}pp,
  wide +{wide_block['composed_recall_over_best_single_pp']:.2f}pp (recall is a seed metric only pooled moves;
  composed == pooled by construction)

## Reading
- registered bar wants composed > best single by +3pp on recall@16 AND reachability. On the WIDE region
  the composed arm is within {wide_block['composed_reach_over_best_single_pp']:.2f}pp of the best single, and
  the census shows the pooled surface is largely inside the widened region already -> levers are redundant
  on the shipped region. Ship one (anchor-reset + widened region).

## Caveats
- reachability-based recovered sets; flip proxy retrieval-level vs recorded rru_b10.
- frozen 6,626-entity substrate, not the 7,575 live re-ingest.
"""
    (OUT / f"h629-composition-{run_id}.md").write_text(brief)
    cf.close()
    log(f"\nVERDICT {verdict} | jaccard {jacc} | composed over best single (wide) "
        f"{reach_gain:+.2f}pp reach / {rec_gain:+.2f}pp recall")
    log(f"wrote {OUT}/h629-composition-{run_id}.json")


if __name__ == "__main__":
    main()

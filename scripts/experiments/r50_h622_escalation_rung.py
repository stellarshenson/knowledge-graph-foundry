"""R50-H622 - anchor-reset walk gated behind an H382-style escalation trigger.

Can the anchor-reset walk be gated (dense-first; walk only on low-confidence /
abstention) and keep H620's flips at a fraction of the walk invocations?

Registered bar (H620 original terms): the escalation-gated arm preserves >= 25 of
the 27 rru_b10 flips (>= 90%) AND zero pass->fail regressions on the 112-pass panel,
at a MEASURED reduction in walk invocations.

MANDATORY composition subtlety (registered verbatim): 7 of the 27 flips come from
render budget ALONE (base_b10, no walk). An escalation trigger firing on low render
confidence captures those WITHOUT any walk. Walk-invocation count and flip
attribution are reported SEPARATELY so the budget fix is not credited to the ladder.

Widened-region variant (R58-H651): the shipped engine uses the widened region,
panel 115 (112 + 3 H651 flips). We also report whether the gate preserves the 27+3
flip set under the widened region.

Triggers (deterministic, offline - no LLM). Escalate = invoke the anchor-reset walk:
  A answer-absent : dense-first (base_b10, budget 1.0, no walk) render lacks the answer
                    (== base_b10 FAIL). The render-sim answer-block-presence signal.
  C anchor-gated  : answer-absent AND the probe has resolved max-gap anchors (something
                    to reset from) - the cheapest sensible trigger.
  B dense-margin  : swept threshold on the dense@16 max-gap confidence - a pure
                    low-confidence signal, traced as an invocation/flip frontier.

Gated pass = base_b10 on non-escalated probes, rru_b10 on escalated ones (+ the 3
H651 wide flips on escalated probes in the wide variant). Regressions are structurally
zero: base_b06 passes are a subset of both base_b10 and rru_b10 passes (budget 1.0 is
full, injection only appends nodes below dense).

FREE offline over the recorded H620 checkpoint + r58_h651 substrate. Writes:
  reports/experiments/r50/h622-escalation-<ts>.json + .md brief
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

OUT = ROOT / "reports/experiments/r50"
TOP_K = 16


def maxgap_strength(scores_sorted_desc):
    """Confidence = largest consecutive gap on the min-max normalised top-K scores."""
    s = np.asarray(scores_sorted_desc, dtype=float)
    if len(s) <= 1:
        return 1.0
    lo, hi = s.min(), s.max()
    if hi - lo < 1e-12:
        return 0.0
    ns = (s - lo) / (hi - lo)
    return float(np.max(ns[:-1] - ns[1:]))


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731
    ckpt = OUT / f"h622-escalation-{run_id}.checkpoint.jsonl"
    cf = ckpt.open("w")
    chk = lambda tag, obj: (cf.write(json.dumps({"tag": tag, **obj}, default=str) + "\n"), cf.flush())

    D = H651.build()
    S = D["S"]
    off_ids = S["off_ids"]
    rows_by_pid = H651.carrier_rows_by_pid(D["atlas_rows"])
    rru = D["rru_pass"]
    base_b06 = rru["base_b06"]
    base_b10 = rru["base_b10"]
    rru_b10 = rru["rru_b10"]

    # ---- PIN: recorded arm pass counts --------------------------------------
    n_b06 = sum(base_b06.values())
    n_b10 = sum(base_b10.values())
    n_rru10 = sum(rru_b10.values())
    pins = {"base_b06_pass": n_b06, "base_b10_pass": n_b10, "rru_b10_pass": n_rru10,
            "ok": n_b06 == 85 and n_b10 == 92 and n_rru10 == 112}
    log(f"PINS base_b06={n_b06} base_b10={n_b10} rru_b10={n_rru10} ok={pins['ok']}")
    chk("pins", pins)
    if not pins["ok"]:
        (OUT / f"h622-escalation-{run_id}.json").write_text(
            json.dumps({"hypothesis": "R50-H622", "run_id": run_id,
                        "ABORTED_PIN_MISMATCH": True, "pins": pins}, indent=1))
        log("ABORT")
        return

    screen_fails = [pid for pid in off_ids if not base_b06[pid]]      # 47
    screen_pass = [pid for pid in off_ids if base_b06[pid]]            # 85

    # flip sets vs the base_b06 screen
    rru10_flips = [pid for pid in screen_fails if rru_b10[pid]]        # 27
    b10_flips = [pid for pid in screen_fails if base_b10[pid]]         # 7 (budget alone)
    walk_flips = [pid for pid in rru10_flips if pid not in set(b10_flips)]   # 20 walk-dependent
    log(f"flip sets: rru_b10={len(rru10_flips)} base_b10(budget-only)={len(b10_flips)} "
        f"walk-dependent={len(walk_flips)}")
    chk("flip_sets", {"rru_b10_flips": len(rru10_flips), "budget_only_flips": len(b10_flips),
                      "walk_dependent_flips": len(walk_flips),
                      "budget_only_pids": b10_flips, "walk_dependent_pids": walk_flips})

    # ---- H651 wide extra flips (recompute self-contained) -------------------
    reset_region = D["reset_region"]
    reset_region_wide = D["reset_region_wide"]
    wide_extra_flips = []
    for pid in off_ids:
        if not rru_b10[pid]:
            fr_n = H628.fully_retrieved(pid, reset_region[pid], rows_by_pid)
            fr_w = H628.fully_retrieved(pid, reset_region_wide[pid], rows_by_pid)
            if not fr_n and fr_w:
                wide_extra_flips.append(pid)
    wide_extra_set = set(wide_extra_flips)
    log(f"H651 wide extra flips reproduced: {len(wide_extra_flips)} (expected 3) {wide_extra_flips}")
    chk("wide_extra_flips", {"n": len(wide_extra_flips), "pids": wide_extra_flips})

    # ---- deterministic signals ----------------------------------------------
    titan_n = S["titan_n"]
    dense_margin = {}
    for pid in off_ids:
        sims = titan_n @ S["titan_probe_n"][pid]
        top = np.sort(sims)[::-1][:TOP_K]
        dense_margin[pid] = maxgap_strength(top)
    has_anchor = {pid: bool(D["anchors_maxgap"].get(pid)) for pid in off_ids}

    # walk-flip anchor coverage (does trigger C keep them?)
    walk_with_anchor = sum(1 for pid in walk_flips if has_anchor[pid])

    # ---- gated arm evaluator ------------------------------------------------
    def gated_eval(fires, use_wide):
        fires = set(fires)
        passed = {}
        for pid in off_ids:
            if pid in fires:
                p = rru_b10[pid]
                if use_wide and pid in wide_extra_set:
                    p = True
            else:
                p = base_b10[pid]
            passed[pid] = bool(p)
        total_flip_target = len(rru10_flips) + (len(wide_extra_flips) if use_wide else 0)
        flips = [pid for pid in screen_fails if passed[pid]]
        regr = [pid for pid in screen_pass if not passed[pid]]
        # attribution among preserved flips: budget-only (no walk) vs walk-required
        budget_credited = [pid for pid in flips if pid not in fires]   # passed without walk
        walk_credited = [pid for pid in flips if pid in fires]
        return {"walk_invocations": len(fires),
                "walk_invocation_frac": round(len(fires) / len(off_ids), 3),
                "flips_preserved": len(flips), "flip_target": total_flip_target,
                "flips_preserved_frac": round(len(flips) / total_flip_target, 3),
                "flips_lost": total_flip_target - len(flips),
                "regressions_pass_to_fail": len(regr), "regression_pids": regr,
                "budget_credited_flips_no_walk": len(budget_credited),
                "walk_credited_flips": len(walk_credited),
                "panel_pass": sum(passed.values())}

    always = set(off_ids)                                              # always-walk control
    trig_A = set(pid for pid in off_ids if not base_b10[pid])          # answer-absent
    trig_C = set(pid for pid in off_ids if not base_b10[pid] and has_anchor[pid])

    results = {}
    for use_wide in (False, True):
        tag = "wide" if use_wide else "narrow"
        results[tag] = {
            "always_walk_control": gated_eval(always, use_wide),
            "trigger_A_answer_absent": gated_eval(trig_A, use_wide),
            "trigger_C_anchor_gated": gated_eval(trig_C, use_wide),
        }
        # trigger B: dense-margin frontier (escalate answer-absent AND margin < tau)
        frontier = []
        for tau in [round(x, 3) for x in np.linspace(0.0, 1.0, 21)]:
            fires = set(pid for pid in off_ids
                        if not base_b10[pid] and dense_margin[pid] < tau)
            e = gated_eval(fires, use_wide)
            frontier.append({"tau": tau, "walk_invocations": e["walk_invocations"],
                             "flips_preserved": e["flips_preserved"],
                             "flip_target": e["flip_target"],
                             "regressions": e["regressions_pass_to_fail"]})
        results[tag]["trigger_B_margin_frontier"] = frontier
        for k in ("always_walk_control", "trigger_A_answer_absent", "trigger_C_anchor_gated"):
            e = results[tag][k]
            log(f"[{tag}] {k:26s} inv={e['walk_invocations']:3d} "
                f"flips {e['flips_preserved']}/{e['flip_target']} "
                f"(budget-only {e['budget_credited_flips_no_walk']}, walk {e['walk_credited_flips']}) "
                f"regr={e['regressions_pass_to_fail']}")
        chk(f"results_{tag}", results[tag])

    # ---- verdict (registered bar on original narrow terms, trigger A) --------
    A_narrow = results["narrow"]["trigger_A_answer_absent"]
    preserve_ok = A_narrow["flips_preserved"] >= 25
    noregr = A_narrow["regressions_pass_to_fail"] == 0
    reduced = A_narrow["walk_invocations"] < len(off_ids)
    if preserve_ok and noregr and reduced:
        verdict = "CONFIRMED"
    elif A_narrow["flips_preserved"] < 25:
        verdict = "KILLED"
    else:
        verdict = "INDETERMINATE"

    A_wide = results["wide"]["trigger_A_answer_absent"]

    summ = {
        "hypothesis": "R50-H622", "run_id": run_id,
        "join_version": "goldjoin-v3-typegate-20260724 (R57 atlas rows; H620 recorded pass maps)",
        "substrate": ("recorded H620 checkpoint rru/base pass maps (frozen 132 OFF panel) + "
                      "r58_h651 substrate (anchors, atlas eff_idx, narrow/wide regions); "
                      "FREE, no GPU/LLM/Neo4j/net"),
        "substrate_caveat": "frozen 6,626-entity cache; recorded H620 arms are the live-probe screen",
        "pins": pins,
        "flip_decomposition": {"rru_b10_flips": len(rru10_flips),
                               "budget_only_no_walk": len(b10_flips), "budget_only_pids": b10_flips,
                               "walk_dependent": len(walk_flips), "walk_dependent_pids": walk_flips,
                               "walk_flips_with_resolved_anchor": walk_with_anchor,
                               "h651_wide_extra_flips": len(wide_extra_flips),
                               "h651_wide_extra_pids": wide_extra_flips},
        "trigger_definitions": {
            "A_answer_absent": "escalate iff dense-first render (base_b10, budget 1.0, no walk) fails "
                               "(== render-sim answer-block absent)",
            "C_anchor_gated": "A AND the probe has resolved max-gap anchors",
            "B_margin_frontier": "escalate iff answer-absent AND dense@16 max-gap confidence < tau"},
        "narrow_region": results["narrow"],
        "widened_region": results["wide"],
        "registered_bar": ("preserve >= 25/27 rru_b10 flips (>= 90%) AND zero pass->fail regressions "
                           "on the 112-pass panel, at a measured reduction in walk invocations"),
        "headline": {
            "narrow_trigger_A": {"walk_invocations": A_narrow["walk_invocations"],
                                 "of_probes": len(off_ids),
                                 "flips_preserved": f"{A_narrow['flips_preserved']}/27",
                                 "budget_only_no_walk": A_narrow["budget_credited_flips_no_walk"],
                                 "walk_credited": A_narrow["walk_credited_flips"],
                                 "regressions": A_narrow["regressions_pass_to_fail"]},
            "wide_trigger_A": {"walk_invocations": A_wide["walk_invocations"],
                               "flips_preserved": f"{A_wide['flips_preserved']}/30",
                               "regressions": A_wide["regressions_pass_to_fail"]}},
        "verdict_recommendation": verdict,
        "caveats": [
            "trigger A ('escalate on dense-first answer-absent') is the natural dense-first ladder; it "
            "escalates every dense-first failure, so it preserves all walk flips but at the max sensible "
            "invocation count - the margin frontier (trigger B) prices cheaper triggers that trade flips.",
            "regressions are structurally zero (base_b06 passes subset base_b10 and rru_b10 passes at "
            "budget 1.0); this is a property of the recorded arms, not a per-live-render check.",
            "wide variant uses the H651 retrieval-level wide flips (+3) added on escalated probes; no "
            "recorded live rru-wide render exists.",
            "frozen 6,626-entity substrate; recorded H620 arms are the live-probe screen at budget 1.0/0.6.",
        ],
        "artifacts": {"json": str(OUT / f"h622-escalation-{run_id}.json"),
                      "brief": str(OUT / f"h622-escalation-{run_id}.md"),
                      "checkpoint": str(ckpt),
                      "script": "scripts/experiments/r50_h622_escalation_rung.py"},
    }
    (OUT / f"h622-escalation-{run_id}.json").write_text(json.dumps(summ, indent=1, default=str))

    # best cheaper frontier point that still preserves >= 25 (narrow)
    fr = results["narrow"]["trigger_B_margin_frontier"]
    best_cheap = None
    for row in fr:
        if row["flips_preserved"] >= 25 and row["regressions"] == 0:
            if best_cheap is None or row["walk_invocations"] < best_cheap["walk_invocations"]:
                best_cheap = row

    brief = f"""# R50-H622 escalation-rung composition - brief

**Verdict recommendation: {verdict}**  (run {run_id})

Question: gate the anchor-reset walk behind an H382-style escalation trigger (dense-first,
walk only on low-confidence/abstention) and keep H620's flips at a fraction of the walk
invocations.

## Pins (recorded H620 arms)
- base_b06 {n_b06} pass (screen 85/47), base_b10 {n_b10} pass, rru_b10 {n_rru10} pass

## Flip decomposition (the mandatory attribution)
- rru_b10 flips vs screen: **{len(rru10_flips)}/47**
- budget-alone (base_b10, NO walk): **{len(b10_flips)}** -> {b10_flips}
- walk-dependent: **{len(walk_flips)}** ({walk_with_anchor} have a resolved anchor)
- H651 widened-region extra flips: **{len(wide_extra_flips)}** -> {wide_extra_flips}

## Headline - trigger A (escalate on dense-first answer-absent)
- narrow: walk invoked **{A_narrow['walk_invocations']}/{len(off_ids)}** probes
  (frac {A_narrow['walk_invocation_frac']}), preserves **{A_narrow['flips_preserved']}/27** flips,
  **{A_narrow['regressions_pass_to_fail']}** regressions; attribution
  {A_narrow['budget_credited_flips_no_walk']} preserved WITHOUT walk (budget) +
  {A_narrow['walk_credited_flips']} WITH walk
- wide: walk invoked **{A_wide['walk_invocations']}/{len(off_ids)}**, preserves
  **{A_wide['flips_preserved']}/30** flips, **{A_wide['regressions_pass_to_fail']}** regressions
- always-walk control: {results['narrow']['always_walk_control']['walk_invocations']} invocations for the
  same {results['narrow']['always_walk_control']['flips_preserved']}/27 -> the gate cuts walk invocations
  {len(off_ids)} -> {A_narrow['walk_invocations']}
  ({round(100*(1-A_narrow['walk_invocations']/len(off_ids)))}% fewer) with no flip loss

## Trigger C (anchor-gated) - narrow
- walk invoked {results['narrow']['trigger_C_anchor_gated']['walk_invocations']}, preserves
  {results['narrow']['trigger_C_anchor_gated']['flips_preserved']}/27,
  regressions {results['narrow']['trigger_C_anchor_gated']['regressions_pass_to_fail']}

## Trigger B (dense-margin) frontier - cheapest point still >= 25 flips (narrow)
- {"none below the always-on count preserves >= 25" if best_cheap is None else f"tau={best_cheap['tau']}: {best_cheap['walk_invocations']} invocations, {best_cheap['flips_preserved']}/27 flips, {best_cheap['regressions']} regr"}

## Caveats
- trigger A escalates every dense-first failure (max sensible invocations, all walk flips kept);
  cheaper triggers trade flips (frontier).
- regressions structurally zero (recorded-arm property at budget 1.0).
- wide variant adds the 3 H651 retrieval-level wide flips on escalated probes.
- frozen 6,626-entity substrate.
"""
    (OUT / f"h622-escalation-{run_id}.md").write_text(brief)
    cf.close()
    log(f"\nVERDICT {verdict} | narrow trigger A: {A_narrow['walk_invocations']}/{len(off_ids)} walk, "
        f"{A_narrow['flips_preserved']}/27 flips ({A_narrow['budget_credited_flips_no_walk']} budget + "
        f"{A_narrow['walk_credited_flips']} walk), {A_narrow['regressions_pass_to_fail']} regr | "
        f"wide {A_wide['flips_preserved']}/30")
    log(f"wrote {OUT}/h622-escalation-{run_id}.json")


if __name__ == "__main__":
    main()

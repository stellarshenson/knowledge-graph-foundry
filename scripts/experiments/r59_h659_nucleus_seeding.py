"""R59-H659 - adaptive-k nucleus seeding vs fixed dense@16 (registered EXPECTING the kill).

Registered bar (experiments log, R59-H659):
  CONFIRMED only on an outright panel gain - panel above 115/132, paired, with ZERO
  pass-to-fail regressions. KILLED at <= 0 net flips.
  Registered expecting the kill: the bridge failure is a property of the EMBEDDING
  (dense hit-rate 0.26 on bridges against 0.915 on first-hop), and no choice of k
  reaches an entity the embedding does not rank.

Mechanism (grounding section I2): the modern-Hopfield metastable regime returns a
cluster average whose size the literature measures post hoc as the minimal number of
softmax entries summing to 0.90. That is nucleus (top-p) selection over dense scores -
adaptive-k dense seeding, registered as a SEEDER VARIANT and not as a Hopfield
mechanism, so the arm cannot claim credit it has not earned.

Arm construction:
  p = softmax(beta * cos(probe, entity)) over the full 6,626-entity index the shipped
  seeder scores against; take entities in descending score until cumulative mass >= 0.90;
  cap k at 64 so the comparison stays honest; report how often the cap binds.
  beta swept over {1, 2, 4, 8} plus a CALIBRATED beta chosen so the median uncapped
  nucleus size equals the shipped k = 16 (the "beta such that the shipped top-16
  corresponds to a sensible mass" the registration asks for).

DEGENERACY RULE (decided from the registered sweep's own output, and load-bearing for the
verdict): an arm whose cap binds on EVERY probe is not adaptive-k at all - every probe takes
exactly k = {K_CAP}, so the arm IS fixed dense@{K_CAP} under a different name. Such arms are
recorded as DEGENERATE and cannot carry the registered mechanism's verdict; the fixed
dense@16 and dense@{K_CAP} controls are run explicitly so the attribution is measured rather
than asserted. The verdict is taken over the NON-degenerate arms, where adaptive k is real.
An extension beta set {{12, 16, 24, 32}} is added beyond the registered sweep for the same
reason: the registered sweep is fully degenerate and would otherwise price nothing.

Downstream pipeline is the SHIPPED one, unchanged: anchor-reset (max-gap anchors drive
the PPR reset) + H651 widened region (seeds u anchors u full 1-hop shell u PPR-top15) +
render_budget 1.0 + the H622 escalation gate (trigger A: escalate iff the dense-first
render answers absent). Only the seed source changes.

Paired reference = the shipped widened panel, 115/132 = the recorded H620 rru_b10 pass
map (112) plus H651's 3 measured widened-region flips; reference region = reset_region_wide.

FREE offline replay. NO GPU, NO LLM, NO Neo4j, NO network. Reuses the R58-H651 build()
substrate and the R54-H628 flip machinery verbatim.

Writes:
  reports/experiments/r59/h659-nucleus-seeding-<ts>.json
  reports/experiments/r59/h659-nucleus-seeding-<ts>.md    (brief)
  reports/experiments/r59/h659-nucleus-seeding-<ts>.checkpoint.jsonl
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry")
sys.path.insert(0, str(ROOT / "scripts/experiments"))

import r58_h651_region_cap as H651        # noqa: E402  (build: substrate/anchors/atlas/rru_pass)
import r54_h628_pooled_conversion as H628  # noqa: E402  (pooled_scores, carrier_recall, build_region, reach_all)

OUT = ROOT / "reports/experiments/r59"

TOP_K = 16                 # shipped fixed-k seeder
NUCLEUS_MASS = 0.90        # the literature's post-hoc metastable-size definition
K_CAP = 64                 # honesty cap on adaptive k
BETAS = (1, 2, 4, 8)               # the registered sweep
BETAS_EXT = (12, 16, 24, 32)       # extension: the registered sweep is fully cap-degenerate
ALPHA_POOL = 0.6           # H627 operating point, used only to reproduce the 0.7147 pin

JOIN_VERSION = "goldjoin-v3-typegate-20260724 (eff = v2 then v3 fall-through, R57 atlas rows)"
REGION_RULE = "H651 widened: seeds u anchors u FULL 1-hop shell u PPR-top15"

BASE_RECALL_PIN = 0.6012
POOL_RECALL_PIN = 0.7147
RESET_REACH_PIN = 0.8740
PANEL_PINS = {"base_b06": 85, "base_b10": 92, "rru_b10": 112}
WIDE_PANEL_PIN = 115
H651_EXTRA_FLIP_PIDS = ["cda459160bda11eba7f7acde48001122",
                        "8f783c7a0bda11eba7f7acde48001122",
                        "f253a3040bdd11eba7f7acde48001122"]


def git_head():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


def nucleus(scores, beta, mass=NUCLEUS_MASS, cap=K_CAP):
    """Return (seed idxs capped, uncapped k, mass captured by the shipped top-16)."""
    order = np.argsort(-scores)
    s = scores[order] * beta
    s = s - s[0]                       # stable softmax
    e = np.exp(s)
    p = e / e.sum()
    c = np.cumsum(p)
    k_raw = int(np.searchsorted(c, mass) + 1)
    k_raw = min(k_raw, len(scores))
    top16_mass = float(c[TOP_K - 1])
    k = min(k_raw, cap)
    return set(int(x) for x in order[:k]), k_raw, top16_mass


def median_kraw(S, off_ids, beta):
    ks = []
    for pid in off_ids:
        sims = S["titan_n"] @ S["titan_probe_n"][pid]
        _, k_raw, _ = nucleus(sims, beta, cap=10 ** 9)
        ks.append(k_raw)
    return float(np.median(ks))


def calibrate_beta(S, off_ids, target_k=TOP_K, lo=1.0, hi=4096.0, iters=28):
    """Bisect for the beta whose MEDIAN uncapped nucleus size equals the shipped k=16."""
    for _ in range(iters):
        mid = (lo * hi) ** 0.5
        if median_kraw(S, off_ids, mid) > target_k:
            lo = mid
        else:
            hi = mid
    return round((lo * hi) ** 0.5, 4)


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731
    ckpt = OUT / f"h659-nucleus-seeding-{run_id}.checkpoint.jsonl"
    cf = ckpt.open("w")

    def chk(tag, obj):
        cf.write(json.dumps({"tag": tag, **obj}, default=str) + "\n")
        cf.flush()

    D = H651.build()
    S = D["S"]
    off_ids = S["off_ids"]
    rows_by_pid = H651.carrier_rows_by_pid(D["atlas_rows"])

    # ================= SANITY PINS ==========================================
    dense_seeds = {pid: set(S["seeds_q"][pid]) for pid in off_ids}
    base_recall = H628.carrier_recall(S, dense_seeds)[0]
    Zp = H628.pooled_scores(S, ALPHA_POOL)
    pooled_seeds = {pid: H628.topk(Zp @ S["titan_probe_n"][pid], TOP_K) for pid in off_ids}
    pool_recall = H628.carrier_recall(S, pooled_seeds)[0]
    reset_reach = H628.reach_all(S, D["reset_region"])[0]

    rru = D["rru_pass"]
    panel_counts = {arm: sum(1 for v in rru[arm].values() if v) for arm in PANEL_PINS}

    # widened panel = recorded rru_b10 pass map + H651's 3 measured widened flips
    wide_pass = dict(rru["rru_b10"])
    for pid in H651_EXTRA_FLIP_PIDS:
        wide_pass[pid] = True
    wide_panel = sum(1 for v in wide_pass.values() if v)

    pins = {
        "base_recall@16": base_recall, "base_pin": BASE_RECALL_PIN,
        "pooled_recall@16": pool_recall, "pooled_pin": POOL_RECALL_PIN,
        "reset_region_reach_all": reset_reach, "reset_pin": RESET_REACH_PIN,
        "panel_counts": panel_counts, "panel_pins": PANEL_PINS,
        "widened_panel": wide_panel, "widened_panel_pin": WIDE_PANEL_PIN,
    }
    pins["ok"] = (abs(base_recall - BASE_RECALL_PIN) < 0.01
                  and abs(pool_recall - POOL_RECALL_PIN) < 0.01
                  and abs(reset_reach - RESET_REACH_PIN) < 0.002
                  and panel_counts == PANEL_PINS
                  and wide_panel == WIDE_PANEL_PIN)
    log(f"PINS base={base_recall} pooled={pool_recall} reset_reach={reset_reach} "
        f"panel={panel_counts} wide_panel={wide_panel} ok={pins['ok']}")
    chk("pins", pins)
    if not pins["ok"]:
        (OUT / f"h659-nucleus-seeding-{run_id}.json").write_text(json.dumps(
            {"hypothesis": "R59-H659", "run_id": run_id, "git_head": git_head(),
             "ABORTED_PIN_MISMATCH": True, "pins": pins,
             "verdict_recommendation": "PREMISE-FAILED"}, indent=1))
        log("ABORT (pin mismatch) - premise failure, no verdict")
        cf.close()
        return

    ref_region = D["reset_region_wide"]
    fr_ref = H628.fr_count(off_ids, ref_region, rows_by_pid)
    ref_reach = H628.reach_all(S, ref_region)[0]
    log(f"reference (shipped): widened region, panel {wide_panel}/132, "
        f"reach_all {ref_reach}, fully-retrieved {fr_ref}/132")

    # ================= calibrated beta ======================================
    beta_cal = calibrate_beta(S, off_ids)
    log(f"calibrated beta (median uncapped nucleus size == {TOP_K}): {beta_cal}")
    chk("beta_calibration", {"beta_calibrated": beta_cal, "target_median_k": TOP_K,
                             "median_k_at_beta": median_kraw(S, off_ids, beta_cal)})

    beta_arms = sorted(set(list(BETAS) + list(BETAS_EXT) + [beta_cal]))
    escalated = set(pid for pid in off_ids if rru["base_b10"].get(pid) is False)

    def evaluate(name, seeds, extra):
        """Region + reach + paired flips for one seed map, on the shipped widened region."""
        region = {pid: H628.build_region(pid, seeds[pid], True, True, D) for pid in off_ids}
        ra, ra_num, ra_den = H628.reach_all(S, region)
        frc = H628.fr_count(off_ids, region, rows_by_pid)
        rec, _ = H628.carrier_recall(S, seeds)
        flips = H628.flip_sim(off_ids, region, ref_region, wide_pass, rows_by_pid)
        flips_in_gate = [p for p in flips["flip_pids"] if p in escalated]
        rec_out = {
            "carrier_recall_at_arm_k": rec,
            "probes_with_k_below_16": sum(1 for pid in off_ids if len(seeds[pid]) < TOP_K),
            "seeds_superset_of_dense16": all(dense_seeds[pid] <= seeds[pid] for pid in off_ids),
            "reach_all": ra, "reach_all_num": ra_num, "reach_all_den": ra_den,
            "fully_retrieved_132": frc,
            "median_region_nodes": int(np.median([len(region[pid]) for pid in off_ids])),
            "median_ref_region_nodes": int(np.median([len(ref_region[pid]) for pid in off_ids])),
            "flips_vs_shipped_widened_panel": flips,
            "panel_est": wide_panel + flips["net"],
            # H622 gate reported as a COST datum: its trigger reads the dense-first render,
            # which is not offline-simulable under changed seeds, so the recorded dense@16
            # trigger set is held fixed. Panel-neutral at budget 1.0 by H622's measured nesting.
            "h622_gate": {"trigger": "A (recorded dense-first render answers absent)",
                          "walk_invocations": len(escalated),
                          "walk_invocation_frac": round(len(escalated) / len(off_ids), 4),
                          "arm_flips_inside_gate": len(flips_in_gate),
                          "arm_flips_outside_gate": flips["flips_fail_to_pass"] - len(flips_in_gate)},
        }
        rec_out.update(extra)
        chk("arm", {"name": name, **{k: v for k, v in rec_out.items()
                                     if k != "flips_vs_shipped_widened_panel"},
                    "flips": flips})
        log(f"  {name:36s} rec={rec:.4f} reach={ra:.4f} fr={frc:3d} "
            f"flips +{flips['flips_fail_to_pass']}/-{flips['regressions_pass_to_fail']} "
            f"net={flips['net']:+d} panel={wide_panel + flips['net']}")
        return rec_out

    # ---- fixed-k controls: the confound the cap creates, measured not asserted ----
    controls = {}
    for k_fixed in (TOP_K, K_CAP):
        seeds_k = {}
        for pid in off_ids:
            sims = S["titan_n"] @ S["titan_probe_n"][pid]
            seeds_k[pid] = set(int(x) for x in np.argsort(-sims)[:k_fixed])
        controls[f"control|fixed dense@{k_fixed}"] = evaluate(
            f"control|fixed dense@{k_fixed}", seeds_k,
            {"kind": "fixed-k control", "k": k_fixed, "degenerate": None})

    # ---- nucleus arms --------------------------------------------------------
    arms = {}
    for beta in beta_arms:
        seeds, kraws, top16_masses, capped = {}, [], [], 0
        for pid in off_ids:
            sims = S["titan_n"] @ S["titan_probe_n"][pid]
            sd, k_raw, m16 = nucleus(sims, beta)
            seeds[pid] = sd
            kraws.append(k_raw)
            top16_masses.append(m16)
            if k_raw > K_CAP:
                capped += 1
        kraws = np.array(kraws)
        ks_used = np.array([len(seeds[pid]) for pid in off_ids])
        degenerate = capped == len(off_ids)     # cap binds everywhere => fixed dense@cap

        name = (f"nucleus|beta={beta}|mass={NUCLEUS_MASS}|cap={K_CAP}"
                + ("|DEGENERATE" if degenerate else ""))
        arms[name] = evaluate(name, seeds, {
            "kind": "nucleus", "beta": beta,
            "registered_sweep": beta in BETAS,
            "beta_is_calibrated": beta == beta_cal,
            "k_uncapped": {"median": int(np.median(kraws)), "min": int(kraws.min()),
                           "max": int(kraws.max()),
                           "p25": int(np.percentile(kraws, 25)),
                           "p75": int(np.percentile(kraws, 75))},
            "k_used": {"median": int(np.median(ks_used)), "min": int(ks_used.min()),
                       "max": int(ks_used.max())},
            "cap_binds_probes": capped, "cap_binds_frac": round(capped / len(off_ids), 4),
            "degenerate_equals_fixed_dense_at_cap": degenerate,
            "shipped_top16_softmax_mass_median": round(float(np.median(top16_masses)), 6),
            "shipped_top16_softmax_mass_min": round(float(np.min(top16_masses)), 6),
        })

    # ================= verdict against the registered bar ====================
    # A cap-degenerate arm is fixed dense@cap, NOT the registered adaptive-k mechanism, so it
    # cannot carry the verdict. The verdict is taken over the non-degenerate arms only.
    live = {n: a for n, a in arms.items() if not a["degenerate_equals_fixed_dense_at_cap"]}
    degen = {n: a for n, a in arms.items() if a["degenerate_equals_fixed_dense_at_cap"]}

    if not live:
        verdict = "PREMISE-FAILED"
        best_name, best_panel, best_net, best_regr = None, None, None, None
    else:
        best_name = max(live, key=lambda k: (live[k]["panel_est"],
                                             -live[k]["flips_vs_shipped_widened_panel"]
                                             ["regressions_pass_to_fail"]))
        best = live[best_name]
        best_panel = best["panel_est"]
        best_regr = best["flips_vs_shipped_widened_panel"]["regressions_pass_to_fail"]
        best_net = best["flips_vs_shipped_widened_panel"]["net"]
        if best_panel > WIDE_PANEL_PIN and best_regr == 0:
            verdict = "CONFIRMED"
        elif best_net <= 0:
            verdict = "KILLED"
        else:
            verdict = "INDETERMINATE"

    d64 = controls[f"control|fixed dense@{K_CAP}"]
    degen_attribution = {
        "degenerate_arms": sorted(degen),
        "degenerate_arm_nets": {n: a["flips_vs_shipped_widened_panel"]["net"] for n, a in degen.items()},
        "fixed_dense_at_cap_net": d64["flips_vs_shipped_widened_panel"]["net"],
        "identical_to_fixed_dense_at_cap": all(
            a["flips_vs_shipped_widened_panel"]["net"] == d64["flips_vs_shipped_widened_panel"]["net"]
            and a["fully_retrieved_132"] == d64["fully_retrieved_132"]
            for a in degen.values()),
        "reading": (f"Every arm in the registered beta sweep hits the k={K_CAP} cap on all "
                    f"{len(off_ids)} probes, so it selects exactly the top {K_CAP} by score - "
                    f"fixed dense@{K_CAP}, not adaptive-k. Any movement in those arms is "
                    f"attributable to k={K_CAP} vs k={TOP_K}, NOT to nucleus selection."),
    }

    summ = {
        "hypothesis": "R59-H659", "run_id": run_id, "git_head": git_head(),
        "utc_timestamp": run_id,
        "join_version": JOIN_VERSION, "region_rule": REGION_RULE,
        "registered_bar": ("CONFIRMED only on panel > 115/132 with ZERO pass-to-fail "
                           "regressions; KILLED at <= 0 net flips."),
        "verdict_recommendation": verdict,
        "substrate": ("medium 2wiki frozen H582 cache tmp/results/r47 (6,626 entities) + "
                      "R50 H597 span cache; FREE numpy/scipy/rapidfuzz, no GPU/LLM/Neo4j/net"),
        "substrate_caveat": ("frozen 6,626-entity cache (NOT the 7,575-entity live re-ingest); "
                             "matches the R57 atlas / H651 / H628 substrate for comparability"),
        "pins": pins,
        "shipped_pipeline": ("raw dense@16 seeds -> max-gap anchor reset -> H651 widened region "
                             "-> render_budget 1.0 -> H622 escalation gate (trigger A); this arm "
                             "replaces ONLY the seed source"),
        "reference": {"region": "reset_region_wide (H651)", "panel": wide_panel,
                      "panel_source": "recorded H620 rru_b10 pass map (112) + H651's 3 widened flips",
                      "reach_all": ref_reach, "fully_retrieved_132": fr_ref},
        "nucleus_rule": {"mass": NUCLEUS_MASS, "cap": K_CAP,
                         "betas_registered": list(BETAS), "betas_extension": list(BETAS_EXT),
                         "beta_calibrated": beta_cal,
                         "calibration": "median uncapped nucleus size == shipped k=16",
                         "extension_reason": ("the registered sweep is fully cap-degenerate and "
                                              "would otherwise price nothing")},
        "controls": controls,
        "arms": arms,
        "cap_degeneracy": degen_attribution,
        "best_non_degenerate_arm": {"name": best_name, "panel": best_panel,
                                    "net_flips": best_net, "regressions": best_regr},
        "verdict_rule": ("a cap-degenerate arm is fixed dense@cap, not the registered adaptive-k "
                         "mechanism, so it cannot carry the verdict; the verdict is taken over "
                         "the non-degenerate arms only"),
        "caveats": [
            "H540 discipline: at n=132 a 1-2 flip movement sits inside the band the registration's "
            "own V2 names (~+-8.5pp), so no single-flip result is a significance claim; exact "
            "counts and per-probe pid lists are given instead.",
            "Flip evaluation is the deterministic retrieval-level proxy of H651/H628: a flip is a "
            "reference FAIL whose gold carriers were not all inside the reference region and are "
            "all inside the arm region at render_budget 1.0. Not a live re-render.",
            "Nucleus seeds change the seed set, so pass-to-fail regressions ARE possible and are "
            "counted; where the arm's seed set is a superset of dense@16 the region is a superset "
            "and regressions are structurally impossible (flagged per arm).",
            "The H622 gate is reported as a COST datum only. Its trigger reads the dense-first "
            "render, which under nucleus seeds cannot be re-simulated offline, so the trigger set "
            "is held at the recorded dense@16 base_b10 failures (40 probes).",
            "carrier_recall_at_nucleus_k is NOT comparable head-to-head with the dense recall@16 "
            "pin when k > 16 - it is reported as a landing datum, never as a win.",
            "frozen 6,626-entity substrate, not the 7,575 live re-ingest.",
        ],
        "artifacts": {"json": str(OUT / f"h659-nucleus-seeding-{run_id}.json"),
                      "brief": str(OUT / f"h659-nucleus-seeding-{run_id}.md"),
                      "checkpoint": str(ckpt),
                      "script": "scripts/experiments/r59_h659_nucleus_seeding.py"},
    }
    (OUT / f"h659-nucleus-seeding-{run_id}.json").write_text(
        json.dumps(summ, indent=1, default=str))

    n_off = len(off_ids)
    rows = "\n".join(
        f"| {a['beta']}{' (registered)' if a['registered_sweep'] else ''}"
        f"{' (calibrated)' if a['beta_is_calibrated'] else ''} | "
        f"{a['k_uncapped']['median']} | {a['k_used']['median']} | "
        f"{a['cap_binds_probes']}/{n_off} | "
        f"{'YES' if a['degenerate_equals_fixed_dense_at_cap'] else 'no'} | "
        f"{a['shipped_top16_softmax_mass_median']:.4f} | "
        f"{a['carrier_recall_at_arm_k']:.4f} | {a['reach_all']:.4f} | "
        f"{a['fully_retrieved_132']} | +{a['flips_vs_shipped_widened_panel']['flips_fail_to_pass']}"
        f"/-{a['flips_vs_shipped_widened_panel']['regressions_pass_to_fail']} | "
        f"{a['flips_vs_shipped_widened_panel']['net']:+d} | {a['panel_est']} |"
        for a in arms.values())
    ctrl_rows = "\n".join(
        f"| {n.replace('|', ' / ')} | {a['carrier_recall_at_arm_k']:.4f} | {a['reach_all']:.4f} | "
        f"{a['fully_retrieved_132']} | +{a['flips_vs_shipped_widened_panel']['flips_fail_to_pass']}"
        f"/-{a['flips_vs_shipped_widened_panel']['regressions_pass_to_fail']} | "
        f"{a['flips_vs_shipped_widened_panel']['net']:+d} | {a['panel_est']} |"
        for n, a in controls.items())
    flip_lists = "\n".join(
        f"- {n}: +flips {a['flips_vs_shipped_widened_panel']['flip_pids']} | "
        f"-flips {a['flips_vs_shipped_widened_panel']['regression_pids']}"
        for n, a in list(controls.items()) + list(arms.items()))

    brief = f"""# R59-H659 adaptive-k nucleus seeding - brief

**Verdict recommendation: {verdict}** (run {run_id}, git {summ['git_head'][:12]},
join {JOIN_VERSION}, region rule: {REGION_RULE})

Registered bar: CONFIRMED only on panel **> 115/132** with **zero** pass-to-fail regressions;
KILLED at **<= 0 net flips**. Registered expecting the kill.

Mechanism: nucleus (top-p) selection over the dense scores at cumulative softmax mass
{NUCLEUS_MASS}, k capped at {K_CAP}, replacing fixed dense@16. Everything downstream is the
shipped pipeline unchanged: anchor-reset + H651 widened region + render_budget 1.0 + H622 gate.

## Pins (reproduced)
- dense@16 carrier recall **{base_recall}** (pin {BASE_RECALL_PIN})
- pooled (H627 alpha 0.6) recall **{pool_recall}** (pin {POOL_RECALL_PIN})
- reset_region reach_all **{reset_reach}** (pin {RESET_REACH_PIN})
- recorded panel base_b06/base_b10/rru_b10 = **{panel_counts['base_b06']}/{panel_counts['base_b10']}/{panel_counts['rru_b10']}** (pins 85/92/112)
- H651 widened panel **{wide_panel}/132** (pin {WIDE_PANEL_PIN})
- reference widened region: reach_all {ref_reach}, fully-retrieved {fr_ref}/132

## THE CAP DEGENERACY - read before any arm number
Every beta in the REGISTERED sweep ({list(BETAS)}) hits the k = {K_CAP} cap on all {n_off}
probes: the median UNCAPPED nucleus size at those betas runs to thousands of entities, so the
0.90 mass is never reached inside the cap and the rule selects exactly the top {K_CAP} by
score. Those arms are **fixed dense@{K_CAP}, not adaptive-k**, and are marked DEGENERATE.
Their movement is attributable to k = {K_CAP} vs k = {TOP_K}, never to nucleus selection -
measured, not asserted, by the explicit fixed-k controls below.
Identical to the fixed dense@{K_CAP} control: **{degen_attribution['identical_to_fixed_dense_at_cap']}**.

## Fixed-k controls
| control | recall@k | reach_all | fully-ret | flips +/- | net | panel |
|---|---|---|---|---|---|---|
{ctrl_rows}

## Arms (exact counts, paired against the 115-pass widened panel)
| beta | median k uncapped | median k used | cap binds | degenerate | median softmax mass in shipped top-16 | recall@arm-k | reach_all | fully-ret | flips +/- | net | panel |
|---|---|---|---|---|---|---|---|---|---|---|---|
{rows}

Calibrated beta = **{beta_cal}** (the beta whose median uncapped nucleus size equals the
shipped k = 16). Betas {list(BETAS_EXT)} are an EXTENSION beyond the registered sweep, added
because the registered sweep is fully degenerate and would otherwise price nothing.

## Per-probe flip lists
{flip_lists}

## Reading
- Best NON-DEGENERATE arm: **{best_name}**, panel **{best_panel}/132**, net **{best_net:+d}**,
  regressions **{best_regr}**
- The registered structural null: the bridge failure is a property of the EMBEDDING
  (dense hit-rate 0.26 on bridges vs 0.915 on first-hop). Widening or adapting k cannot
  reach an entity the embedding does not rank; a larger k only re-orders what it already ranks.

## Caveats
- H540 discipline: at n = 132 a 1-2 flip movement sits inside the band the registration's own
  V2 names (~+-8.5pp); no single-flip result here is a significance claim
- retrieval-level deterministic flip proxy (H651/H628 pattern), not a live re-render
- nucleus changes the seed set, so regressions are possible and counted; arms whose seeds are
  a superset of dense@16 have structurally impossible regressions (flagged per arm)
- the H622 gate is a cost datum only; its trigger reads the dense-first render, not
  offline-simulable under changed seeds, so the recorded 40-probe trigger set is held fixed
- recall@arm-k is not head-to-head comparable with recall@16 when k > 16
- frozen 6,626-entity substrate, not the 7,575 live re-ingest
"""
    (OUT / f"h659-nucleus-seeding-{run_id}.md").write_text(brief)
    cf.close()
    log(f"\nVERDICT {verdict} | best {best_name} panel {best_panel}/132 net {best_net:+d} "
        f"regressions {best_regr}")
    log(f"wrote {OUT}/h659-nucleus-seeding-{run_id}.json")


if __name__ == "__main__":
    main()

"""R58-H653 Gated second-round walk - the filter is the mechanism.

Mechanism: a heuristic missing-role gate. A probe whose round-1 region contains the
FIRST-HOP entity but NO candidate for the BRIDGE role triggers a round-2 reset PPR
seeded from round-1's top carriers (highest round-1 PPR-mass nodes). The gate reads
ROLE composition ONLY - never score shape (H646 fence). Heuristic gate, no LLM judge
in wave 1. Role labels per carrier come from the R57 atlas (reasoning_role).

Round-2 unions into the round-1 region, so retrieval regressions are structurally
impossible (superset); the drift KILL concerns render poisoning by the added nodes,
carried as a caveat since live render is not simulable offline.

Run on the BASELINE region rule (round-1 = reset_region_union, the recorded rru_b10
baseline, JUDGED) AND on the H651-widened rule (round-1 = reset_region_wide) so the
coordinator can judge composition.

FREE offline replay on the frozen 132. Reuses r58_h651 build().

Writes:
  reports/experiments/r58/h653-gated-round2-<ts>.json + .md
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry")
sys.path.insert(0, str(ROOT / "scripts/experiments"))

import r47_h582_embedder_swap as H          # noqa: E402
import r58_h651_region_cap as H651          # noqa: E402

OUT = ROOT / "reports/experiments/r58"
PPR_TOP_N = 15
ROUND2_TOP_CARRIERS = 5      # round-2 reset seeds = top-5 round-1 PPR-mass nodes
JOIN_VERSION = H651.JOIN_VERSION


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731
    ckpt = OUT / f"h653-gated-round2-{run_id}.checkpoint.jsonl"
    cf = ckpt.open("w")

    def chk(tag, obj):
        cf.write(json.dumps({"tag": tag, **obj}, default=str) + "\n")
        cf.flush()

    D = H651.build()
    S = D["S"]
    n = D["n"]
    adj, out_deg = D["adj"], D["out_deg"]
    off_ids = D["off_ids"]
    dense_seeds = D["dense_seeds"]
    anchors_maxgap = D["anchors_maxgap"]
    reset_region = D["reset_region"]
    reset_region_wide = D["reset_region_wide"]
    ppr_vec = D["ppr_vec"]
    atlas_rows = D["atlas_rows"]
    rru = D["rru_pass"]

    rows_by_pid = defaultdict(list)
    for r in atlas_rows:
        rows_by_pid[r["probe"]].append(r)

    # ---- per-probe gold role -> node sets (from atlas reasoning_role) ------
    first_hop_nodes = defaultdict(set)
    bridge_nodes = defaultdict(set)
    for r in atlas_rows:
        eff = r["eff_idx"]
        if eff is None:
            continue
        if r["reasoning_role"] == "first-hop":
            first_hop_nodes[r["probe"]].add(eff)
        elif r["reasoning_role"] == "bridge":
            bridge_nodes[r["probe"]].add(eff)

    def fully_retrieved(pid, region):
        rows = rows_by_pid[pid]
        if not rows:
            return False
        return all(r["eff_idx"] is not None and r["eff_idx"] in region for r in rows)

    # ---- round-2 region for a probe (reset from round-1 top carriers) -----
    def round2_region(pid, round1_region):
        r1 = ppr_vec[pid]
        # top carriers = highest round-1 PPR-mass nodes present in the round-1 region
        region_nodes = np.array(sorted(round1_region))
        if len(region_nodes) == 0:
            return round1_region
        masses = r1[region_nodes]
        top = region_nodes[np.argsort(-masses)[:ROUND2_TOP_CARRIERS]].tolist()
        r2 = H.ppr(adj, out_deg, top, n)
        top15 = set(np.argsort(-r2)[:PPR_TOP_N].tolist())
        return set(round1_region) | top15 | set(top)

    # ---- gate: first-hop present in region, bridge role slot empty --------
    def gate_fires(pid, round1_region):
        fh = first_hop_nodes.get(pid, set())
        br = bridge_nodes.get(pid, set())
        if not br:
            return False                       # no bridge slot -> gate cannot fire
        first_hop_present = bool(fh & round1_region)
        bridge_present = bool(br & round1_region)
        return first_hop_present and not bridge_present

    def run_variant(name, round1_of, recorded_arm):
        fired = []
        flips_pos = []
        flips_neg = []          # retrieval regressions (structurally impossible)
        bridge_recovered = []   # probes where round-2 pulled a missing bridge into region
        pass_map = rru.get(recorded_arm, {}) if recorded_arm else {}
        for pid in off_ids:
            r1 = round1_of[pid]
            if not gate_fires(pid, r1):
                continue
            fired.append(pid)
            r2 = round2_region(pid, r1)
            br = bridge_nodes.get(pid, set())
            if (br - r1) and (br & r2) == br:
                bridge_recovered.append(pid)
            # flip against recorded pass (only defined for the baseline variant)
            if recorded_arm:
                passed = pass_map.get(pid)
                if passed is False:
                    if not fully_retrieved(pid, r1) and fully_retrieved(pid, r2):
                        flips_pos.append(pid)
                elif passed is True:
                    if fully_retrieved(pid, r1) and not fully_retrieved(pid, r2):
                        flips_neg.append(pid)
        # retrieval-level flips (arm-agnostic): probes newly fully-retrieved by round-2
        retr_flips = [pid for pid in fired
                      if not fully_retrieved(pid, round1_of[pid])
                      and fully_retrieved(pid, round2_region(pid, round1_of[pid]))]
        res = {
            "variant": name, "recorded_arm": recorded_arm,
            "n_gate_fires": len(fired), "gate_fire_rate": round(len(fired) / len(off_ids), 4),
            "fired_pids": fired,
            "flips_fail_to_pass_recorded": len(flips_pos), "flip_pids": flips_pos,
            "regressions_pass_to_fail_recorded": len(flips_neg), "regression_pids": flips_neg,
            "retrieval_level_flips": len(retr_flips), "retrieval_flip_pids": retr_flips,
            "bridge_carriers_recovered": len(bridge_recovered),
            "bridge_recovered_pids": bridge_recovered,
        }
        chk(name, res)
        log(f"{name}: fires {len(fired)}/132 ({res['gate_fire_rate']}) | "
            f"flips(recorded) +{len(flips_pos)}/-{len(flips_neg)} | "
            f"retr-flips {len(retr_flips)} | bridge-recov {len(bridge_recovered)}")
        return res

    base = run_variant("baseline_region_rru_b10", reset_region, "rru_b10")
    wide = run_variant("h651_widened_region", reset_region_wide, None)

    # ---- verdict (judged on the BASELINE region variant) -------------------
    fire_rate = base["gate_fire_rate"]
    net_flips = base["flips_fail_to_pass_recorded"]
    regr = base["regressions_pass_to_fail_recorded"]
    if fire_rate <= 0.30 and net_flips >= 3 and regr == 0:
        verdict = "CONFIRMED"
    elif net_flips <= 1 or regr > 0:
        verdict = "KILLED"
    else:
        verdict = "INDETERMINATE"

    summ = {
        "hypothesis": "R58-H653", "run_id": run_id, "join_version": JOIN_VERSION,
        "substrate": ("medium 2wiki frozen H582 cache (6,626 entities); FREE numpy/scipy, "
                      "no GPU/LLM/Neo4j/net; reuses r58_h651 build()"),
        "substrate_caveat": "frozen 6,626-entity cache, not the 7,575 live re-ingest",
        "mechanism": ("gate = first-hop gold node in round-1 region AND no bridge gold node in "
                      "round-1 region (role composition only, H646 fence); round-2 = PPR reset from "
                      "top-5 round-1 PPR-mass region nodes, top15, unioned into round-1"),
        "gate_role_source": "R57 atlas reasoning_role per carrier (evidence-triple pivot classification)",
        "round2_top_carriers": ROUND2_TOP_CARRIERS,
        "baseline_region_variant_JUDGED": base,
        "h651_widened_region_variant": wide,
        "verdict_recommendation": verdict,
        "bar": ("CONFIRMED at gate fire <=30% AND >=3 net flips paired with zero regressions; "
                "KILLED at <=1 net flip OR any pass->fail drift regression"),
        "caveats": [
            "gate consults GOLD role labels (atlas reasoning_role) - a deployable gate would infer "
            "roles from the question (LLM, deferred to a later wave); this is a heuristic-gate "
            "feasibility probe, its OUTPUT (flips) is measured on the frozen 132, it does not train "
            "on outcomes (no R50/leakage violation).",
            "round-2 unions into round-1 => retrieval regressions structurally impossible; render "
            "drift (added nodes poisoning render at budget<1.0) is NOT simulable offline, carried as "
            "a caveat and the registered drift-KILL surface.",
            "flip proxy is retrieval-level (fully-retrieved => pass at budget 1.0); render-absent "
            "probes are a disjoint bucket unaffected by round-2.",
            "frozen 6,626-entity substrate, not the 7,575 live re-ingest.",
        ],
        "artifacts": {"json": str(OUT / f"h653-gated-round2-{run_id}.json"),
                      "brief": str(OUT / f"h653-gated-round2-{run_id}.md"),
                      "checkpoint": str(ckpt),
                      "script": "scripts/experiments/r58_h653_gated_round2.py"},
    }
    (OUT / f"h653-gated-round2-{run_id}.json").write_text(json.dumps(summ, indent=1, default=str))

    brief = f"""# R58-H653 gated second-round walk - brief

**Verdict recommendation: {verdict}**  (run {run_id}, join {JOIN_VERSION})

Gate (role composition only, H646 fence): first-hop gold node in round-1 region AND no
bridge gold node in round-1 region. Round-2 = PPR reset from top-{ROUND2_TOP_CARRIERS}
round-1 PPR-mass nodes, top15, unioned into round-1. Role labels from R57 atlas.

## Baseline region variant (round-1 = reset_region_union / rru_b10) - JUDGED
- **gate fires: {base['n_gate_fires']}/132 ({base['gate_fire_rate']})** (bar <=30%)
- **flips fail->pass (recorded rru_b10): +{base['flips_fail_to_pass_recorded']} / -{base['regressions_pass_to_fail_recorded']}** (bar >=3, zero regr)
- retrieval-level flips: {base['retrieval_level_flips']}
- bridge carriers recovered by round-2: {base['bridge_carriers_recovered']}
- flip pids: {base['flip_pids']}

## H651-widened region variant (round-1 = reset_region_wide)
- gate fires: {wide['n_gate_fires']}/132 ({wide['gate_fire_rate']})
- retrieval-level flips: {wide['retrieval_level_flips']}
- bridge carriers recovered by round-2: {wide['bridge_carriers_recovered']}

## Caveats
- gate consults gold role labels (heuristic feasibility probe; deployable gate infers roles via
  LLM, deferred). Does not train on outcomes (no leakage).
- round-2 unions => retrieval regressions impossible; render drift at budget<1.0 not simulable
  offline (the registered drift-KILL surface).
- frozen 6,626-entity substrate, not the 7,575 live re-ingest.
"""
    (OUT / f"h653-gated-round2-{run_id}.md").write_text(brief)
    cf.close()
    log(f"\nVERDICT {verdict} | fire {base['gate_fire_rate']} | "
        f"flips +{net_flips}/-{regr}")
    log(f"wrote {OUT}/h653-gated-round2-{run_id}.json")


if __name__ == "__main__":
    main()

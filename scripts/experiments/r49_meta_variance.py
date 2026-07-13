"""R49 meta-domain variance harvest: H539 freeze-probes, H540 bands+MDE,
H541 paired-gate mandate, H543 G-theory components.

All four replay existing logs - no LLM, no graph access.
- H539/H540/H543: reports/experiments/bench/progressive-probe-trajectory.jsonl,
  fixed-graph cycles = cycles at the modal ingested_titles value (1173).
  Frozen-manifest band estimated from within-question outcome variance
  (sqrt(mean within-question var / n)) because each cycle samples 15-of-162,
  so a literal frozen replay has no shared rows - deviation recorded in JSON.
- H541: r46-h499-screen-*.jsonl dual-arm files; paired SE from discordant
  pairs (McNemar b+c), unpaired SE from two-proportion formula.

Registered: docs/experiments/kgf-redesign-experiments.md R49-H539/H540/H541/H543.
Usage: python scripts/experiments/r49_meta_variance.py
Writes: reports/experiments/r49/meta-variance-<ts>.json
"""

import glob
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

TRAJ = Path("reports/experiments/bench/progressive-probe-trajectory.jsonl")
SCREENS = sorted(glob.glob("reports/experiments/bench/r46-h499-screen-*.jsonl"))
RNG = np.random.default_rng(42)


def load_traj():
    rows = [json.loads(x) for x in TRAJ.read_text().splitlines() if x.strip()]
    return [r for r in rows if "answer_in_context" in r]


def fixed_graph_cycles(rows):
    modal_titles = Counter(r["ingested_titles"] for r in rows).most_common(1)[0][0]
    fixed = [r for r in rows if r["ingested_titles"] == modal_titles]
    by_cycle = defaultdict(list)
    for r in fixed:
        by_cycle[r["cycle"]].append(r)
    return modal_titles, by_cycle


def h539_h540_h543(rows):
    modal_titles, by_cycle = fixed_graph_cycles(rows)
    cycle_rates = [np.mean([r["answer_in_context"] for r in v]) for v in by_cycle.values()]
    cycle_n = int(np.median([len(v) for v in by_cycle.values()]))
    resampled_sd = float(np.std(cycle_rates, ddof=1))

    # per-question outcome records at the fixed graph
    per_q = defaultdict(list)
    for v in by_cycle.values():
        for r in v:
            per_q[r["id"]].append(bool(r["answer_in_context"]))
    seen5 = {q: o for q, o in per_q.items() if len(o) >= 5}
    flips = [q for q, o in seen5.items() if 0 < sum(o) < len(o)]
    flip_share = len(flips) / len(seen5) if seen5 else float("nan")

    # frozen-manifest band: sqrt(mean within-question variance / manifest size)
    within_var = [np.var(o, ddof=0) for o in per_q.values() if len(o) >= 2]
    frozen_sd_15 = math.sqrt(np.mean(within_var) / cycle_n) if within_var else float("nan")

    p = float(np.mean(cycle_rates))
    q_means = np.array([np.mean(o) for o in per_q.values()])

    def analytic(n):
        return math.sqrt(p * (1 - p) / n)

    def bootstrap_sd(n, reps=4000):
        draws = RNG.choice(q_means, size=(reps, n), replace=True)
        # each drawn question contributes a Bernoulli realization of its own mean
        outc = RNG.random((reps, n)) < draws
        return float(np.std(outc.mean(axis=1), ddof=1))

    bands = []
    for n in (15, 25, 50, 100, 200):
        bands.append({
            "n": n,
            "analytic_sd": round(analytic(n), 4),
            "bootstrap_sd": round(bootstrap_sd(n), 4),
            "ci95_half_pp": round(1.96 * analytic(n) * 100, 1),
        })
    # MDE at 80% power, alpha .05 two-sided, unpaired two-proportion
    z = 1.96 + 0.8416
    mde = {str(n): round(z * math.sqrt(2 * p * (1 - p) / n), 3) for n in (15, 25, 50, 100, 200)}
    n_for_2pct = math.ceil((z ** 2) * 2 * p * (1 - p) / (0.02 ** 2))

    # H543 G-study (method-of-moments, unbalanced two-way, binary outcomes)
    grand = float(np.mean(np.concatenate([np.array(o, float) for o in per_q.values()])))
    var_total = grand * (1 - grand)
    var_q = max(0.0, float(np.var(q_means, ddof=1)) - np.mean(
        [np.mean(o) * (1 - np.mean(o)) / len(o) for o in per_q.values()]))
    cyc_effects = [np.mean([r["answer_in_context"] - np.mean(per_q[r["id"]]) for r in v])
                   for v in by_cycle.values()]
    var_run = max(0.0, float(np.var(cyc_effects, ddof=1)) - np.mean(
        [1 / len(v) for v in by_cycle.values()]) * np.mean(within_var))
    var_resid = max(0.0, var_total - var_q - var_run)
    comp_sum = var_q + var_run + var_resid

    def phi(n_q, n_r=1):
        denom = var_q + var_run / n_r + var_resid / (n_q * n_r)
        return var_q / denom if denom else float("nan")

    d_study = {str(nq): round(phi(nq), 3) for nq in (15, 30, 60, 120, 162)}

    return {
        "modal_titles": modal_titles,
        "n_fixed_cycles": len(by_cycle),
        "probes_per_cycle_median": cycle_n,
        "pooled_pass_rate": round(p, 4),
        "h539": {
            "resampled_sd_pp": round(resampled_sd * 100, 1),
            "frozen_manifest_sd_pp": round(frozen_sd_15 * 100, 1),
            "questions_seen_ge5": len(seen5),
            "flip_questions": len(flips),
            "flip_share": round(flip_share, 4),
            "bars": {"confirmed": "frozen sd <= 5pp AND flip <= 5%",
                     "killed": "frozen sd > 8pp OR flip > 10%"},
            "deviation": "frozen band estimated from within-question variance "
            "(cycles sample 15-of-pool, no literal shared manifest across cycles)",
        },
        "h540": {
            "bands": bands,
            "mde_80pct_power_unpaired": mde,
            "n_for_pm2pct_unpaired": n_for_2pct,
            "bars": {"confirmed": "empirical-analytic gap <= 5pp AND n-for-2% >= 1000",
                     "killed": "empirical exceeds binomial by > 5pp"},
        },
        "h543": {
            "var_question": round(var_q, 4),
            "var_run_instrument": round(var_run, 4),
            "var_residual": round(var_resid, 4),
            "share_question": round(var_q / comp_sum, 3) if comp_sum else None,
            "share_run": round(var_run / comp_sum, 3) if comp_sum else None,
            "share_residual": round(var_resid / comp_sum, 3) if comp_sum else None,
            "d_study_phi_by_frozen_manifest": d_study,
            "bars": {"confirmed": "query share >= 70% AND D-study n < naive binomial n",
                     "killed": "instrument share > 20%"},
            "deviation": "method-of-moments on unbalanced binary matrix, not gt4ireval ANOVA",
        },
    }


def h541():
    out = []
    for f in SCREENS:
        rows = [json.loads(x) for x in Path(f).read_text().splitlines() if x.strip()]
        arms = defaultdict(dict)
        for r in rows:
            arms[r["id"]][r["arm"]] = bool(r["pass"])
        pairs = [(v.get("off"), v.get("on")) for v in arms.values()
                 if "off" in v and "on" in v]
        if len(pairs) < 10:
            continue
        a = np.array([p[0] for p in pairs], float)
        b = np.array([p[1] for p in pairs], float)
        n = len(pairs)
        rho = float(np.corrcoef(a, b)[0, 1]) if a.std() and b.std() else 1.0
        disc = int(np.sum(a != b))
        se_unpaired = math.sqrt(a.mean() * (1 - a.mean()) / n + b.mean() * (1 - b.mean()) / n)
        se_paired = math.sqrt(max(disc, 1)) / n
        out.append({
            "file": Path(f).name, "n_pairs": n, "rho": round(rho, 4),
            "discordant": disc,
            "se_unpaired_pp": round(se_unpaired * 100, 2),
            "se_paired_pp": round(se_paired * 100, 2),
            "variance_reduction": round(1 - (se_paired / se_unpaired) ** 2, 4)
            if se_unpaired else None,
        })
    return {
        "screens": out,
        "median_rho": round(float(np.median([s["rho"] for s in out])), 4) if out else None,
        "median_var_reduction": round(float(np.median(
            [s["variance_reduction"] for s in out if s["variance_reduction"] is not None])), 4)
        if out else None,
        "bars": {"confirmed": "median rho >= 0.90 AND paired variance reduction >= 75%",
                 "killed": "median rho < 0.70"},
    }


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rows = load_traj()
    result = {"run_id": run_id, "traj_rows": len(rows),
              **h539_h540_h543(rows), "h541": h541()}
    outdir = Path("reports/experiments/r49")
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"meta-variance-{run_id}.json"
    path.write_text(json.dumps(result, indent=1))
    print("SUMMARY " + json.dumps(result))
    print(f"WROTE {path}", flush=True)


if __name__ == "__main__":
    main()

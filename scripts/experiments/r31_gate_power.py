"""R31-H351: are 2-run reproducibility bands underpowered at the measured sigma?

Pure replay over recorded reports - no GPU, no ingest, no graph read.

Question: R29's C4 clause (within-arm |d recall| <= 0.03 over 2 runs) failed on the
CONTROL arm (v1: 0.7917 vs 0.7292). Was that instability, or was the gate form itself
a coin flip at the engine's inherent run-to-run churn (DEF-11)?

Method:
  1. Pool config-identical run-mean recall@16 samples per stack family from the
     recorded reports; estimate the within-family run-mean sigma.
  2. Analytic + Monte Carlo false-fail rate of the 2-run |d| <= 0.03 band under a
     TRUE NULL (both runs same config) at that sigma.
  3. Per-probe empirical corroboration: the v2 family has 3 per-probe vectors;
     simulate runs by drawing each probe iid from its empirical value set.
  4. The replacement gate: CI-based difference test (Welch) - type-I is alpha by
     construction; report the POWER cost: minimum detectable arm difference at
     N=2..6 runs/arm, and the N needed to detect +0.03.

Registered bar (R31-H351): PASS if the 2-run false-fail rate >= 20% AND the CI gate
form's false-fail is <= half of it.

Usage: python scripts/experiments/r31_gate_power.py
"""

import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path

random.seed(31)

BAND_R = 0.03          # R29 C4 recall band
ALPHA = 0.05           # one-sided, replacement gate
POWER = 0.80
MC = 200_000

# Config-identical run-mean recall@16 samples (provenance: reports/*.json + R29 stats).
# v1 = shipped stack scratch ingests, same corpus/harness; v2 = candidate stack ditto.
FAMILIES = {
    "v1-scratch": {
        "reports/experiments/adjudicated/h241-v1-recall.json": 0.7708,
        "reports/experiments/adjudicated/r29-v1-run1-stats.json": 0.7917,
        "reports/experiments/adjudicated/r29-v1-run2-stats.json": None,  # read below
    },
    "v2-scratch": {
        "reports/experiments/adjudicated/h241-v2-recall.json": 0.7708,
        "reports/experiments/adjudicated/h212-v2-recall.json": 0.7500,
        "reports/experiments/adjudicated/h212-v2-recall-rerun.json": 0.7917,
        "reports/experiments/adjudicated/r29-v2-run1-stats.json": None,
    },
}

PER_PROBE_FAMILY = [  # v2 family vectors for the empirical corroboration
    "reports/experiments/adjudicated/h212-v2-recall.json",
    "reports/experiments/adjudicated/h212-v2-recall-rerun.json",
    "reports/experiments/adjudicated/h241-v2-recall.json",
]


def load_mean(path):
    d = json.loads(Path(path).read_text())
    return d["mean_recall"]


def sd(xs):
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def main():
    # 1. sigma per family, pooled
    fam_stats, pooled_num, pooled_den = {}, 0.0, 0
    for fam, files in FAMILIES.items():
        vals = [v if v is not None else load_mean(p) for p, v in files.items()]
        s = sd(vals)
        fam_stats[fam] = {"n": len(vals), "means": vals, "sd": round(s, 4)}
        pooled_num += (len(vals) - 1) * s * s
        pooled_den += len(vals) - 1
    sigma = math.sqrt(pooled_num / pooled_den)

    print("=" * 72)
    print("R31-H351 gate power analysis")
    print("=" * 72)
    for fam, st in fam_stats.items():
        print(f"  {fam}: n={st['n']} means={[f'{v:.4f}' for v in st['means']]} sd={st['sd']}")
    print(f"  pooled within-family run-mean sigma = {sigma:.4f}\n")

    # 2. true-null false-fail of the 2-run band: |d| ~ HalfNormal(sigma*sqrt(2))
    z = BAND_R / (sigma * math.sqrt(2.0))
    ff_analytic = 2.0 * (1.0 - phi(z))
    ff_mc = sum(
        abs(random.gauss(0, sigma) - random.gauss(0, sigma)) > BAND_R for _ in range(MC)
    ) / MC
    print(f"2-run band |dR| <= {BAND_R} at true null:")
    print(f"  analytic false-fail = {ff_analytic:.3f}   monte-carlo = {ff_mc:.3f}")

    # 3. per-probe empirical corroboration (v2 family, 3 config-identical-ish runs)
    vecs = []
    for p in PER_PROBE_FAMILY:
        d = json.loads(Path(p).read_text())
        pp = d["per_probe"]
        vecs.append([pp[k] for k in sorted(pp)])
    n_probes = len(vecs[0])
    per_probe_vals = [[v[i] for v in vecs] for i in range(n_probes)]

    def sim_run():
        return sum(random.choice(vals) for vals in per_probe_vals) / n_probes

    ff_emp = sum(abs(sim_run() - sim_run()) > BAND_R for _ in range(MC)) / MC
    sim_means = [sim_run() for _ in range(20000)]
    sigma_emp = sd(sim_means)
    print(f"  per-probe empirical (v2 family, {len(vecs)} runs, {n_probes} probes):")
    print(f"    simulated run-mean sigma = {sigma_emp:.4f}   empirical false-fail = {ff_emp:.3f}\n")

    # 4. replacement gate: Welch difference test, type-I = alpha by construction.
    #    Cost is power: minimum detectable difference (MDD) per N, and N for +0.03.
    za, zb = 1.6449, 0.8416  # alpha 0.05 one-sided, power 0.80
    mdd = {n: (za + zb) * sigma * math.sqrt(2.0 / n) for n in range(2, 7)}
    n_for_003 = math.ceil(2.0 * ((za + zb) * sigma / BAND_R) ** 2)
    print(f"replacement gate (one-sided Welch, alpha={ALPHA}, power={POWER}):")
    print(f"  type-I (false-fail on a true-null control) = {ALPHA:.3f} by construction")
    for n, d in mdd.items():
        print(f"  N={n}/arm -> minimum detectable recall difference = {d:.3f}")
    print(f"  runs/arm to detect +{BAND_R}: N = {n_for_003}\n")

    # verdict against the registered bar
    tworun_ff = ff_analytic
    ci_ff = ALPHA
    c_a = tworun_ff >= 0.20
    c_b = ci_ff <= tworun_ff / 2.0
    verdict = "PASS" if (c_a and c_b) else "FAIL"
    print("-" * 72)
    print(f"bar: 2-run false-fail >= 0.20 -> {tworun_ff:.3f} ({'PASS' if c_a else 'FAIL'})")
    print(f"bar: CI-form false-fail <= half of it -> {ci_ff:.3f} vs {tworun_ff/2:.3f} ({'PASS' if c_b else 'FAIL'})")
    print(f"R31-H351 VERDICT: {verdict}")
    print("  consequence: gates decide on N>=3 run means via one-sided difference CIs;")
    print("  a hard 2-run within-arm band is retired as a clause form. POWER CAVEAT:")
    print(f"  at sigma={sigma:.3f} a +0.03 effect needs ~{n_for_003} runs/arm - small-delta")
    print("  bars must lean on low-variance mechanism clauses (e.g. the never-extracted")
    print("  census), with recall means as supporting evidence.")

    out = {
        "hypothesis": "R31-H351",
        "generated": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "band_recall": BAND_R,
        "families": fam_stats,
        "pooled_sigma": round(sigma, 4),
        "two_run_false_fail_analytic": round(ff_analytic, 4),
        "two_run_false_fail_mc": round(ff_mc, 4),
        "empirical_sigma_v2family": round(sigma_emp, 4),
        "empirical_false_fail_v2family": round(ff_emp, 4),
        "ci_gate_type1": ALPHA,
        "min_detectable_diff_by_n": {str(n): round(d, 4) for n, d in mdd.items()},
        "runs_per_arm_to_detect_003": n_for_003,
        "verdict": verdict,
    }
    ts = out["generated"]
    path = Path(f"reports/experiments/adjudicated/r31-gate-power-{ts}.json")
    path.write_text(json.dumps(out, indent=2))
    print(f"\nwritten: {path}")


if __name__ == "__main__":
    main()

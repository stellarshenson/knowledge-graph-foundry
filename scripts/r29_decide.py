"""R29 SLOT-1 v2 identity-stack reopen: the decider.

Aggregates the four per-arm/run stats files written by scripts/r29_measure.py and
applies the PRE-REGISTERED R29-H340 decider VERBATIM (docs/experiments/
kgf-redesign-experiments.md line 3682; mirrored in scripts/r29_chain.sh header).
Supersedes the H241 false-merge-COUNT clause per GAP-1 (this is the NEW rate-normalized
decider registered as the reopen condition - NOT a post-hoc renegotiation).

Pre-registered acceptance bar (ALL four required, on 2-run means):
  C1 recall:    mean_recall(v2)    >= mean_recall(v1) - 0.02
  C2 precision: mean same_as_precision(v2) >= 0.50  AND  >= mean same_as_precision(v1)
  C3 rate:      mean false_merge_rate(v2)  <= mean false_merge_rate(v1)   [rate = false_merges/merges_total]
  C4 variance:  within EACH arm, |d recall(r1,r2)| <= 0.03 AND |d precision(r1,r2)| <= 0.10

GO  -> promote v2 to default (identity_stack: v2); the winning arm's two runs double as
       the Phase-3 reproducibility evidence.
NO-GO (any clause fails) -> v1 + demotion court stays the RC default; H241 stands, GAP-1
       remains open, DEF-10 closes as "raw overconfident, court is the effective repair".

The clauses are implemented as the registered pure-numeric tests - no extra veto is added
(discipline: the bar is not renegotiated at decision time). `same_as_edges == 0` is surfaced
as a NON-GATING note (an arm expressing identity via soft SIMILAR_TO links rather than hard
SAME_AS edges), never as a clause input.

Pure analysis over reports/r29-{v1,v2}-run{1,2}-stats.json - no GPU, no engine, no graph
write. Safe to run mid-chain: prints a PENDING preview until all four checkpoints exist.

Usage: python scripts/r29_decide.py
"""

import json
from pathlib import Path

ARMS = ("v1", "v2")
RUNS = ("1", "2")
REC_MARGIN = 0.02       # C1
PREC_BAR = 0.50         # C2 absolute floor
REC_REPRO = 0.03        # C4 recall band
PREC_REPRO = 0.10       # C4 precision band


def load():
    """Return {arm: {run: stats}} for whichever stats files exist."""
    data = {a: {} for a in ARMS}
    for a in ARMS:
        for r in RUNS:
            p = Path(f"reports/r29-{a}-run{r}-stats.json")
            if p.exists():
                data[a][r] = json.loads(p.read_text())
    return data


def arm_mean(runs, key):
    vals = [s[key] for s in runs.values()]
    return sum(vals) / len(vals)


def fmt(x, nd=4):
    return f"{x:.{nd}f}"


def mark(ok):
    return "PASS" if ok else "FAIL"


def main():
    data = load()
    n = sum(len(data[a]) for a in ARMS)

    print("=" * 74)
    print(f"R29 DECIDER  -  {n}/4 checkpoints present")
    print("=" * 74)

    hdr = f"{'arm/run':<8} {'recall':>8} {'precision':>10} {'rate':>8} {'SAME_AS':>8} {'SIMILAR':>8} {'ent':>6}"
    print(hdr)
    print("-" * len(hdr))
    for a in ARMS:
        for r in RUNS:
            if r not in data[a]:
                print(f"{a}/{r:<6} {'--':>8} {'--':>10} {'--':>8} {'--':>8} {'--':>8} {'--':>6}  (pending)")
                continue
            s = data[a][r]
            soft = "  [0 hard SAME_AS - identity via soft links]" if s.get("same_as_edges", 0) == 0 else ""
            print(
                f"{a}/{r:<6} {fmt(s['mean_recall']):>8} {fmt(s['same_as_precision'],3):>10} "
                f"{fmt(s['false_merge_rate']):>8} {s['same_as_edges']:>8} {s['similar_to_edges']:>8} "
                f"{s['entities']:>6}{soft}"
            )
    print()

    if n < 4:
        remaining = [f"{a}-run{r}" for a in ARMS for r in RUNS if r not in data[a]]
        print(f"PENDING - decider needs all four. Waiting on: {', '.join(remaining)}")
        return

    v1, v2 = data["v1"], data["v2"]
    v1_rec, v2_rec = arm_mean(v1, "mean_recall"), arm_mean(v2, "mean_recall")
    v1_prec, v2_prec = arm_mean(v1, "same_as_precision"), arm_mean(v2, "same_as_precision")
    v1_rate, v2_rate = arm_mean(v1, "false_merge_rate"), arm_mean(v2, "false_merge_rate")

    # C1-C4, registered pure-numeric tests
    c1 = v2_rec >= v1_rec - REC_MARGIN
    c2 = (v2_prec >= PREC_BAR) and (v2_prec >= v1_prec)
    c3 = v2_rate <= v1_rate

    def repro(arm):
        dr = abs(arm["1"]["mean_recall"] - arm["2"]["mean_recall"])
        dp = abs(arm["1"]["same_as_precision"] - arm["2"]["same_as_precision"])
        return (dr <= REC_REPRO and dp <= PREC_REPRO), dr, dp

    c4_v1, dr1, dp1 = repro(v1)
    c4_v2, dr2, dp2 = repro(v2)
    c4 = c4_v1 and c4_v2

    print("PRE-REGISTERED DECIDER (R29-H340), 2-run means")
    print("-" * 74)
    print(f"  C1 recall     v2 {fmt(v2_rec)}  >=  v1 {fmt(v1_rec)} - {REC_MARGIN} = {fmt(v1_rec - REC_MARGIN)}    -> {mark(c1)}")
    print(f"  C2 precision  v2 {fmt(v2_prec,3)}  >=  {PREC_BAR} floor  AND  >= v1 {fmt(v1_prec,3)}    -> {mark(c2)}")
    print(f"  C3 rate       v2 {fmt(v2_rate)}  <=  v1 {fmt(v1_rate)}    -> {mark(c3)}")
    print(f"  C4 variance   v1 dR {fmt(dr1)} dP {fmt(dp1)} ({mark(c4_v1)})  ;  v2 dR {fmt(dr2)} dP {fmt(dp2)} ({mark(c4_v2)})    -> {mark(c4)}")
    print("-" * 74)

    go = c1 and c2 and c3 and c4
    if go:
        print("VERDICT: GO  -  promote v2 identity stack to default (identity_stack: v2).")
        print("  Consequences: flip the shipped default to v2; the two v2 runs are the Phase-3")
        print("  reproducibility evidence; record the promotion; GAP-1 closes (reopen resolved).")
    else:
        failed = [name for name, ok in (("C1", c1), ("C2", c2), ("C3", c3), ("C4", c4)) if not ok]
        print(f"VERDICT: NO-GO  -  keep v1 + demotion court as the RC default. Failed: {', '.join(failed)}.")
        print("  Consequences: H241 stands, GAP-1 remains open, DEF-10 closes as")
        print("  'raw posteriors overconfident, the demotion court is the effective repair'.")
    print("=" * 74)


if __name__ == "__main__":
    main()

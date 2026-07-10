"""R38-H383: conformal risk control certificate on the H382 escalation ledger.

Verifies that the H382 fitted escalation threshold is the CRC solution at
alpha = 0.08 on the 24-outcome ledger, upgrading the fitted point to a
distribution-free finite-sample certificate E[miss] <= alpha (Angelopoulos
et al. 2022, arXiv 2208.02814 - archived).

Loss: L_i(theta) = 1{probe i not fully covered under the gated policy at
threshold theta}, where the gated policy escalates rung0 -> rung2 when the
top-seed signal < theta. Monotone in theta iff rung2 coverage is a superset
of rung0 coverage per probe (checked probe-by-probe).

Pure offline compute on reports/r37-h382-ladder-arm1-*.json. No GPU, no LLM.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

LEDGER = Path("reports/r37-h382-ladder-arm1-20260710T173529Z.json")
ALPHAS = [0.04, 0.08, 0.12]
TARGET_ALPHA = 0.08


def candidates(signals: dict) -> list[float]:
    """Candidate cuts: midpoints of sorted signal values + extremes (the
    same family as fit_threshold in r37_h382_ladder.py, for comparability)."""
    vals = sorted(signals.values())
    cands = [vals[0] - 0.01]
    cands += [round((a + b) / 2, 5) for a, b in zip(vals, vals[1:])]
    cands.append(vals[-1] + 0.01)
    return cands


def risk(theta: float, ids: list[str], signals: dict, r0: dict, r2: dict) -> float:
    """Empirical risk R_hat(theta): fraction of probes not fully covered
    under the gated policy (escalate to rung2 when signal < theta)."""
    misses = 0
    for p in ids:
        rec = r2[p] if signals[p] < theta else r0[p]
        misses += rec < 1.0
    return misses / len(ids)


def crc_fit(ids, signals, r0, r2, alpha):
    """theta_hat = inf{theta : (n/(n+1)) R_hat(theta) + 1/(n+1) <= alpha};
    infeasible -> lambda_max (always escalate), the graceful degradation."""
    n = len(ids)
    for theta in candidates({p: signals[p] for p in ids}):
        if (n / (n + 1)) * risk(theta, ids, signals, r0, r2) + 1 / (n + 1) <= alpha:
            return theta, False
    return max(signals[p] for p in ids) + 0.01, True  # lambda_max, infeasible


def main():
    rep = json.loads(LEDGER.read_text())
    signals, r0, r2 = rep["signals"], rep["rung_recall"]["rung0"], rep["rung_recall"]["rung2"]
    ids = sorted(signals)
    n = len(ids)

    # monotonicity premise: rung2 recall >= rung0 recall on every probe
    inversions = [p for p in ids if r2[p] < r0[p]]
    print(f"monotonicity: {len(inversions)} rung-inversions "
          f"{'(premise HOLDS)' if not inversions else inversions}", flush=True)

    # full-ledger CRC across the alpha sweep
    sweep = {}
    for alpha in ALPHAS:
        theta, infeasible = crc_fit(ids, signals, r0, r2, alpha)
        r = risk(theta, ids, signals, r0, r2)
        esc = sum(signals[p] < theta for p in ids)
        sweep[str(alpha)] = {"theta": theta, "infeasible": infeasible,
                             "empirical_risk": round(r, 4), "escalation_rate": round(esc / n, 4)}
        print(f"alpha={alpha}: theta_CRC={theta}{' (INFEASIBLE -> always-escalate)' if infeasible else ''} "
              f"R_hat={r:.4f} esc={esc}/{n}", flush=True)

    # comparison to the H382 fitted cuts
    fitted = {"fold_a": rep["folds"]["thr_fit_a"], "fold_b": rep["folds"]["thr_fit_b"]}
    theta_08 = sweep[str(TARGET_ALPHA)]["theta"]
    cands = candidates(signals)
    step = min(abs(cands[i + 1] - cands[i]) for i in range(len(cands) - 1)
               if cands[i] <= theta_08 <= cands[i + 1] or cands[i + 1] >= theta_08 >= cands[i])
    within = {k: abs(theta_08 - v) for k, v in fitted.items()}
    print(f"theta_CRC(0.08)={theta_08} vs fitted cuts {fitted} -> deltas {within}", flush=True)

    # out-of-fold check: CRC fit per fold, misses evaluated on the other fold
    folds = {"a": rep["folds"]["a"], "b": rep["folds"]["b"]}
    oof = {}
    total_miss = 0
    for fit_f, eval_f in (("a", "b"), ("b", "a")):
        theta, infeasible = crc_fit(folds[fit_f], signals, r0, r2, TARGET_ALPHA)
        miss = sum((r2[p] if signals[p] < theta else r0[p]) < 1.0 for p in folds[eval_f])
        total_miss += miss
        oof[fit_f] = {"theta": theta, "infeasible": infeasible,
                      "oof_misses": miss, "oof_n": len(folds[eval_f]),
                      "slack_B_over_n1": round(1 / (len(folds[fit_f]) + 1), 4)}
        print(f"fold {fit_f} fit: theta={theta}{' (INFEASIBLE -> always-escalate)' if infeasible else ''} "
              f"-> oof misses on fold {eval_f}: {miss}/{len(folds[eval_f])}", flush=True)
    pooled = total_miss / n
    print(f"pooled out-of-fold miss rate: {pooled:.4f} (bar: <= {TARGET_ALPHA})", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/r38-h383-crc-{ts}.json")
    out.write_text(json.dumps({
        "hypothesis": "R38-H383 CRC certificate on the H382 ledger",
        "generated": ts, "ledger": str(LEDGER), "n": n,
        "monotonicity_inversions": inversions,
        "crc_sweep": sweep, "fitted_cuts_h382": fitted,
        "target_alpha": TARGET_ALPHA, "oof": oof,
        "pooled_oof_miss_rate": round(pooled, 4),
        "unfixable_probes": [p for p in ids if r2[p] < 1.0],
    }, indent=2))
    print(f"\nH383 CRC COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

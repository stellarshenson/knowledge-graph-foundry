"""R38-H386: drift-triggered refit - does the certificate know when it expired?

Two-channel monitor per the literature brief (Podkopaev-Ramdas 2110.06177,
t-digest/KLL persistence):

- OUTCOME channel: level-delta sequential test of H0 "gated miss rate <=
  p0 = alpha + eps_tol" via a mixture likelihood-ratio supermartingale;
  Ville's inequality gives P(alarm EVER fires on a benign stream) <= delta.
  State = per-alternative log-LR sums, mergeable across ingestions by
  addition (the persistence-friendly form)
- SIGNAL channel (label-free): the stored class escalation rate at theta vs
  the new ingestion's - a distribution shift at the threshold quantile flags
  an embedder/register swap before any outcome label lands. At tens of
  values per replay raw arrays beat sketches (brief section 4); t-digest/KLL
  take over at production volumes

Streams are bootstrap replays of the H382 pinned ledger (24 probes) at the
certified cut theta = 0.7644: benign = resample as-is; harm A = embedder
swap (+0.05 signal shift - the gate goes dead, misses drift to the
never-escalate rate 0.125); harm B = corpus register change (rung-0
coverage degrades, misses ~0.29). Registered budget: alarm within <= 2
replay batches on harm, zero alarms across >= 3 benign re-ingestions.
"""

import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path

LEDGER = Path("reports/experiments/adjudicated/r37-h382-ladder-arm1-20260710T173529Z.json")
THETA = 0.7644  # H383 certified cut
ALPHA = 0.08  # certified miss budget
EPS_TOL = 0.02  # harmful = miss rate above alpha + eps_tol (p0 = 0.10); sits
# below the dead-gate breach (never-escalate = 3/24 = 0.125) by construction
DELTA = 0.05  # ever-false-alarm budget
ALTERNATIVES = (0.15, 0.2, 0.3, 0.5)  # mixture experts
BATCH = 24  # one replay = one ingestion's labels
SEEDS = 500


class MixtureLRMonitor:
    """H0: miss rate <= p0. Mixture of Bernoulli likelihood-ratio
    supermartingales (each valid for the composite null since the LR factor
    has expectation <= 1 for every p <= p0); alarm when the mixture reaches
    1/delta (Ville). log_m is the mergeable per-ingestion state."""

    def __init__(self, p0: float, delta: float):
        self.p0, self.delta = p0, delta
        self.log_m = {p1: 0.0 for p1 in ALTERNATIVES}

    def update(self, miss: bool) -> bool:
        for p1 in self.log_m:
            self.log_m[p1] += (
                math.log(p1 / self.p0) if miss else math.log((1 - p1) / (1 - self.p0))
            )
        mix = sum(math.exp(v) for v in self.log_m.values()) / len(self.log_m)
        return mix >= 1 / self.delta


def gated_miss(row: dict, theta: float, shift: float = 0.0, degrade: float = 0.0,
               rng: random.Random = None) -> tuple[bool, bool]:
    """(miss, escalated) for one probe draw under the gated policy. ``shift``
    moves the signal (embedder swap); ``degrade`` is the probability an
    otherwise rung-0-covered draw is uncovered (register change)."""
    sig = row["signal"] + shift
    escalated = sig < theta
    covered = row["rung2_covered"] if escalated else row["rung0_covered"]
    if degrade and covered and not escalated and rng.random() < degrade:
        covered = False
    return (not covered), escalated


def run_stream(ledger, seed, batches, shift=0.0, degrade=0.0):
    """One monitored deployment: returns (alarm_batch or None, sketch_flag_batch
    or None). Sketch check: cumulative escalation rate vs the stored class
    rate with a 3-sigma binomial band."""
    rng = random.Random(seed)
    monitor = MixtureLRMonitor(ALPHA + EPS_TOL, DELTA)
    stored_rate = sum(r["signal"] < THETA for r in ledger) / len(ledger)
    esc_n, n = 0, 0
    alarm_at, sketch_at = None, None
    for b in range(1, batches + 1):
        for _ in range(BATCH):
            row = rng.choice(ledger)
            miss, escalated = gated_miss(row, THETA, shift, degrade, rng)
            esc_n += escalated
            n += 1
            if alarm_at is None and monitor.update(miss):
                alarm_at = b
        band = 3 * math.sqrt(stored_rate * (1 - stored_rate) / n)
        if sketch_at is None and abs(esc_n / n - stored_rate) > band:
            sketch_at = b
    return alarm_at, sketch_at


def main():
    rep = json.loads(LEDGER.read_text())
    signals, r0, r2 = rep["signals"], rep["rung_recall"]["rung0"], rep["rung_recall"]["rung2"]
    ledger = [
        {"signal": signals[p], "rung0_covered": r0[p] >= 1.0, "rung2_covered": r2[p] >= 1.0}
        for p in sorted(signals)
    ]

    cases = {
        "benign": dict(shift=0.0, degrade=0.0),
        "harm_A_embedder_swap": dict(shift=0.05, degrade=0.0),
        "harm_B_register_change": dict(shift=0.0, degrade=4 / 21),
    }
    results = {}
    for name, kw in cases.items():
        alarms, sketches = [], []
        for seed in range(SEEDS):
            a, s = run_stream(ledger, seed, batches=5, **kw)
            alarms.append(a)
            sketches.append(s)
        fired = [a for a in alarms if a is not None]
        flagged = [s for s in sketches if s is not None]
        results[name] = {
            "outcome_alarm_rate": len(fired) / SEEDS,
            "outcome_alarm_within_2": sum(a <= 2 for a in fired) / SEEDS,
            "outcome_median_batch": sorted(fired)[len(fired) // 2] if fired else None,
            "sketch_flag_rate": len(flagged) / SEEDS,
            "sketch_flag_within_2": sum(s <= 2 for s in flagged) / SEEDS,
            "sketch_median_batch": sorted(flagged)[len(flagged) // 2] if flagged else None,
        }
        r = results[name]
        print(f"{name}: outcome alarms {r['outcome_alarm_rate']:.3f} "
              f"(<=2 batches {r['outcome_alarm_within_2']:.3f}, median {r['outcome_median_batch']}); "
              f"sketch flags {r['sketch_flag_rate']:.3f} "
              f"(<=2 batches {r['sketch_flag_within_2']:.3f}, median {r['sketch_median_batch']})",
              flush=True)

    # the registered benign clause: zero alarms across >= 3 re-ingestions (seed 0)
    a, s = run_stream(ledger, seed=0, batches=3)
    print(f"benign 3-ingestion run: outcome alarm={a}, sketch flag={s}", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/experiments/adjudicated/r38-h386-monitor-{ts}.json")
    out.write_text(json.dumps({
        "hypothesis": "R38-H386 drift-triggered refit (two-channel monitor, offline)",
        "generated": ts, "ledger": str(LEDGER), "theta": THETA,
        "alpha": ALPHA, "eps_tol": EPS_TOL, "delta": DELTA,
        "alternatives": ALTERNATIVES, "batch": BATCH, "seeds": SEEDS,
        "cases": results,
        "benign_3_ingestions": {"outcome_alarm": a, "sketch_flag": s},
    }, indent=2))
    print(f"\nH386 MONITOR ARM COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

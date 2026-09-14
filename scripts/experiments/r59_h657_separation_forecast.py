"""R59-H657 - separation-certificate scale forecast (FREE INSTRUMENT, no pass/fail).

Registered bar (experiments log, R59): INSTRUMENT - no pass/fail. The deliverable is
the empirical `Delta` percentile curve over the entity prototype bank plus the
below-certificate fraction at the current N and at the projected large rung, with the
LOWER-BOUND caveat stated explicitly. The arm fails ONLY if `Delta` cannot be computed
over the existing embedding dump.

Mechanism (grounding section E4 of reports/experiments/r59/hopfield-grounding-*.md):
Ramsauer Theorem 5 inverted gives a pattern-distribution-free retrieval certificate
that depends only on observables:

    Delta_required(N, eps) = (1/beta) * ln( 2 (N-1) M / eps )

with M = max l2 norm of a stored pattern (= 1 after l2-normalisation) and eps the target
retrieval error (0.01 here). The observable on l2-normalised vectors is

    Delta_i = 1 - cos(i, nearest OTHER prototype)

Scaling the stored count by r raises the requirement by exactly (1/beta) ln r. Medium ->
large rung ratio r = 46, so the requirement rises by ln(46)/beta = 3.829/beta.

LOWER BOUND ON THE DAMAGE - stated as the round registered it: the forecast holds the
SHAPE of the Delta distribution fixed under scaling. New documents add near-duplicate
entities, which pushes the left tail DOWN faster than log N pushes the requirement UP.
The projected below-certificate fraction is therefore a floor, not a prediction.

Substrate: frozen H582 entity embedding bank tmp/results/r47/titan_emb.npy
(6,626 x 1024 Titan vectors) - the same bank the shipped dense seeder scores against.
FREE numpy. NO GPU, NO LLM, NO Neo4j, NO network, NO writes outside reports/.

Sanity pin: dense@16 carrier recall 0.6012 (H582/H627), recomputed from this bank so a
swapped or corrupted dump aborts the arm before any certificate is reported.

Writes:
  reports/experiments/r59/h657-separation-forecast-<ts>.json
  reports/experiments/r59/h657-separation-forecast-<ts>.md    (brief)
  reports/experiments/r59/h657-separation-forecast-<ts>.checkpoint.jsonl
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry")
sys.path.insert(0, str(ROOT / "scripts/experiments"))

import r50_h619_seedland_digs as R50     # noqa: E402  (load_substrate)

CACHE = ROOT / "tmp/results/r47"
OUT = ROOT / "reports/experiments/r59"

EPS = 0.01
BETAS = (1, 2, 4, 8, 16)                    # the registered sweep
# Extension beyond the registered sweep. Reason recorded rather than assumed: the registered
# sweep saturates - 100% of prototypes sit below the certificate at every beta up to 16, both
# now and at the projected rung - so it prices neither H658 nor H663. The extension locates
# the beta range where the certificate becomes discriminative at all.
BETAS_EXT = (24, 32, 48, 64, 96, 128)
RUNG_RATIO = 46            # medium (1,000 docs) -> large (6,118 docs) entity-count ratio
PCTILES = (1, 5, 10, 25, 50, 75, 90)
BASE_RECALL_PIN = 0.6012

JOIN_VERSION = "goldjoin-v3-typegate-20260724 (eff = v2 then v3 fall-through, R57 atlas rows)"
REGION_RULE = "H651 widened (seeds u anchors u full 1-hop shell u PPR-top15) - not exercised by this arm"


def git_head():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


def carrier_recall(S, seeds_by_pid):
    """dense@16 r0 carrier recall over ALL carriers (H627 convention) - the pin."""
    name_norms = S["name_norms"]
    hits = []
    for c in S["carriers"]:
        seed_norms = {name_norms[i] for i in seeds_by_pid[c["probe"]]}
        hits.append(1 if c["tnorm"] in seed_norms else 0)
    return round(float(np.mean(hits)), 4)


def nearest_other_cos(X, block=512):
    """max_j!=i cos(x_i, x_j) over l2-normalised rows, blocked to bound memory."""
    n = X.shape[0]
    best = np.full(n, -np.inf, dtype=np.float64)
    arg = np.full(n, -1, dtype=np.int64)
    for s in range(0, n, block):
        e = min(s + block, n)
        sims = (X[s:e] @ X.T).astype(np.float64)
        for r in range(e - s):
            sims[r, s + r] = -np.inf
        j = np.argmax(sims, axis=1)
        best[s:e] = sims[np.arange(e - s), j]
        arg[s:e] = j
    return best, arg


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731
    ckpt = OUT / f"h657-separation-forecast-{run_id}.checkpoint.jsonl"
    cf = ckpt.open("w")

    def chk(tag, obj):
        cf.write(json.dumps({"tag": tag, **obj}, default=str) + "\n")
        cf.flush()

    # ---------------- substrate + pin ---------------------------------------
    S = R50.load_substrate()
    dense_seeds = {pid: set(S["seeds_q"][pid]) for pid in S["off_ids"]}
    base_recall = carrier_recall(S, dense_seeds)
    pin_ok = abs(base_recall - BASE_RECALL_PIN) < 0.01
    pins = {"dense16_carrier_recall": base_recall, "pin": BASE_RECALL_PIN, "ok": pin_ok}
    log(f"PIN dense@16 carrier recall = {base_recall} (pin {BASE_RECALL_PIN}) ok={pin_ok}")
    chk("pins", pins)
    if not pin_ok:
        (OUT / f"h657-separation-forecast-{run_id}.json").write_text(json.dumps(
            {"hypothesis": "R59-H657", "run_id": run_id,
             "ABORTED_PIN_MISMATCH": True, "pins": pins}, indent=1))
        log("ABORT (pin mismatch) - premise failure, no certificate reported")
        cf.close()
        return

    # ---------------- the prototype bank ------------------------------------
    raw = np.load(CACHE / "titan_emb.npy").astype(np.float64)
    n, d = raw.shape
    norms = np.linalg.norm(raw, axis=1)
    zero_rows = int((norms < 1e-12).sum())
    X = raw / (norms[:, None] + 1e-12)
    M = float(np.linalg.norm(X, axis=1).max())     # = 1.0 after normalisation
    log(f"bank: N={n} d={d} zero_norm_rows={zero_rows} M(after l2)={M:.6f}")
    chk("bank", {"N": n, "dim": d, "zero_norm_rows": zero_rows, "M": M,
                 "raw_norm_min": float(norms.min()), "raw_norm_max": float(norms.max())})

    # ---------------- Delta_i = 1 - cos(i, nearest OTHER prototype) ----------
    best_cos, arg = nearest_other_cos(X)
    delta = 1.0 - best_cos
    meta = S["meta"]

    pct = {f"p{p}": round(float(np.percentile(delta, p)), 6) for p in PCTILES}
    stats = {"min": round(float(delta.min()), 6), "max": round(float(delta.max()), 6),
             "mean": round(float(delta.mean()), 6), "std": round(float(delta.std()), 6),
             "exact_duplicates_delta_lt_1e-6": int((delta < 1e-6).sum()),
             "delta_lt_0.01": int((delta < 0.01).sum()),
             "delta_lt_0.05": int((delta < 0.05).sum()),
             "delta_lt_0.10": int((delta < 0.10).sum())}
    log("Delta percentiles: " + "  ".join(f"{k}={v:.4f}" for k, v in pct.items()))
    log(f"Delta min={stats['min']:.6f} median={pct['p50']:.4f} max={stats['max']:.4f}")
    chk("delta_distribution", {"percentiles": pct, "stats": stats})

    left_tail = [int(i) for i in np.argsort(delta)[:15]]
    tail_rows = [{"idx": i, "name": meta[i]["name"], "delta": round(float(delta[i]), 6),
                  "nearest_idx": int(arg[i]), "nearest_name": meta[int(arg[i])]["name"]}
                 for i in left_tail]
    chk("left_tail", {"rows": tail_rows})

    # ---------------- the certificate ---------------------------------------
    N_now = n
    N_large = RUNG_RATIO * n
    rise = float(np.log(RUNG_RATIO))               # ln(46) = 3.8286, divided by beta

    def required(N, beta):
        return float(np.log(2.0 * (N - 1) * M / EPS) / beta)

    cert = {}
    for beta in list(BETAS) + list(BETAS_EXT):
        r_now = required(N_now, beta)
        r_lg = required(N_large, beta)
        below_now = int((delta < r_now).sum())
        below_lg = int((delta < r_lg).sum())
        cert[str(beta)] = {
            "beta": beta,
            "registered_sweep": beta in BETAS,
            "delta_required_now": round(r_now, 6),
            "delta_required_large": round(r_lg, 6),
            "requirement_rise": round(r_lg - r_now, 6),
            "below_certificate_now_count": below_now,
            "below_certificate_now_frac": round(below_now / n, 6),
            "below_certificate_large_count": below_lg,
            "below_certificate_large_frac": round(below_lg / n, 6),
            "newly_below_at_large": below_lg - below_now,
        }
        log(f"beta={beta:2d}  req_now={r_now:8.4f} below {below_now:5d}/{n} "
            f"({100*below_now/n:6.2f}%)  |  req_large={r_lg:8.4f} below {below_lg:5d}/{n} "
            f"({100*below_lg/n:6.2f}%)")
        chk("certificate", cert[str(beta)])

    # beta at which ANY prototype clears the certificate (delta_max >= req)
    dmax = float(delta.max())
    beta_any_now = round(float(np.log(2.0 * (N_now - 1) * M / EPS) / dmax), 4)
    beta_any_large = round(float(np.log(2.0 * (N_large - 1) * M / EPS) / dmax), 4)
    # beta at which the MEDIAN prototype clears
    dmed = float(np.percentile(delta, 50))
    beta_med_now = round(float(np.log(2.0 * (N_now - 1) * M / EPS) / dmed), 4)
    beta_med_large = round(float(np.log(2.0 * (N_large - 1) * M / EPS) / dmed), 4)
    thresholds = {"beta_for_best_prototype_now": beta_any_now,
                  "beta_for_best_prototype_large": beta_any_large,
                  "beta_for_median_prototype_now": beta_med_now,
                  "beta_for_median_prototype_large": beta_med_large}
    log(f"beta needed for the BEST prototype to clear: now {beta_any_now}, large {beta_any_large}")
    log(f"beta needed for the MEDIAN prototype to clear: now {beta_med_now}, large {beta_med_large}")
    chk("beta_thresholds", thresholds)

    # ---------------- the registered prediction, read off the curve ----------
    # Registered: "under 1% means identity is scale-safe on this axis, over 10% means the
    # large rung needs a separation intervention before ingest".
    ordered = sorted(cert.values(), key=lambda c: c["beta"])
    b10 = next((c["beta"] for c in ordered if c["below_certificate_large_frac"] < 0.10), None)
    b01 = next((c["beta"] for c in ordered if c["below_certificate_large_frac"] < 0.01), None)
    reading = {
        "rule": ("registered: < 1% projected below-certificate = scale-safe on this axis; "
                 "> 10% = the large rung needs a separation intervention before ingest"),
        "lowest_beta_with_projected_below_10pct": b10,
        "lowest_beta_with_projected_below_1pct": b01,
        "registered_sweep_verdict": ("every beta in the registered sweep {1,2,4,8,16} reads "
                                     "100% below-certificate at BOTH N and 46N - saturated, so "
                                     "the registered sweep alone prices nothing"),
        "verdict_on_the_rule": (
            f"the projected fraction stays above 10% for every beta up to "
            f"{(b10 // 1) if b10 else 'any tested'}"
            + (f", first dropping under 10% at beta = {b10}" if b10 else "")
            + (f" and under 1% at beta = {b01}" if b01 else
               "; it never drops under 1% at any tested beta, so identity is NOT scale-safe "
               "on this axis at any beta this bank supports")),
    }
    log(f"registered reading: projected <10% first at beta={b10}, <1% at beta={b01}")
    chk("registered_prediction_reading", reading)

    # ---------------- artifact ----------------------------------------------
    summ = {
        "hypothesis": "R59-H657", "run_id": run_id,
        "registered_bar": ("INSTRUMENT - no pass/fail. Deliverable = Delta percentile curve + "
                           "below-certificate fractions at current and projected N, labelled a "
                           "LOWER BOUND. Fails only if Delta cannot be computed."),
        "verdict_recommendation": "INSTRUMENT-DELIVERED",
        "git_head": git_head(),
        "join_version": JOIN_VERSION,
        "region_rule": REGION_RULE,
        "utc_timestamp": run_id,
        "substrate": ("frozen H582 entity prototype bank tmp/results/r47/titan_emb.npy "
                      f"({n} x {d} Titan vectors), l2-normalised; FREE numpy, "
                      "no GPU/LLM/Neo4j/net"),
        "substrate_caveat": ("frozen 6,626-entity cache (NOT the 7,575-entity live re-ingest); "
                             "matches the R57 atlas / H651 / H628 substrate for comparability"),
        "pins": pins,
        "bank": {"N": n, "dim": d, "M_max_l2_norm_after_normalisation": M,
                 "zero_norm_rows": zero_rows},
        "formula": ("Delta_required(N, eps) = (1/beta) ln(2 (N-1) M / eps); "
                    f"eps={EPS}, M={M}; observable Delta_i = 1 - cos(i, nearest OTHER prototype)"),
        "beta_sweep": {"registered": list(BETAS), "extension": list(BETAS_EXT),
                       "extension_reason": ("the registered sweep saturates at 100% "
                                            "below-certificate everywhere and prices neither "
                                            "H658 nor H663; the extension locates the beta "
                                            "range where the certificate discriminates")},
        "rung_projection": {"ratio_r": RUNG_RATIO, "N_now": N_now, "N_large": N_large,
                            "requirement_rise_ln_r": round(rise, 6),
                            "note": "requirement rises by ln(46)/beta = "
                                    f"{round(rise, 4)}/beta, independent of the data"},
        "delta_percentiles": pct,
        "delta_stats": stats,
        "delta_left_tail_15": tail_rows,
        "certificate_by_beta": cert,
        "beta_thresholds": thresholds,
        "registered_prediction_reading": reading,
        "LOWER_BOUND_LABEL": (
            "EVERY below-certificate fraction reported here is a LOWER BOUND ON THE DAMAGE, "
            "not a prediction. The projection holds the SHAPE of the Delta distribution fixed "
            "and shifts only the requirement by ln(r)/beta. New documents add near-duplicate "
            "entities, which pushes the left tail DOWN faster than log N pushes the requirement "
            "UP, so the true large-rung below-certificate fraction is at least this large."),
        "caveats": [
            "The capacity theorems (N >= sqrt(p) c^((d-1)/4), 2^(d/2)) assume randomly chosen "
            "patterns and do NOT transfer to correlated text embeddings; only the Theorem-5 "
            "certificate is used here because it depends solely on observables.",
            "Delta_i is one minus the runner-up cosine - the certificate adds margin-awareness "
            "and N-awareness, not an independent quantity (the H658 honest reduction).",
            "The bank is entity prototypes as embedded by the shipped indexer "
            "('{type}: {name} - {description[:200]}'), so Delta mixes name and description "
            "separation; it is not a name-identity statistic.",
            "frozen 6,626-entity substrate, not the 7,575 live re-ingest.",
        ],
        "artifacts": {"json": str(OUT / f"h657-separation-forecast-{run_id}.json"),
                      "brief": str(OUT / f"h657-separation-forecast-{run_id}.md"),
                      "checkpoint": str(ckpt),
                      "script": "scripts/experiments/r59_h657_separation_forecast.py"},
    }
    (OUT / f"h657-separation-forecast-{run_id}.json").write_text(
        json.dumps(summ, indent=1, default=str))

    pct_row = " | ".join(f"{v:.4f}" for v in pct.values())
    cert_rows = "\n".join(
        f"| {c['beta']}{'' if c['registered_sweep'] else ' (ext)'} | {c['delta_required_now']:.4f} | "
        f"{c['below_certificate_now_count']}/{n} ({100*c['below_certificate_now_frac']:.2f}%) | "
        f"{c['delta_required_large']:.4f} | "
        f"{c['below_certificate_large_count']}/{n} ({100*c['below_certificate_large_frac']:.2f}%) | "
        f"{c['newly_below_at_large']} |"
        for c in cert.values())
    tail_md = "\n".join(
        f"| {r['delta']:.6f} | {r['name']} | {r['nearest_name']} |" for r in tail_rows[:10])

    brief = f"""# R59-H657 separation-certificate scale forecast - brief

**INSTRUMENT-DELIVERED** (no pass/fail). Run {run_id}, git {summ['git_head'][:12]},
join {JOIN_VERSION}, region rule: {REGION_RULE}.

Certificate: `Delta_required(N, eps) = (1/beta) ln(2 (N-1) M / eps)`, `eps = {EPS}`,
`M = {M:.4f}` (l2-normalised bank). Observable: `Delta_i = 1 - cos(i, nearest OTHER prototype)`
over the frozen {n}-entity prototype bank (dim {d}).

## Pin
- dense@16 carrier recall recomputed from this bank: **{base_recall}** (pin {BASE_RECALL_PIN}) - held

## Delta percentile curve (exact)
| p1 | p5 | p10 | p25 | p50 | p75 | p90 |
|---|---|---|---|---|---|---|
| {pct_row} |

- min **{stats['min']:.6f}**, max **{stats['max']:.4f}**, mean {stats['mean']:.4f}, sd {stats['std']:.4f}
- prototypes with `Delta < 1e-6` (embedding-exact duplicates): **{stats['exact_duplicates_delta_lt_1e-6']}**
- `Delta < 0.01`: **{stats['delta_lt_0.01']}**; `< 0.05`: **{stats['delta_lt_0.05']}**;
  `< 0.10`: **{stats['delta_lt_0.10']}** of {n}

## Certificate - fraction BELOW at current N and at N' = 46 N
Current N = {N_now}; projected N' = {N_large}. The requirement rises by
`ln(46)/beta = {rise:.4f}/beta`, independent of the data.

Betas {list(BETAS)} are the registered sweep; rows marked `(ext)` are an extension added
because the registered sweep saturates at 100% below-certificate everywhere and would
otherwise price neither H658 nor H663.

| beta | required now | below now | required at 46N | below at 46N | newly below |
|---|---|---|---|---|---|
{cert_rows}

- beta needed for the BEST-separated prototype to clear: **{beta_any_now}** now,
  **{beta_any_large}** at the large rung
- beta needed for the MEDIAN prototype to clear: **{beta_med_now}** now,
  **{beta_med_large}** at the large rung

## Reading against the registered prediction
Registered: under 1% projected below-certificate means identity is scale-safe on this axis;
over 10% means the large rung needs a separation intervention before ingest.

- the whole registered sweep {list(BETAS)} reads **100% below-certificate at both N and 46N** -
  saturated, so the registered sweep alone prices nothing, which is why the extension exists
- projected fraction first drops under **10%** at beta = **{b10}**
- projected fraction first drops under **1%** at beta = **{b01}**
- {reading['verdict_on_the_rule']}

## Left tail (10 least-separated prototypes)
| Delta | prototype | nearest competitor |
|---|---|---|
{tail_md}

## LOWER BOUND - read this before quoting any number
Every below-certificate fraction above is a **LOWER BOUND ON THE DAMAGE**, not a prediction.
The projection holds the SHAPE of the `Delta` distribution fixed and shifts only the requirement
by `ln(r)/beta`. New documents add near-duplicate entities, which pushes the left tail down
faster than `log N` pushes the requirement up, so the true large-rung below-certificate
fraction is at least this large.

## Caveats
- capacity theorems assume random patterns and do not transfer to correlated text embeddings;
  only the Theorem-5 certificate is used, because it depends solely on observables
- `Delta_i` is one minus the runner-up cosine; the certificate adds margin- and N-awareness,
  not an independent quantity
- the bank embeds `"{{type}}: {{name}} - {{description[:200]}}"`, so `Delta` mixes name and
  description separation and is not a name-identity statistic
- frozen 6,626-entity substrate, not the 7,575-entity live re-ingest
"""
    (OUT / f"h657-separation-forecast-{run_id}.md").write_text(brief)
    cf.close()
    log(f"\nINSTRUMENT-DELIVERED | wrote {OUT}/h657-separation-forecast-{run_id}.json")


if __name__ == "__main__":
    main()

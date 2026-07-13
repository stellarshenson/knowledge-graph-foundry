"""R49-H580: demand-weighted value-of-information scheduling of gap repairs.

Hypothesis (registered R49-H580): ranking ledger entries by probe-demand repairs
most probe-flippable gaps within a small queue head, even though the FACTS
(coverage) are not concentrated. Prediction: demand-ranked top-20% captures
>= 70% of probe-flips vs <= 40% fact-count, <= 25% random.
Bar: CONFIRMED per prediction; KILLED if demand top-20% < 40% (H493 generalizes,
no scheduling shortcut) OR demand beats fact-count by < 10 pts.

FREE replay - no LLM, no graph. Substrate = the H579 per-gap outcomes
(reports/experiments/r49/h579-narrow-repair-*.json, latest): each gap carries its
probe-flip outcome (flip), retrieval-time abstention flag (pre_repair_absent),
anchor carrier type labels + graph-wide prevalence, and doc. Coverage per doc
from the R39 h389 certificates. Three rankings scored, top-20% flip-capture
measured; random averaged over 8 seeds.

Ranking signals (per gap):
  probe-demand = abstention-triggered (pre_repair_absent + (1 - doc_coverage))
                 + per-type prevalence deficit (anchor carrier label rarity)
  fact-count   = per-doc gap count (the naive "repair the biggest producers")
  random       = shuffle, 8 seeds averaged

Usage: python scripts/experiments/r49_h580_voi.py
Writes: reports/experiments/r49/h580-voi-<UTC ts>.json
"""

import glob
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("reports/experiments/r49")
H579_GLOB = "reports/experiments/r49/h579-narrow-repair-*.json"
H389_GLOB = "reports/experiments/r39/h389-coverage-*.jsonl"
SEEDS = list(range(8))
E = math.e


def latest_h579() -> Path:
    paths = [p for p in glob.glob(H579_GLOB) if ".checkpoint." not in p]
    if not paths:
        raise SystemExit("no h579-narrow-repair-*.json found - run H579 first")
    return Path(sorted(paths)[-1])


def doc_coverage() -> dict[str, float]:
    cov: dict[str, float] = {}
    for fp in sorted(glob.glob(H389_GLOB)):
        for line in open(fp):
            if not line.strip():
                continue
            r = json.loads(line)
            d, c = r.get("doc"), r.get("coverage")
            if d is not None and c is not None:
                cov[d] = min(cov.get(d, 1.0), c)   # worst observed coverage
    return cov


def minmax(vals: list[float]) -> list[float]:
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-12:
        return [0.0] * len(vals)
    return [(v - lo) / (hi - lo) for v in vals]


def capture_at(order: list[int], flip: list[int], frac: float) -> float:
    total = sum(flip)
    if total == 0:
        return 0.0
    head = order[:max(1, math.ceil(frac * len(order)))]
    return sum(flip[i] for i in head) / total


def curve(order: list[int], flip: list[int]) -> list[float]:
    return [round(capture_at(order, flip, f), 4)
            for f in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)]


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    src = latest_h579()
    cases = json.loads(src.read_text())["cases"]
    cov = doc_coverage()
    n = len(cases)

    flip = [int(bool(c.get("flip"))) for c in cases]
    total_flips = sum(flip)

    # per-doc gap count (fact-count signal)
    doc_count: dict[str, int] = {}
    for c in cases:
        doc_count[c["doc"]] = doc_count.get(c["doc"], 0) + 1

    # ---- probe-demand components ------------------------------------------------
    abst = []      # abstention-triggered
    tdef = []      # per-type prevalence deficit
    for c in cases:
        pre_absent = 1.0 if c.get("pre_repair_absent") else 0.0
        cov_pressure = 1.0 - cov.get(c["doc"], 1.0)
        abst.append(0.5 * pre_absent + 0.5 * cov_pressure)
        lc = c.get("carrier_label_min_count")
        # rarer carrier type -> larger deficit; missing carrier -> max deficit
        tdef.append(1.0 / math.log(lc + E) if lc else 1.0 / math.log(E))
    abst_n, tdef_n = minmax(abst), minmax(tdef)
    demand = [a + t for a, t in zip(abst_n, tdef_n)]
    factcount = [float(doc_count[c["doc"]]) for c in cases]

    def order_desc(score: list[float]) -> list[int]:
        # stable: higher score first, original index breaks ties
        return sorted(range(n), key=lambda i: (-score[i], i))

    demand_order = order_desc(demand)
    factcount_order = order_desc(factcount)

    demand_cap20 = capture_at(demand_order, flip, 0.20)
    factcount_cap20 = capture_at(factcount_order, flip, 0.20)

    rnd_caps, rnd_curves = [], []
    for sd in SEEDS:
        rng = random.Random(sd)
        idx = list(range(n))
        rng.shuffle(idx)
        rnd_caps.append(capture_at(idx, flip, 0.20))
        rnd_curves.append(curve(idx, flip))
    random_cap20 = sum(rnd_caps) / len(rnd_caps)
    random_curve = [round(sum(col) / len(col), 4) for col in zip(*rnd_curves)]

    demand_gap_vs_factcount = demand_cap20 - factcount_cap20

    clauses = [
        {"clause": "demand top-20% >= 70% capture (CONFIRM) / < 40% (KILL)",
         "measured": round(demand_cap20, 4),
         "confirm": demand_cap20 >= 0.70, "kill": demand_cap20 < 0.40},
        {"clause": "fact-count top-20% <= 40% capture (prediction)",
         "measured": round(factcount_cap20, 4), "holds": factcount_cap20 <= 0.40},
        {"clause": "random top-20% <= 25% capture (prediction)",
         "measured": round(random_cap20, 4), "holds": random_cap20 <= 0.25},
        {"clause": "demand beats fact-count by >= 10 pts (KILL if < 10)",
         "measured_pts": round(100 * demand_gap_vs_factcount, 1),
         "kill": demand_gap_vs_factcount < 0.10},
    ]
    kill = (demand_cap20 < 0.40) or (demand_gap_vs_factcount < 0.10)
    confirm = (demand_cap20 >= 0.70 and factcount_cap20 <= 0.40
               and random_cap20 <= 0.25 and demand_gap_vs_factcount >= 0.10)
    verdict = "CONFIRMED" if confirm else ("KILLED" if kill else "PARTIAL")
    if total_flips == 0:
        verdict = "NO-SUBSTRATE"

    top_head = [
        {"rank": r, "flip": flip[i], "doc": cases[i]["doc"],
         "fact": cases[i]["fact"][:60], "demand": round(demand[i], 3),
         "abst": round(abst_n[i], 3), "tdef": round(tdef_n[i], 3),
         "carrier": cases[i].get("carrier")}
        for r, i in enumerate(demand_order[:max(1, math.ceil(0.20 * n))])
    ]

    summary = {
        "hypothesis": "R49-H580", "run_id": ts, "source_h579": str(src),
        "n_gaps": n, "total_probe_flips": total_flips,
        "head_size_20pct": max(1, math.ceil(0.20 * n)),
        "capture_by_ranking": {
            "probe_demand": round(demand_cap20, 4),
            "fact_count": round(factcount_cap20, 4),
            "random_mean": round(random_cap20, 4),
            "random_seeds": [round(x, 4) for x in rnd_caps],
        },
        "curves_cumulative_capture": {
            "fractions": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            "probe_demand": curve(demand_order, flip),
            "fact_count": curve(factcount_order, flip),
            "random_mean": random_curve,
        },
        "demand_minus_factcount_pts": round(100 * demand_gap_vs_factcount, 1),
        "demand_top20_head": top_head,
        "signal_def": {
            "probe_demand": "minmax(0.5*pre_repair_absent + 0.5*(1-doc_coverage)) "
                            "+ minmax(1/log(carrier_label_min_count+e))",
            "fact_count": "per-doc gap count (naive biggest-producer first)",
            "random": "8-seed shuffle, capture averaged",
        },
        "clauses": clauses, "proposed_verdict": verdict,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / f"h580-voi-{ts}.json"
    out_path.write_text(json.dumps(
        {"summary": summary,
         "per_gap": [{"doc": c["doc"], "fact": c["fact"][:70], "flip": flip[i],
                      "flippable": bool(c.get("flippable")),
                      "recovered": bool(c.get("recovered")),
                      "demand": round(demand[i], 4),
                      "factcount": factcount[i],
                      "pre_repair_absent": bool(c.get("pre_repair_absent")),
                      "doc_coverage": cov.get(c["doc"]),
                      "carrier_label_min_count": c.get("carrier_label_min_count")}
                     for i, c in enumerate(cases)]},
        indent=1, ensure_ascii=False))
    print("SUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)
    print(f"WROTE {out_path}", flush=True)


if __name__ == "__main__":
    main()

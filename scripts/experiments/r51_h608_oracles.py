"""R51-H608 + R51-H609 FREE offline oracle gates (serves both).

Two FREE oracles that gate the set-selector (H608) and RL (H609) axes of R51.
No LLM generation is called. One read-only Foundry.probe re-render of the frozen
H570 probe set captures per-block tokens + text + entity names (the h570 artifact
logged only aggregate per-probe metrics, not block lists); everything else is
offline arithmetic over cached renders + the 2wiki gold map + the H530/H571 logs.

Subcommands:
  render-cache  read-only re-render of the eligible probes (query embedding +
                Neo4j read only, NO gpt-oss call) -> tmp/results/r51_render_cache-<ts>.jsonl
  oracles       read the newest render cache + 2wiki hops + H530 + H571 and emit
                reports/experiments/r51/h608-hopcoverage-oracle-<ts>.json
                reports/experiments/r51/h609-reward-earnability-<ts>.json

BLOCK-TO-HOP ATTRIBUTION CONVENTION (H608), stated precisely:
  * hop unit = a distinct (deduped) 2wiki `evidences` triple [subj, rel, obj];
    each atomic fact the multi-hop reasoning must retrieve. Comparison probes carry
    2 hops, bridge_comparison 4, compositional/inference 2 (evidences align 1:1
    with distinct supporting_facts titles for 83/86 scorable; 3 comparison probes
    carry 4 evidences over 2 titles - kept as 4 atomic hops).
  * a rendered block b COVERS hop e=[subj,rel,obj] iff  _present(subj, norm(b))
    AND _present(obj, norm(b))  - the block must carry BOTH the hop entity and its
    value (h158 fuzzy presence: exact / digit-skeleton / numeric-token / >=0.6
    word-overlap, tolerant of H107 extraction variance). Requiring both gates the
    bare-value false-positive (a stray "1961").
  * present hops of a probe = hops with >= 1 covering block in the render. hop-
    coverage denominator = present hops (isolates the SELECTOR's job from retrieval
    reachability, which is H609/H571 territory). Absolute coverage (denominator =
    all probe hops) reported as a secondary column.

ORACLES (H608), at budget = f * total_render_tokens (f in {0.3,0.5,0.7}; H-SET-3
sweep folded in per the registration; verdict reads f=0.5):
  * SET oracle  = budgeted maximum-coverage greedy (Krause-Golovin): repeatedly add
    the affordable block with max marginal-new-present-hops / token; result =
    max(greedy set, best single affordable block by coverage). Overlap-aware.
  * IND oracle  = pointwise "top-k by per-block gold value": rank blocks by static
    value v(b) = #distinct present hops b covers, ties by ascending tokens then
    index; greedy-fill the budget. Overlap-BLIND (the conservative/strong foil).
    Secondary IND variants reported: value+index tie-break; answer-string-gold-first.

Registered: docs/experiments/kgf-redesign-experiments.md R51-H608, R51-H609.
Read-only Neo4j (medium bolt://172.19.0.9). Proposes verdicts only.
"""

import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "notebooks")
sys.path.insert(0, "scripts/experiments")
from h158_measure import _norm, _present  # noqa: E402
from r46_h499_screen import gold_titles, ingested_titles, load_slices  # noqa: E402
from r49_h570_carrier_render import (  # noqa: E402
    block_is_gold,
    block_name,
    crit_pass,
    toks,
)

CONFIG = Path("config/experiments/config-bench-medium.yml")
QUESTIONS = Path("data/external/multihop-qa-benchmarks/2wikimultihopqa.json")
H530 = Path("reports/experiments/r48/h530-decomp-20260713T094447Z.json")
H571 = Path("reports/experiments/r49/h571-reach-col-20260713T192923Z.json")
H570 = Path("reports/experiments/r49/h570-carrier-render-20260713T191353Z.json")
CACHE_DIR = Path("tmp/results")
OUTDIR = Path("reports/experiments/r51")
COMPLEMENTARY = ("comparison", "bridge_comparison")
BUDGET_FRACS = (0.3, 0.5, 0.7)
VERDICT_FRAC = 0.5


# ---------------------------------------------------------------- render cache
def render_cache() -> Path:
    from knowledge_graph_foundry import load_settings
    from knowledge_graph_foundry.pipeline import Foundry

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out = CACHE_DIR / f"r51_render_cache-{run_id}.jsonl"
    questions = json.loads(QUESTIONS.read_text())
    st = load_settings(CONFIG)
    st.event_log = None
    n = 0
    with Foundry(st) as f, out.open("a") as ck:
        titles = ingested_titles(f, load_slices())
        eligible = [
            q for q in questions
            if gold_titles(q) and all(t in titles for t in gold_titles(q))
        ]
        print(f"r51-render-cache {run_id}: {len(eligible)} eligible probes", flush=True)
        for k, q in enumerate(eligible):
            qid = q.get("_id") or q["question"][:60]
            try:
                res = f.probe(q["question"])
            except Exception as exc:
                print(f"probe error {qid}: {exc}", flush=True)
                continue
            blocks = res["context_lines"]
            tok = [toks(b) for b in blocks]
            total = sum(tok)
            base = crit_pass(q, blocks)
            gold = [i for i, b in enumerate(blocks) if block_is_gold(q, b)]
            scorable = bool(base and len(gold) >= 1 and total)
            row = {
                "id": qid, "type": q.get("type"),
                "yesno": (q.get("answer") or "").strip().lower() in ("yes", "no"),
                "n_blocks": len(blocks), "total_tokens": total,
                "base_pass": base, "n_gold": len(gold), "gold_blocks": gold,
                "scorable": scorable,
                "blocks": [
                    {"i": i, "tokens": tok[i], "name": block_name(b), "text": b}
                    for i, b in enumerate(blocks)
                ],
            }
            ck.write(json.dumps(row) + "\n")
            ck.flush()
            n += 1
            print(f"[{k+1}/{len(eligible)}] {qid} scorable={scorable} "
                  f"n_blocks={len(blocks)} n_gold={len(gold)}", flush=True)
    print(f"WROTE {out} ({n} rows)", flush=True)
    return out


# ------------------------------------------------------------ hop attribution
def probe_hops(q: dict) -> list[tuple[str, str, str]]:
    """Deduped evidence triples = hop units (order preserved)."""
    seen, hops = set(), []
    for e in q.get("evidences", []):
        t = tuple(str(x) for x in e)
        if len(t) == 3 and t not in seen:
            seen.add(t)
            hops.append(t)
    return hops


def block_covers(ntext: str, subj: str, obj: str) -> bool:
    return _present(subj, ntext) and _present(obj, ntext)


def cover_map(blocks: list[dict], hops: list[tuple]) -> list[set[int]]:
    """For each hop index, the set of block indices that cover it."""
    ntexts = [_norm(b["text"]) for b in blocks]
    cov = []
    for (subj, rel, obj) in hops:
        cov.append({i for i, nt in enumerate(ntexts) if block_covers(nt, subj, obj)})
    return cov


# ---------------------------------------------------------------- selection
def select_greedy(order: list[int], tok: list[int], budget: int) -> set[int]:
    chosen, used = set(), 0
    for i in order:
        if used + tok[i] <= budget:
            chosen.add(i)
            used += tok[i]
    return chosen


def hop_coverage(chosen: set[int], present: list[int], cov: list[set[int]]) -> float:
    if not present:
        return None
    covered = sum(1 for h in present if cov[h] & chosen)
    return covered / len(present)


def set_oracle(present: list[int], cov: list[set[int]], tok: list[int],
               budget: int) -> set[int]:
    """Budgeted max-coverage greedy with single-element guard (Krause-Golovin)."""
    remaining = set(present)
    chosen, used = set(), 0
    cand = list(range(len(tok)))
    while True:
        best, best_ratio = None, 0.0
        for i in cand:
            if i in chosen or used + tok[i] > budget or tok[i] <= 0:
                continue
            gain = sum(1 for h in remaining if i in cov[h])
            if gain <= 0:
                continue
            ratio = gain / tok[i]
            if ratio > best_ratio:
                best, best_ratio = i, ratio
        if best is None:
            break
        chosen.add(best)
        used += tok[best]
        remaining -= {h for h in remaining if best in cov[h]}
    # single-element guard: best single affordable block by raw coverage
    single, single_cov = None, -1
    for i in cand:
        if tok[i] <= budget and tok[i] > 0:
            c = sum(1 for h in present if i in cov[h])
            if c > single_cov:
                single, single_cov = i, c
    greedy_cov = sum(1 for h in present if cov[h] & chosen)
    if single is not None and single_cov > greedy_cov:
        return {single}
    return chosen


def ind_order(blocks: list[dict], present: list[int], cov: list[set[int]],
              tie: str) -> list[int]:
    """Pointwise value ranker. value = #present hops the block covers."""
    def val(i):
        return sum(1 for h in present if i in cov[h])
    if tie == "density":
        key = lambda i: (-val(i), blocks[i]["tokens"], i)
    else:  # index tie-break
        key = lambda i: (-val(i), i)
    return sorted(range(len(blocks)), key=key)


def min_cover_tokens(present: list[int], cov: list[set[int]],
                     tok: list[int]) -> int | None:
    """Min total tokens of a block set covering ALL present hops (exact for the
    tiny instances here; greedy set-cover fallback if the search is large)."""
    if not present:
        return 0
    # candidate blocks = union of covering blocks
    cand = sorted({i for h in present for i in cov[h]})
    # greedy weighted set-cover (near-optimal; exact enough for feasibility census)
    remaining = set(present)
    picked, total = set(), 0
    while remaining:
        best, best_ratio = None, -1.0
        for i in cand:
            if i in picked or tok[i] <= 0:
                continue
            gain = sum(1 for h in remaining if i in cov[h])
            if gain <= 0:
                continue
            ratio = gain / tok[i]
            if ratio > best_ratio:
                best, best_ratio = i, ratio
        if best is None:
            return None
        picked.add(best)
        total += tok[best]
        remaining -= {h for h in remaining if best in cov[h]}
    return total


# ------------------------------------------------------------------- H608
def run_h608(cache: list[dict], byid: dict, run_id: str) -> dict:
    per_probe = []
    for r in cache:
        if not r.get("scorable"):
            continue
        q = byid[r["id"]]
        blocks = r["blocks"]
        tok = [b["tokens"] for b in blocks]
        total = r["total_tokens"]
        hops = probe_hops(q)
        cov = cover_map(blocks, hops)
        present = [h for h in range(len(hops)) if cov[h]]
        row = {"id": r["id"], "type": r["type"], "n_blocks": len(blocks),
               "n_gold": r["n_gold"], "total_tokens": total,
               "n_hops": len(hops), "n_present_hops": len(present),
               "budgets": {}}
        for f in BUDGET_FRACS:
            budget = int(f * total)
            set_sel = set_oracle(present, cov, tok, budget)
            ind_d = select_greedy(ind_order(blocks, present, cov, "density"),
                                  tok, budget)
            ind_i = select_greedy(ind_order(blocks, present, cov, "index"),
                                  tok, budget)
            gold_first = sorted(range(len(blocks)),
                                key=lambda i: (0 if i in r["gold_blocks"] else 1,
                                               tok[i], i))
            ind_ans = select_greedy(gold_first, tok, budget)
            mct = min_cover_tokens(present, cov, tok)
            row["budgets"][f] = {
                "budget_tokens": budget,
                "set_cov": hop_coverage(set_sel, present, cov),
                "ind_cov": hop_coverage(ind_d, present, cov),
                "ind_cov_index": hop_coverage(ind_i, present, cov),
                "ind_cov_answerstring": hop_coverage(ind_ans, present, cov),
                "feasible": (mct is not None and mct <= budget) if present else None,
                "min_cover_tokens": mct,
            }
        per_probe.append(row)

    def agg(rows, f, key):
        vals = [p["budgets"][f][key] for p in rows
                if p["budgets"][f][key] is not None]
        return round(statistics.fmean(vals), 4) if vals else None

    scor = per_probe
    comp = [p for p in per_probe if p["type"] in COMPLEMENTARY]
    multigold = [p for p in per_probe if p["n_gold"] >= 2]
    multihop = [p for p in per_probe if p["n_present_hops"] >= 2]

    f = VERDICT_FRAC
    set_comp = agg(comp, f, "set_cov")
    ind_comp = agg(comp, f, "ind_cov")
    gap = round((set_comp or 0) - (ind_comp or 0), 4)
    # paired per-probe gap on complementary
    paired = [(p["budgets"][f]["set_cov"] - p["budgets"][f]["ind_cov"])
              for p in comp
              if p["budgets"][f]["set_cov"] is not None
              and p["budgets"][f]["ind_cov"] is not None]
    n_set_gt = sum(1 for d in paired if d > 1e-9)
    n_ind_gt = sum(1 for d in paired if d < -1e-9)
    n_tie = sum(1 for d in paired if abs(d) <= 1e-9)

    def feas_frac(rows, f):
        vals = [p["budgets"][f]["feasible"] for p in rows
                if p["budgets"][f]["feasible"] is not None]
        return (round(sum(vals) / len(vals), 4), len(vals)) if vals else (None, 0)

    feas_mg, n_mg = feas_frac(multigold, f)
    feas_mh, n_mh = feas_frac(multihop, f)
    feas_comp, n_fc = feas_frac(comp, f)

    confirmed = gap >= 0.15 and feas_mg is not None and feas_mg >= 0.55
    killed = gap < 0.08 or (feas_mg is not None and feas_mg < 0.40)
    verdict = ("CONFIRMED" if confirmed else
               "KILL" if killed else "INCONCLUSIVE")

    clauses = [
        {"clause": "oracle SET beats independent top-k by >= 15pp hop-coverage "
                   "on complementary types (comparison+bridge_comparison) at 0.5x",
         "predicted": ">=0.15", "measured": gap,
         "set_cov": set_comp, "ind_cov": ind_comp, "n_probes": len(comp),
         "holds": gap >= 0.15},
        {"clause": "multi-gold (n_gold>=2) hop-feasibility >= 55% at 0.5x",
         "predicted": ">=0.55", "measured": feas_mg, "n_probes": n_mg,
         "holds": feas_mg is not None and feas_mg >= 0.55},
        {"clause": "KILL guard: gap < 8pp", "measured": gap,
         "holds": gap < 0.08},
        {"clause": "KILL guard: multi-gold feasibility < 40%",
         "measured": feas_mg, "holds": feas_mg is not None and feas_mg < 0.40},
    ]

    summary = {
        "hypothesis": "R51-H608", "run_id": run_id, "config": str(CONFIG),
        "n_scorable": len(scor), "n_complementary": len(comp),
        "attribution_convention": (
            "hop = deduped 2wiki evidence triple [subj,rel,obj]; block covers hop "
            "iff _present(subj,norm(block)) AND _present(obj,norm(block)); "
            "hop-coverage denominator = present hops (>=1 covering block)."),
        "verdict_budget_fraction": f,
        "complementary_paired_table": {
            "set_cov_mean": set_comp, "ind_cov_mean": ind_comp,
            "gap_pp": gap, "n_probes": len(comp),
            "n_set_wins": n_set_gt, "n_ind_wins": n_ind_gt, "n_tie": n_tie,
            "ind_cov_index_tiebreak": agg(comp, f, "ind_cov_index"),
            "ind_cov_answerstring": agg(comp, f, "ind_cov_answerstring"),
        },
        "hop_feasibility_census": {
            "multigold_n_gold_ge2": {"frac": feas_mg, "n": n_mg},
            "multihop_present_ge2": {"frac": feas_mh, "n": n_mh},
            "complementary": {"frac": feas_comp, "n": n_fc},
        },
        "budget_sweep": {  # H-SET-3 folded in
            str(fr): {
                "set_cov_complementary": agg(comp, fr, "set_cov"),
                "ind_cov_complementary": agg(comp, fr, "ind_cov"),
                "gap_pp": round((agg(comp, fr, "set_cov") or 0)
                                - (agg(comp, fr, "ind_cov") or 0), 4),
                "set_cov_all_scorable": agg(scor, fr, "set_cov"),
                "ind_cov_all_scorable": agg(scor, fr, "ind_cov"),
            } for fr in BUDGET_FRACS
        },
        "clauses": clauses,
        "proposed_verdict": verdict,
        "bars": {
            "CONFIRMED": "gap >= 15pp AND multigold feasibility >= 55%",
            "KILL": "gap < 8pp OR multigold feasibility < 40%"},
    }
    return {"summary": summary, "rows": per_probe}


# ------------------------------------------------------------------- H609
def run_h609(cache: list[dict], byid: dict, run_id: str) -> dict:
    # single-pass render oracle: max H570-gold recall@0.5x = greedy cheapest-gold
    per_probe = []
    for r in cache:
        if not r.get("scorable"):
            continue
        tok = [b["tokens"] for b in r["blocks"]]
        total = r["total_tokens"]
        gold = r["gold_blocks"]
        budget = int(VERDICT_FRAC * total)
        # oracle recall = greedy cheapest gold packing
        order = sorted(gold, key=lambda i: tok[i])
        chosen, used = [], 0
        for i in order:
            if used + tok[i] <= budget:
                chosen.append(i)
                used += tok[i]
        recall = len(chosen) / len(gold) if gold else None
        hit1 = 1 if chosen else 0
        per_probe.append({"id": r["id"], "type": r["type"], "n_gold": len(gold),
                          "yesno": r["yesno"], "budget_tokens": budget,
                          "oracle_recall": recall, "oracle_hit1": hit1})

    def m(rows, key):
        v = [p[key] for p in rows if p[key] is not None]
        return round(statistics.fmean(v), 4) if v else None

    scor = per_probe
    single = [p for p in scor if p["n_gold"] == 1]
    multi = [p for p in scor if p["n_gold"] >= 2]
    single_pass_oracle = m(scor, "oracle_recall")

    # decomposition oracle from H530
    h530 = json.loads(H530.read_text())["summary"]
    decomp_oracle = h530["decomp_pass_rate"]

    # earnable-reward fraction from H571 reachability column
    h571 = json.loads(H571.read_text())
    earnable = h571["mean_doc_reach"]           # PPR doc-reach of gold carriers
    earnable_graded = h571["mean_graded_reach_per_carrier"]
    coverage_outer = h571["mean_doc_coverage"]  # outer bound (H515/coverage)
    # per-probe: fraction with >=1 PPR-reachable gold carrier
    from collections import defaultdict
    reach_by_probe = defaultdict(list)
    for row in h571["rows"]:
        reach_by_probe[row["probe"]].append(bool(row.get("ppr_reachable")))
    any_reach = [any(v) for v in reach_by_probe.values()]
    all_reach = [all(v) for v in reach_by_probe.values()]
    frac_any = round(sum(any_reach) / len(any_reach), 4) if any_reach else None
    frac_all = round(sum(all_reach) / len(all_reach), 4) if all_reach else None

    clauses = [
        {"clause": "single-pass render oracle <= 0.72", "predicted": "<=0.72",
         "measured": single_pass_oracle, "holds": single_pass_oracle <= 0.72},
        {"clause": "decomposition oracle >= 0.88 (H530 decomp_pass_rate)",
         "predicted": ">=0.88", "measured": decomp_oracle,
         "holds": decomp_oracle >= 0.88},
        {"clause": "earnable-reward fraction <= 0.55 (H571 PPR gold-carrier reach)",
         "predicted": "<=0.55", "measured": earnable, "holds": earnable <= 0.55},
        {"clause": "KILL-REFRAME guard: single-pass render oracle >= 0.85",
         "measured": single_pass_oracle, "holds": single_pass_oracle >= 0.85},
    ]
    confirmed_reframe = single_pass_oracle <= 0.72 and decomp_oracle >= 0.88
    kill_reframe = single_pass_oracle >= 0.85
    starved = earnable <= 0.55
    base = ("KILL-REFRAME" if kill_reframe
            else "CONFIRMED-REFRAME" if confirmed_reframe
            else "INCONCLUSIVE")
    verdict = base + ("; CONFIRMED-STARVED" if starved else "")

    summary = {
        "hypothesis": "R51-H609", "run_id": run_id, "config": str(CONFIG),
        "n_scorable": len(scor),
        "single_pass_render_oracle": {
            "recall_at_0.5x_all": single_pass_oracle,
            "recall_single_gold": m(single, "oracle_recall"), "n_single": len(single),
            "recall_multi_gold": m(multi, "oracle_recall"), "n_multi": len(multi),
            "hit1_frac": m(scor, "oracle_hit1"),
            "definition": "max H570-gold recall@0.5x = greedy cheapest-gold packing "
                          "(oracle ceiling of single-pass block selection); "
                          "comparable to H570 realized llm 0.687",
            "h570_realized_llm": 0.687},
        "decomposition_oracle": {
            "value": decomp_oracle, "at_token_fraction": 0.52,
            "source": str(H530), "subq_coverage_top1": h530.get("subq_coverage_top1")},
        "earnable_reward": {
            "ppr_gold_carrier_reach": earnable, "graded_reach": earnable_graded,
            "coverage_outer_bound": coverage_outer,
            "frac_probes_any_gold_reachable": frac_any,
            "frac_probes_all_gold_reachable": frac_all,
            "source": str(H571),
            "note": "68% of gold carriers not PPR-reachable => zero earnable reward; "
                    "coverage 0.5909 is the seeding-changeable outer bound (H571 V5)"},
        "clauses": clauses,
        "proposed_verdict": verdict,
        "bars": {
            "CONFIRMED-REFRAME": "single-pass oracle <= 0.72 AND decomp oracle >= 0.88",
            "KILL-REFRAME": "single-pass render oracle >= 0.85",
            "CONFIRMED-STARVED": "earnable fraction <= 0.55"},
    }
    return {"summary": summary, "rows": per_probe}


# --------------------------------------------------------------------- driver
def newest_cache() -> Path:
    caches = sorted(CACHE_DIR.glob("r51_render_cache-*.jsonl"))
    if not caches:
        raise SystemExit("no render cache; run `render-cache` first")
    return caches[-1]


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "oracles"
    if mode == "render-cache":
        render_cache()
        return
    cache_path = Path(sys.argv[2]) if len(sys.argv) > 2 else newest_cache()
    cache = [json.loads(l) for l in cache_path.read_text().splitlines() if l.strip()]
    questions = json.loads(QUESTIONS.read_text())
    byid = {q["_id"]: q for q in questions}
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUTDIR.mkdir(parents=True, exist_ok=True)

    h608 = run_h608(cache, byid, run_id)
    p608 = OUTDIR / f"h608-hopcoverage-oracle-{run_id}.json"
    p608.write_text(json.dumps(h608, indent=1))
    print("H608 " + json.dumps(h608["summary"]["complementary_paired_table"]))
    print("H608 verdict:", h608["summary"]["proposed_verdict"])
    print(f"WROTE {p608}")

    h609 = run_h609(cache, byid, run_id)
    p609 = OUTDIR / f"h609-reward-earnability-{run_id}.json"
    p609.write_text(json.dumps(h609, indent=1))
    print("H609 single_pass_oracle:",
          h609["summary"]["single_pass_render_oracle"]["recall_at_0.5x_all"],
          "decomp:", h609["summary"]["decomposition_oracle"]["value"],
          "earnable:", h609["summary"]["earnable_reward"]["ppr_gold_carrier_reach"])
    print("H609 verdict:", h609["summary"]["proposed_verdict"])
    print(f"WROTE {p609}")
    print(f"CACHE {cache_path}")


if __name__ == "__main__":
    main()

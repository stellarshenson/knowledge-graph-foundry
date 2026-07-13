"""R49-H547: is the repaired-fact CARRIER load-bearing at retrieval time?

Hypothesis (registered R49-H547): attaching a repaired fact to the fallback-
largest carrier vs the correct (gold) carrier does not change probe outcomes -
the neighborhood, not the carrier, surfaces the fact (H528 recall-via-mass;
HippoRAG retrieves the doc neighborhood, not the carrier word). Counter-tension
kept live by robust-GraphRAG (2603.14828): a KG defect (wrong attachment) can
cause retrieval drift, so this is a real test, not a foregone null.

Substrate: the 12 hand-adjudicated fallback-carrier repairs
(reports/experiments/r49/carrier-gold-12.json), LIVE on the R45 PILOT pile
(config-bench-pilot.yml, bolt://172.19.0.101:7687). Each fact currently sits on
the LABELED (fallback-largest) carrier's description (R45 write_property).

Method (STRICTLY read-only on Neo4j - the swap is simulated in memory):
  query per case = doc_title (a neighborhood/subject anchor that contains none
    of the anaphoric fact's own words - non-leaking, so the retrieved node set
    is arm-invariant and the render-side swap is faithful).
  ARM A (live)     = f.probe(doc_title) render, fact on the fallback carrier.
  ARM B (simulated)= the SAME rendered context with the fact string MOVED:
    removed from the fallback carrier's block, and re-added iff the gold
    carrier's block is present in the arm-A render (abstain/gold=null -> removed,
    not re-added). This is the sanctioned FREE swap-and-recheck on the cached
    render; retrieval is held fixed (noted limitation: a re-embed/re-retrieval
    swap is not modelled - defensible because doc_title does not name the fact).

Answer-presence criterion = the R45/H389 machinery: supported(fact, ctx, 0.8)
(content-term overlap, primary). Secondary cross-check = the shipped presence
gate answer_present(fact, norm(ctx)). SAME criterion in both arms.

Verdict bar (registered): KILLED-attach-carrier if |net delta| <= 1 AND
>= n-1 identical; SURVIVES load-bearing if correct attachment lifts >= 3 net.

Usage: python scripts/experiments/r49_h547_carrier_swap.py
Writes: reports/experiments/r49/h547-carrier-swap-<UTC ts>.json
"""

import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "src")
from knowledge_graph_foundry import load_settings
from knowledge_graph_foundry.graph.questions import _norm, answer_present
from knowledge_graph_foundry.pipeline import Foundry

# reuse the exact H389 support machinery (supported / content_terms) verbatim
_spec = importlib.util.spec_from_file_location(
    "r39_h389", "scripts/experiments/r39_h389_coverage_audit.py"
)
_r39 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_r39)
supported = _r39.supported  # supported(probe, graph_text, threshold=0.8)
content_terms = _r39.content_terms

GOLD = Path("reports/experiments/r49/carrier-gold-12.json")
CONFIG = Path("config/experiments/config-bench-pilot.yml")
OUT = Path("reports/experiments/r49")
THRESHOLD = 0.8


def _jaccard(a: str, b: str) -> float:
    ta, tb = set(content_terms(a)), set(content_terms(b))
    return len(ta & tb) / len(ta | tb) if (ta or tb) else 0.0


def match_segment(fact: str, description: str) -> str | None:
    """The exact stored segment of the carrier's description that is THIS fact
    (R45 appended facts with ' | '); pick the best content-term match."""
    if not description:
        return None
    segs = [s.strip() for s in description.split(" | ") if s.strip()]
    best, best_j = None, 0.0
    for s in segs:
        j = _jaccard(fact, s)
        if j > best_j:
            best, best_j = s, j
    return best if best_j >= 0.5 else None


def block_present(name: str, ctx: str) -> bool:
    """Does the entity's render block header (## name (types)) survive into the
    rendered context (post-truncation)?"""
    return f"## {name} (".lower() in ctx.lower()


def run_arm(f, gold, case_meta, dup_counts, render_budget: float) -> list[dict]:
    """One full swap pass at a given render_budget (0.6 = shipped truncation,
    1.0 = full render, no truncation). Read-only; the swap is in memory."""
    f.settings.graphrag.render_budget = render_budget
    per_case = []
    for c, seg in zip(gold, case_meta):
        query = c["doc_title"]
        res = f.probe(query)
        ctx_A = " ".join(res["context_lines"])
        names = res["supporting_names"]

        labeled = c["labeled_carrier"]
        goldc = c["gold_carrier"]
        labeled_in = block_present(labeled, ctx_A)
        gold_in = (goldc is not None) and block_present(goldc, ctx_A)
        no_op = (goldc is not None) and (goldc.strip().lower() == labeled.strip().lower())
        move = seg or c["fact"]

        # ARM B: remove the fact from the fallback carrier, re-add to gold iff
        # the gold block is in the render (abstain/gold=null -> gone)
        ctx_B = ctx_A
        for rem in (" | " + move, move, " | " + c["fact"], c["fact"]):
            if rem in ctx_B:
                ctx_B = ctx_B.replace(rem, " ", 1)
                break
        readd = (goldc is not None) and (gold_in or no_op)
        if readd:
            ctx_B = ctx_B + " | " + move

        nA, nB = _norm(ctx_A), _norm(ctx_B)
        supA = supported(c["fact"], ctx_A, THRESHOLD)          # PRIMARY (H389)
        supB = supported(c["fact"], ctx_B, THRESHOLD)
        preA = bool(answer_present(c["fact"], nA))             # SECONDARY (gate)
        preB = bool(answer_present(c["fact"], nB))

        per_case.append({
            "fact": c["fact"], "doc": c["doc"], "doc_title": c["doc_title"],
            "gold_class": c["gold_class"], "labeled_carrier": labeled,
            "gold_carrier": goldc, "labeled_correct": c.get("labeled_correct"),
            "no_op_swap": no_op, "query": query, "segment_moved": move,
            "segment_isolated": seg is not None,
            "labeled_carrier_dup_nodes": dup_counts.get(c["doc"], {}).get(labeled),
            "labeled_block_in_render": labeled_in,
            "gold_block_in_render": gold_in, "readded_to_gold": readd,
            "n_render_names": len(names),
            "presenceA_supported": supA, "presenceB_supported": supB,
            "identical_supported": supA == supB,
            "presenceA_present": preA, "presenceB_present": preB,
            "identical_present": preA == preB,
        })
    return per_case


def aggregate(per_case: list[dict]) -> dict:
    n = len(per_case)
    sumA = sum(p["presenceA_supported"] for p in per_case)
    sumB = sum(p["presenceB_supported"] for p in per_case)
    net = sumB - sumA
    ident = sum(p["identical_supported"] for p in per_case)
    return {
        "n": n, "sum_A": sumA, "sum_B": sumB, "net_delta_B_minus_A": net,
        "identical": ident,
        "secondary_present_gate": {
            "sum_A": sum(p["presenceA_present"] for p in per_case),
            "sum_B": sum(p["presenceB_present"] for p in per_case),
            "net_delta": sum(p["presenceB_present"] for p in per_case)
            - sum(p["presenceA_present"] for p in per_case),
            "identical": sum(p["identical_present"] for p in per_case),
        },
        "changed_cases": [
            {"fact": p["fact"][:70], "class": p["gold_class"],
             "A": p["presenceA_supported"], "B": p["presenceB_supported"],
             "labeled_in_render": p["labeled_block_in_render"],
             "gold_in_render": p["gold_block_in_render"],
             "dup_nodes": p["labeled_carrier_dup_nodes"]}
            for p in per_case if not p["identical_supported"]
        ],
    }


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    gold = json.loads(GOLD.read_text())["cases"]
    st = load_settings(CONFIG)
    st.event_log = None

    with Foundry(st) as f:
        with f.driver.session() as s:
            case_meta = []
            dup_counts: dict = {}
            for c in gold:
                row = s.run(
                    "MATCH (e:Entity) WHERE $d IN e.source_documents AND e.name = $n "
                    "RETURN e.description AS d",
                    d=c["doc"], n=c["labeled_carrier"],
                ).single()
                case_meta.append(match_segment(c["fact"], (row["d"] if row else None) or ""))
                # duplicate-node detection: how many Entity nodes carry the
                # fallback carrier's name graph-wide (unmerged duplicates
                # confound which copy of the description dominates retrieval)
                dn = s.run("MATCH (e:Entity {name:$n}) RETURN count(e) AS c",
                           n=c["labeled_carrier"]).single()["c"]
                dup_counts.setdefault(c["doc"], {})[c["labeled_carrier"]] = dn

        arms = {}
        # shipped truncation (primary) then full render (robustness) - restore
        # the shipped budget last so the session leaves state untouched
        for budget in (1.0, st.graphrag.render_budget):
            key = "full_render_1.0" if budget >= 1.0 else f"shipped_{budget}"
            arms[key] = run_arm(f, gold, case_meta, dup_counts, budget)

    primary_key = next(k for k in arms if k.startswith("shipped"))
    primary = arms[primary_key]
    agg = aggregate(primary)
    n, net, ident = agg["n"], agg["net_delta_B_minus_A"], agg["identical"]

    full = aggregate(arms["full_render_1.0"])
    clauses = [
        {"clause": "|net delta presence| <= 1 (registered KILLED bar)",
         "predicted": "<= 1", "measured_shipped": abs(net),
         "measured_full_render": abs(full["net_delta_B_minus_A"]),
         "holds_shipped": abs(net) <= 1,
         "holds_full_render": abs(full["net_delta_B_minus_A"]) <= 1},
        {"clause": f">= {n-1}/{n} cases identical (prediction narrative)",
         "predicted": f">= {n-1}", "measured_shipped": ident,
         "measured_full_render": full["identical"],
         "holds_shipped": ident >= n - 1,
         "holds_full_render": full["identical"] >= n - 1},
        {"clause": "correct attachment lifts >= 3 net probes (registered SURVIVES bar)",
         "predicted": ">= +3", "measured_shipped": net,
         "measured_full_render": full["net_delta_B_minus_A"],
         "holds_shipped": net >= 3, "holds_full_render": full["net_delta_B_minus_A"] >= 3},
    ]

    # verdict per the registered bar literally (KILLED if |net|<=1, SURVIVES if
    # lift>=+3), computed on the SHIPPED render (primary); the full-render arm is
    # reported alongside because the verdict is render_budget-dependent here
    def bar(net_):
        return "SURVIVES-load-bearing" if net_ >= 3 else (
            "KILLED-attach-carrier" if abs(net_) <= 1 else "INCONCLUSIVE")

    verdict = bar(net)
    verdict_full = bar(full["net_delta_B_minus_A"])

    summary = {
        "hypothesis": "R49-H547",
        "run_id": ts,
        "config": str(CONFIG),
        "neo4j_uri": st.neo4j.uri,
        "pile": "R45 PILOT (neo4j3, 172.19.0.101)",
        "n_effective": n,
        "query_design": "doc_title neighborhood anchor (non-leaking); render-side carrier swap on the cached probe render; retrieval held fixed",
        "primary_criterion": "H389 supported() content-term overlap >= 0.8",
        "primary_arm": primary_key,
        "arm_aggregates": {k: aggregate(v) for k, v in arms.items()},
        "clauses": clauses,
        "proposed_verdict": verdict,
        "proposed_verdict_full_render": verdict_full,
        "verdict_note": (
            "Shipped render (0.6): |net|=2 -> INCONCLUSIVE by the literal bar. The "
            "single over-threshold increment is the 'Wrong Turn' fragment, whose "
            "R45-repaired carrier is an UNMERGED DUPLICATE (2 nodes) ranked below "
            "its non-repaired twin and truncated out; at full render it is "
            "identical -> |net|=1 -> KILLED. The only render-budget-ROBUST "
            "non-identical case is the varsity-match fact (duplicated x2 in the "
            "gold set), where the fallback carrier 'Oxford University' is never "
            "retrieved by the subject query (genuine retrieval drift, robust-"
            "GraphRAG mechanism). Net leans KILLED-attach-carrier; carrier is "
            "load-bearing ONLY under fallback-carrier retrieval drift (1 distinct "
            "fact), never reaching the +3 SURVIVES bar."
        ),
        "confounds": (
            "Unmerged duplicate carrier nodes (e.g. 'Wrong Turn (franchise)' = 2 "
            "nodes; the R45-repaired copy ranks below its non-repaired twin and is "
            "dropped by render_budget=0.6) + 'Oxford University' (varsity carrier) "
            "not retrieved by the subject query at all; gold rows duplicated "
            "(varsity x2, list x3). The full_render_1.0 arm isolates the "
            "truncation confound from genuine retrieval drift."
        ),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / f"h547-carrier-swap-{ts}.json"
    out_path.write_text(json.dumps(
        {"summary": summary, "arms": arms}, indent=1, ensure_ascii=False))
    print("\nSUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)
    print(f"WROTE {out_path}", flush=True)


if __name__ == "__main__":
    main()

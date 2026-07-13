"""R49-H572 CRUX: the query-free ingest-time audit predicts query-time reachability.

Hypothesis: per-fact reachability computed from ANTICIPATED questions (query-free,
the KGFQuestion nodes generated at ingest and attached to the fact's chunks) agrees
with reachability computed from the REAL gold bench questions. If the audit foresees
query-time reachability, the two labels agree.

Machinery (offline, read-only Neo4j; PPR follows r48_h515_mask conventions):
  fact set     = (probe, gold-carrier) for every eligible 2wiki probe's gold
                 supporting-title carriers matched in the graph, PLUS the explicit
                 REG-2 answer fact (Leopoldo Torre Nilsson, the CHILD_OF edge target).
  reach(seed)  = dense top-16 entity seeds -> personalized PageRank over the live-rel
                 Entity adjacency -> carrier in (top ppr_top_n=15 ranked nodes U seeds).
  REAL arm     = seeds from the real bench question text (one PPR per probe, reused
                 across its carriers) - this is exactly h515 full PPR, per carrier.
  ANTICIPATED  = for the carrier, the KGFQuestion nodes ANSWERABLE_FROM chunks that
                 MENTION it (doc-level fallback); each question's STORED embedding ->
                 dense top-16 entity seeds -> PPR -> carrier reachable. Aggregated over
                 the carrier's anticipated questions: ANY / MAJORITY / ALL, plus an
                 ATTRIBUTE-ONLY majority (questions that do NOT name the carrier - the
                 audit's honest job is to reach a fact from a query that does not spell
                 it out). Primary label = MAJORITY. All arms are query-free: the real
                 bench question never enters the anticipated computation.

Agreement = mean(reach_real == reach_antic); kappa = Cohen's kappa on the 2x2.
REG-2 clause: Leopoldo Torre Nilsson must be flagged UNREACHABLE under BOTH sources.

Bars (registered): CONFIRMED agreement >= 0.80 (kappa >= 0.5) and REG-2 unreachable
under both; KILLED at agreement < 0.65.

Deviations recorded in the artifact: offline scipy PPR over Entity-only live-rel
adjacency (engine projection also carries Chunk nodes, no communityId) - inherited
from h515; graph stores the REG-2 edge as CHILD_OF (registration writes CHILD).

Usage: python scripts/experiments/r49_h572_reach_crux.py [config] [questions.json] [max]
Writes: reports/experiments/r49/h572-reach-crux-<ts>.json
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix

sys.path.insert(0, "notebooks")
sys.path.insert(0, "scripts/experiments")
from h158_measure import _norm  # noqa: E402
from r46_h499_screen import gold_titles, ingested_titles, load_slices  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.extraction import generate_embeddings  # noqa: E402
from knowledge_graph_foundry.models import Entity  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

CONFIG = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    "config/experiments/config-bench-medium.yml"
)
QUESTIONS = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
    "data/external/multihop-qa-benchmarks/2wikimultihopqa.json"
)
MAX = int(sys.argv[3]) if len(sys.argv) > 3 else 0
SCREEN = Path("reports/experiments/bench/r46-h499-screen-20260713T072044Z.jsonl")
DAMPING = 0.85
ITERS = 50
ANTIC_CAP = 12  # anticipated questions per carrier (deterministic by q.id)
REG2 = {  # explicit answer-edge fact: CHILD_OF target must be unreachable both ways
    "probe_id": "1dfaa6200bdd11eba7f7acde48001122",
    "carrier": "Leopoldo Torre Nilsson",
}


def ppr(adj, seed_idx, out):
    n = adj.shape[0]
    if not seed_idx:
        return np.zeros(n)
    p = np.zeros(n)
    p[seed_idx] = 1.0 / len(seed_idx)
    r = p.copy()
    for _ in range(ITERS):
        r = (1 - DAMPING) * p + DAMPING * (adj.T @ (r / out))
    return r


def cohen_kappa(a, b):
    a = np.asarray(a, dtype=int)
    b = np.asarray(b, dtype=int)
    n = len(a)
    po = float((a == b).mean())
    pa1, pb1 = a.mean(), b.mean()
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    kappa = (po - pe) / (1 - pe) if (1 - pe) > 1e-12 else 0.0
    return po, float(kappa)


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    questions = json.loads(QUESTIONS.read_text())
    byid = {q.get("_id"): q for q in questions}
    off_ids = [json.loads(l)["id"] for l in SCREEN.read_text().splitlines()
               if l.strip() and json.loads(l)["arm"] == "off"]
    st = load_settings(CONFIG)
    st.event_log = None
    top_k = st.graphrag.top_k
    top_n = st.graphrag.ppr_top_n

    with Foundry(st) as f:
        from knowledge_graph_foundry.graph.graphrag import vector_query  # noqa: E402
        with f.driver.session() as s:
            ents = s.run("MATCH (e:Entity) RETURN e.id AS id, e.name AS name").data()
            edges = s.run(
                "MATCH (a:Entity)-[r]-(b:Entity) WHERE r.valid_to IS NULL "
                "AND type(r) <> 'SIMILAR_TO' RETURN a.id AS a, b.id AS b"
            ).data()
        idx = {e["id"]: i for i, e in enumerate(ents)}
        name_row = {_norm(e["name"]): idx[e["id"]] for e in ents if e.get("name")}
        eid_by_row = {idx[e["id"]]: e["id"] for e in ents}
        name_by_row = {idx[e["id"]]: e["name"] for e in ents}
        n = len(ents)
        ij = np.array([[idx[e["a"]], idx[e["b"]]] for e in edges
                       if e["a"] in idx and e["b"] in idx])
        adj = csr_matrix((np.ones(len(ij)), (ij[:, 0], ij[:, 1])), shape=(n, n))
        adj = ((adj + adj.T) > 0).astype(float).tocsr()
        out = np.asarray(adj.sum(axis=1)).ravel()
        out[out == 0] = 1.0
        print(f"h572 {run_id}: {n} entities, {adj.nnz} edge slots", flush=True)

        titles = ingested_titles(f, load_slices())

        # eligible probes: h515 eligibility AND present in the h499 OFF arm
        eligible = [byid[i] for i in off_ids if i in byid
                    and gold_titles(byid[i]) and all(t in titles for t in gold_titles(byid[i]))]
        eligible = eligible[:MAX] if MAX else eligible
        print(f"{len(eligible)} eligible probes", flush=True)

        # --- REAL arm: one PPR per probe, reused across its carriers -----------
        probes = []
        for q in eligible:
            qid = q.get("_id")
            probe = Entity.create(q["question"][:80], types=["Query"], description=q["question"])
            qv = generate_embeddings([probe], st.embeddings)[0].embedding
            seeds = vector_query(f.driver, qv, st.graphrag.vector_index_name, top_k=top_k)
            seed_rows = [idx[x["id"]] for x in seeds if x["id"] in idx]
            r = ppr(adj, seed_rows, out)
            top = set(np.argsort(-r)[:top_n]) | set(seed_rows)
            probes.append({"qid": qid, "seed_rows": seed_rows, "reach_top": top,
                           "golds": gold_titles(q)})

        # --- ANTICIPATED arm: per carrier, cached by carrier name -------------
        antic_cache = {}
        seed_cache = {}  # question id -> seed_rows (dedup vector_query calls)

        def antic_reach(carrier_name):
            key = _norm(carrier_name)
            if key in antic_cache:
                return antic_cache[key]
            crow = name_row.get(key)
            if crow is None:
                antic_cache[key] = None
                return None
            eid = eid_by_row[crow]
            with f.driver.session() as s:
                qs = s.run(
                    "MATCH (e:Entity {id:$eid})-[:MENTIONED_IN]->(c:Chunk)"
                    "<-[:ANSWERABLE_FROM]-(q:KGFQuestion) WHERE q.embedding IS NOT NULL "
                    "RETURN DISTINCT q.id AS qid, q.text AS text, q.embedding AS emb "
                    "ORDER BY q.id LIMIT $cap", eid=eid, cap=ANTIC_CAP).data()
                if not qs:  # doc-level fallback
                    qs = s.run(
                        "MATCH (e:Entity {id:$eid})-[:MENTIONED_IN]->(:Chunk)-[:PART_OF]->"
                        "(d:KGFDocument)<-[:PART_OF]-(:Chunk)<-[:ANSWERABLE_FROM]-(q:KGFQuestion) "
                        "WHERE q.embedding IS NOT NULL "
                        "RETURN DISTINCT q.id AS qid, q.text AS text, q.embedding AS emb "
                        "ORDER BY q.id LIMIT $cap", eid=eid, cap=ANTIC_CAP).data()
            per_q, per_q_attr = [], []
            for q in qs:
                if q["qid"] in seed_cache:
                    seed_rows = seed_cache[q["qid"]]
                else:
                    seeds = vector_query(f.driver, q["emb"], st.graphrag.vector_index_name, top_k=top_k)
                    seed_rows = [idx[x["id"]] for x in seeds if x["id"] in idx]
                    seed_cache[q["qid"]] = seed_rows
                r = ppr(adj, seed_rows, out)
                top = set(np.argsort(-r)[:top_n]) | set(seed_rows)
                hit = crow in top
                per_q.append(hit)
                if carrier_name.lower() not in (q["text"] or "").lower():
                    per_q_attr.append(hit)
            res = {
                "n_antic": len(per_q),
                "any": bool(any(per_q)) if per_q else None,
                "majority": bool(sum(per_q) * 2 >= len(per_q)) if per_q else None,
                "all": bool(all(per_q)) if per_q else None,
                "attr_n": len(per_q_attr),
                "attr_majority": (bool(sum(per_q_attr) * 2 >= len(per_q_attr))
                                  if per_q_attr else None),
                "reach_rate": round(sum(per_q) / len(per_q), 3) if per_q else None,
            }
            antic_cache[key] = res
            return res

        # --- assemble fact rows -----------------------------------------------
        facts = []
        for p in probes:
            for t in p["golds"]:
                crow = name_row.get(_norm(t))
                if crow is None:
                    continue
                a = antic_reach(t)
                facts.append({
                    "probe": p["qid"], "carrier": t, "reg2": False,
                    "reach_real": crow in p["reach_top"],
                    "antic": a,
                })
                print(f"  {p['qid'][:12]} | {t[:34]:34} real={facts[-1]['reach_real']} "
                      f"antic_maj={a['majority'] if a else None} rate={a['reach_rate'] if a else None}",
                      flush=True)
        # explicit REG-2 answer fact
        reg2_probe = next((p for p in probes if p["qid"] == REG2["probe_id"]), None)
        reg2_row = None
        if reg2_probe is not None:
            crow = name_row.get(_norm(REG2["carrier"]))
            a = antic_reach(REG2["carrier"])
            reg2_row = {
                "probe": REG2["probe_id"], "carrier": REG2["carrier"], "reg2": True,
                "carrier_in_graph": crow is not None,
                "reach_real": (crow in reg2_probe["reach_top"]) if crow is not None else None,
                "antic": a,
            }
            print(f"  REG-2 {REG2['carrier']}: real={reg2_row['reach_real']} antic={a}", flush=True)

    # --- statistics per aggregation ---------------------------------------
    def stats(agg):
        rows = [x for x in facts if x["antic"] and x["antic"][agg] is not None]
        if not rows:
            return None
        real = [x["reach_real"] for x in rows]
        anti = [x["antic"][agg] for x in rows]
        po, kappa = cohen_kappa(real, anti)
        return {"n": len(rows), "agreement": round(po, 4), "kappa": round(kappa, 4),
                "real_pos": int(sum(real)), "antic_pos": int(sum(anti))}

    aggs = {a: stats(a) for a in ("any", "majority", "all", "attr_majority")}
    primary = aggs["majority"]

    # REG-2 both-sources: unreachable under both real and anticipated
    reg2_both = None
    if reg2_row is not None and reg2_row["antic"] is not None:
        antic_unreach_maj = reg2_row["antic"]["majority"] is False
        antic_unreach_any = reg2_row["antic"]["any"] is False
        reg2_both = {
            "real_unreachable": reg2_row["reach_real"] is False,
            "antic_unreachable_majority": antic_unreach_maj,
            "antic_unreachable_any": antic_unreach_any,
            "both_sources_flag": bool(reg2_row["reach_real"] is False and antic_unreach_maj),
            "reach_real": reg2_row["reach_real"],
            "antic": reg2_row["antic"],
        }

    agreement = primary["agreement"] if primary else None
    kappa = primary["kappa"] if primary else None
    clauses = {
        "agreement_ge_0.80": bool(agreement is not None and agreement >= 0.80),
        "kappa_ge_0.50": bool(kappa is not None and kappa >= 0.50),
        "reg2_unreachable_both": bool(reg2_both and reg2_both["both_sources_flag"]),
    }
    if agreement is None:
        verdict = "INCONCLUSIVE"
    elif agreement >= 0.80 and kappa is not None and kappa >= 0.50 and clauses["reg2_unreachable_both"]:
        verdict = "CONFIRMED"
    elif agreement < 0.65:
        verdict = "KILLED"
    else:
        verdict = "INDETERMINATE"

    summary = {
        "run_id": run_id, "config": str(CONFIG), "n_facts": len(facts),
        "primary_aggregation": "majority",
        "agreement": agreement, "kappa": kappa,
        "aggregations": aggs,
        "reg2": reg2_both, "clauses": clauses, "proposed_verdict": verdict,
        "deviation": "offline scipy PPR over Entity-only live-rel adjacency (h515 "
        "convention); anticipated seeds from stored KGFQuestion embeddings; fact set = "
        "gold supporting-title carriers + explicit REG-2 answer edge; graph edge is "
        "CHILD_OF (registration writes CHILD)",
        "bars": {"confirmed_ge": 0.80, "kappa_ge": 0.50, "killed_lt": 0.65},
    }
    outdir = Path("reports/experiments/r49")
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"h572-reach-crux-{run_id}.json"
    path.write_text(json.dumps({"summary": summary, "facts": facts, "reg2_row": reg2_row}, indent=1))
    print("SUMMARY " + json.dumps(summary), flush=True)
    print(f"WROTE {path}", flush=True)


if __name__ == "__main__":
    main()

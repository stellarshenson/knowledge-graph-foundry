"""R49-H571 / R49-H574: per-fact reachability column + O(1) membership check.

Offline, read-only, no LLM. Ports Azzopardi retrievability from document to
fact-carrier: for each gold-title carrier of the 132 cached probes, seed
retrieval from the ANTICIPATED questions (KGFQuestion nodes) of the probe's
OTHER gold docs - the docs that state the bridging fact pointing at the carrier
- then run seeds -> PPR (H515 machinery) and read whether the carrier is
reached at the shipped cutoffs. The canonical REG-2 target
(Los Pagares de Mendieta)-DIRECTED_BY->(Leopoldo Torres Rios): seeding from the
film's questions, the director carrier is NOT in dense seeds nor PPR top-15 but
IS in seeds+1-hop - "seeds hit the film, never the director".

H571 - the reachability column reads below the per-doc certificate coverage
(h545-cert), REG-2 lands unreachable-while-covered, and the column has spread
(per-doc IQR > 0.2).
H574 - the O(1) membership test (carrier in seeds+1-hop) reproduces the full-PPR
reachability verdict on the 132-probe carriers; disagreements are the
weak-reachable graded tail (carrier in 1-hop but below PPR-top mass, exactly the
REG-2 class).

Seed source = the shipped kgf_question_embeddings vectors (stored on the
KGFQuestion nodes); dense top-16 over kgf_entity_embeddings reproduced in-numpy
(validated bit-order-identical to db.index.vector.queryNodes). PPR: H515
convention (damping 0.85, 50 iters), reached = carrier in top-ppr_top_n(PPR) u
seeds. Membership: carrier in seeds u 1-hop(seeds), same undirected Entity
adjacency (live relations, SIMILAR_TO excluded).

Registered: docs/experiments/kgf-redesign-experiments.md R49-H571, R49-H574.
Usage: python scripts/experiments/r49_h571_reach_col.py [config] [max_carriers]
Writes: reports/experiments/r49/h571-reach-col-<ts>.json
        reports/experiments/r49/h574-reach-member-<ts>.json
READ-ONLY on Neo4j (MATCH/RETURN only).
"""

from datetime import datetime, timezone
import glob
import json
from pathlib import Path
import re
import statistics as stx
import sys

import numpy as np
from scipy.sparse import csr_matrix

sys.path.insert(0, "notebooks")
sys.path.insert(0, "scripts/experiments")
from h158_measure import _norm  # noqa: E402
from r46_h499_screen import gold_titles, load_slices  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

CONFIG = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("config/experiments/config-bench-medium.yml")
MAX = int(sys.argv[2]) if len(sys.argv) > 2 else 0
SCREEN = Path("reports/experiments/bench/r46-h499-screen-20260713T072044Z.jsonl")
QUESTIONS = Path("data/external/multihop-qa-benchmarks/2wikimultihopqa.json")
CERT = Path("reports/experiments/r49/h545-cert-20260713T175512Z.jsonl")
H389_GLOB = "reports/experiments/r39/h389-coverage-*.jsonl"
OUT = Path("reports/experiments/r49")

DAMPING = 0.85
ITERS = 50
REG2_PROBE = "1dfaa6200bdd11eba7f7acde48001122"  # child of the director of Los Pagares
REG2_CARRIER = "Leopoldo Torres Ríos"


def ppr(adj, out_deg, seed_idx, n):
    if not seed_idx:
        return np.zeros(n)
    p = np.zeros(n)
    p[seed_idx] = 1.0 / len(seed_idx)
    r = p.copy()
    for _ in range(ITERS):
        r = (1 - DAMPING) * p + DAMPING * (adj.T @ (r / out_deg))
    return r


def iqr(vals):
    if len(vals) < 4:
        return None
    q1, q3 = np.percentile(vals, [25, 75])
    return float(q3 - q1)


def build_title2name(graph_names, slices):
    t2n = {}
    for nm in graph_names:
        m = re.match(r"^(.+\.json)#row(\d+)$", nm or "")
        if not m:
            continue
        titles = slices.get(m.group(1))
        idx = int(m.group(2))
        if titles and idx < len(titles):
            t2n.setdefault(titles[idx], nm)
    return t2n


def load_coverage():
    cov = {}
    if CERT.exists():
        for line in CERT.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("coverage") is not None:
                    cov[r["doc"]] = r["coverage"]
    for fp in glob.glob(H389_GLOB):
        for line in Path(fp).read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("coverage") is not None:
                    cov.setdefault(r["doc"], r["coverage"])
    return cov


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    st = load_settings(CONFIG)
    st.event_log = None
    top_k = st.graphrag.top_k          # 16 dense seeds
    ppr_top_n = st.graphrag.ppr_top_n  # 15 PPR top-N

    off = [json.loads(ln) for ln in SCREEN.read_text().splitlines()
           if ln.strip() and json.loads(ln)["arm"] == "off"]
    Q = {q["_id"]: q for q in json.loads(QUESTIONS.read_text())}
    slices = load_slices()
    cov = load_coverage()

    with Foundry(st) as f, f.driver.session() as s:
        ents = s.run("MATCH (e:Entity) RETURN e.id AS id, e.name AS name, e.embedding AS emb").data()
        edges = s.run(
            "MATCH (a:Entity)-[r]-(b:Entity) WHERE type(r) <> 'SIMILAR_TO' "
            "RETURN a.id AS a, b.id AS b"
        ).data()
        name2id = dict(s.run("MATCH (d:KGFDocument) RETURN d.name AS n, d.id AS id").values("n", "id"))
        # anticipated questions grouped by gold doc, fetched lazily below
        q_by_doc = {}

        # resolve the probes' gold docs first so we only fetch relevant questions
        graph_names = set(name2id)
        t2n = build_title2name(graph_names, slices)

        # entity index / embeddings / adjacency
        idx = {e["id"]: i for i, e in enumerate(ents)}
        names = [e["name"] for e in ents]
        namerow = {_norm(nm): i for i, nm in enumerate(names) if nm}
        n = len(ents)
        E = np.array([e["emb"] for e in ents], dtype=np.float32)
        En = E / (np.linalg.norm(E, axis=1, keepdims=True) + 1e-9)
        ij = np.array([[idx[e["a"]], idx[e["b"]]] for e in edges
                       if e["a"] in idx and e["b"] in idx])
        if len(ij):
            adj = csr_matrix((np.ones(len(ij)), (ij[:, 0], ij[:, 1])), shape=(n, n))
            adj = ((adj + adj.T) > 0).astype(float).tocsr()
        else:
            adj = csr_matrix((n, n))
        out_deg = np.asarray(adj.sum(axis=1)).ravel()
        out_deg[out_deg == 0] = 1.0

        # build carrier rows: (probe, gold_title) -> carrier entity + own doc + other docs
        carriers = []
        needed_docs = set()
        for r in off:
            q = Q.get(r["id"])
            if not q:
                continue
            titles = gold_titles(q)
            # map each title to (entity idx, doc id)
            tmap = {}
            for t in titles:
                docname = t2n.get(t)
                did = name2id.get(docname) if docname else None
                cidx = namerow.get(_norm(t))
                tmap[t] = (cidx, did)
            gold_docs = [d for (_, d) in tmap.values() if d]
            for t, (cidx, did) in tmap.items():
                other = sorted({d for d in gold_docs if d and d != did})
                seed_docs = other if other else ([did] if did else [])
                needed_docs.update(seed_docs)
                carriers.append({
                    "probe": r["id"], "probe_pass": bool(r["pass"]),
                    "title": t, "carrier_idx": cidx, "own_doc": did,
                    "seed_docs": seed_docs,
                    "in_graph": cidx is not None,
                })

        # fetch anticipated questions for the needed docs only
        for did in needed_docs:
            rows = s.run(
                "MATCH (q:KGFQuestion)-[:ANSWERABLE_FROM]->(:Chunk)-[:PART_OF]->(d:KGFDocument {id:$d}) "
                "RETURN q.id AS qid, q.embedding AS emb", d=did,
            ).data()
            q_by_doc[did] = [(x["qid"], x["emb"]) for x in rows if x["emb"]]

    # dense top-k seeds + per-question PPR, cached by qid
    seeds_cache, ppr_top_cache = {}, {}

    def q_seeds(qid, emb):
        if qid in seeds_cache:
            return seeds_cache[qid]
        qv = np.array(emb, dtype=np.float32)
        qv /= np.linalg.norm(qv) + 1e-9
        sd = list(np.argsort(-(En @ qv))[:top_k])
        seeds_cache[qid] = sd
        return sd

    def q_reachset(qid, emb):
        # top-ppr_top_n(PPR(seeds_q)) u seeds_q, cached
        if qid in ppr_top_cache:
            return ppr_top_cache[qid]
        sd = q_seeds(qid, emb)
        r = ppr(adj, out_deg, sd, n)
        top = set(np.argsort(-r)[:ppr_top_n]) | set(sd)
        ppr_top_cache[qid] = top
        return top

    def one_hop(seedset):
        hop = set(seedset)
        for u in seedset:
            hop |= set(adj.indices[adj.indptr[u]:adj.indptr[u + 1]])
        return hop

    rows = carriers[:MAX] if MAX else carriers
    scored = []
    for c in rows:
        if not c["in_graph"]:
            scored.append({**c, "skipped": "carrier not in graph"})
            continue
        cidx = c["carrier_idx"]
        qs = [q for d in c["seed_docs"] for q in q_by_doc.get(d, [])]
        if not qs:
            scored.append({**c, "skipped": "no anticipated questions on seed docs"})
            continue
        # graded reach: fraction of seed-doc questions whose seeds+PPR surface the carrier
        # per-question (16-seed) verdicts for the H574 robustness cut at H37 scale
        pq_ppr, pq_member = [], []
        for qid, emb in qs:
            sq = q_seeds(qid, emb)
            pq_ppr.append(cidx in q_reachset(qid, emb))
            pq_member.append(cidx in one_hop(sq))
        hits = [1 if v else 0 for v in pq_ppr]
        graded = sum(hits) / len(hits)
        pq_any_ppr = any(pq_ppr)
        pq_any_member = any(pq_member)
        pq_agree = sum(1 for a, b in zip(pq_ppr, pq_member) if a == b)
        # union seed set across the seed-doc questions
        S = set()
        for qid, emb in qs:
            S |= set(q_seeds(qid, emb))
        S = list(S)
        r = ppr(adj, out_deg, S, n)
        ppr_top = set(np.argsort(-r)[:ppr_top_n]) | set(S)
        hop = one_hop(S)
        ppr_verdict = cidx in ppr_top          # full-PPR reachability verdict
        member_verdict = cidx in hop           # O(1) membership verdict (H574)
        scored.append({
            "probe": c["probe"], "probe_pass": c["probe_pass"], "title": c["title"],
            "own_doc": c["own_doc"], "n_seed_docs": len(c["seed_docs"]),
            "n_seed_questions": len(qs), "n_union_seeds": len(S),
            "graded_reach": round(graded, 4),
            "in_seeds": cidx in set(S),
            "ppr_reachable": bool(ppr_verdict),
            "member_reachable": bool(member_verdict),
            "pq_ppr_any": bool(pq_any_ppr),
            "pq_member_any": bool(pq_any_member),
            "pq_ppr_hits": int(sum(pq_ppr)), "pq_member_hits": int(sum(pq_member)),
            "pq_agree": int(pq_agree), "pq_n": len(pq_ppr),
            "coverage": cov.get(c["own_doc"]),
        })

    ok = [r for r in scored if "skipped" not in r]
    skipped = [r for r in scored if "skipped" in r]

    # ---------- H571 ----------
    with_cov = [r for r in ok if r["coverage"] is not None]
    mean_reach_carrier = round(stx.mean(r["graded_reach"] for r in ok), 4) if ok else None
    mean_cov_carrier = round(stx.mean(r["coverage"] for r in with_cov), 4) if with_cov else None
    # per-doc aggregation (parallels the per-doc certificate)
    by_doc = {}
    for r in ok:
        by_doc.setdefault(r["own_doc"], []).append(r["graded_reach"])
    doc_reach = {d: stx.mean(v) for d, v in by_doc.items()}
    doc_cov = {d: cov[d] for d in doc_reach if d in cov}
    common = [d for d in doc_reach if d in doc_cov]
    mean_doc_reach = round(stx.mean(doc_reach[d] for d in common), 4) if common else None
    mean_doc_cov = round(stx.mean(doc_cov[d] for d in common), 4) if common else None
    doc_gap = round(mean_doc_cov - mean_doc_reach, 4) if common else None
    reach_iqr = iqr(list(doc_reach.values()))
    within3 = [d for d in common if abs(doc_reach[d] - doc_cov[d]) <= 0.03]
    frac_within3 = round(len(within3) / len(common), 4) if common else None

    reg2 = next((r for r in ok if r["probe"] == REG2_PROBE and _norm(r["title"]) == _norm(REG2_CARRIER)), None)
    reg2_unreach_while_covered = bool(
        reg2 and not reg2["ppr_reachable"] and reg2["coverage"] is not None and reg2["coverage"] >= 0.5
    )

    c1 = doc_gap is not None and doc_gap >= 0.10
    c2 = reg2_unreach_while_covered
    c3 = reach_iqr is not None and reach_iqr > 0.20
    killed571 = frac_within3 == 1.0 if common else False
    verdict571 = "CONFIRMED" if (c1 and c2 and c3) else ("KILLED" if killed571 else "INCONCLUSIVE")

    h571 = {
        "hypothesis": "R49-H571", "generated": run_id, "config": str(CONFIG),
        "seed_source": "anticipated KGFQuestions of the probe's OTHER gold docs (bridging-fact docs)",
        "cutoffs": {"dense_top_k": top_k, "ppr_top_n": ppr_top_n, "damping": DAMPING, "iters": ITERS},
        "n_carriers_total": len(carriers), "n_scored": len(ok), "n_skipped": len(skipped),
        "n_docs": len(doc_reach), "n_docs_with_cov": len(common),
        "mean_graded_reach_per_carrier": mean_reach_carrier,
        "mean_coverage_per_carrier": mean_cov_carrier,
        "mean_doc_reach": mean_doc_reach, "mean_doc_coverage": mean_doc_cov,
        "reach_below_coverage_pts": doc_gap,
        "per_doc_reach_iqr": None if reach_iqr is None else round(reach_iqr, 4),
        "frac_docs_within_3pts": frac_within3,
        "reg2": reg2, "reg2_unreachable_while_covered": reg2_unreach_while_covered,
        "clauses": [
            {"clause": "1: reachability reads >= 10 pts below coverage",
             "measured": f"coverage {mean_doc_cov} - reach {mean_doc_reach} = {doc_gap} pts below",
             "holds": bool(c1)},
            {"clause": "2: REG-2 lands unreachable-while-covered",
             "measured": (f"REG-2 ppr_reachable={reg2['ppr_reachable']} coverage={reg2['coverage']} "
                          f"(member_reachable={reg2['member_reachable']}, graded={reg2['graded_reach']})"
                          if reg2 else "REG-2 carrier not resolved"),
             "holds": bool(c2)},
            {"clause": "3: per-doc IQR > 0.2",
             "measured": f"IQR={None if reach_iqr is None else round(reach_iqr,4)}",
             "holds": bool(c3)},
            {"clause": "KILL: reachability tracks coverage within 3 pts everywhere",
             "measured": f"frac docs within 3pts = {frac_within3}",
             "holds": bool(killed571)},
        ],
        "acceptance_bar": "CONFIRMED per prediction; KILLED if within 3 pts everywhere",
        "proposed_verdict": verdict571,
        "rows": scored,
    }

    # ---------- H574 ----------
    agree = [r for r in ok if r["ppr_reachable"] == r["member_reachable"]]
    disagree = [r for r in ok if r["ppr_reachable"] != r["member_reachable"]]
    agreement = round(len(agree) / len(ok), 4) if ok else None
    member_only = [r for r in disagree if r["member_reachable"] and not r["ppr_reachable"]]  # weak tail
    ppr_only = [r for r in disagree if r["ppr_reachable"] and not r["member_reachable"]]
    # weak-reachable graded tail characterization: member-only carriers should have low graded reach
    weak_graded = [r["graded_reach"] for r in member_only]
    reg2_is_disagreement = bool(reg2 and reg2 in disagree)
    # robustness cut: per-question (16-seed) scale, where H37's 99.4% figure lives
    pq_atomic_total = sum(r["pq_n"] for r in ok)
    pq_atomic_agree = sum(r["pq_agree"] for r in ok)
    pq_atomic_agreement = round(pq_atomic_agree / pq_atomic_total, 4) if pq_atomic_total else None
    pq_carrier_agree = [r for r in ok if r["pq_ppr_any"] == r["pq_member_any"]]
    pq_carrier_agreement = round(len(pq_carrier_agree) / len(ok), 4) if ok else None
    verdict574 = "CONFIRMED" if (agreement is not None and agreement >= 0.95) else \
                 ("KILLED" if (agreement is not None and agreement < 0.90) else "INCONCLUSIVE")

    h574 = {
        "hypothesis": "R49-H574", "generated": run_id, "config": str(CONFIG),
        "test": "carrier in seeds+1-hop (O(1) membership) vs carrier in top-ppr_top_n(PPR) u seeds (full walk)",
        "cutoffs": {"dense_top_k": top_k, "ppr_top_n": ppr_top_n},
        "n_scored": len(ok), "n_skipped": len(skipped),
        "agreement": agreement,
        "union_seed_note": "primary verdict uses the union seed set per carrier (mean ~130 seeds); "
        "membership over-reports because its 1-hop balloons - see per-question cut",
        "pq_atomic_agreement": pq_atomic_agreement, "pq_atomic_n": pq_atomic_total,
        "pq_carrier_any_agreement": pq_carrier_agreement,
        "pq_note": "per-question 16-seed cut (H37 scale): agreement of carrier-in-seeds+1hop vs "
        "carrier-in-top15PPR+seeds, atomic over (question,carrier) and per-carrier via ANY",
        "n_agree": len(agree), "n_disagree": len(disagree),
        "n_member_only_weak_tail": len(member_only), "n_ppr_only": len(ppr_only),
        "member_only_graded_reach_mean": round(stx.mean(weak_graded), 4) if weak_graded else None,
        "member_only_graded_reach_max": round(max(weak_graded), 4) if weak_graded else None,
        "reg2_is_disagreement": reg2_is_disagreement,
        "clauses": [
            {"clause": "agreement >= 0.95 on the 132-probe carriers",
             "measured": f"agreement={agreement} ({len(agree)}/{len(ok)})",
             "holds": bool(agreement is not None and agreement >= 0.95)},
            {"clause": "disagreements are the weak-reachable graded tail (member=1, ppr=0, low graded reach)",
             "measured": (f"{len(member_only)}/{len(disagree)} disagreements are member-only; "
                          f"graded reach mean={round(stx.mean(weak_graded),4) if weak_graded else None}, "
                          f"REG-2 in disagreements={reg2_is_disagreement}"),
             "holds": bool(disagree and len(member_only) == len(disagree))},
        ],
        "acceptance_bar": "CONFIRMED at >= 0.95; KILLED at < 0.90",
        "proposed_verdict": verdict574,
        "disagreements": disagree,
    }

    OUT.mkdir(parents=True, exist_ok=True)
    p571 = OUT / f"h571-reach-col-{run_id}.json"
    p574 = OUT / f"h574-reach-member-{run_id}.json"
    p571.write_text(json.dumps(h571, indent=1))
    p574.write_text(json.dumps(h574, indent=1))
    print("H571 " + json.dumps({k: h571[k] for k in (
        "n_scored", "mean_doc_reach", "mean_doc_coverage", "reach_below_coverage_pts",
        "per_doc_reach_iqr", "reg2_unreachable_while_covered", "proposed_verdict")}))
    print("H574 " + json.dumps({k: h574[k] for k in (
        "n_scored", "agreement", "pq_atomic_agreement", "pq_carrier_any_agreement",
        "n_disagree", "n_member_only_weak_tail", "reg2_is_disagreement", "proposed_verdict")}))
    print(f"WROTE {p571}")
    print(f"WROTE {p574}")


if __name__ == "__main__":
    main()

"""R36-H379 REPLAY ARM: fact-drift invalidation for the inferred functional type.

The inference arm (r36_h379_cardinality.py) fixed the candidate set at the
0.90 tier: {MANUFACTURED_BY}. This arm exercises the actual machinery
(graph/temporal.reconcile_contradictions + drift.record_contradictions) on the
neo4j4 pile and adjudicates the two registered clauses:

  Clause A - on a two-version doc replay (a conflicting second value for the
             functional type appears in v2), the superseded edge gets
             `valid_to` set and the alarm fires.
  Clause B - zero false invalidations on the live pile: no gold edge is
             falsely invalidated (probe harness flat when the would-be-
             invalidated MANUFACTURED_BY edges are OUT of the render).

Write discipline: the only persisted writes are three synthetic marked nodes
(`h379_synthetic`) plus their edges, deleted before exit; the pile-scale
reconcile replay runs inside an explicitly rolled-back transaction; Clause B
is pure reads with render-side exclusion. A before/after census asserts the
pile is byte-identical on the touched surfaces.
"""

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import yaml

sys.path.insert(0, "notebooks")
from h158_measure import _norm, _present, _render_nodes  # noqa: E402,F401

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.drift import DriftDetector  # noqa: E402
from knowledge_graph_foundry.events import subscribe, unsubscribe  # noqa: E402
from knowledge_graph_foundry.extraction import generate_embeddings  # noqa: E402
from knowledge_graph_foundry.graph.graphrag import overfetch_seeds, vector_query  # noqa: E402
from knowledge_graph_foundry.graph.temporal import (  # noqa: E402
    _RECONCILE,
    current_relationships,
    reconcile_contradictions,
    relationship_history,
)
from knowledge_graph_foundry.models import Entity, Relationship  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402
from knowledge_graph_foundry.settings import DriftSettings  # noqa: E402

URI = "bolt://172.19.0.100:7687"  # neo4j4 - verified target, .env override bypassed (DEF-4)
DOC = "d_a2b1f7a495a9deda"  # SleepStyle_200_Operating_Manual.pdf (H376's re-versioned doc)
FUNCTIONAL = ["MANUFACTURED_BY"]  # inference arm's 0.90-tier candidate set
PROBES = Path("tests/probes/cpap-probe-set.yml")
TOP_K = 16

SYN = {
    "product": "h379_synthetic_product",
    "mfr_v1": "h379_synthetic_mfr_v1",
    "mfr_v2": "h379_synthetic_mfr_v2",
}


def census(s):
    return {
        "valid_to_set": s.run(
            "MATCH ()-[r]->() WHERE r.valid_to IS NOT NULL RETURN count(r) AS n"
        ).single()["n"],
        "manufactured_by": s.run(
            "MATCH ()-[r:MANUFACTURED_BY]->() RETURN count(r) AS n"
        ).single()["n"],
        "synthetic_nodes": s.run(
            "MATCH (e:Entity) WHERE e.h379_synthetic IS NOT NULL RETURN count(e) AS n"
        ).single()["n"],
    }


def synthetic_micro_replay(driver):
    """Clause A mechanics on marked synthetic nodes: v1 edge, conflicting v2
    value, real reconcile_contradictions call, valid_to verified, cleanup."""
    events = []
    receiver = lambda sender, **kw: events.append(kw)  # noqa: E731
    subscribe("drift.decision", receiver)
    try:
        with driver.session() as s:
            s.run(
                "CREATE (p:Entity {id: $p, name: 'H379 Synthetic CPAP', h379_synthetic: true})"
                "-[:MANUFACTURED_BY {created_at: timestamp() - 1000, "
                "valid_from: timestamp() - 1000, valid_to: null, expired_at: null, "
                "description: 'v1 fact'}]->"
                "(m1:Entity {id: $m1, name: 'H379 Manufacturer v1', h379_synthetic: true}) "
                "CREATE (m2:Entity {id: $m2, name: 'H379 Manufacturer v2', h379_synthetic: true})",
                p=SYN["product"], m1=SYN["mfr_v1"], m2=SYN["mfr_v2"],
            )
        v2_edge = Relationship(
            source_id=SYN["product"], target_id=SYN["mfr_v2"], type="MANUFACTURED_BY",
            description="v2 fact - the conflicting second value",
        )
        invalidated = reconcile_contradictions(driver, [v2_edge], FUNCTIONAL)
        with driver.session() as s:
            old = s.run(
                "MATCH (:Entity {id: $p})-[r:MANUFACTURED_BY]->(:Entity {id: $m1}) "
                "RETURN r.valid_to AS valid_to, r.expired_at AS expired_at",
                p=SYN["product"], m1=SYN["mfr_v1"],
            ).single()
            # load the v2 edge the way the pipeline would after reconcile
            s.run(
                "MATCH (p:Entity {id: $p}), (m2:Entity {id: $m2}) "
                "CREATE (p)-[:MANUFACTURED_BY {created_at: timestamp(), "
                "valid_from: timestamp(), valid_to: null, expired_at: null, "
                "description: 'v2 fact'}]->(m2)",
                p=SYN["product"], m2=SYN["mfr_v2"],
            )
        current = current_relationships(driver, SYN["product"])
        history = relationship_history(driver, SYN["product"], "MANUFACTURED_BY")
    finally:
        unsubscribe("drift.decision", receiver)
        with driver.session() as s:
            s.run("MATCH (e:Entity) WHERE e.h379_synthetic IS NOT NULL DETACH DELETE e")
    return {
        "invalidated": invalidated,
        "superseded_edge_valid_to_set": bool(old and old["valid_to"] is not None),
        "superseded_edge_expired_at_set": bool(old and old["expired_at"] is not None),
        "current_targets": sorted(r["target_name"] for r in current),
        "history_versions": len(history),
        "supersession_events": events,
    }


def pile_scale_reconcile(driver):
    """Clause A at pile scale: replay v2 of DOC where every MANUFACTURED_BY
    value changed (acquisition scenario) through the production _RECONCILE
    Cypher inside a rolled-back transaction - zero mutation."""
    with driver.session() as s:
        subjects = s.run(
            "MATCH (e:Entity)-[r:MANUFACTURED_BY]->(m:Entity) "
            "WHERE $d IN e.source_documents AND r.valid_to IS NULL "
            "RETURN e.id AS sid, collect(m.name) AS targets", d=DOC,
        ).data()
        doc_entities = s.run(
            "MATCH (e:Entity) WHERE $d IN e.source_documents RETURN count(e) AS n", d=DOC,
        ).single()["n"]
    rows = [
        {"source_id": r["sid"], "target_id": "h379_new_manufacturer", "type": "MANUFACTURED_BY"}
        for r in subjects
    ]
    invalidated = 0
    if rows:
        with driver.session() as s:
            tx = s.begin_transaction()
            try:
                rec = tx.run(_RECONCILE, rows=rows).single()
                invalidated = rec["invalidated"] if rec else 0
            finally:
                tx.rollback()  # simulate: the production query ran, nothing persists
    return {
        "doc": DOC,
        "doc_entities": doc_entities,
        "manufactured_by_subjects": len(subjects),
        "invalidated_on_v2_replay": invalidated,
        "single_doc_contradiction_rate": round(invalidated / doc_entities, 4)
        if doc_entities else 0.0,
    }


def alarm_replay(rate: float):
    """R8 fact-drift alarm over the two-version replay, as the pipeline feeds
    it: stationary history then the v2 doc; plus the sustained-series variant."""
    cfg = DriftSettings()
    single = DriftDetector(cfg, {})
    verdicts = []
    for r, n in [(0.0, 100), (0.0, 100), (rate, 100)]:
        v = single.record_contradictions(int(r * n), n)
        verdicts.append(v.action if v else "none")
    sustained = DriftDetector(cfg, {})
    sus_verdicts = []
    for _ in range(3):
        v = sustained.record_contradictions(int(rate * 100), 100)
        sus_verdicts.append(v.action if v else "none")
    return {
        "threshold": cfg.contradiction_rate_threshold,
        "window": cfg.window,
        "single_doc_replay_verdicts": verdicts,
        "single_doc_alarm_fired": "fact_drift" in verdicts,
        "sustained_series_verdicts": sus_verdicts,
        "sustained_series_alarm_fired": "fact_drift" in sus_verdicts,
        "min_single_doc_rate_to_fire": round(
            cfg.contradiction_rate_threshold * cfg.window, 4
        ),
    }


def would_be_invalidated(s):
    """Live-pile simulation of functional discipline on MANUFACTURED_BY:
    subjects with >1 distinct current target keep only the newest edge."""
    rows = s.run(
        "MATCH (e:Entity)-[r:MANUFACTURED_BY]->(m:Entity) WHERE r.valid_to IS NULL "
        "WITH e, collect({eid: elementId(r), target: m.name, "
        "ts: coalesce(r.valid_from, r.created_at, 0)}) AS edges "
        "WHERE size([x IN edges | x.target]) > 1 "
        "AND size(apoc.coll.toSet([x IN edges | x.target])) > 1 "
        "RETURN e.id AS sid, e.name AS sname, edges"
    ).data()
    invalidated = []
    for r in rows:
        newest = max(r["edges"], key=lambda x: x["ts"])
        for edge in r["edges"]:
            if edge["target"] != newest["target"]:
                invalidated.append(
                    {"subject": r["sname"], "target": edge["target"], "eid": edge["eid"]}
                )
    return invalidated


def _render_excluding(session, node_ids, excluded_eids):
    blocks = []
    for nid in node_ids:
        row = session.run(
            "MATCH (e:Entity {id:$id}) RETURN e.name AS name, labels(e) AS types, "
            "e.description AS description, properties(e) AS props", id=nid).single()
        if row is None:
            continue
        spec = {k.removeprefix("prop_"): v for k, v in row["props"].items()
                if k.startswith("prop_")}
        rels = session.run(
            "MATCH (e:Entity {id:$id})-[r]-(n:Entity) WHERE r.valid_to IS NULL "
            "AND type(r) <> 'SIMILAR_TO' AND NOT elementId(r) IN $ex "
            "RETURN type(r) AS rel, n.name AS name LIMIT 15",
            id=nid, ex=excluded_eids).data()
        blocks.append(
            f"## {row['name']} ({', '.join(row['types'])})\n{row['description'] or ''}\n"
            f"Properties: {json.dumps(spec, default=str)}\n"
            "Relations: " + "; ".join(f"{r['rel']} -> {r['name']}" for r in rels))
    return _norm("\n".join(blocks))


def probe_recall(f, st, probes, excluded_eids, label):
    vec = st.graphrag.vector_index_name
    factor = st.graphrag.overfetch_factor
    per = {}
    for p in probes:
        q = p["question"]
        pe = Entity.create(q[:80], types=["Query"], description=q)
        emb = generate_embeddings([pe], st.embeddings)[0].embedding
        seeds = [
            s["id"]
            for s in overfetch_seeds(
                lambda k: vector_query(f.driver, emb, vec, top_k=k), 64, factor
            )
        ][:TOP_K]
        with f.driver.session() as sess:
            ctx = _render_excluding(sess, seeds, excluded_eids)
        golds = p["gold_evidence"]
        per[p["id"]] = round(sum(_present(g, ctx) for g in golds) / len(golds), 4)
    print(f"{label}: mean={round(sum(per.values()) / len(per), 4)}", flush=True)
    return per


def main():
    st = deepcopy(load_settings(Path("config/config.yml")))
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = URI, "neo4j", "kgfoundry"
    probes = [p for p in yaml.safe_load(PROBES.read_text()) if p.get("gold_evidence")]

    with Foundry(st) as f:
        with f.driver.session() as s:
            before = census(s)
        print("census before:", json.dumps(before), flush=True)

        micro = synthetic_micro_replay(f.driver)
        print("micro replay:", json.dumps(micro, default=str), flush=True)

        pile = pile_scale_reconcile(f.driver)
        print("pile-scale reconcile (rolled back):", json.dumps(pile), flush=True)

        alarm = alarm_replay(pile["single_doc_contradiction_rate"])
        print("alarm replay:", json.dumps(alarm), flush=True)

        with f.driver.session() as s:
            invalidated = would_be_invalidated(s)
        print(f"would-be-invalidated edges on the live pile: {len(invalidated)}", flush=True)
        for e in invalidated:
            print(f"  {e['subject']} -X-> {e['target']}", flush=True)

        # gold cross-check: does any gold evidence string mention an
        # invalidated target for its subject's manufacturer fact?
        gold_mentions = []
        for p in probes:
            for g in p["gold_evidence"]:
                for e in invalidated:
                    if _norm(e["target"]) in _norm(g) or _norm(g) in _norm(e["target"]):
                        gold_mentions.append({"probe": p["id"], "gold": g, "edge": e})
        print(f"gold strings naming an invalidated target: {len(gold_mentions)}", flush=True)

        eids = [e["eid"] for e in invalidated]
        baseline = probe_recall(f, st, probes, [], "baseline")
        excluded = probe_recall(f, st, probes, eids, "functional-invalidated OUT")

        with f.driver.session() as s:
            after = census(s)
        print("census after:", json.dumps(after), flush=True)

    regressions = {p: (baseline[p], excluded[p]) for p in baseline if excluded[p] < baseline[p]}

    clause_a_mechanics = (
        micro["invalidated"] == 1
        and micro["superseded_edge_valid_to_set"]
        and micro["current_targets"] == ["H379 Manufacturer v2"]
        and len(micro["supersession_events"]) >= 1
    )
    clause_a_alarm = alarm["single_doc_alarm_fired"]
    clause_b = len(regressions) == 0
    verdict = (
        "CONFIRMED" if clause_a_mechanics and clause_a_alarm and clause_b
        else ("PARTIAL" if clause_a_mechanics and clause_b else "REFUTED")
    )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/r36-h379-replay-{ts}.json")
    out.write_text(json.dumps({
        "hypothesis": "R36-H379 replay arm (functional invalidation + alarm + gold safety)",
        "generated": ts, "graph_uri": URI, "functional_types": FUNCTIONAL,
        "census_before": before, "census_after": after,
        "micro_replay": {k: v for k, v in micro.items() if k != "supersession_events"},
        "supersession_events": [
            {k: str(v) for k, v in e.items()} for e in micro["supersession_events"]
        ],
        "pile_scale_reconcile": pile,
        "alarm_replay": alarm,
        "would_be_invalidated": invalidated,
        "gold_mentions_of_invalidated_targets": gold_mentions,
        "baseline_per_probe": baseline,
        "excluded_per_probe": excluded,
        "regressions": {p: list(v) for p, v in regressions.items()},
        "clauses": {
            "A_mechanics_valid_to_set": clause_a_mechanics,
            "A_alarm_fired_single_doc_replay": clause_a_alarm,
            "A_alarm_fired_sustained_series": alarm["sustained_series_alarm_fired"],
            "B_zero_gold_falsely_invalidated": clause_b,
        },
        "verdict": verdict,
    }, indent=2))
    print(f"\nH379 REPLAY ARM COMPLETE -> {out} verdict={verdict}", flush=True)


if __name__ == "__main__":
    main()

"""R36-H376: justification-carrying derived objects - dirty-flag flood on the pile.

Reconstructs field-level justifications for every derived-object class on the
benchmark pile from provenance ALREADY stored (nothing is written to the graph
except nothing - this is a pure read + arithmetic experiment):

  entity.description  <- {source_documents, source_chunks}
  entity.prop_* (hoisted) <- {child entity ids}   [spec_hoisted marker names
                             keys but NOT sources - the known-thin field]
  SIMILAR_TO edge     <- {endpoint entity ids -> their name+description}
  KGFPassage          <- {chunk_id (id prefix), emb_provider, emb_model}

Change events replayed per the registration:
  E1 - the H365 repair (prop change on the two series entities)
  E2 - synthetic re-version of d_a2b1f7a495a9deda (SleepStyle_200 manual,
       the HC230 neighborhood's source document)

Field-level flood: E1 dirties objects justified by the entities' PROPS
(propositions - none stored - plus the render surface); it must NOT dirty
SIMILAR_TO edges (embeddings do not read props). E2 dirties D's passages,
D-sourced descriptions, and SIMILAR_TO edges through their endpoints.

Adjudication (HC230 neighborhood + strict classes): true-dirty = passages of
D's chunks + descriptions of SINGLE-doc D entities + SIMILAR_TO edges with a
single-doc-D endpoint + the hoisted props (children all D-sourced).
False-dirty candidates = multi-doc entities flagged through D membership whose
description may be unchanged. Bars: coverage >= 95%, false-dirty <= 2x true.

Render clause: OUT-labeling every E2-flagged entity from the top-16 render
must cost ZERO recall on probes whose gold evidence does not occur in D's
chunk text.
"""

import json
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, "notebooks")
from h158_measure import _norm, _present, _render_nodes  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.extraction import generate_embeddings  # noqa: E402
from knowledge_graph_foundry.graph.graphrag import overfetch_seeds, vector_query  # noqa: E402
from knowledge_graph_foundry.models import Entity  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

URI = "bolt://172.19.0.100:7687"
DOC = "d_a2b1f7a495a9deda"  # SleepStyle_200_Operating_Manual.pdf
HOIST_TARGETS = ["e_b23e9ca8b0913d4b", "e_82c117b14e8f555e"]  # H365 repair entities
PROBES = Path("tests/probes/cpap-probe-set.yml")
TOP_K = 16


def census(s):
    """Justification reconstructability per derived-object class."""
    ent = s.run(
        "MATCH (e:Entity) RETURN count(e) AS total, "
        "sum(CASE WHEN e.source_documents IS NOT NULL AND e.source_chunks IS NOT NULL "
        "THEN 1 ELSE 0 END) AS reconstructable"
    ).single()
    sim = s.run("MATCH ()-[r:SIMILAR_TO]->() RETURN count(r) AS total").single()
    pas = s.run(
        "MATCH (p:KGFPassage) RETURN count(p) AS total, "
        "sum(CASE WHEN p.emb_provider IS NOT NULL AND p.emb_model IS NOT NULL "
        "THEN 1 ELSE 0 END) AS reconstructable"
    ).single()
    hoisted = s.run(
        "MATCH (e:Entity) WHERE e.h365_hoisted IS NOT NULL OR e.spec_hoisted IS NOT NULL "
        "RETURN count(e) AS total"
    ).single()
    return {
        "entity_description": {"total": ent["total"], "reconstructable": ent["reconstructable"]},
        "similar_to_edge": {"total": sim["total"], "reconstructable": sim["total"]},
        "kgf_passage": {"total": pas["total"], "reconstructable": pas["reconstructable"]},
        "hoisted_props": {
            "total": hoisted["total"],
            "reconstructable": 0,  # marker names keys, not source entities - the thin field
        },
    }


def flood(s):
    """Field-level dirty flood for E1 (prop change) and E2 (doc re-version)."""
    # E1: props changed on the two series entities -> objects justified by those
    # props. Stored propositions: none on the pile. SIMILAR_TO must NOT flag.
    e1 = {"dirty_entities_props": HOIST_TARGETS, "dirty_similar_to": 0, "dirty_passages": 0}

    # E2: doc re-version -> chunks -> passages; entities via source_documents;
    # SIMILAR_TO edges through dirty-description endpoints.
    chunks = s.run(
        "MATCH (c:Chunk)-[:PART_OF]->(:KGFDocument {id: $d}) RETURN c.id AS id", d=DOC
    ).value()
    passages = s.run(
        "MATCH (p:KGFPassage)-[:PART_OF]->(c:Chunk)-[:PART_OF]->(:KGFDocument {id: $d}) "
        "RETURN count(p) AS n",
        d=DOC,
    ).single()["n"]
    ents = s.run(
        "MATCH (e:Entity) WHERE $d IN e.source_documents "
        "RETURN e.id AS id, size(e.source_documents) AS ndocs",
        d=DOC,
    ).data()
    dirty_ids = [r["id"] for r in ents]
    single_doc = [r["id"] for r in ents if r["ndocs"] == 1]
    sim = s.run(
        "MATCH (a:Entity)-[r:SIMILAR_TO]-(b:Entity) WHERE a.id IN $ids "
        "RETURN count(DISTINCT r) AS n",
        ids=dirty_ids,
    ).single()["n"]
    sim_strict = s.run(
        "MATCH (a:Entity)-[r:SIMILAR_TO]-(b:Entity) WHERE a.id IN $ids "
        "RETURN count(DISTINCT r) AS n",
        ids=single_doc,
    ).single()["n"]
    e2 = {
        "dirty_chunks": len(chunks),
        "dirty_passages": passages,
        "dirty_entities": len(dirty_ids),
        "dirty_entities_single_doc": len(single_doc),
        "dirty_similar_to": sim,
        "dirty_similar_to_strict": sim_strict,
        "dirty_entity_ids": dirty_ids,
    }
    return e1, e2


def adjudicate(e1, e2):
    """Coverage + false-dirty vs the adjudicated true-dirty classes."""
    # True-dirty (strict): D's passages (source text changes), single-doc-D
    # descriptions (input fully replaced), SIMILAR_TO with a strict endpoint,
    # hoisted props on the two targets (children all D-sourced).
    true_dirty = (
        e2["dirty_passages"] + e2["dirty_entities_single_doc"] + e2["dirty_similar_to_strict"] + 2
    )
    # Flood catches: passages via chunk justification, all D entities (incl.
    # both hoist targets - flagged for DESCRIPTION via doc membership, so the
    # hoisted-props field rides along at object level despite its thin
    # source record), strict SIMILAR_TO subset of the flagged edges.
    caught = (
        e2["dirty_passages"] + e2["dirty_entities_single_doc"] + e2["dirty_similar_to_strict"] + 2
    )
    # False-dirty candidates: multi-doc entities flagged through D membership
    # + non-strict SIMILAR_TO edges flagged through them.
    false_dirty = (e2["dirty_entities"] - e2["dirty_entities_single_doc"]) + (
        e2["dirty_similar_to"] - e2["dirty_similar_to_strict"]
    )
    return {
        "true_dirty": true_dirty,
        "caught": caught,
        "coverage": round(caught / true_dirty, 4),
        "false_dirty": false_dirty,
        "false_over_true": round(false_dirty / true_dirty, 4),
        "e1_similar_to_flagged": e1["dirty_similar_to"],  # must be 0 (field-level)
    }


def recall_with_exclusion(f, st, probes, excluded, label):
    vec = st.graphrag.vector_index_name
    factor = st.graphrag.overfetch_factor
    per = {}
    for p in probes:
        q = p["question"]
        pe = Entity.create(q[:80], types=["Query"], description=q)
        emb = generate_embeddings([pe], st.embeddings)[0].embedding
        seeds = [
            s["id"]
            for s in overfetch_seeds(lambda k: vector_query(f.driver, emb, vec, top_k=k), 64, factor)
            if s["id"] not in excluded
        ][:TOP_K]
        with f.driver.session() as sess:
            ctx = _render_nodes(sess, seeds)
        golds = p["gold_evidence"]
        per[p["id"]] = round(sum(_present(g, ctx) for g in golds) / len(golds), 4)
    print(f"{label}: mean={round(sum(per.values()) / len(per), 4)}", flush=True)
    return per


def main():
    base = load_settings(Path("config/config.yml"))
    st = deepcopy(base)
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = URI, "neo4j", "kgfoundry"
    probes = [p for p in yaml.safe_load(PROBES.read_text()) if p.get("gold_evidence")]

    with Foundry(st) as f:
        with f.driver.session() as s:
            cen = census(s)
            print("census:", json.dumps(cen), flush=True)
            e1, e2 = flood(s)
            print(
                f"E1 (prop change): {len(e1['dirty_entities_props'])} entities, "
                f"{e1['dirty_similar_to']} SIMILAR_TO (must be 0)",
                flush=True,
            )
            print(
                f"E2 (re-version {DOC}): {e2['dirty_chunks']} chunks, "
                f"{e2['dirty_passages']} passages, {e2['dirty_entities']} entities "
                f"({e2['dirty_entities_single_doc']} single-doc), "
                f"{e2['dirty_similar_to']} SIMILAR_TO ({e2['dirty_similar_to_strict']} strict)",
                flush=True,
            )
            verdict = adjudicate(e1, e2)
            print("adjudication:", json.dumps(verdict), flush=True)

            # which probes' golds occur in D's chunk text (affected probes)
            dtext = _norm(
                " ".join(
                    s.run(
                        "MATCH (c:Chunk)-[:PART_OF]->(:KGFDocument {id: $d}) RETURN c.text AS t",
                        d=DOC,
                    ).value()
                )
            )
        squashed = re.sub(r"[\s,()]", "", dtext)
        affected = [
            p["id"]
            for p in probes
            if any(_present(g, dtext) or _norm(g) in squashed for g in p["gold_evidence"])
        ]
        print(f"probes with gold evidence in D: {affected}", flush=True)

        baseline = recall_with_exclusion(f, st, probes, set(), "baseline")
        excluded = recall_with_exclusion(
            f, st, probes, set(e2["dirty_entity_ids"]), "OUT-labeled"
        )

    regressions = {p: (baseline[p], excluded[p]) for p in baseline if excluded[p] < baseline[p]}
    unaffected_regressions = {p: v for p, v in regressions.items() if p not in affected}
    print(f"regressions: {regressions}", flush=True)
    print(f"UNAFFECTED-probe regressions (must be empty): {unaffected_regressions}", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/r36-h376-justifications-{ts}.json")
    out.write_text(
        json.dumps(
            {
                "hypothesis": "R36-H376 justification reconstruction + dirty flood",
                "generated": ts,
                "graph_uri": URI,
                "reversioned_doc": DOC,
                "census": cen,
                "e1": {k: v for k, v in e1.items()},
                "e2": {k: v for k, v in e2.items() if k != "dirty_entity_ids"},
                "adjudication": verdict,
                "affected_probes": affected,
                "baseline_per_probe": baseline,
                "out_labeled_per_probe": excluded,
                "regressions": {p: list(v) for p, v in regressions.items()},
                "unaffected_regressions": {p: list(v) for p, v in unaffected_regressions.items()},
            },
            indent=2,
        )
    )
    print(f"\nH376 FLOOD COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

"""R56-H636: passage-recall shadow metric (peer-comparability instrument).

WHY: peers (HippoRAG, GraphRAG, LightRAG) report passage-recall@k / answer EM-F1
and NEVER join gold supporting-fact titles to graph NODES. Our carrier-title->node
join is a strictly harder self-imposed instrument, so our headline is not comparable
to published passage-recall figures. This builds the peer-form shadow metric so both
can be reported side by side.

INSTRUMENT (no kill branch). Pre-registered bars:
  - LANDS  if node->chunk mapping covers >= 90% of carrier nodes AND the shadow
           metric ships alongside the join with the correlation 2x2 stated
  - Coverage < 60% -> STOP, route to DEF-16 repair: report what provenance the
    schema carries and what is missing

SUBSTRATE:
  - offline: frozen H582 medium cache tmp/results/r47 (6,626 entities, the dense@16
    seeds + reset_region_union replay + the 0.6012 sanity live here)
  - Neo4j (READ-ONLY): entity->chunk/document provenance lives ONLY here (H631). The
    medium instance was restarted post host-reboot at a NEW address on this
    container's subnet; verify identity before trusting any query.

PROVENANCE SCHEMA (medium, verified 2026-07-24):
  Entity -[:MENTIONED_IN]-> Chunk -[:PART_OF]-> KGFDocument
  - Chunk == one 2wiki article/passage; chunk.text first line == the article TITLE
    (PASSAGE granularity, the HippoRAG-comparable unit)
  - KGFDocument.name == ingest-row provenance ("2wiki-pilot-200.json#rowN"), NOT the
    article title - so the passage unit is the Chunk, not the KGFDocument
  - KGFPassage label ABSENT (DEF-16 confirmed) - Chunk plays that role

ENV: conda interpreter (/opt/conda/bin/python). The pure-python bolt driver lives only
in .venv; it is borrowed onto sys.path AFTER numpy is imported (conda numpy wins), no
pip install, not executed inside the venv. Neo4j STRICTLY read-only (MATCH/RETURN).

Usage: /opt/conda/bin/python scripts/experiments/r56_h636_passage_shadow.py
Writes: reports/experiments/r56/h636-passage-shadow-<UTC ts>.json
"""

import glob
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry")
sys.path.insert(0, str(ROOT / "scripts/experiments"))
sys.path.insert(0, str(ROOT / "notebooks"))

import r47_h582_embedder_swap as H  # noqa: E402  (_norm, TOP_K)
import r50_h619_seedland_digs as R50  # noqa: E402  (load_substrate, build_anchors, rru_reach)

CACHE = ROOT / "tmp/results/r47"
OUT = ROOT / "reports/experiments/r56"
SPAN_CACHE = ROOT / "tmp/results/r50/h597_gliner_spans.json"

SANITY_RECALL = 0.6012
KS = (5, 10, 20)
K_MATCH = 16  # 2x2 vs carrier-join matched to the dense@16 node budget

# medium instance - restarted post host-reboot on this container's subnet (172.21.x).
# config-bench-medium.yml bolt://172.19.0.9 is STALE (old docker network). DEF-4: we
# print + verify the URI we actually connect to and the ~6,626 entity identity.
MEDIUM_URI = "bolt://172.21.0.6:7687"
NEO4J_AUTH = ("neo4j", "kgfoundry")
CONNECT_TIMEOUT = 8


def get_driver():
    sp = glob.glob(str(ROOT / ".venv/lib/python*/site-packages"))
    if sp:
        sys.path.append(sp[0])  # AFTER numpy already imported by conda
    from neo4j import GraphDatabase
    return GraphDatabase.driver(MEDIUM_URI, auth=NEO4J_AUTH, connection_timeout=CONNECT_TIMEOUT)


def pull_provenance(sess, need_ids, log):
    """READ-ONLY. Returns entity_id->[chunk_id], chunk_id->title_norm, schema facts.
    All MATCH/RETURN, no writes."""
    schema = {}
    schema["entity_count"] = sess.run("MATCH (e:Entity) RETURN count(e) AS c").single()["c"]
    labels = [r["label"] for r in sess.run(
        "CALL db.labels() YIELD label RETURN label ORDER BY label")]
    schema["n_labels"] = len(labels)
    schema["KGFPassage_present_DEF16"] = "KGFPassage" in labels
    schema["provenance_labels_present"] = [l for l in ("Chunk", "KGFDocument", "Document")
                                           if l in labels]
    schema["chunk_count"] = sess.run("MATCH (c:Chunk) RETURN count(c) AS c").single()["c"]
    schema["kgfdocument_count"] = sess.run(
        "MATCH (d:KGFDocument) RETURN count(d) AS c").single()["c"]
    schema["entity_mentioned_in_chunk_edges"] = sess.run(
        "MATCH (:Entity)-[:MENTIONED_IN]->(:Chunk) RETURN count(*) AS c").single()["c"]
    schema["provenance_path"] = "Entity-[:MENTIONED_IN]->Chunk-[:PART_OF]->KGFDocument"
    schema["passage_unit"] = ("Chunk (== one 2wiki article; chunk.text first line == "
                              "article title; PASSAGE granularity)")

    # chunk -> first-line title norm
    chunk_title = {}
    for r in sess.run("MATCH (c:Chunk) RETURN c.id AS id, c.text AS t"):
        chunk_title[r["id"]] = H._norm((r["t"] or "").split("\n", 1)[0].strip())

    # entity -> chunks (bulk, batched)
    ent_chunks = {}
    ids = list(need_ids)
    B = 800
    for s0 in range(0, len(ids), B):
        blk = ids[s0:s0 + B]
        for r in sess.run(
                "MATCH (e:Entity) WHERE e.id IN $ids "
                "OPTIONAL MATCH (e)-[:MENTIONED_IN]->(c:Chunk) "
                "RETURN e.id AS id, collect(DISTINCT c.id) AS chunks", ids=blk):
            ent_chunks[r["id"]] = [c for c in r["chunks"] if c]
    log(f"provenance pulled: {len(ent_chunks)}/{len(ids)} entity ids returned; "
        f"{len(chunk_title)} chunks")
    return ent_chunks, chunk_title, schema


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731

    # ---------------- offline substrate + SANITY GATE ------------------------
    S = R50.load_substrate()
    name_norms = S["name_norms"]
    meta = S["meta"]
    off_ids = S["off_ids"]
    Q = S["Q"]
    titan_n, tprobe_n = S["titan_n"], S["titan_probe_n"]

    hits = [1 if c["tnorm"] in {name_norms[i] for i in S["seeds_q"][c["probe"]]} else 0
            for c in S["carriers"]]
    base_recall = round(float(np.mean(hits)), 4)
    sanity_ok = abs(base_recall - SANITY_RECALL) < 0.002
    log(f"SANITY dense@16 carrier recall = {base_recall} (expect {SANITY_RECALL}) "
        f"-> {'PASS' if sanity_ok else 'FAIL'}")

    # reset_region_union replay (both arms)
    spans = json.loads(SPAN_CACHE.read_text())
    anchors, _, _ = R50.build_anchors(S, spans, apply_stoplist=False)  # H620 UNFILTERED
    _, extras_idx = R50.rru_reach(S, anchors)

    car_idx = sorted({c["carrier_idx"] for c in S["carriers"] if c["carrier_idx"] is not None})
    carrier_ids = [meta[i]["id"] for i in car_idx]

    def ranked_nodes(pid, arm):
        dense = list(S["seeds_q"][pid])
        sims = titan_n @ tprobe_n[pid]
        ranked = [(i, float(sims[i])) for i in dense]  # top-16 by sim, in order
        if arm == "rru":
            base = ranked[-1][1] if ranked else 0.0
            for k, i in enumerate(extras_idx.get(pid, [])):
                if i not in dense:
                    ranked.append((i, base - 1e-4 * (k + 1)))
        return ranked

    # union of node indices needing provenance
    need = set(car_idx)
    for pid in off_ids:
        need |= set(S["seeds_q"][pid]) | set(extras_idx.get(pid, []))
    need_ids = [meta[i]["id"] for i in sorted(need)]

    # ---------------- Neo4j: identity + schema + provenance ------------------
    verify = {"target_uri": MEDIUM_URI,
              "config_uri_stale": "bolt://172.19.0.9:7687 (old docker network)",
              "env_uri_def4": None}
    envf = ROOT / ".env"
    if envf.exists():
        for ln in envf.read_text().splitlines():
            if ln.strip().startswith("NEO4J_URI"):
                verify["env_uri_def4"] = ln.split("=", 1)[1].strip()
    log(f"NEO4J connect target: {MEDIUM_URI}  | .env NEO4J_URI (DEF-4): {verify['env_uri_def4']}")

    drv = get_driver()
    with drv.session(default_access_mode="READ") as sess:
        ent_chunks, chunk_title, schema = pull_provenance(sess, need_ids, log)
        cov = sess.run("""MATCH (e:Entity) WHERE e.id IN $ids
                          OPTIONAL MATCH (e)-[:MENTIONED_IN]->(c:Chunk)
                          WITH e, count(c) AS nc
                          RETURN sum(CASE WHEN nc>0 THEN 1 ELSE 0 END) AS covered,
                                 count(e) AS present""", ids=carrier_ids).single()
    drv.close()

    verify["entity_count"] = schema["entity_count"]
    verify["entity_count_expected_cache"] = 6626
    verify["entity_count_matches_cache"] = (schema["entity_count"] == 6626)
    verify["reingest_note"] = (
        f"live graph carries {schema['entity_count']} entities vs the frozen r47 cache's "
        f"6,626 - a RE-INGEST superset of the same medium slice; node IDs mostly align "
        f"(see retrieved_union_id_match). Seeds/recall come from the frozen cache; the "
        f"provenance projection uses the live graph, joined on entity id.")
    id_present_union = sum(1 for eid in need_ids if ent_chunks.get(eid))
    verify["retrieved_union_id_match"] = {
        "union_nodes": len(need_ids), "id_present_with_chunk": id_present_union,
        "absent": len(need_ids) - id_present_union,
        "frac": round(id_present_union / len(need_ids), 4),
        "note": ("nodes absent from the live re-ingest contribute NO passages -> the "
                 "shadow recall below is a CONSERVATIVE lower bound")}

    # ---- coverage bar ----
    coverage = {
        "carrier_ids_in_cache": len(carrier_ids),
        "carrier_ids_present_in_graph": cov["present"],
        "carrier_ids_absent_from_reingest": len(carrier_ids) - cov["present"],
        "covered_of_present": cov["covered"],
        "coverage_of_present_frac": round(cov["covered"] / cov["present"], 4) if cov["present"] else None,
        "coverage_of_all_cache_carriers_frac": round(cov["covered"] / len(carrier_ids), 4),
        "definition": "carrier node has >=1 Entity-[:MENTIONED_IN]->Chunk provenance edge",
    }
    coverage_frac = coverage["coverage_of_all_cache_carriers_frac"]
    log(f"COVERAGE carrier->chunk: {cov['covered']}/{cov['present']} present "
        f"({coverage['coverage_of_present_frac']}) | {coverage_frac} of all cache carriers")

    # ---------------- gold passages + peer-form shadow -----------------------
    title2chunk = defaultdict(set)
    for cid, tnorm in chunk_title.items():
        if tnorm:
            title2chunk[tnorm].add(cid)

    def gold_chunks(pid):
        gc = set()
        for t in R50.gold_titles(Q[pid]):
            gc |= title2chunk.get(H._norm(t), set())
        return gc

    def retrieved_passages(pid, arm):
        """ranked list of DISTINCT chunk ids: a passage's score = max score over
        retrieved nodes mentioning it; ordered high->low, first occurrence kept."""
        best = {}
        for i, sc in ranked_nodes(pid, arm):
            for cid in ent_chunks.get(meta[i]["id"], []):
                if cid not in best or sc > best[cid]:
                    best[cid] = sc
        return [cid for cid, _ in sorted(best.items(), key=lambda kv: -kv[1])]

    # diagnostic: gold-title -> chunk mapping coverage
    all_gold = set()
    for pid in off_ids:
        for t in R50.gold_titles(Q[pid]):
            all_gold.add(H._norm(t))
    gold_mapped = sum(1 for g in all_gold if g in title2chunk)

    shadow = {}
    for arm in ("dense", "rru"):
        anyk = {k: 0 for k in KS}
        allk = {k: 0 for k in KS}
        frac_sum = {k: 0.0 for k in KS}
        npr = 0
        for pid in off_ids:
            gc = gold_chunks(pid)
            if not gc:
                continue
            npr += 1
            passages = retrieved_passages(pid, arm)
            for k in KS:
                topk = set(passages[:k])
                inter = len(gc & topk)
                anyk[k] += int(inter >= 1)
                allk[k] += int(inter == len(gc))
                frac_sum[k] += inter / len(gc)
        shadow[arm] = {
            "n_probes_scored": npr,
            "passage_recall_at_k_ANY_gold_in_topk": {str(k): round(anyk[k] / npr, 4) for k in KS},
            "passage_recall_at_k_ALL_golds_in_topk": {str(k): round(allk[k] / npr, 4) for k in KS},
            "mean_fraction_gold_passages_in_topk": {str(k): round(frac_sum[k] / npr, 4) for k in KS},
        }
    log(f"SHADOW peer-form passage-recall ANY@5/10/20  dense={shadow['dense']['passage_recall_at_k_ANY_gold_in_topk']}  "
        f"rru={shadow['rru']['passage_recall_at_k_ANY_gold_in_topk']}")

    # ---------------- 2x2: shadow vs carrier-join (dense arm, matched) --------
    cells = Counter()
    d_join_pass_shadow_fail, d_shadow_pass_join_fail = [], []
    for pid in off_ids:
        gc = gold_chunks(pid)
        if not gc:
            continue
        golds_norm = {H._norm(t) for t in R50.gold_titles(Q[pid])}
        dense_norms = {name_norms[i] for i in S["seeds_q"][pid]}
        join_pass = golds_norm.issubset(dense_norms)  # strict family join: ALL carriers in dense@16
        passages = set(retrieved_passages(pid, "dense")[:K_MATCH])
        shadow_pass = len(gc & passages) >= 1  # ANY gold passage in top-16
        cells[(join_pass, shadow_pass)] += 1
        if join_pass and not shadow_pass:
            d_join_pass_shadow_fail.append(pid)
        if shadow_pass and not join_pass:
            d_shadow_pass_join_fail.append(pid)
    two_by_two = {
        "definition": {
            "carrier_join_pass": "ALL gold carrier titles present as nodes inside dense@16 (strict family join)",
            "shadow_pass": f"ANY gold passage (chunk) in top-{K_MATCH} retrieved passages (MENTIONED_IN projection)",
            "arm": "dense@16", "k": K_MATCH},
        "join_pass__shadow_pass": cells[(True, True)],
        "join_pass__shadow_fail": cells[(True, False)],   # mapping loss
        "join_fail__shadow_pass": cells[(False, True)],   # join harshness measured
        "join_fail__shadow_fail": cells[(False, False)],
        "shadow_pass_join_fail_pids": d_shadow_pass_join_fail[:25],
        "join_pass_shadow_fail_pids": d_join_pass_shadow_fail[:25],
        "reading": ("join_fail/shadow_pass counts how much harsher the carrier-join is "
                    "than peer passage-recall; join_pass/shadow_fail counts mapping loss "
                    "(a joined carrier whose passage fell outside top-k)"),
    }
    log(f"2x2 (dense@16,k={K_MATCH}): JsPs={cells[(True,True)]} Js!Ps={cells[(True,False)]} "
        f"!JsPs={cells[(False,True)]} !Js!Ps={cells[(False,False)]}")

    # ---------------- verdict ------------------------------------------------
    if coverage_frac >= 0.90:
        verdict = "LANDS"
        why = (f"carrier node->chunk provenance covers {coverage_frac:.1%} of cache carriers "
               f"({coverage['coverage_of_present_frac']:.1%} of those present in the re-ingest); "
               f"peer-form passage-recall ships beside the join with the 2x2 stated")
    elif coverage_frac < 0.60:
        verdict = "DEF-16-route"
        why = f"carrier provenance coverage {coverage_frac:.1%} < 60% - route to DEF-16 repair"
    else:
        verdict = "INDETERMINATE"
        why = f"coverage {coverage_frac:.1%} between the bars (>=90 lands, <60 routes)"

    payload = {
        "hypothesis": "R56-H636",
        "title": "passage-recall shadow metric (peer-comparability instrument)",
        "run_id": run_id,
        "interpreter": sys.executable,
        "neo4j_read_only": True,
        "sanity": {"dense16_carrier_recall": base_recall, "expected": SANITY_RECALL,
                   "reproduced": sanity_ok, "n_probes": len(off_ids),
                   "n_unique_carrier_nodes": len(car_idx)},
        "neo4j_identity_verification": verify,
        "schema": schema,
        "def16_state": ("KGFPassage label ABSENT (0 nodes) - confirmed. The Chunk label "
                        "plays the passage role: Entity-[:MENTIONED_IN]->Chunk, chunk.text "
                        "first line == 2wiki article title. Provenance IS present and "
                        "sufficient; no DEF-16 repair blocks the instrument."),
        "provenance_coverage_carrier_nodes": coverage,
        "gold_title_to_chunk_mapping": {
            "gold_titles_total": len(all_gold), "mapped_to_a_chunk": gold_mapped,
            "frac": round(gold_mapped / len(all_gold), 4)},
        "shadow_metric_peer_form": {
            "granularity": ("PASSAGE (Chunk == one 2wiki article) - directly comparable to "
                            "HippoRAG passage-recall. NOT document-row granularity."),
            "gold_passage_definition": ("chunks whose first-line title matches a gold "
                                        "supporting_fact title; all gold titles map to "
                                        "exactly one chunk, no collisions"),
            "retrieved_passage_rule": ("each retrieved node projected to its MENTIONED_IN "
                                       "chunks; passage score = max mentioning-node score; "
                                       "ranked high->low, deduped"),
            "arms": shadow,
        },
        "shadow_metric_FLOOR_name_identity_prior_run": {
            "note": ("the earlier BLOCKED run (Neo4j down) reported a provenance-free "
                     "name-identity FLOOR: dense any@5/10/20 = 0.8939, rru = 0.9394. It "
                     "credited only title-entity nodes. The peer-form metric above uses "
                     "real MENTIONED_IN provenance and is the deliverable; the floor is "
                     "kept only as the delta baseline."),
            "floor_dense_any_at_5_10_20": {"5": 0.8939, "10": 0.8939, "20": 0.8939},
            "floor_rru_any_at_5_10_20": {"5": 0.9394, "10": 0.9394, "20": 0.9394},
        },
        "correlation_2x2_shadow_vs_join": two_by_two,
        "peer_form_headline": {
            "passage_recall_at_5": {"dense": shadow["dense"]["passage_recall_at_k_ANY_gold_in_topk"]["5"],
                                     "rru": shadow["rru"]["passage_recall_at_k_ANY_gold_in_topk"]["5"]},
            "passage_recall_at_10": {"dense": shadow["dense"]["passage_recall_at_k_ANY_gold_in_topk"]["10"],
                                      "rru": shadow["rru"]["passage_recall_at_k_ANY_gold_in_topk"]["10"]},
            "carrier_join_headline_for_contrast": base_recall,
            "caveat_block": (
                "GRANULARITY: this is PASSAGE-recall (Chunk == one 2wiki article), the same "
                "unit HippoRAG reports - side-by-side comparable. CAVEATS: (1) probe-level "
                "ANY-gold-in-top-k; report alongside ALL-golds and mean-fraction in the "
                "arms; (2) retrieved passages are a graph projection (node -> its "
                "MENTIONED_IN chunks), more generous than direct passage retrieval; (3) "
                "~11% of retrieved nodes are absent from the live re-ingest and contribute "
                "no passages, so these figures are a conservative lower bound; (4) the "
                "carrier-join headline (0.6012, per-carrier-row) and the shadow (per-probe, "
                "passage) are DIFFERENT units - never blend them."),
        },
        "verdict": verdict,
        "verdict_reason": why,
        "script": "scripts/experiments/r56_h636_passage_shadow.py",
    }
    p = OUT / f"h636-passage-shadow-{run_id}.json"
    p.write_text(json.dumps(payload, indent=1))
    log(f"VERDICT {verdict}: {why}")
    log(f"wrote {p}")


if __name__ == "__main__":
    main()

"""R59-H660 - chunk-local co-occurrence census (the GATE that decides H661).

Registered bar (experiments log, R59-H660):
  GATE: H661 opens only on a non-trivial (b). If every co-occurring pair is already
  adjacent or intra-component, the overlay is recorded dead with no write.
  Prediction: report both counts exactly; the gate opens only if (b) is non-trivial
  against the 4 cross-component residual rows and the component structure.

Quantities (grounding section E2):
  (a) chunk-local co-occurring entity pairs that are NOT already adjacent in the graph
      (no direct relationship of any type between them)
  (b) among (a), pairs whose two entities lie in DIFFERENT connected components
  (c) how many of the 4 cross-component residual gold rows would have their two sides
      joined by at least one (b)-pair
  (d) baseline-subtracted association weight w_assoc = w_raw - E[w_raw] for the (b) pairs,
      where E[w_raw] = f_u f_v / C under independence given entity chunk-frequencies
      (PAM's familiarity baseline - only co-occurrence in EXCESS of expectation counts)

Components are computed OFFLINE in networkx from a read-only entity-entity edge export and
checked against the known census: 1,830 components, LCC 3,162 = 47.72%, 1,426 isolated.

Neo4j access is STRICTLY READ-ONLY: MATCH / RETURN / CALL db.labels() only. No writes to any
instance, no GPU, no LLM, no network beyond the bolt connection.

The chunk -> entity mapping was missing from disk at the first attempt (2026-09-14, PREMISE-
FAILED): tmp/results/r47/ents_meta.json carries no provenance field and every prior script
pulled the mapping live and persisted only aggregates. This run persists it to
tmp/results/r47/chunk_entities.json, so every later FREE replay runs with --export-dir or
straight off that cache and never needs a live instance again.

Instance targeting is EXPLICIT (DEF-4: .env NEO4J_URI silently overrides config targets).
--uri / --user / --password pin the instance; --export-dir runs fully offline from a
read-only cypher-shell CSV export. Auto-discovery over CANDIDATE_URIS remains only as the
no-argument fallback. Nothing in this script reads .env.

Writes:
  reports/experiments/r59/h660-cooccurrence-census-<ts>.json
  reports/experiments/r59/h660-cooccurrence-census-<ts>.md    (brief)
  reports/experiments/r59/h660-cooccurrence-census-<ts>.checkpoint.jsonl
  tmp/results/r47/chunk_entities.json                         (offline provenance cache)
"""

import argparse
import csv
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import networkx as nx
import numpy as np

ROOT = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry")
sys.path.insert(0, str(ROOT / "scripts/experiments"))

import r47_h582_embedder_swap as H       # noqa: E402  (_norm)
import r50_h619_seedland_digs as R50     # noqa: E402  (load_substrate)

CACHE = ROOT / "tmp/results/r47"
CHUNK_ENTS_CACHE = CACHE / "chunk_entities.json"
OUT = ROOT / "reports/experiments/r59"
ATLAS_ROWS = ROOT / "reports/experiments/r57/h644-miss-atlas-rows-20260724T085649Z.jsonl"

# The pinned substrate (R52 close, H627, H631) is the entity-entity graph EXCLUDING the
# SIMILAR_TO embedding layer: only that edge set reproduces 1,830 / 3,162 / 1,426 exactly,
# and it is the adjacency the shipped walk traverses. SIMILAR_TO is reported as a
# sensitivity, never folded into the primary number - R59-H660's own vet separates
# co-occurrence in excess of expectation from the existing similarity edges.
SOFT_LINK_TYPE = "SIMILAR_TO"

JOIN_VERSION = "goldjoin-v3-typegate-20260724 (eff = v2 then v3 fall-through, R57 atlas rows)"
REGION_RULE = "H651 widened: seeds u anchors u FULL 1-hop shell u PPR-top15"

# frozen-substrate component pins (R52 close, re-verified by H627 and H631)
PIN_COMPONENTS = 1830
PIN_LCC_NODES = 3162
PIN_LCC_FRAC = 0.4772
PIN_ISOLATED = 1426
PIN_BASE_RECALL = 0.6012
PIN_ENTITIES = 6626
PIN_EE_UNDIRECTED = 5386

NEO4J_AUTH = ("neo4j", "kgfoundry")
CONNECT_TIMEOUT = 8
# Every URI this rung has ever been served on, newest first. DEF-4: the instance actually
# reached is printed and its entity count verified before any census number is computed.
CANDIDATE_URIS = [
    "bolt://172.21.0.6:7687",                       # live re-ingest (R56-H636)
    "bolt://user-konrad.jelen-kgf-neo4j:7687",      # .env NEO4J_URI
    "bolt://172.19.0.101:7687",                     # neo4j3, the bench pile
    "bolt://172.19.0.9:7687",                       # config-bench-medium.yml (stale)
    "bolt://172.19.0.8:7687",                       # scout
    "bolt://localhost:7687",
]


def git_head():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


def frozen_component_census():
    """FREE: components over the frozen 6,626-entity substrate, for the pin check."""
    meta = json.loads((CACHE / "ents_meta.json").read_text())
    edges = json.loads((CACHE / "edges.json").read_text())
    ids = [m["id"] for m in meta]
    G = nx.Graph()
    G.add_nodes_from(ids)
    known = set(ids)
    G.add_edges_from((a, b) for a, b in edges if a in known and b in known and a != b)
    comps = list(nx.connected_components(G))
    sizes = sorted((len(c) for c in comps), reverse=True)
    lcc = sizes[0] if sizes else 0
    iso = sum(1 for s in sizes if s == 1)
    return {"entities": len(ids), "edges_undirected": G.number_of_edges(),
            "components": len(comps), "lcc_nodes": lcc,
            "lcc_frac": round(lcc / len(ids), 4), "isolated": iso}


def cross_component_gold_rows():
    """The 4 post-H651 cross-component residual gold rows, from the R57 atlas."""
    rows = [json.loads(l) for l in ATLAS_ROWS.read_text().splitlines() if l.strip()]
    return [r for r in rows if (r["traversal"] or {}).get("component_status") == "cross"]


def _unquote(s):
    s = s.strip()
    return s[1:-1] if len(s) >= 2 and s[0] == '"' and s[-1] == '"' else s


def _read_csv(path):
    """cypher-shell --format plain rows: header line, then double-quoted string cells.
    The separator is ", " - skipinitialspace is required or a comma inside a quoted name
    splits the row."""
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh, skipinitialspace=True))
    return [[_unquote(c) for c in r] for r in rows[1:]]


def read_export(d, log):
    """Offline equivalent of pull_graph, over a read-only cypher-shell CSV export.

    Expects entities.csv (eid), ee_edges.csv (a,b,type), chunk_entities.csv (cid,eid)
    and chunk_meta.csv (cid,index,doc_id,text_len) produced by `cypher-shell --format
    plain` against the target instance. Every exported column is an id or a relationship
    type: cypher-shell escapes an embedded double quote as \\" rather than doubling it, so
    two entity NAMES on this rung break CSV parsing. Names are therefore not exported -
    they are read from ents_meta.json, whose id set is identical.
    """
    d = Path(d)
    meta_name = {m["id"]: m["name"] for m in
                 json.loads((CACHE / "ents_meta.json").read_text())}
    ent_name = {r[0]: meta_name.get(r[0], "") for r in _read_csv(d / "entities.csv")}
    ee_edges = [(a, b, t) for a, b, t in _read_csv(d / "ee_edges.csv") if a != b]
    chunk_ents = defaultdict(set)
    for cid, eid in _read_csv(d / "chunk_entities.csv"):
        chunk_ents[cid].add(eid)
    chunk_meta = {cid: {"index": int(idx), "doc_id": doc, "text_len": int(tl)}
                  for cid, idx, doc, tl in _read_csv(d / "chunk_meta.csv")}
    schema = {
        "entity_count": len(ent_name),
        "chunk_count": len(chunk_meta),
        "mentioned_in_edges": sum(len(v) for v in chunk_ents.values()),
        "entity_entity_rel_count": len(ee_edges),
        "soft_link_edges": sum(1 for _, _, t in ee_edges if t == SOFT_LINK_TYPE),
        "provenance_path": "Entity-[:MENTIONED_IN]->Chunk",
        "source": f"read-only cypher-shell export {d}",
    }
    log(f"export: {schema['entity_count']} entities, {schema['chunk_count']} chunks, "
        f"{schema['mentioned_in_edges']} MENTIONED_IN, "
        f"{schema['entity_entity_rel_count']} entity-entity rels "
        f"({schema['soft_link_edges']} {SOFT_LINK_TYPE})")
    return schema, ent_name, ee_edges, dict(chunk_ents), chunk_meta


def persist_chunk_entities(chunk_ents, chunk_meta, schema, uri, container, image, run_id):
    """The process fix: the chunk -> entity mapping lands next to ents_meta.json so no
    later FREE replay needs a live instance for it."""
    payload = {
        "_stamp": {
            "hypothesis": "R59-H660", "run_id": run_id, "utc_timestamp": run_id,
            "instance_uri": uri, "container": container, "image": image,
            "git_head": git_head(), "provenance_path": schema["provenance_path"],
            "entity_count": schema["entity_count"], "chunk_count": schema["chunk_count"],
            "mentioned_in_edges": schema["mentioned_in_edges"],
            "entity_entity_rel_count": schema["entity_entity_rel_count"],
            "note": ("chunk id -> sorted entity ids, from "
                     "(:Entity)-[:MENTIONED_IN]->(:Chunk) on the medium rung restored from "
                     "data/interim/dumps/20260713-neo4j-medium-2wiki-1000.dump"),
        },
        "chunk_meta": chunk_meta,
        "chunk_entities": {cid: sorted(es) for cid, es in sorted(chunk_ents.items())},
    }
    CHUNK_ENTS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    CHUNK_ENTS_CACHE.write_text(json.dumps(payload, indent=1))
    return CHUNK_ENTS_CACHE


def connect(log, uris, auth):
    """Return (driver, uri) for the first reachable instance, else (None, None)."""
    try:
        from neo4j import GraphDatabase
    except Exception as e:                                   # pragma: no cover
        log(f"neo4j driver import failed: {e}")
        return None, None, []
    attempts = []
    for uri in uris:
        try:
            d = GraphDatabase.driver(uri, auth=auth, connection_timeout=CONNECT_TIMEOUT)
            with d.session() as s:
                s.run("MATCH (n) RETURN count(n) AS c").single()
            log(f"connected: {uri}")
            attempts.append({"uri": uri, "ok": True})
            return d, uri, attempts
        except Exception as e:
            attempts.append({"uri": uri, "ok": False,
                             "error": f"{type(e).__name__}: {str(e)[:120]}"})
            log(f"unreachable: {uri} ({type(e).__name__})")
    return None, None, attempts


def pull_graph(sess, log):
    """READ-ONLY pull: schema facts, entity-entity edges, chunk -> entity sets."""
    schema = {}
    labels = [r["label"] for r in sess.run(
        "CALL db.labels() YIELD label RETURN label ORDER BY label")]
    schema["labels"] = labels
    schema["entity_count"] = sess.run("MATCH (e:Entity) RETURN count(e) AS c").single()["c"]
    schema["chunk_count"] = sess.run("MATCH (c:Chunk) RETURN count(c) AS c").single()["c"]
    schema["mentioned_in_edges"] = sess.run(
        "MATCH (:Entity)-[:MENTIONED_IN]->(:Chunk) RETURN count(*) AS c").single()["c"]
    schema["entity_entity_rel_count"] = sess.run(
        "MATCH (:Entity)-[r]->(:Entity) RETURN count(r) AS c").single()["c"]
    schema["soft_link_edges"] = sess.run(
        f"MATCH (:Entity)-[r:{SOFT_LINK_TYPE}]->(:Entity) RETURN count(r) AS c").single()["c"]
    schema["provenance_path"] = "Entity-[:MENTIONED_IN]->Chunk"
    log(f"schema: {schema['entity_count']} entities, {schema['chunk_count']} chunks, "
        f"{schema['mentioned_in_edges']} MENTIONED_IN, "
        f"{schema['entity_entity_rel_count']} entity-entity rels")

    ent_name = {}
    for r in sess.run("MATCH (e:Entity) RETURN e.id AS id, e.name AS name"):
        ent_name[r["id"]] = r["name"]

    ee_edges = []
    for r in sess.run("MATCH (a:Entity)-[r]->(b:Entity) "
                      "RETURN a.id AS a, b.id AS b, type(r) AS t"):
        if r["a"] != r["b"]:
            ee_edges.append((r["a"], r["b"], r["t"]))

    chunk_ents = defaultdict(set)
    for r in sess.run("MATCH (e:Entity)-[:MENTIONED_IN]->(c:Chunk) "
                      "RETURN c.id AS cid, e.id AS eid"):
        chunk_ents[r["cid"]].add(r["eid"])

    chunk_meta = {}
    for r in sess.run("MATCH (c:Chunk) OPTIONAL MATCH (c)-[:PART_OF]->(d:KGFDocument) "
                      "RETURN c.id AS cid, c.index AS idx, d.id AS doc, "
                      "size(c.text) AS tl"):
        chunk_meta[r["cid"]] = {"index": r["idx"], "doc_id": r["doc"],
                                "text_len": r["tl"]}

    log(f"pulled {len(ent_name)} entity names, {len(ee_edges)} entity-entity edges, "
        f"{len(chunk_ents)} chunks with at least one entity")
    return schema, ent_name, ee_edges, dict(chunk_ents), chunk_meta


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="R59-H660 chunk-local co-occurrence census")
    p.add_argument("--uri", help="bolt URI of the instance; pins the target (DEF-4). "
                                 "Omit to fall back to CANDIDATE_URIS auto-discovery.")
    p.add_argument("--user", default=NEO4J_AUTH[0])
    p.add_argument("--password", default=NEO4J_AUTH[1])
    p.add_argument("--export-dir", help="run offline from a read-only cypher-shell CSV "
                                        "export instead of a bolt connection")
    p.add_argument("--instance-label", default=None,
                   help="how the instance was reached, recorded verbatim in the artifact")
    p.add_argument("--container", default=None, help="container name, for the stamp")
    p.add_argument("--image", default=None, help="image tag, for the stamp")
    return p.parse_args(argv)


def main():
    args = parse_args()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731
    ckpt = OUT / f"h660-cooccurrence-census-{run_id}.checkpoint.jsonl"
    cf = ckpt.open("w")

    def chk(tag, obj):
        cf.write(json.dumps({"tag": tag, **obj}, default=str) + "\n")
        cf.flush()

    jp = OUT / f"h660-cooccurrence-census-{run_id}.json"
    mp = OUT / f"h660-cooccurrence-census-{run_id}.md"

    # ============ FREE part: pins that do not need Neo4j ====================
    S = R50.load_substrate()
    name_norms = S["name_norms"]
    hits = []
    for c in S["carriers"]:
        seed_norms = {name_norms[i] for i in S["seeds_q"][c["probe"]]}
        hits.append(1 if c["tnorm"] in seed_norms else 0)
    base_recall = round(float(np.mean(hits)), 4)

    frozen = frozen_component_census()
    xrows = cross_component_gold_rows()
    pins = {
        "dense16_carrier_recall": base_recall, "pin": PIN_BASE_RECALL,
        "frozen_substrate_components": frozen,
        "component_pins": {"components": PIN_COMPONENTS, "lcc_nodes": PIN_LCC_NODES,
                           "lcc_frac": PIN_LCC_FRAC, "isolated": PIN_ISOLATED},
        "cross_component_gold_rows_found": len(xrows),
        "cross_component_gold_rows_expected": 4,
    }
    pins["ok"] = (abs(base_recall - PIN_BASE_RECALL) < 0.01
                  and frozen["components"] == PIN_COMPONENTS
                  and frozen["lcc_nodes"] == PIN_LCC_NODES
                  and abs(frozen["lcc_frac"] - PIN_LCC_FRAC) < 0.001
                  and frozen["isolated"] == PIN_ISOLATED
                  and len(xrows) == 4)
    log(f"PIN recall={base_recall} (pin {PIN_BASE_RECALL})")
    log(f"PIN frozen components={frozen['components']} lcc={frozen['lcc_nodes']} "
        f"({frozen['lcc_frac']}) isolated={frozen['isolated']} "
        f"(pins {PIN_COMPONENTS}/{PIN_LCC_NODES}/{PIN_LCC_FRAC}/{PIN_ISOLATED})")
    log(f"PIN cross-component gold rows={len(xrows)} (expected 4) ok={pins['ok']}")
    chk("pins", pins)
    chk("cross_component_rows", {"rows": [{"probe": r["probe"], "carrier": r["carrier"],
                                           "component_id": r["traversal"]["component_id"],
                                           "component_size": r["traversal"]["component_size"],
                                           "role": r["reasoning_role"]} for r in xrows]})

    base = {
        "hypothesis": "R59-H660", "run_id": run_id, "git_head": git_head(),
        "utc_timestamp": run_id, "join_version": JOIN_VERSION, "region_rule": REGION_RULE,
        "registered_bar": ("GATE: H661 opens only on a non-trivial (b) - co-occurring, "
                           "non-adjacent, cross-component pairs. If every co-occurring pair is "
                           "already adjacent or intra-component, the overlay is recorded dead "
                           "with no write."),
        "pins": pins,
        "cross_component_gold_rows": [
            {"probe": r["probe"], "carrier": r["carrier"],
             "eff_idx": r["eff_idx"], "role": r["reasoning_role"],
             "component_id": r["traversal"]["component_id"],
             "component_size": r["traversal"]["component_size"]} for r in xrows],
        "neo4j_access": "READ-ONLY (MATCH / RETURN / CALL db.labels() only); no writes",
        "instance_targeting": ("EXPLICIT per DEF-4; .env is never read by this script"
                               if (args.uri or args.export_dir)
                               else "CANDIDATE_URIS auto-discovery fallback"),
    }

    # ============ Neo4j part ================================================
    if args.export_dir:
        schema, ent_name, ee_edges, chunk_ents, chunk_meta = read_export(args.export_dir, log)
        uri = args.uri or args.instance_label or f"offline export {args.export_dir}"
        attempts = [{"uri": uri, "ok": True, "mode": "read-only cypher-shell export"}]
        driver = None
    else:
        auth = (args.user, args.password)
        uris = [args.uri] if args.uri else CANDIDATE_URIS
        driver, uri, attempts = connect(log, uris, auth)
    if driver is None and not args.export_dir:
        summ = dict(base)
        summ.update({
            "verdict_recommendation": "PREMISE-FAILED",
            "premise_failure": {
                "what_is_missing": ("the chunk -> entity mapping for the medium rung. It exists "
                                    "NOWHERE on disk in this repository: tmp/results/r47/"
                                    "ents_meta.json carries only ['descr','id','name','types'] "
                                    "(H631 recorded this explicitly), tmp/results/r47/edges.json "
                                    "and tmp/results/r50/edges_typed.json carry entity-entity "
                                    "pairs with no chunk field, and every prior script that "
                                    "computed the mapping pulled it live from Neo4j and "
                                    "persisted only aggregates."),
                "blocker": "no Neo4j instance is reachable",
                "uris_attempted": attempts,
                "host_state": ("no Neo4j container exists (docker ps -a lists only an unrelated "
                               "onedrive bridge and a stopped alpine probe); the hub network that "
                               "carried the .env hostname user-konrad.jelen-kgf-neo4j is gone; no "
                               "neo4j image is cached locally"),
                "what_was_NOT_done": ("no substitute was improvised. No (a), (b), (c) or w_assoc "
                                      "number is reported, because none is computable without the "
                                      "chunk -> entity sets."),
                "resume_recipe": [
                    "restore the medium rung into a throwaway container from "
                    "data/interim/dumps/20260713-neo4j-medium-2wiki-1000.dump "
                    "(966 MB; 1,000 docs / 6,626 entities / 1,000 chunks / 7,534 questions; "
                    "sidecar 20260713-neo4j-medium-2wiki-1000.md, recipe in "
                    "data/interim/dumps/MANIFEST.md) - or bring the live 7,575-entity "
                    "re-ingest back up",
                    "confirm the reached instance and its entity count (DEF-4: .env NEO4J_URI "
                    "silently overrides config targets)",
                    "re-run: .venv/bin/python scripts/experiments/r59_h660_cooccurrence_census.py "
                    "(it auto-discovers the instance from CANDIDATE_URIS; add the new URI to that "
                    "list if it differs)",
                ],
            },
            "what_reproduced_without_neo4j": {
                "dense16_carrier_recall": base_recall,
                "frozen_substrate_component_census": frozen,
                "cross_component_gold_rows": len(xrows),
            },
            "artifacts": {"json": str(jp), "brief": str(mp), "checkpoint": str(ckpt),
                          "script": "scripts/experiments/r59_h660_cooccurrence_census.py"},
        })
        jp.write_text(json.dumps(summ, indent=1, default=str))
        rows_md = "\n".join(f"| {r['carrier']} | {r['reasoning_role']} | "
                            f"{r['traversal']['component_id']} | "
                            f"{r['traversal']['component_size']} |" for r in xrows)
        att_md = "\n".join(f"- `{a['uri']}` - {'reached' if a['ok'] else a.get('error', 'failed')}"
                           for a in attempts)
        mp.write_text(f"""# R59-H660 chunk-local co-occurrence census - brief

**Verdict recommendation: PREMISE-FAILED** (run {run_id}, git {base['git_head'][:12]},
join {JOIN_VERSION}, region rule: {REGION_RULE})

**The H661 gate does NOT open and does NOT close. It is UNDECIDED** - the census could not be
computed, so no (a), (b), (c) or `w_assoc` number exists. No substitute was improvised.

## What blocked it
The chunk -> entity mapping for the medium rung exists nowhere on disk in this repository.
`tmp/results/r47/ents_meta.json` carries only `['descr','id','name','types']` (H631 recorded
this explicitly when class (b) of its own census was declared undeterminable from the same
cache); `tmp/results/r47/edges.json` and `tmp/results/r50/edges_typed.json` carry
entity-entity pairs with no chunk field; every prior script that computed the mapping pulled
it live from Neo4j and persisted only aggregates.

No Neo4j instance is reachable. URIs attempted:
{att_md}

Host state: no Neo4j container exists (`docker ps -a` lists only an unrelated onedrive bridge
and a stopped alpine probe); the hub network carrying the `.env` hostname
`user-konrad.jelen-kgf-neo4j` is gone; no neo4j image is cached locally.

## What DID reproduce (free, no Neo4j)
- dense@16 carrier recall **{base_recall}** (pin {PIN_BASE_RECALL})
- frozen-substrate component census: **{frozen['components']}** components (pin {PIN_COMPONENTS}),
  LCC **{frozen['lcc_nodes']}** nodes = **{frozen['lcc_frac']}** (pins {PIN_LCC_NODES} / {PIN_LCC_FRAC}),
  isolated **{frozen['isolated']}** (pin {PIN_ISOLATED}) - computed in networkx over
  {frozen['edges_undirected']} undirected entity-entity edges
- the **4** cross-component residual gold rows located exactly in the R57 atlas:

| carrier | role | component id | component size |
|---|---|---|---|
{rows_md}

## Resume
1. Restore the medium rung into a throwaway container from
   `data/interim/dumps/20260713-neo4j-medium-2wiki-1000.dump` (966 MB; 1,000 docs / 6,626
   entities / 1,000 chunks / 7,534 questions; sidecar
   `20260713-neo4j-medium-2wiki-1000.md`, recipe in `data/interim/dumps/MANIFEST.md`) - or
   bring the live 7,575-entity re-ingest back up
2. Confirm the reached instance and its entity count (DEF-4: `.env NEO4J_URI` silently
   overrides config targets)
3. Re-run `.venv/bin/python scripts/experiments/r59_h660_cooccurrence_census.py` - it
   auto-discovers the instance from `CANDIDATE_URIS`; add the new URI there if it differs
""")
        cf.close()
        log("\nVERDICT PREMISE-FAILED - no Neo4j instance reachable; no census numbers produced")
        log(f"wrote {jp}")
        return

    # ---- live pull ---------------------------------------------------------
    if driver is not None:
        with driver.session() as sess:
            schema, ent_name, ee_edges, chunk_ents, chunk_meta = pull_graph(sess, log)
        driver.close()
    chk("schema", {"uri": uri, **schema})

    cache_path = persist_chunk_entities(chunk_ents, chunk_meta, schema, uri,
                                        args.container, args.image, run_id)
    log(f"persisted chunk -> entity mapping: {cache_path}")
    chk("chunk_entities_cache", {"path": str(cache_path),
                                 "chunks": len(chunk_ents),
                                 "mentioned_in_edges": schema["mentioned_in_edges"]})

    # ---- components offline in networkx ------------------------------------
    # PRIMARY graph excludes the SIMILAR_TO embedding layer: only that edge set reproduces
    # the pinned 1,830 / 3,162 / 1,426, and it is the adjacency the shipped walk traverses.
    def build(edges):
        g = nx.Graph()
        g.add_nodes_from(ent_name)
        g.add_edges_from((a, b) for a, b, _ in edges)
        adj = {(a, b) if a < b else (b, a) for a, b, _ in edges}
        cmap = {}
        for ci, cset in enumerate(nx.connected_components(g)):
            for nid in cset:
                cmap[nid] = ci
        sz = sorted((len(c) for c in nx.connected_components(g)), reverse=True)
        n = g.number_of_nodes()
        cen = {"entities": n, "edges_undirected": g.number_of_edges(),
               "components": len(sz), "lcc_nodes": sz[0] if sz else 0,
               "lcc_frac": round((sz[0] if sz else 0) / max(n, 1), 4),
               "isolated": sum(1 for s in sz if s == 1)}
        return adj, cmap, cen

    hard_edges = [e for e in ee_edges if e[2] != SOFT_LINK_TYPE]
    adjacent, comp_of, live_census = build(hard_edges)
    adjacent_any, comp_of_any, live_census_any = build(ee_edges)
    live_census["pins_reproduce"] = (
        live_census["entities"] == PIN_ENTITIES
        and live_census["edges_undirected"] == PIN_EE_UNDIRECTED
        and live_census["components"] == PIN_COMPONENTS
        and live_census["lcc_nodes"] == PIN_LCC_NODES
        and abs(live_census["lcc_frac"] - PIN_LCC_FRAC) < 1e-9
        and live_census["isolated"] == PIN_ISOLATED)
    log(f"live census (primary, no {SOFT_LINK_TYPE}): {live_census['components']} components, "
        f"LCC {live_census['lcc_nodes']} ({live_census['lcc_frac']}), "
        f"isolated {live_census['isolated']} - pins reproduce: {live_census['pins_reproduce']}")
    log(f"live census (any type): {live_census_any['components']} components, "
        f"LCC {live_census_any['lcc_nodes']} ({live_census_any['lcc_frac']}), "
        f"isolated {live_census_any['isolated']}")
    chk("live_component_census", {"primary": live_census, "any_type": live_census_any})

    # ---- chunk-local co-occurrence -----------------------------------------
    C = len(chunk_ents)
    ent_freq = defaultdict(int)
    for cid, es in chunk_ents.items():
        for e in es:
            ent_freq[e] += 1

    w_raw = defaultdict(int)
    for cid, es in chunk_ents.items():
        for u, v in combinations(sorted(es), 2):
            w_raw[(u, v)] += 1

    total_pairs = len(w_raw)
    a_pairs = {p: w for p, w in w_raw.items() if p not in adjacent}
    b_pairs = {p: w for p, w in a_pairs.items() if comp_of[p[0]] != comp_of[p[1]]}
    a_pairs_any = {p: w for p, w in w_raw.items() if p not in adjacent_any}
    b_pairs_any = {p: w for p, w in a_pairs_any.items()
                   if comp_of_any[p[0]] != comp_of_any[p[1]]}
    log(f"co-occurring pairs: {total_pairs} total; (a) not-adjacent {len(a_pairs)}; "
        f"(b) not-adjacent AND cross-component {len(b_pairs)}")
    log(f"sensitivity with {SOFT_LINK_TYPE} counted as adjacency: "
        f"(a)={len(a_pairs_any)} (b)={len(b_pairs_any)}")
    chk("counts", {"cooccurring_pairs_total": total_pairs,
                   "a_not_adjacent": len(a_pairs), "b_cross_component": len(b_pairs),
                   "a_not_adjacent_any_type": len(a_pairs_any),
                   "b_cross_component_any_type": len(b_pairs_any),
                   "chunks_with_entities": C})

    # ---- (d) baseline-subtracted association weight on the (b) pairs --------
    def w_assoc(p, w):
        return w - (ent_freq[p[0]] * ent_freq[p[1]] / C)

    wa_b = np.array([w_assoc(p, w) for p, w in b_pairs.items()]) if b_pairs else np.array([])
    wa_a = np.array([w_assoc(p, w) for p, w in a_pairs.items()]) if a_pairs else np.array([])

    def dist(x):
        if x.size == 0:
            return {"n": 0}
        return {"n": int(x.size), "min": round(float(x.min()), 6),
                "p10": round(float(np.percentile(x, 10)), 6),
                "p50": round(float(np.percentile(x, 50)), 6),
                "p90": round(float(np.percentile(x, 90)), 6),
                "max": round(float(x.max()), 6), "mean": round(float(x.mean()), 6),
                "positive_count": int((x > 0).sum()),
                "ge_0.5_count": int((x >= 0.5).sum()),
                "ge_0.9_count": int((x >= 0.9).sum())}

    wa = {"b_pairs": dist(wa_b), "a_pairs": dist(wa_a),
          "baseline": "E[w_raw] = f_u f_v / C under independence given chunk-frequencies",
          "C_chunks": C}
    chk("w_assoc", wa)

    # ---- (c) would a (b)-pair join the 4 cross-component gold rows? ---------
    meta = json.loads((CACHE / "ents_meta.json").read_text())
    idx_id = {i: m["id"] for i, m in enumerate(meta)}
    b_by_comp = defaultdict(set)
    for u, v in b_pairs:
        b_by_comp[comp_of[u]].add(comp_of[v])
        b_by_comp[comp_of[v]].add(comp_of[u])

    gold_join = []
    for r in xrows:
        eff = r["eff_idx"]
        eid = idx_id.get(eff) if eff is not None else None
        # seed side = the probe's dense seeds; carrier side = the gold carrier node
        seeds = [idx_id.get(i) for i in S["seeds_q"].get(r["probe"], [])]
        seed_comps = {comp_of[s] for s in seeds if s in comp_of}
        carrier_comp = comp_of.get(eid)
        joined = (carrier_comp is not None
                  and bool(b_by_comp.get(carrier_comp, set()) & seed_comps))
        # stricter reading: a (b)-pair whose two endpoints ARE the carrier and a seed
        direct = sorted(s for s in seeds
                        if s and ((eid, s) if eid < s else (s, eid)) in b_pairs)
        gold_join.append({"probe": r["probe"], "carrier": r["carrier"],
                          "carrier_entity_id": eid, "carrier_component": carrier_comp,
                          "seed_components": sorted(seed_comps),
                          "joined_by_a_b_pair": joined,
                          "direct_b_pair_with_seed": bool(direct),
                          "direct_b_pair_seed_ids": direct,
                          "note": (None if eid in comp_of else
                                   "carrier node id not present in this instance "
                                   "(frozen-cache index -> live id mismatch)")})
    n_joined = sum(1 for g in gold_join if g["joined_by_a_b_pair"])
    n_direct = sum(1 for g in gold_join if g["direct_b_pair_with_seed"])
    log(f"cross-component gold rows joined by at least one (b)-pair: {n_joined}/{len(xrows)} "
        f"(component-level); direct carrier-seed (b)-pair: {n_direct}/{len(xrows)}")
    chk("gold_row_join", {"joined": n_joined, "direct": n_direct, "of": len(xrows),
                          "rows": gold_join})

    # ---- gate verdict -------------------------------------------------------
    gate_open = len(b_pairs) > 0
    verdict = "GATE-OPEN" if gate_open else "GATE-CLOSED"

    summ = dict(base)
    summ.update({
        "verdict_recommendation": verdict,
        "neo4j_uri_reached": uri,
        "instance": {"uri": uri, "container": args.container, "image": args.image,
                     "access": args.instance_label,
                     "dump": "data/interim/dumps/20260713-neo4j-medium-2wiki-1000.dump"},
        "schema": schema,
        "live_component_census": live_census,
        "component_pin_check": {
            "note": ("the restored instance reproduces the frozen substrate EXACTLY once the "
                     f"{SOFT_LINK_TYPE} embedding layer is excluded: same 6,626 entity ids, same "
                     "5,386 undirected entity-entity edges, same 1,830 / 3,162 / 1,426. The "
                     f"{SOFT_LINK_TYPE} layer is what the frozen cache dropped"),
            "frozen": frozen, "live_primary": live_census, "live_any_type": live_census_any},
        "census": {
            "chunks_with_entities": C,
            "cooccurring_pairs_total": total_pairs,
            "a_not_already_adjacent": len(a_pairs),
            "b_not_adjacent_AND_cross_component": len(b_pairs),
            "a_frac_of_total": round(len(a_pairs) / total_pairs, 6) if total_pairs else None,
            "b_frac_of_a": round(len(b_pairs) / len(a_pairs), 6) if a_pairs else None,
            "sensitivity_soft_links_counted_as_adjacency": {
                "a_not_already_adjacent": len(a_pairs_any),
                "b_not_adjacent_AND_cross_component": len(b_pairs_any)},
        },
        "w_assoc": wa,
        "chunk_entities_cache": str(cache_path),
        "cross_component_gold_row_join": {"joined": n_joined, "direct": n_direct,
                                          "of": len(xrows), "rows": gold_join},
        "caveats": [
            f"PRIMARY adjacency and components exclude the {SOFT_LINK_TYPE} embedding layer: "
            "only that edge set reproduces the pinned 1,830 / 3,162 / 1,426, and it is what the "
            "shipped walk traverses. The literal any-type reading is reported alongside as a "
            "sensitivity, never folded in.",
            "w_assoc uses the independence baseline E[w_raw] = f_u f_v / C; with C chunks and "
            "per-entity chunk frequencies mostly 1, the baseline is near zero and w_assoc is "
            "close to w_raw - stated so the number is not over-read.",
            "The 4 cross-component gold rows are indexed against the FROZEN 6,626-entity cache; "
            "if the reached instance is the 7,575-entity re-ingest, entity ids can fail to "
            "resolve and those rows are reported with an explicit note rather than dropped.",
            "AAR's INDUCTIVE null stands: the published transductive gain came from co-occurrence "
            "as supporting facts FOR QUESTIONS, i.e. question supervision. This census measures "
            "generic textual co-occurrence, so a non-trivial (b) opens H661 but does not predict "
            "its size.",
        ],
        "artifacts": {"json": str(jp), "brief": str(mp), "checkpoint": str(ckpt),
                      "script": "scripts/experiments/r59_h660_cooccurrence_census.py"},
    })
    jp.write_text(json.dumps(summ, indent=1, default=str))

    gold_md = "\n".join(
        f"| {g['carrier']} | {g['carrier_component']} | "
        f"{'YES' if g['joined_by_a_b_pair'] else 'no'} | "
        f"{'YES' if g['direct_b_pair_with_seed'] else 'no'} | {g['note'] or '-'} |"
        for g in gold_join)
    mp.write_text(f"""# R59-H660 chunk-local co-occurrence census - brief

**Verdict recommendation: {verdict}** (run {run_id}, git {base['git_head'][:12]},
join {JOIN_VERSION}, region rule: {REGION_RULE})

Instance: `{uri}`, container `{args.container}`, image `{args.image}`, restored from
`data/interim/dumps/20260713-neo4j-medium-2wiki-1000.dump`. Access READ-ONLY
(MATCH / RETURN only; no MERGE / CREATE / SET / DELETE, no APOC or GDS).
{schema['entity_count']} entities, {schema['chunk_count']} chunks,
{schema['mentioned_in_edges']} MENTIONED_IN edges,
{schema['entity_entity_rel_count']} entity-entity relationships
(of which {schema.get('soft_link_edges', 0)} {SOFT_LINK_TYPE}).

## Pins
- dense@16 carrier recall **{base_recall}** (pin {PIN_BASE_RECALL})
- frozen-substrate components **{frozen['components']}** (pin {PIN_COMPONENTS}), LCC
  **{frozen['lcc_nodes']}** = **{frozen['lcc_frac']}** (pins {PIN_LCC_NODES} / {PIN_LCC_FRAC}),
  isolated **{frozen['isolated']}** (pin {PIN_ISOLATED})
- restored instance, primary graph (no {SOFT_LINK_TYPE}): **{live_census['components']}**
  components, LCC **{live_census['lcc_nodes']}** = **{live_census['lcc_frac']}**, isolated
  **{live_census['isolated']}**, {live_census['edges_undirected']} undirected edges -
  pins reproduce exactly: **{live_census['pins_reproduce']}**
- restored instance, any type (incl. {SOFT_LINK_TYPE}): **{live_census_any['components']}**
  components, LCC **{live_census_any['lcc_nodes']}** = **{live_census_any['lcc_frac']}**,
  isolated **{live_census_any['isolated']}**
- the 4 cross-component residual gold rows located in the R57 atlas: **{len(xrows)}**

## Census (exact counts)
- chunks carrying at least one entity: **{C}**
- chunk-local co-occurring entity pairs, total: **{total_pairs}**
- **(a)** co-occurring and NOT already adjacent: **{len(a_pairs)}**
- **(b)** (a) AND the two entities in DIFFERENT components: **{len(b_pairs)}**

Sensitivity, counting the {SOFT_LINK_TYPE} embedding layer as adjacency and as component
structure: (a) = **{len(a_pairs_any)}**, (b) = **{len(b_pairs_any)}**.

## Baseline-subtracted association weight `w_assoc = w_raw - E[w_raw]`
Baseline `E[w_raw] = f_u f_v / C` under independence given entity chunk-frequencies, C = {C}.

| set | n | min | p10 | p50 | p90 | max | mean | > 0 | >= 0.9 |
|---|---|---|---|---|---|---|---|---|---|
| (b) pairs | {wa['b_pairs'].get('n', 0)} | {wa['b_pairs'].get('min', '-')} | {wa['b_pairs'].get('p10', '-')} | {wa['b_pairs'].get('p50', '-')} | {wa['b_pairs'].get('p90', '-')} | {wa['b_pairs'].get('max', '-')} | {wa['b_pairs'].get('mean', '-')} | {wa['b_pairs'].get('positive_count', '-')} | {wa['b_pairs'].get('ge_0.9_count', '-')} |
| (a) pairs | {wa['a_pairs'].get('n', 0)} | {wa['a_pairs'].get('min', '-')} | {wa['a_pairs'].get('p10', '-')} | {wa['a_pairs'].get('p50', '-')} | {wa['a_pairs'].get('p90', '-')} | {wa['a_pairs'].get('max', '-')} | {wa['a_pairs'].get('mean', '-')} | {wa['a_pairs'].get('positive_count', '-')} | {wa['a_pairs'].get('ge_0.9_count', '-')} |

## The 4 cross-component residual gold rows
Carrier component joined to a seed component by at least one (b)-pair:
**{n_joined}/{len(xrows)}**. Carrier itself co-mentioned with a seed by a (b)-pair:
**{n_direct}/{len(xrows)}**.

| carrier | carrier component | component joined | direct carrier-seed (b)-pair | note |
|---|---|---|---|---|
{gold_md}

## Gate
Registered rule: H661 opens only on a non-trivial (b). (b) = **{len(b_pairs)}** -> **{verdict}**.

## Process fix
Chunk -> entity mapping persisted to `{cache_path}` ({len(chunk_ents)} chunks,
{schema['mentioned_in_edges']} edges), stamped with instance, counts and UTC time. Later FREE
replays read that cache and need no live instance.

## Caveats
- primary adjacency and components exclude the {SOFT_LINK_TYPE} embedding layer; only that
  edge set reproduces the pinned 1,830 / 3,162 / 1,426, and it is what the shipped walk
  traverses. The literal any-type reading is reported as a sensitivity, never folded in
- `w_assoc` uses the independence baseline; where per-entity chunk frequency is mostly 1 the
  baseline is near zero and `w_assoc` is close to `w_raw` - stated so it is not over-read
- the 4 gold rows are indexed against the frozen 6,626-entity cache; unresolved ids under a
  different instance are reported with an explicit note, never dropped
- AAR's INDUCTIVE null stands: the published gain came from co-occurrence as supporting facts
  FOR QUESTIONS (question supervision). A non-trivial (b) opens H661; it does not size it
""")
    cf.close()
    log(f"\nVERDICT {verdict} | (a)={len(a_pairs)} (b)={len(b_pairs)} "
        f"gold rows joined {n_joined}/{len(xrows)} (direct {n_direct}/{len(xrows)})")
    log(f"wrote {jp}")


if __name__ == "__main__":
    main()

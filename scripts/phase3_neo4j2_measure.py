"""Phase-3 neo4j2 rebuild per-run measurement: graph shape by label/rel-type,
24-probe recall@16 via the pinned h158 harness (engine-parity overfetch default),
event-log summary (precision proxy), entity-id fingerprint.
Run from repo root AFTER a run's ingest completion line, BEFORE the next wipe.
Usage: .venv/bin/python scripts/phase3_neo4j2_measure.py <1|2>
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "notebooks")
from h158_measure import precision_proxy, recall_at_k  # noqa: E402
from neo4j import GraphDatabase  # noqa: E402

RUN = sys.argv[1]
URI = "bolt://172.19.0.7:7687"
AUTH = ("neo4j", "kgfoundry")
EVENTS = "logs/phase3-rebuild-events.jsonl"
BENCH = "reports/identity-benchmark-h101-20260707-094448.json"
TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT = f"reports/phase3-rebuild{RUN}-{TS}.json"

rec = recall_at_k(URI, 16, f"phase3-neo4j2-run{RUN}")

prec = precision_proxy(EVENTS, BENCH) if Path(EVENTS).exists() else None

d = GraphDatabase.driver(URI, auth=AUTH)
with d.session() as s:
    labels = {r["l"]: r["c"] for r in s.run(
        "MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c ORDER BY c DESC")}
    rel_types = {r["t"]: r["c"] for r in s.run(
        "MATCH ()-[x]->() RETURN type(x) AS t, count(*) AS c ORDER BY c DESC")}
    nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
    chunks = labels.get("Chunk", 0)
    kgfdocs = labels.get("KGFDocument", 0)
    ids = [row["id"] for row in s.run(
        "MATCH (e:Entity) RETURN e.id AS id ORDER BY e.id")]
    ctrl = s.run("MATCH (c:KGFControl) RETURN properties(c) AS p LIMIT 1").single()
d.close()
fp = hashlib.sha256("".join(ids).encode()).hexdigest()[:16]

ctrl_props = dict(ctrl["p"]) if ctrl else {}
ctrl_summary = {k: ctrl_props.get(k) for k in
                ("fsm_state", "cured", "documents_processed", "purpose") if k in ctrl_props}

out = {
    "run": RUN,
    "captured_at": TS,
    "uri": URI,
    "config": "config/experiments/config-phase3-rebuild.yml",
    "corpus": "data/external/cpap-datasheets-and-manuals",
    "total_nodes": nodes,
    "entities": rec["entities"],
    "relationships": rec["relationships"],
    "documents": rec["documents"],
    "chunks": chunks,
    "kgf_documents": kgfdocs,
    "entity_types": len([l for l in labels if not l.startswith("KGF")
                         and l not in ("Chunk", "Document", "Entity")]),
    "labels": labels,
    "rel_types": rel_types,
    "entity_id_fingerprint": fp,
    "control": ctrl_summary,
    "recall": {k: rec[k] for k in ("label", "top_k", "overfetch_factor",
                                   "mean_recall", "fully_covered", "n_probes")},
    "per_probe": rec["per_probe"],
    "event_summary": prec,
}
Path(OUT).write_text(json.dumps(out, indent=2))
print(json.dumps({k: v for k, v in out.items() if k not in ("labels", "rel_types", "per_probe")}, indent=2))
print("saved:", OUT)

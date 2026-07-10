"""Phase-3 rebuild per-run measurement: recall@16 + graph stats + entity-id fingerprint.
Run from repo root AFTER a run's ingest, BEFORE the next wipe.
Usage: python scripts/phase3_measure.py <run1|run2>
The entity_id_fingerprint + entities + mean_recall are the reproducibility-gate signals:
two runs must match within the H229 model-inherent variance floor.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, "notebooks")
from h158_measure import precision_proxy, recall_at_k  # noqa: E402
from neo4j import GraphDatabase  # noqa: E402

RUN = sys.argv[1]
URI = "bolt://172.19.0.4:7687"
AUTH = ("neo4j", "kgfoundry")
EVENTS = "logs/phase3-rebuild-events.jsonl"
RECALL_JSON = f"reports/phase3-{RUN}-recall.json"
STATS_JSON = f"reports/phase3-{RUN}-stats.json"
BENCH = "reports/identity-benchmark-h101-20260707-094448.json"

rec = recall_at_k(URI, 16, f"phase3-{RUN}")
Path(RECALL_JSON).write_text(json.dumps(rec, indent=2))

prec = precision_proxy(EVENTS, BENCH)

d = GraphDatabase.driver(URI, auth=AUTH)
with d.session() as s:
    ids = [row["id"] for row in s.run("MATCH (e:Entity) RETURN e.id AS id ORDER BY e.id")]
    chunks = s.run("MATCH (c:Chunk) RETURN count(c) AS c").single()["c"]
    kgfdocs = s.run("MATCH (x:KGFDocument) RETURN count(x) AS c").single()["c"]
d.close()
fp = hashlib.sha256("".join(ids).encode()).hexdigest()[:16]
stats = {
    "run": RUN,
    "entities": rec["entities"],
    "relationships": rec["relationships"],
    "chunks": chunks,
    "kgf_documents": kgfdocs,
    "entity_id_fingerprint": fp,
    "mean_recall": rec["mean_recall"],
    "fully_covered": rec["fully_covered"],
    "same_as_precision": prec["same_as_precision"],
    "false_merges": prec["false_merges"],
    "merges_total": prec["merges_total"],
    "defers_total": prec["defers_total"],
    "nli_vetoes": prec["nli_vetoes"],
}
Path(STATS_JSON).write_text(json.dumps(stats, indent=2))
print(json.dumps(stats, indent=2))

"""R15-H241 per-arm measurement: recall@16 (persist JSON) + graph stats.
Run from repo root AFTER an arm's ingest, BEFORE the next wipe.
Usage: python scripts/experiments/h241_measure.py <v1|v2>
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, "notebooks")
from h158_measure import recall_at_k, precision_proxy  # noqa: E402
from neo4j import GraphDatabase  # noqa: E402

ARM = sys.argv[1]
URI = "bolt://172.19.0.100:7687"
AUTH = ("neo4j", "kgfoundry")
EVENTS = f"logs/h241-{ARM}-events.jsonl"
RECALL_JSON = f"reports/experiments/adjudicated/h241-{ARM}-recall.json"
STATS_JSON = f"reports/experiments/adjudicated/h241-{ARM}-stats.json"
BENCH = "reports/experiments/adjudicated/identity-benchmark-h101-20260707-094448.json"

# recall@16 against the live arm graph (H158 harness, cpap-probe-set, 24 gold probes)
rec = recall_at_k(URI, 16, f"{ARM}-h241")
Path(RECALL_JSON).write_text(json.dumps(rec, indent=2))

# precision proxy from the event log (298 H101 pairs)
prec = precision_proxy(EVENTS, BENCH)

# graph fingerprint
d = GraphDatabase.driver(URI, auth=AUTH)
with d.session() as s:
    ids = [row["id"] for row in s.run("MATCH (e:Entity) RETURN e.id AS id ORDER BY e.id")]
    chunks = s.run("MATCH (c:Chunk) RETURN count(c) AS c").single()["c"]
    kgfdocs = s.run("MATCH (x:KGFDocument) RETURN count(x) AS c").single()["c"]
d.close()
fp = hashlib.sha256("".join(ids).encode()).hexdigest()[:16]
stats = {"arm": ARM, "entities": rec["entities"], "relationships": rec["relationships"],
         "chunks": chunks, "kgf_documents": kgfdocs, "entity_id_fingerprint": fp,
         "mean_recall": rec["mean_recall"], "fully_covered": rec["fully_covered"],
         "same_as_precision": prec["same_as_precision"], "false_merges": prec["false_merges"],
         "merges_total": prec["merges_total"], "defers_total": prec["defers_total"],
         "nli_vetoes": prec["nli_vetoes"]}
Path(STATS_JSON).write_text(json.dumps(stats, indent=2))
print(f"[{ARM}] recall {rec['mean_recall']:.4f} ({rec['fully_covered']}/{rec['n_probes']})  "
      f"precision {prec['same_as_precision']:.3f}  false_merges {prec['false_merges']}  "
      f"entities {rec['entities']}  fp {fp}")

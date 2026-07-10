"""R29 SLOT-1 v2 identity-stack reopen: per arm+run measurement.

Reuses the H158/H241 harness: recall@16 (live graph) + RAW SAME_AS precision
proxy (event log vs the 298 H101 adjudicated pairs). Adds the false-merge RATE
(the rate-normalized clause GAP-1 asked for) and the effective-surface signals -
demotion-court demotions and surviving SAME_AS / SIMILAR_TO edge counts.

Run from repo root AFTER an arm's ingest, BEFORE the next wipe.
Usage: python scripts/r29_measure.py <v1|v2> <run>
"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, "notebooks")
from h158_measure import precision_proxy, recall_at_k  # noqa: E402
from neo4j import GraphDatabase  # noqa: E402

ARM = sys.argv[1]
RUN = sys.argv[2]
URI = "bolt://172.19.0.4:7687"
AUTH = ("neo4j", "kgfoundry")
EVENTS = f"logs/r29-{ARM}-events.jsonl"
STATS = f"reports/r29-{ARM}-run{RUN}-stats.json"
BENCH = "reports/identity-benchmark-h101-20260707-094448.json"

# recall@16 against the live arm graph (H158 harness, cpap-probe-set, 24 gold probes)
rec = recall_at_k(URI, 16, f"{ARM}-r29-run{RUN}")

# RAW (pre-court) SAME_AS precision proxy from the event log (298 H101 pairs)
prec = precision_proxy(EVENTS, BENCH)
rate = prec["false_merges"] / prec["merges_total"] if prec["merges_total"] else 0.0

# effective-surface signals: the demotion court summary + final SAME_AS/SIMILAR_TO edges
court = {"docket": 0, "demoted": 0, "freebies": 0, "judged": 0}
for line in Path(EVENTS).read_text().splitlines():
    r = json.loads(line)
    if r.get("event") == "resolution.court":
        court = {k: r.get(k, 0) for k in ("docket", "demoted", "freebies", "judged")}

d = GraphDatabase.driver(URI, auth=AUTH)
with d.session() as s:
    ids = [row["id"] for row in s.run("MATCH (e:Entity) RETURN e.id AS id ORDER BY e.id")]
    same_as = s.run("MATCH ()-[r:SAME_AS]->() RETURN count(r) AS c").single()["c"]
    soft = s.run("MATCH ()-[r:SIMILAR_TO]->() RETURN count(r) AS c").single()["c"]
d.close()
fp = hashlib.sha256("".join(ids).encode()).hexdigest()[:16]

stats = {
    "arm": ARM,
    "run": RUN,
    "entities": rec["entities"],
    "relationships": rec["relationships"],
    "mean_recall": rec["mean_recall"],
    "fully_covered": rec["fully_covered"],
    "n_probes": rec["n_probes"],
    "same_as_precision": prec["same_as_precision"],
    "false_merges": prec["false_merges"],
    "merges_total": prec["merges_total"],
    "false_merge_rate": round(rate, 4),
    "defers_total": prec["defers_total"],
    "nli_vetoes": prec["nli_vetoes"],
    "court_docket": court["docket"],
    "court_demoted": court["demoted"],
    "same_as_edges": same_as,
    "similar_to_edges": soft,
    "entity_id_fingerprint": fp,
}
Path(STATS).write_text(json.dumps(stats, indent=2))
print(
    f"[{ARM} run{RUN}] recall {rec['mean_recall']:.4f} ({rec['fully_covered']}/{rec['n_probes']})  "
    f"precision {prec['same_as_precision']:.3f}  rate {rate:.4f} "
    f"(false {prec['false_merges']}/{prec['merges_total']})  "
    f"court {court['demoted']}/{court['docket']}  SAME_AS {same_as}  entities {rec['entities']}  fp {fp}"
)

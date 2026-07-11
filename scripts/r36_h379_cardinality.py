"""R36-H379 INFERENCE ARM: functional relationship types from cardinality profiles.

A relation that is single-valued per subject (one distinct live target per
source entity) across the graph is a functional candidate - the set that
should populate `functional_relationship_types` so bitemporal invalidation
(`valid_to`) can ever fire. This arm profiles every relationship type on the
live pile and proposes the candidate set at swept single-valued fractions
(0.90 / 0.95 / 1.00). The two-version doc replay (alarm actually fires,
zero false invalidations) runs separately on scratch post-H363.

Reads only. SIMILAR_TO excluded (soft-link infrastructure, not a fact edge).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase

URI = "bolt://172.19.0.100:7687"
EXCLUDE = {"SIMILAR_TO"}
SWEEP = [0.90, 0.95, 1.00]


def main():
    driver = GraphDatabase.driver(URI, auth=("neo4j", "kgfoundry"))
    with driver.session() as sess:
        rows = sess.run(
            "MATCH (s:Entity)-[r]->(t:Entity) WHERE r.valid_to IS NULL "
            "WITH type(r) AS rel, s.id AS sid, count(DISTINCT t.id) AS fanout "
            "RETURN rel, count(*) AS subjects, "
            "sum(CASE WHEN fanout = 1 THEN 1 ELSE 0 END) AS single_valued, "
            "avg(fanout) AS mean_fanout, max(fanout) AS max_fanout "
            "ORDER BY subjects DESC"
        ).data()
    driver.close()

    profiles = []
    for r in rows:
        if r["rel"] in EXCLUDE:
            continue
        pct = r["single_valued"] / r["subjects"]
        profiles.append({
            "type": r["rel"], "subjects": r["subjects"],
            "pct_single_valued": round(pct, 4),
            "mean_fanout": round(r["mean_fanout"], 2), "max_fanout": r["max_fanout"],
        })
        print(f"{r['rel']:<40} subjects={r['subjects']:<6} single={pct:.2%} "
              f"mean={r['mean_fanout']:.2f} max={r['max_fanout']}", flush=True)

    candidates = {}
    for th in SWEEP:
        cand = [p["type"] for p in profiles if p["pct_single_valued"] >= th and p["subjects"] >= 5]
        candidates[str(th)] = cand
        print(f"\nfunctional candidates @ >={th:.0%} single-valued (>=5 subjects): "
              f"{len(cand)} of {len(profiles)} types", flush=True)
        for c in cand:
            print(f"  {c}", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/r36-h379-cardinality-{ts}.json")
    out.write_text(json.dumps({
        "hypothesis": "R36-H379 inference arm (cardinality -> functional types)",
        "generated": ts, "graph_uri": URI, "excluded": sorted(EXCLUDE),
        "min_subjects": 5, "profiles": profiles, "candidates": candidates,
    }, indent=2))
    print(f"\nH379 INFERENCE ARM COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

"""R33-H365 OFFLINE PROTOTYPE: spec-reachability repair on the live graph (no GPU).

The H364 walk located 83.3% of the emitted-but-lost mass at the resolution stage:
spec props sit only on HC23x child models under 'HC230 Product Range', an unmerged
duplicate of the retrieved-but-empty 'HC230-Series'. This prototype simulates the
engine fix additively (reversible, provenance-tagged) instead of destructive merges:

  (a) merge simulation - PART_OF edges from every HC child to 'HC230-Series'
      (edge property h365=true)
  (b) spec hoist - every child prop_* whose value is UNANIMOUS across the children
      is copied onto the series-level entities retrieval already finds
      ('HC230-Series', 'Sleep Style 200 Series'); conflicting values stay put;
      existing parent values are never overwritten; hoisted keys recorded in
      an `h365_hoisted` marker property for one-shot rollback

Verdict comes from re-running recall@16 (h158 harness) and diffing per-probe vs the
fresh baseline: PASS = P09 0.0 -> 1.0, P16 0.5 -> 1.0, all other probes non-regressing.

Rollback: MATCH (e:Entity) WHERE e.h365_hoisted IS NOT NULL -> remove listed keys +
marker; MATCH ()-[r:PART_OF {h365:true}]->() DELETE r.
"""

import json

from neo4j import GraphDatabase

URI = "bolt://172.19.0.100:7687"
SOURCE_HUB = "HC230 Product Range"  # carrier fragment the children link to
TARGETS = ["HC230-Series", "Sleep Style 200 Series"]  # retrieved series-level subjects


def main():
    drv = GraphDatabase.driver(URI, auth=("neo4j", "kgfoundry"))
    with drv.session() as s:
        children = s.run(
            "MATCH (c:Entity)-[:PART_OF]->(:Entity {name:$hub}) "
            "RETURN c.id AS id, c.name AS name, properties(c) AS p ORDER BY c.name",
            hub=SOURCE_HUB,
        ).data()
        print(f"children of {SOURCE_HUB!r}: {[c['name'] for c in children]}", flush=True)

        keys = sorted({k for c in children for k in c["p"] if k.startswith("prop_")})
        unanimous, conflicting = {}, []
        for k in keys:
            vals = {c["p"].get(k) for c in children}
            if len(vals) == 1:
                unanimous[k] = vals.pop()
            else:
                conflicting.append(k)
        print(f"hoistable (unanimous): {len(unanimous)}; left in place (conflict): {conflicting}", flush=True)

        for target in TARGETS:
            row = s.run(
                "MATCH (e:Entity {name:$n}) RETURN e.id AS id, properties(e) AS p", n=target
            ).single()
            hoist = {k: v for k, v in unanimous.items() if k not in row["p"]}  # never overwrite
            s.run(
                "MATCH (e:Entity {id:$id}) SET e += $props, e.h365_hoisted = $keys",
                id=row["id"], props=hoist, keys=sorted(hoist),
            )
            print(f"hoisted {len(hoist)} props -> {target!r} ({row['id']})", flush=True)

        merged = s.run(
            "MATCH (c:Entity)-[:PART_OF]->(:Entity {name:$hub}) "
            "MATCH (t:Entity {name:'HC230-Series'}) "
            "MERGE (c)-[r:PART_OF {h365:true}]->(t) RETURN count(r) AS n",
            hub=SOURCE_HUB,
        ).single()["n"]
        print(f"merge simulation: {merged} PART_OF edges -> 'HC230-Series'", flush=True)

    drv.close()
    print("H365 REPAIR APPLIED", flush=True)


if __name__ == "__main__":
    main()

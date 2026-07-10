"""R33-H364 STAGE-LOCALIZATION CENSUS: walk each emitted-but-lost gold through the
pipeline stages on the freshest graph. Offline + Neo4j, no GPU.

For every gold the H354 census classed i_emission_covered (extracted 6/6 passes at
chunk level, probe still failing recall@16), assign exactly ONE loss stage:

  loader_loss      - gold absent from every entity surface (name/desc/props/rels)
                     AND from the union of all surfaces: extraction emitted it, the
                     loader never landed it on the graph
  resolution_loss  - gold present, but only on carrier entities whose name/surface
                     does not align with the probe's subject: merged/demoted where
                     vector search for the probe cannot reach it
  ranking_loss     - gold present on a subject-aligned carrier that sits BELOW
                     top-16 in the probe's vector retrieval (rank reported)
  render_gap       - a carrier IS in the top-16 seeds, but the harness render
                     (15-relation cap, rendered fields) drops the gold string

Retrieval/render/matching primitives are the recall harness's own (h158_measure),
so a stage verdict here is a verdict about the measured pipeline, not a proxy.

Inputs: reports/r32-h354-census-*.json (target golds), tests/probes/cpap-probe-set.yml,
the h212-v2 graph (bolt://172.19.0.4:7687). Output: reports/r33-h364-stage-census-<ts>.json
+ printed per-gold stage table with carrier evidence.
"""

import json
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, "notebooks")
from h158_measure import _norm, _present, _render_nodes  # noqa: E402 - the harness's own primitives

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.extraction import generate_embeddings  # noqa: E402
from knowledge_graph_foundry.graph.graphrag import vector_query  # noqa: E402
from knowledge_graph_foundry.models import Entity  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

URI = "bolt://172.19.0.4:7687"  # the graph the failing recall map (h212-v2 rerun) measured
TOP_K = 16
RANK_K = 200  # extended retrieval depth for locating carriers below the cutoff
PROBES = Path("tests/probes/cpap-probe-set.yml")
CENSUS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports/r32-h354-census-20260710T125440Z.json")


def main():
    census = json.load(CENSUS.open())
    targets = [
        (d["probe"], d["gold"], d["mass"])
        for d in census["detail"]
        if d["class"] == "i_emission_covered"
    ]
    probes = {p["id"]: p for p in yaml.safe_load(PROBES.read_text())}
    probe_ids = sorted({pid for pid, _, _ in targets})
    print(f"walking {len(targets)} golds across probes {probe_ids}", flush=True)

    base = load_settings(Path("config.yml"))
    vec = base.graphrag.vector_index_name
    st = deepcopy(base)
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = URI, "neo4j", "kgfoundry"
    st.graphrag.top_k = TOP_K

    with Foundry(st) as f:
        with f.driver.session() as s:
            ents = s.run("MATCH (e:Entity) RETURN count(e) AS c").single()["c"]
            rels = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        print(f"graph: {ents} entities, {rels} rels (h212-v2 rerun measured 1094/3946)", flush=True)

        # full entity surfaces, split by component so the evidence names WHERE the gold sits
        surfaces, meta = {}, {}
        with f.driver.session() as s:
            rows = s.run(
                "MATCH (e:Entity) RETURN e.id AS id, e.name AS name, labels(e) AS types, "
                "e.description AS description, properties(e) AS props"
            ).data()
            for r in rows:
                spec = {k.removeprefix("prop_"): v for k, v in r["props"].items() if k.startswith("prop_")}
                rr = s.run(
                    "MATCH (e:Entity {id:$id})-[rel]-(n:Entity) WHERE rel.valid_to IS NULL "
                    "AND type(rel) <> 'SIMILAR_TO' RETURN type(rel) AS rel, n.name AS name",
                    id=r["id"],
                ).data()
                comp = {
                    "name": _norm(r["name"] or ""),
                    "desc": _norm(r["description"] or ""),
                    "props": _norm(json.dumps(spec, default=str)) if spec else "",
                    "rels": _norm(" ".join(f"{x['rel']} {x['name']}" for x in rr)),
                }
                surfaces[r["id"]] = comp
                meta[r["id"]] = {"name": r["name"], "types": r["types"], "n_rels": len(rr)}
        union_all = " ".join(" ".join(c.values()) for c in surfaces.values())

        # per-probe retrieval, harness path: question embedding -> vector top-k
        retrieval = {}
        for pid in probe_ids:
            q = probes[pid]["question"]
            pe = Entity.create(q[:80], types=["Query"], description=q)
            emb = generate_embeddings([pe], st.embeddings)[0].embedding
            ranked = [x["id"] for x in vector_query(f.driver, emb, vec, top_k=RANK_K)]
            with f.driver.session() as sess:
                ctx16 = _render_nodes(sess, ranked[:TOP_K])
            retrieval[pid] = {"ranked": ranked, "ctx16": ctx16}
            print(f"{pid}: retrieved {len(ranked)}, top-3 = "
                  f"{[meta[i]['name'] for i in ranked[:3]]}", flush=True)

        def subject_tokens(question: str) -> set:
            # device/model tokens: capitalized-or-alphanumeric words from the question,
            # minus generic english - what a subject-aligned carrier name should share
            stop = {"what", "which", "does", "the", "and", "for", "how", "are", "its",
                    "of", "is", "in", "to", "a", "on", "with", "between", "compare",
                    "device", "machine", "much", "long", "many"}
            toks = {t for t in re.findall(r"[a-z0-9][a-z0-9\-]+", _norm(question)) if t not in stop}
            return toks

        detail, masses = [], {}
        for pid, gold, mass in targets:
            q = probes[pid]["question"]
            ranked, ctx16 = retrieval[pid]["ranked"], retrieval[pid]["ctx16"]
            found_now = _present(gold, ctx16)

            carriers = []
            for eid, comp in surfaces.items():
                whole = " ".join(comp.values())
                if _present(gold, whole):
                    where = [k for k, v in comp.items() if v and _present(gold, v)]
                    rank = ranked.index(eid) + 1 if eid in ranked else None
                    name_toks = set(re.findall(r"[a-z0-9][a-z0-9\-]+", comp["name"]))
                    carriers.append({
                        "id": eid, "name": meta[eid]["name"], "types": meta[eid]["types"],
                        "where": where, "rank": rank, "n_rels": meta[eid]["n_rels"],
                        "subject_overlap": sorted(name_toks & subject_tokens(q)),
                    })
            carriers.sort(key=lambda c: (c["rank"] is None, c["rank"] or 10**9))

            if found_now:
                stage = "recovered_now"  # graph/harness drift vs the rerun - flag, do not classify
            elif not carriers:
                stage = "loader_loss" if not _present(gold, union_all) else "loader_fragmented"
            elif any(c["rank"] is not None and c["rank"] <= TOP_K for c in carriers):
                stage = "render_gap"
            elif any(c["subject_overlap"] for c in carriers):
                stage = "ranking_loss"
            else:
                stage = "resolution_loss"

            masses[stage] = masses.get(stage, 0.0) + mass
            best = carriers[0] if carriers else None
            detail.append({
                "probe": pid, "gold": gold, "mass": mass, "stage": stage,
                "n_carriers": len(carriers),
                "best_carrier": best,
                "carriers": carriers[:8],
            })
            print(f"  {pid} [{stage}] {gold!r}: {len(carriers)} carriers"
                  + (f", best={best['name']!r} rank={best['rank']} where={best['where']} "
                     f"overlap={best['subject_overlap']}" if best else ""), flush=True)

        total = sum(masses.values())
        print("\nSTAGE MASSES (share of walked mass):", flush=True)
        for stg, m in sorted(masses.items(), key=lambda kv: -kv[1]):
            print(f"  {stg:20s} {m:.3f}  ({m / total:.1%})", flush=True)

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = Path(f"reports/r33-h364-stage-census-{ts}.json")
        out.write_text(json.dumps({
            "hypothesis": "R33-H364",
            "generated": ts,
            "graph": {"uri": URI, "entities": ents, "relationships": rels},
            "census_input": str(CENSUS),
            "stage_masses": {k: round(v, 4) for k, v in masses.items()},
            "detail": detail,
        }, indent=2, default=str))
        print(f"\nH364 STAGE CENSUS COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

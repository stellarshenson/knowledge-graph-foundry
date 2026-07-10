"""R34-H369 OFFLINE PROTOTYPE: node-specificity seed weighting (the free IDF prior).

HippoRAG-1 scales PPR reset probability by s_i = |sources|^-1 (+2.0 avg). KGF
transplant: re-rank the vector overfetch by score x specificity from the
entities' own `source_chunks` provenance, take top-16, render. Two variants
against baseline:

  base    - vector top-16 as retrieved (must reproduce 0.8542)
  linear  - score / |source_chunks|
  log     - score / log2(1 + |source_chunks|)

Overfetch: top-64. Metrics per arm: recall@16, fully_covered, mean seed
|source_chunks| and mean seed degree (the registered occupancy prediction).
Bar: zero regressions required, any gain counts; REFUTED if series-level hub
answers regress. Entity channel: Titan query embedding (live index space).
No GPU. Graph writes: NONE.
"""

import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, "notebooks")
from h158_measure import _present, _render_nodes  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.extraction import generate_embeddings  # noqa: E402
from knowledge_graph_foundry.graph.graphrag import vector_query  # noqa: E402
from knowledge_graph_foundry.models import Entity  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

URI = "bolt://172.19.0.4:7687"
TOP_K = 16
OVERFETCH = 64
PROBES = Path("tests/probes/cpap-probe-set.yml")
ARMS = ["base", "linear", "log"]


def main():
    import math

    base = load_settings(Path("config.yml"))
    vec = base.graphrag.vector_index_name
    st = deepcopy(base)
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = URI, "neo4j", "kgfoundry"
    st.graphrag.top_k = TOP_K

    probes = [p for p in yaml.safe_load(PROBES.read_text()) if p.get("gold_evidence")]

    with Foundry(st) as f:
        with f.driver.session() as s:
            rows = s.run(
                "MATCH (e:Entity) RETURN e.id AS id, size(coalesce(e.source_chunks, [])) AS sc, "
                "COUNT { (e)--() } AS deg"
            ).data()
        meta = {r["id"]: (max(r["sc"], 1), r["deg"]) for r in rows}
        print(f"entities: {len(meta)}", flush=True)

        per = {a: {} for a in ARMS}
        occ = {a: {"sc": 0.0, "deg": 0.0} for a in ARMS}
        for p in probes:
            q = p["question"]
            pe = Entity.create(q[:80], types=["Query"], description=q)
            emb = generate_embeddings([pe], st.embeddings)[0].embedding
            fetched = vector_query(f.driver, emb, vec, top_k=OVERFETCH)

            def rerank(fn):
                return [s["id"] for s in sorted(
                    fetched, key=lambda s: -s.get("score", 0.0) * fn(meta[s["id"]][0])
                )][:TOP_K]

            arm_seeds = {
                "base": [s["id"] for s in fetched[:TOP_K]],
                "linear": rerank(lambda sc: 1.0 / sc),
                "log": rerank(lambda sc: 1.0 / math.log2(1 + sc + 1)),
            }
            golds = p["gold_evidence"]
            with f.driver.session() as sess:
                for a in ARMS:
                    ctx = _render_nodes(sess, arm_seeds[a])
                    per[a][p["id"]] = sum(_present(g, ctx) for g in golds) / len(golds)
                    occ[a]["sc"] += sum(meta[i][0] for i in arm_seeds[a]) / TOP_K
                    occ[a]["deg"] += sum(meta[i][1] for i in arm_seeds[a]) / TOP_K
            print(f"{p['id']}: " + " ".join(f"{a}={per[a][p['id']]:.2f}" for a in ARMS), flush=True)

        print("\nARM SUMMARY:", flush=True)
        summary = {}
        n = len(probes)
        for a in ARMS:
            mean = sum(per[a].values()) / n
            full = sum(1 for v in per[a].values() if v == 1.0)
            summary[a] = {"mean_recall": round(mean, 4), "fully_covered": full,
                          "mean_seed_source_chunks": round(occ[a]["sc"] / n, 2),
                          "mean_seed_degree": round(occ[a]["deg"] / n, 2),
                          "per_probe": {k: round(v, 4) for k, v in per[a].items()}}
            print(f"  {a}: mean {mean:.4f}, full {full}/24, "
                  f"seed_sc {occ[a]['sc'] / n:.1f}, seed_deg {occ[a]['deg'] / n:.1f}", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/r34-h369-specificity-{ts}.json")
    out.write_text(json.dumps({
        "hypothesis": "R34-H369", "generated": ts, "graph_uri": URI,
        "overfetch": OVERFETCH, "summary": summary,
    }, indent=2))
    print(f"\nH369 PROTOTYPE COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

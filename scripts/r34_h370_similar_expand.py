"""R34-H370 OFFLINE PROTOTYPE (forward arm): one-hop SIMILAR_TO seed expansion.

KGF creates SIMILAR_TO three ways (kNN densify, defer soft-links, court
demotions) and consumes them nowhere: render excludes the type, the posterior
`weight` feeds nothing. This arm expands the harness's top-16 vector seeds one
hop over SIMILAR_TO (weight >= threshold, capped additions) before render.
Pile edge stats: 573 edges, weights 0.138-0.276 - thresholds swept inside that
range. Baseline = direct top-16 (instrument-consistent with the R34 arms; the
DEF-14 parity caveat applies to all arms equally).

Arms: base | th in {0.15, 0.20, 0.25} with cap 8 additions per probe.
Bar (registered): zero regressions, gains count; REFUTED if expansion floods
the render budget (fully_covered drops). The retro-arm (H365 marks rolled back,
expansion bridging the fragment pair alone) runs SEPARATELY - it mutates graph
state and must not overlap H367's measurement. Graph writes: NONE (this arm).
Entity channel: Titan query embedding (live index space). No GPU.
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
CAP = 8  # max SIMILAR_TO additions per probe
THRESHOLDS = [0.15, 0.20, 0.25]
PROBES = Path("tests/probes/cpap-probe-set.yml")
ARMS = ["base"] + [f"th{t}" for t in THRESHOLDS]


def main():
    base = load_settings(Path("config.yml"))
    vec = base.graphrag.vector_index_name
    st = deepcopy(base)
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = URI, "neo4j", "kgfoundry"
    st.graphrag.top_k = TOP_K

    probes = [p for p in yaml.safe_load(PROBES.read_text()) if p.get("gold_evidence")]

    per = {a: {} for a in ARMS}
    ctx_chars = {a: 0 for a in ARMS}
    added_total = {a: 0 for a in ARMS}
    with Foundry(st) as f:
        for p in probes:
            q = p["question"]
            pe = Entity.create(q[:80], types=["Query"], description=q)
            emb = generate_embeddings([pe], st.embeddings)[0].embedding
            seeds = [s["id"] for s in vector_query(f.driver, emb, vec, top_k=TOP_K)]

            with f.driver.session() as sess:
                rows = sess.run(
                    "MATCH (e:Entity)-[r:SIMILAR_TO]-(n:Entity) WHERE e.id IN $ids "
                    "RETURN DISTINCT n.id AS id, max(r.weight) AS w ORDER BY w DESC",
                    ids=seeds,
                ).data()
                golds = p["gold_evidence"]
                for a in ARMS:
                    if a == "base":
                        ids = seeds
                    else:
                        th = float(a[2:])
                        extra = [r["id"] for r in rows
                                 if r["w"] is not None and r["w"] >= th and r["id"] not in seeds][:CAP]
                        added_total[a] += len(extra)
                        ids = seeds + extra
                    ctx = _render_nodes(sess, ids)
                    ctx_chars[a] += len(ctx)
                    per[a][p["id"]] = sum(_present(g, ctx) for g in golds) / len(golds)
            print(f"{p['id']}: " + " ".join(f"{a}={per[a][p['id']]:.2f}" for a in ARMS), flush=True)

        print("\nARM SUMMARY:", flush=True)
        summary = {}
        n = len(probes)
        for a in ARMS:
            mean = sum(per[a].values()) / n
            full = sum(1 for v in per[a].values() if v == 1.0)
            growth = ctx_chars[a] / ctx_chars["base"] - 1
            summary[a] = {"mean_recall": round(mean, 4), "fully_covered": full,
                          "context_growth": round(growth, 3),
                          "mean_added_seeds": round(added_total[a] / n, 2),
                          "per_probe": {k: round(v, 4) for k, v in per[a].items()}}
            print(f"  {a}: mean {mean:.4f}, full {full}/24, ctx growth {growth:+.1%}, "
                  f"added {added_total[a] / n:.1f}", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/r34-h370-simexpand-{ts}.json")
    out.write_text(json.dumps({
        "hypothesis": "R34-H370 (forward arm)", "generated": ts, "graph_uri": URI,
        "cap": CAP, "thresholds": THRESHOLDS, "summary": summary,
    }, indent=2))
    print(f"\nH370 FORWARD ARM COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

"""H371 wiring verification - retrieval arm: the ENGINE question channel
(Foundry._question_channel, the shipped read-path code) composed with the
parity entity render on the production pile (neo4j4, READ ONLY), 24-probe
DEF-14 instrument (overfetch top_k*factor -> top_k=16).

Must reproduce the R35-H371 prototype result: mean 1.0, 24/24, zero
regressions vs the 0.8958 parity base. The pile carries the 2,048
r35_prototype KGFQuestion nodes and NO question vector index - the channel's
exhaustive-scan fallback is the path under test there.
"""

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import yaml

sys.path.insert(0, "notebooks")
from h158_measure import _norm, _present, _render_nodes  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.extraction import generate_embeddings  # noqa: E402
from knowledge_graph_foundry.graph.graphrag import overfetch_seeds, vector_query  # noqa: E402
from knowledge_graph_foundry.models import Entity  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

URI = "bolt://172.19.0.100:7687"  # neo4j4 - production pile, READ ONLY
TOP_K = 16
PROBES = Path("tests/probes/cpap-probe-set.yml")


def main():
    base_cfg = load_settings(Path("config/config.yml"))
    st = deepcopy(base_cfg)
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = URI, "neo4j", "kgfoundry"
    st.graphrag.top_k = TOP_K
    assert st.questions.enabled and st.questions.channel_m == 1, "shipped defaults expected"
    vec = st.graphrag.vector_index_name
    factor = st.graphrag.overfetch_factor

    probes = [p for p in yaml.safe_load(PROBES.read_text()) if p.get("gold_evidence")]
    per_base, per_arm = {}, {}
    channel_meta = {}
    with Foundry(st) as f:
        with f.driver.session() as s:
            n_questions = s.run("MATCH (q:KGFQuestion) RETURN count(q) AS n").single()["n"]
            has_index = any(
                r["name"] == st.questions.index_name for r in s.run("SHOW INDEXES YIELD name")
            )
        print(f"pile: {n_questions} KGFQuestion nodes, index present: {has_index}", flush=True)
        for p in probes:
            q = p["question"]
            pe = Entity.create(q[:80], types=["Query"], description=q)
            emb = generate_embeddings([pe], st.embeddings)[0].embedding
            seeds = [
                r["id"]
                for r in overfetch_seeds(
                    lambda k: vector_query(f.driver, emb, vec, top_k=k), TOP_K, factor
                )
            ]
            with f.driver.session() as sess:
                entity_ctx = _render_nodes(sess, seeds)
            # the ENGINE question channel - the exact shipped read-path code
            blocks, names = f._question_channel(emb)
            ctx = entity_ctx + " " + _norm("\n".join(blocks))
            golds = p["gold_evidence"]
            per_base[p["id"]] = round(sum(_present(g, entity_ctx) for g in golds) / len(golds), 4)
            per_arm[p["id"]] = round(sum(_present(g, ctx) for g in golds) / len(golds), 4)
            channel_meta[p["id"]] = {"blocks": len(blocks), "about_names": names[:5]}
            print(
                f"{p['id']}: base={per_base[p['id']]} engine_q={per_arm[p['id']]} "
                f"(blocks={len(blocks)})",
                flush=True,
            )

    def summarize(per):
        return {
            "mean_recall": round(sum(per.values()) / len(per), 4),
            "fully_covered": sum(1 for v in per.values() if v == 1.0),
            "per_probe": per,
        }

    regressions = [pid for pid in per_arm if per_arm[pid] < per_base[pid]]
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {
        "verification": "H371 wiring - retrieval arm (engine question channel)",
        "generated": ts,
        "graph_uri": URI,
        "instrument": "engine parity (DEF-14)",
        "top_k": TOP_K,
        "overfetch_factor": factor,
        "questions_on_pile": n_questions,
        "question_index_present": has_index,
        "channel_m": st.questions.channel_m,
        "base": summarize(per_base),
        "engine_question_channel": summarize(per_arm),
        "regressions_vs_base": regressions,
        "reference": {"prototype_qg_1": 1.0, "prototype_base": 0.8958},
        "channel_meta": channel_meta,
    }
    out = Path(f"reports/h371-wire-retrieval-{ts}.json")
    out.write_text(json.dumps(report, indent=2))
    arm = report["engine_question_channel"]
    print(
        f"\nH371 RETRIEVAL VERIFY COMPLETE: base mean={report['base']['mean_recall']} "
        f"engine_q mean={arm['mean_recall']} full={arm['fully_covered']}/24 "
        f"regressions={regressions or 'none'} -> {out}",
        flush=True,
    )


if __name__ == "__main__":
    main()

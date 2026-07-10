"""R34-H367 OFFLINE PROTOTYPE: proposition-seeded entities enter the render.

The engine already matches queries to proposition sentences and extends seed_ids
with the hits' ABOUT entities - but only PPR consumes the extension and PPR is
off, so the entities never reach the render (pipeline.py:1085 `nodes = seeds`).
This prototype measures the missing routing harness-side, zero graph writes.

Propositions are DETERMINISTIC (one sentence per valid relationship, one per
prop_* set - propositions.py); they are rebuilt here in memory with the module's
own render/split primitives, then embedded LOCALLY (bge-m3 on GPU 2 - new channel
= local space per the 2026-07-10 embeddings directive; the proposition channel
never existed in Titan space, so queries against it embed bge-m3 too). The ENTITY
channel keeps the harness's Titan query embedding (live index space, fixed control).

Arms (per probe, recall@16 harness primitives):
  A  baseline           - vector top-16 render (must reproduce 0.8542)
  B  budget union       - vector seeds + top-8 diversified prop-hit entities,
                          truncated to 16 total (prop entities displace the tail)
  C  additive union     - vector top-16 + prop-hit entities (budget exceeded,
                          upper bound for the lever)
  D  facts only         - vector top-16 render + the 8 matched sentences as a
                          Facts section (decomposes sentence-text vs entity-block)

Bar (registered): zero regressions, any failed-probe gain counts; REFUTED if
seed dilution pushes gold entities out of the render budget (fully_covered
tracked). Graph writes: NONE.
"""

import os

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "2"  # RTX 5000 Ada, idle (GPU 1 holds the H363 ramp)
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import json  # noqa: E402
import sys  # noqa: E402
from copy import deepcopy  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

import yaml  # noqa: E402

sys.path.insert(0, "notebooks")
from h158_measure import _norm, _present, _render_nodes  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.extraction import generate_embeddings  # noqa: E402
from knowledge_graph_foundry.graph.graphrag import vector_query  # noqa: E402
from knowledge_graph_foundry.graph.propositions import (  # noqa: E402
    _split_fat_propositions,
    diversify_hits,
    render_property_sentence,
    render_relation_sentence,
)
from knowledge_graph_foundry.models import Entity  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

URI = "bolt://172.19.0.4:7687"
TOP_K = 16
PROP_TOP_K = 8  # engine default proposition_top_k
PROBES = Path("tests/probes/cpap-probe-set.yml")
EMB_MODEL = "BAAI/bge-m3"
CACHE = Path("results/r34/h367-prop-embs-bgem3.jsonl")
ARMS = ["A", "B", "C", "D"]


def main():
    base = load_settings(Path("config.yml"))
    vec = base.graphrag.vector_index_name
    split_max = base.graphrag.proposition_split_max_tokens
    st = deepcopy(base)
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = URI, "neo4j", "kgfoundry"
    st.graphrag.top_k = TOP_K

    with Foundry(st) as f:
        # rebuild proposition sentences exactly as generate_propositions does, in memory
        sentences: dict[str, set[str]] = {}
        with f.driver.session() as session:
            for row in session.run(
                "MATCH (s:Entity)-[r]->(t:Entity) WHERE r.valid_to IS NULL "
                "RETURN s.id AS sid, s.name AS sname, type(r) AS rel, "
                "t.id AS tid, t.name AS tname"
            ):
                text = render_relation_sentence(row["sname"], row["rel"], row["tname"])
                sentences.setdefault(text, set()).update((row["sid"], row["tid"]))
            for row in session.run(
                "MATCH (e:Entity) WHERE any(k IN keys(e) WHERE k STARTS WITH 'prop_') "
                "RETURN e.id AS id, e.name AS name, properties(e) AS props"
            ):
                spec = {
                    k.removeprefix("prop_"): v
                    for k, v in row["props"].items()
                    if k.startswith("prop_")
                }
                text = render_property_sentence(row["name"], spec)
                sentences.setdefault(text, set()).add(row["id"])
        sentences = _split_fat_propositions(sentences, split_max)
        props = [{"text": t, "entity_ids": sorted(ids)} for t, ids in sentences.items()]
        print(f"propositions (in-memory): {len(props)}", flush=True)

        import torch  # noqa: F401
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(EMB_MODEL, device="cuda")
        model.max_seq_length = 8192
        model.half()

        cache = {}
        if CACHE.exists():
            for line in CACHE.read_text().splitlines():
                rec = json.loads(line)
                cache[rec["text"]] = rec["embedding"]
        todo = [p["text"] for p in props if p["text"] not in cache]
        if todo:
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            with CACHE.open("a") as fh:
                for i in range(0, len(todo), 512):
                    batch = todo[i : i + 512]
                    embs = model.encode(batch, batch_size=64,
                                        normalize_embeddings=True, show_progress_bar=False)
                    for t, e in zip(batch, embs):
                        cache[t] = [float(x) for x in e]
                        fh.write(json.dumps({"text": t, "model": EMB_MODEL,
                                             "embedding": cache[t]}) + "\n")
                    print(f"embedded {min(i + 512, len(todo))}/{len(todo)}", flush=True)
        print(f"proposition embeddings ready: {len(cache)} ({len(todo)} computed)", flush=True)

        probes = [p for p in yaml.safe_load(PROBES.read_text()) if p.get("gold_evidence")]
        q_embs = model.encode([p["question"] for p in probes], batch_size=8,
                              normalize_embeddings=True, show_progress_bar=False)
        q_emb_by_id = {p["id"]: e for p, e in zip(probes, q_embs)}

        per = {a: {} for a in ARMS}
        ctx_chars = {a: 0 for a in ARMS}
        for p in probes:
            q = p["question"]
            pe = Entity.create(q[:80], types=["Query"], description=q)
            emb = generate_embeddings([pe], st.embeddings)[0].embedding  # Titan: entity index space
            seeds = [s["id"] for s in vector_query(f.driver, emb, vec, top_k=TOP_K)]

            qe = q_emb_by_id[p["id"]]
            ranked = sorted(props, key=lambda pr: -sum(a * b for a, b in zip(qe, cache[pr["text"]])))
            hits = diversify_hits(
                [{"text": pr["text"], "entity_ids": pr["entity_ids"], "score": 0.0} for pr in ranked[:64]],
                PROP_TOP_K,
            )
            prop_eids = []
            for h in hits:
                for eid in h["entity_ids"]:
                    if eid not in prop_eids and eid not in seeds:
                        prop_eids.append(eid)
            fact_lines = _norm(" ".join(h["text"] for h in hits))

            arm_seeds = {
                "A": seeds,
                "B": (seeds + prop_eids)[:TOP_K] if len(seeds) < TOP_K
                     else seeds[: TOP_K - min(len(prop_eids), 4)] + prop_eids[:4],
                "C": seeds + prop_eids,
                "D": seeds,
            }
            golds = p["gold_evidence"]
            with f.driver.session() as sess:
                for a in ARMS:
                    ctx = _render_nodes(sess, arm_seeds[a])
                    if a == "D":
                        ctx = ctx + " " + fact_lines
                    ctx_chars[a] += len(ctx)
                    per[a][p["id"]] = sum(_present(g, ctx) for g in golds) / len(golds)
            print(f"{p['id']}: " + " ".join(f"{a}={per[a][p['id']]:.2f}" for a in ARMS), flush=True)

        print("\nARM SUMMARY:", flush=True)
        summary = {}
        for a in ARMS:
            mean = sum(per[a].values()) / len(per[a])
            full = sum(1 for v in per[a].values() if v == 1.0)
            growth = ctx_chars[a] / ctx_chars["A"] - 1
            summary[a] = {"mean_recall": round(mean, 4), "fully_covered": full,
                          "context_growth": round(growth, 3),
                          "per_probe": {k: round(v, 4) for k, v in per[a].items()}}
            print(f"  {a}: mean {mean:.4f}, full {full}/24, ctx growth {growth:+.1%}", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/r34-h367-propseeds-{ts}.json")
    out.write_text(json.dumps({
        "hypothesis": "R34-H367", "generated": ts, "graph_uri": URI,
        "proposition_embedder": EMB_MODEL, "propositions": len(props),
        "arms": {"A": "vector top-16 baseline", "B": "budget union (prop entities displace tail)",
                 "C": "additive union (upper bound)", "D": "baseline + fact sentences"},
        "summary": summary,
    }, indent=2))
    print(f"\nH367 PROTOTYPE COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

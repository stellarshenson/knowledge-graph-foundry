"""R35-H374: multi-view retrieval voting - consensus over independent channels.

Three live channels vote per probe (>= 3 per the acceptance bar, all offline):
  entity - Titan query embedding -> kgf_entity_embeddings kNN (the shipped
           channel, fixed control arm)
  props  - bge-m3 query (GPU 2) -> in-memory deterministic propositions ranked
           by dot vs the r34 cache -> owner entities (best prop rank)
  spans  - bge-m3 query -> 900-char spans ranked vs the r34 cache -> chunk ->
           MENTIONED_IN entities (best span rank)

Consensus: entities ordered by (channel-agreement votes desc, reciprocal-rank
fusion desc); top-16 rendered with the harness primitives.

Clauses (registration): zero recall regressions vs the entity-channel baseline
with measurable precision or evacuation gain; REFUTED-as-theater if the
consensus ordering just recapitulates the vector ranking (mean Spearman over
the union of top-32 sets > 0.95).
"""

import os

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "2"  # RTX 5000 Ada; GPU 1 holds the H363 ramp
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import json  # noqa: E402
import sys  # noqa: E402
from copy import deepcopy  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

import yaml  # noqa: E402

sys.path.insert(0, "notebooks")
from h158_measure import _present, _render_nodes  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.extraction import generate_embeddings  # noqa: E402
from knowledge_graph_foundry.graph.graphrag import vector_query  # noqa: E402
from knowledge_graph_foundry.graph.propositions import (  # noqa: E402
    _split_fat_propositions,
    render_property_sentence,
    render_relation_sentence,
)
from knowledge_graph_foundry.models import Entity  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

URI = "bolt://172.19.0.100:7687"
PROBES = Path("tests/probes/cpap-probe-set.yml")
PROP_CACHE = Path("tmp/cache/h367-prop-embs-bgem3.jsonl")
SPAN_CACHE = Path("tmp/cache/h366-span-embs-bgem3.jsonl")
TOP_K = 16
CHANNEL_K = 32  # per-channel candidate depth
RRF_K = 60


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def spearman(order_a: list, order_b: list) -> float:
    union = list(dict.fromkeys(order_a + order_b))
    n = len(union)
    if n < 2:
        return 1.0
    ra = {e: i for i, e in enumerate(order_a)}
    rb = {e: i for i, e in enumerate(order_b)}
    fa = [ra.get(e, len(order_a)) for e in union]
    fb = [rb.get(e, len(order_b)) for e in union]
    d2 = sum((x - y) ** 2 for x, y in zip(fa, fb))
    return 1 - 6 * d2 / (n * (n * n - 1))


def main():
    base = load_settings(Path("config/config.yml"))
    vec = base.graphrag.vector_index_name
    st = deepcopy(base)
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = URI, "neo4j", "kgfoundry"
    probes = [p for p in yaml.safe_load(PROBES.read_text()) if p.get("gold_evidence")]

    prop_cache = {}
    for line in PROP_CACHE.read_text().splitlines():
        rec = json.loads(line)
        prop_cache[rec["text"]] = rec["embedding"]
    span_cache = {}
    for line in SPAN_CACHE.read_text().splitlines():
        rec = json.loads(line)
        span_cache[rec["key"]] = rec["embedding"]
    print(f"caches: {len(prop_cache)} props, {len(span_cache)} spans", flush=True)

    import torch  # noqa: F401
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("BAAI/bge-m3", device="cuda")
    model.max_seq_length = 8192
    model.half()
    q_embs = model.encode(
        [p["question"] for p in probes], batch_size=8,
        normalize_embeddings=True, show_progress_bar=False,
    )
    q_emb = {p["id"]: e for p, e in zip(probes, q_embs)}

    with Foundry(st) as f:
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
            chunk_ents = {
                r["cid"]: r["eids"]
                for r in session.run(
                    "MATCH (e:Entity)-[:MENTIONED_IN]->(c:Chunk) "
                    "RETURN c.id AS cid, collect(e.id) AS eids"
                )
            }
        sentences = _split_fat_propositions(
            sentences, base.graphrag.proposition_split_max_tokens
        )
        props = [
            {"text": t, "entity_ids": sorted(ids)}
            for t, ids in sentences.items()
            if t in prop_cache
        ]
        print(f"propositions: {len(props)} (cache-covered)", flush=True)

        span_keys = list(span_cache)
        per_base, per_cons, spearmans, turnover = {}, {}, [], []
        for p in probes:
            q = p["question"]
            pe = Entity.create(q[:80], types=["Query"], description=q)
            emb = generate_embeddings([pe], st.embeddings)[0].embedding
            entity_rank = [s["id"] for s in vector_query(f.driver, emb, vec, top_k=CHANNEL_K)]

            qe = q_emb[p["id"]]
            prop_sorted = sorted(props, key=lambda pr: -dot(qe, prop_cache[pr["text"]]))
            prop_rank, seen = [], set()
            for pr in prop_sorted:
                for eid in pr["entity_ids"]:
                    if eid not in seen:
                        seen.add(eid)
                        prop_rank.append(eid)
                if len(prop_rank) >= CHANNEL_K:
                    break
            prop_rank = prop_rank[:CHANNEL_K]

            span_sorted = sorted(span_keys, key=lambda k: -dot(qe, span_cache[k]))
            span_rank, seen = [], set()
            for key in span_sorted:
                for eid in chunk_ents.get(key.split(":")[0], []):
                    if eid not in seen:
                        seen.add(eid)
                        span_rank.append(eid)
                if len(span_rank) >= CHANNEL_K:
                    break
            span_rank = span_rank[:CHANNEL_K]

            channels = [entity_rank, prop_rank, span_rank]
            score = {}
            for ch in channels:
                for i, eid in enumerate(ch):
                    votes, rrf = score.get(eid, (0, 0.0))
                    score[eid] = (votes + 1, rrf + 1 / (RRF_K + i))
            consensus = sorted(score, key=lambda e: score[e], reverse=True)

            with f.driver.session() as sess:
                ctx_b = _render_nodes(sess, entity_rank[:TOP_K])
                ctx_c = _render_nodes(sess, consensus[:TOP_K])
            golds = p["gold_evidence"]
            per_base[p["id"]] = round(sum(_present(g, ctx_b) for g in golds) / len(golds), 4)
            per_cons[p["id"]] = round(sum(_present(g, ctx_c) for g in golds) / len(golds), 4)
            spearmans.append(round(spearman(consensus[:CHANNEL_K], entity_rank), 4))
            turnover.append(TOP_K - len(set(entity_rank[:TOP_K]) & set(consensus[:TOP_K])))
            print(
                f"{p['id']}: base={per_base[p['id']]} cons={per_cons[p['id']]} "
                f"rho={spearmans[-1]} turnover={turnover[-1]}",
                flush=True,
            )

    mean_b = round(sum(per_base.values()) / len(per_base), 4)
    mean_c = round(sum(per_cons.values()) / len(per_cons), 4)
    regress = {p: (per_base[p], per_cons[p]) for p in per_base if per_cons[p] < per_base[p]}
    mean_rho = round(sum(spearmans) / len(spearmans), 4)
    print(
        f"\nbaseline mean={mean_b} full={sum(1 for v in per_base.values() if v == 1.0)}/24; "
        f"consensus mean={mean_c} full={sum(1 for v in per_cons.values() if v == 1.0)}/24",
        flush=True,
    )
    print(f"regressions: {regress}", flush=True)
    print(f"mean spearman vs entity ranking: {mean_rho} (theater if > 0.95)", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/r35-h374-consensus-{ts}.json")
    out.write_text(json.dumps({
        "hypothesis": "R35-H374 multi-view consensus voting",
        "generated": ts,
        "graph_uri": URI,
        "channels": ["entity(titan)", "props(bge-m3)", "spans(bge-m3)"],
        "channel_k": CHANNEL_K,
        "baseline_mean": mean_b,
        "consensus_mean": mean_c,
        "baseline_full": sum(1 for v in per_base.values() if v == 1.0),
        "consensus_full": sum(1 for v in per_cons.values() if v == 1.0),
        "regressions": {p: list(v) for p, v in regress.items()},
        "mean_spearman_vs_entity": mean_rho,
        "per_probe_spearman": dict(zip([p["id"] for p in probes], spearmans)),
        "render_turnover_per_probe": dict(zip([p["id"] for p in probes], turnover)),
        "per_probe": {p: [per_base[p], per_cons[p]] for p in per_base},
    }, indent=2))
    print(f"\nH374 CONSENSUS COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

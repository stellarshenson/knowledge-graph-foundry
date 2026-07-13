"""R35-H374 precision arm: the deferred verdict clause. The 2026-07-10 context
run proved not-theater (mean rho 0.5494) and zero recall regressions with
bit-identical recall - the registered "measurable precision or evacuation
gain" needs a relevance judge over the rendered entities, now live post-H363
(gpt-oss-120b on vLLM).

Reconstructs the same three channels (entity/Titan control, props/bge-m3,
spans/bge-m3 from the r34 caches) and the same consensus ordering, then judges
every unique (probe, rendered-entity) pair once: does the entity block carry
information relevant to answering the probe? Precision@16 per arm; evacuation
gain = irrelevant baseline entities evicted minus relevant ones evicted.

Graph writes: NONE.
"""

import os

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "2"
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import json  # noqa: E402
import sys  # noqa: E402
import urllib.request  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402
from copy import deepcopy  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

import yaml  # noqa: E402

sys.path.insert(0, "notebooks")
sys.path.insert(0, "src")
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
VLLM = "http://localhost:8010/v1/chat/completions"
MODEL = "gpt-oss-120b"
PROBES = Path("tests/probes/cpap-probe-set.yml")
PROP_CACHE = Path("tmp/cache/h367-prop-embs-bgem3.jsonl")
SPAN_CACHE = Path("tmp/cache/h366-span-embs-bgem3.jsonl")
JUDGE_CACHE = Path("tmp/results/r35/h374-judge-cache.jsonl")
TOP_K = 16
CHANNEL_K = 32
RRF_K = 60


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def judge(question: str, block: str) -> bool:
    prompt = (
        "QUESTION: " + question + "\n\nENTITY RECORD:\n" + block[:2500] + "\n\n"
        "Does this entity record contain information that helps answer the question "
        "(the asked-about product, feature, or value)? Answer with exactly one word: yes or no."
    )
    body = json.dumps({"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.0, "max_tokens": 500}).encode()
    req = urllib.request.Request(VLLM, data=body, headers={"Content-Type": "application/json"})
    resp = json.load(urllib.request.urlopen(req, timeout=600))
    return resp["choices"][0]["message"]["content"].strip().lower().startswith("yes")


def main():
    base = load_settings(Path("config/config.yml"))
    vec = base.graphrag.vector_index_name
    st = deepcopy(base)
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = URI, "neo4j", "kgfoundry"
    probes = [p for p in yaml.safe_load(PROBES.read_text()) if p.get("gold_evidence")]

    prop_cache = {json.loads(l)["text"]: json.loads(l)["embedding"] for l in PROP_CACHE.read_text().splitlines()}
    span_cache = {json.loads(l)["key"]: json.loads(l)["embedding"] for l in SPAN_CACHE.read_text().splitlines()}
    print(f"caches: {len(prop_cache)} props, {len(span_cache)} spans", flush=True)

    import torch  # noqa: F401
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("BAAI/bge-m3", device="cuda")
    model.max_seq_length = 8192
    model.half()
    q_embs = model.encode([p["question"] for p in probes], batch_size=8,
                          normalize_embeddings=True, show_progress_bar=False)
    q_emb = {p["id"]: e for p, e in zip(probes, q_embs)}

    with Foundry(st) as f:
        sentences: dict[str, set[str]] = {}
        with f.driver.session() as session:
            for row in session.run(
                "MATCH (s:Entity)-[r]->(t:Entity) WHERE r.valid_to IS NULL "
                "RETURN s.id AS sid, s.name AS sname, type(r) AS rel, t.id AS tid, t.name AS tname"
            ):
                text = render_relation_sentence(row["sname"], row["rel"], row["tname"])
                sentences.setdefault(text, set()).update((row["sid"], row["tid"]))
            for row in session.run(
                "MATCH (e:Entity) WHERE any(k IN keys(e) WHERE k STARTS WITH 'prop_') "
                "RETURN e.id AS id, e.name AS name, properties(e) AS props"
            ):
                spec = {k.removeprefix("prop_"): v for k, v in row["props"].items() if k.startswith("prop_")}
                text = render_property_sentence(row["name"], spec)
                sentences.setdefault(text, set()).add(row["id"])
            chunk_ents = {r["cid"]: r["eids"] for r in session.run(
                "MATCH (e:Entity)-[:MENTIONED_IN]->(c:Chunk) RETURN c.id AS cid, collect(e.id) AS eids")}
        sentences = _split_fat_propositions(sentences, base.graphrag.proposition_split_max_tokens)
        props = [{"text": t, "entity_ids": sorted(ids)} for t, ids in sentences.items() if t in prop_cache]
        span_keys = list(span_cache)

        cache = {}
        if JUDGE_CACHE.exists():
            for line in JUDGE_CACHE.read_text().splitlines():
                r = json.loads(line)
                cache[(r["probe"], r["eid"])] = r["relevant"]
        jfh = JUDGE_CACHE.open("a")

        results = {}
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

            score = {}
            for ch in (entity_rank, prop_rank, span_rank):
                for i, eid in enumerate(ch):
                    votes, rrf = score.get(eid, (0, 0.0))
                    score[eid] = (votes + 1, rrf + 1 / (RRF_K + i))
            consensus = sorted(score, key=lambda e: score[e], reverse=True)

            arm_base, arm_cons = entity_rank[:TOP_K], consensus[:TOP_K]
            uniq = list(dict.fromkeys(arm_base + arm_cons))
            with f.driver.session() as sess:
                blocks = {eid: _render_nodes(sess, [eid]) for eid in uniq}

            todo = [eid for eid in uniq if (p["id"], eid) not in cache]
            with ThreadPoolExecutor(max_workers=8) as pool:
                verdicts = list(pool.map(lambda e: judge(q, blocks[e]), todo))
            for eid, v in zip(todo, verdicts):
                cache[(p["id"], eid)] = v
                jfh.write(json.dumps({"probe": p["id"], "eid": eid, "relevant": v}) + "\n")
            jfh.flush()

            prec_b = sum(cache[(p["id"], e)] for e in arm_base) / TOP_K
            prec_c = sum(cache[(p["id"], e)] for e in arm_cons) / TOP_K
            evicted = [e for e in arm_base if e not in arm_cons]
            admitted = [e for e in arm_cons if e not in arm_base]
            ev_irr = sum(1 for e in evicted if not cache[(p["id"], e)])
            ad_rel = sum(1 for e in admitted if cache[(p["id"], e)])
            golds = p["gold_evidence"]
            ctx_b = " ".join(blocks[e] for e in arm_base)
            ctx_c = " ".join(blocks[e] for e in arm_cons)
            rec_b = round(sum(_present(g, ctx_b) for g in golds) / len(golds), 4)
            rec_c = round(sum(_present(g, ctx_c) for g in golds) / len(golds), 4)
            results[p["id"]] = {
                "precision_base": round(prec_b, 4), "precision_consensus": round(prec_c, 4),
                "recall_base": rec_b, "recall_consensus": rec_c,
                "turnover": len(evicted), "evicted_irrelevant": ev_irr, "admitted_relevant": ad_rel,
            }
            print(f"{p['id']}: prec {prec_b:.3f}->{prec_c:.3f} rec {rec_b}->{rec_c} "
                  f"turnover={len(evicted)} evict_irr={ev_irr} admit_rel={ad_rel}", flush=True)
        jfh.close()

    mp_b = round(sum(r["precision_base"] for r in results.values()) / len(results), 4)
    mp_c = round(sum(r["precision_consensus"] for r in results.values()) / len(results), 4)
    mr_b = round(sum(r["recall_base"] for r in results.values()) / len(results), 4)
    mr_c = round(sum(r["recall_consensus"] for r in results.values()) / len(results), 4)
    regress = [k for k, r in results.items() if r["recall_consensus"] < r["recall_base"]]
    print(f"\nmean precision: base={mp_b} consensus={mp_c} (delta {mp_c-mp_b:+.4f})", flush=True)
    print(f"mean recall: base={mr_b} consensus={mr_c}; regressions={regress or 'none'}", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/experiments/adjudicated/r35-h374-precision-{ts}.json")
    out.write_text(json.dumps({
        "hypothesis": "R35-H374 multi-view consensus - precision arm (deferred clause)",
        "generated": ts, "graph_uri": URI,
        "judge": MODEL, "channels": ["entity(titan)", "props(bge-m3)", "spans(bge-m3)"],
        "top_k": TOP_K, "channel_k": CHANNEL_K,
        "note": "channel fetch depth 32 truncated to render 16, matching the 20260710 context run",
        "mean_precision_base": mp_b, "mean_precision_consensus": mp_c,
        "precision_delta": round(mp_c - mp_b, 4),
        "mean_recall_base": mr_b, "mean_recall_consensus": mr_c,
        "recall_regressions": regress,
        "per_probe": results,
    }, indent=2))
    print(f"H374 PRECISION COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

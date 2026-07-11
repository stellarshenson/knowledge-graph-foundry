"""R34 COMPOSED FRONTIER: the three confirmed levers measured together.

Levers, in the order they stack:
  parity   - engine-parity retrieval (overfetch 64 -> head 16, R15-H195a; DEF-14)
  +props   - H367 arm B: top-8 diversified proposition hits' ABOUT entities
             displace the vector tail (16 seeds total)
  +window  - H366 s900k1: top query-anchored 900-char span rendered after the
             entity blocks (bge-m3 space, cached)

Prediction: full compose reaches 23/24 fully covered - every failed probe except
P08 (reader parse loss: gold absent from every extracted text; no retrieval-side
lever can carry it). Caches reused; only probe questions embed fresh. Writes: NONE.
"""

import os

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "2"
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

URI = "bolt://172.19.0.100:7687"
TOP_K = 16
OVERFETCH = 64
PROP_TOP_K = 8
SPAN = 900
PROBES = Path("tests/probes/cpap-probe-set.yml")
EMB_MODEL = "BAAI/bge-m3"
SPAN_CACHE = Path("tmp/cache/h366-span-embs-bgem3.jsonl")
PROP_CACHE = Path("tmp/cache/h367-prop-embs-bgem3.jsonl")
ARMS = ["parity", "parity+props", "parity+props+window"]


def main():
    base = load_settings(Path("config/config.yml"))
    vec = base.graphrag.vector_index_name
    split_max = base.graphrag.proposition_split_max_tokens
    st = deepcopy(base)
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = URI, "neo4j", "kgfoundry"
    st.graphrag.top_k = TOP_K

    # span pool: rebuild texts (parse) and pair with the cached embeddings
    ex = load_settings(Path("config/experiments/config-r29-v1.yml")).extraction
    from knowledge_graph_foundry.ingest.chunking import chunk_document
    from knowledge_graph_foundry.ingest.readers import iter_source_files, read_document

    chunks = []
    for f in iter_source_files(Path("data/external/cpap-datasheets-and-manuals")):
        if f.suffix.lower() != ".pdf":
            continue
        try:
            doc = read_document(f, parser_union=ex.parser_union, glyph_normalization=ex.glyph_normalization)
            chunks.extend(chunk_document(doc, ex.chunk_size, ex.chunk_overlap, ex.header_carryover))
        except Exception as exc:
            print(f"skip {f.name}: {exc}", flush=True)
    span_emb = {}
    for line in SPAN_CACHE.read_text().splitlines():
        rec = json.loads(line)
        span_emb[rec["key"]] = rec["embedding"]
    spans = []
    stride = SPAN // 2
    for ch in chunks:
        for start in range(0, max(len(ch.text) - stride, 1), stride):
            piece = ch.text[start : start + SPAN]
            key = f"{ch.id}:{SPAN}:{start}"
            if piece.strip() and key in span_emb:
                spans.append({"key": key, "text": piece})
    print(f"spans: {len(spans)} (cache {len(span_emb)})", flush=True)

    prop_emb = {}
    for line in PROP_CACHE.read_text().splitlines():
        rec = json.loads(line)
        prop_emb[rec["text"]] = rec["embedding"]

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
                sentences.setdefault(render_property_sentence(row["name"], spec), set()).add(row["id"])
        sentences = _split_fat_propositions(sentences, split_max)
        props = [{"text": t, "entity_ids": sorted(ids)} for t, ids in sentences.items() if t in prop_emb]
        print(f"propositions: {len(props)}", flush=True)

        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(EMB_MODEL, device="cuda")
        model.max_seq_length = 8192
        model.half()
        probes = [p for p in yaml.safe_load(PROBES.read_text()) if p.get("gold_evidence")]
        q_embs = model.encode([p["question"] for p in probes], batch_size=8,
                              normalize_embeddings=True, show_progress_bar=False)
        q_by_id = {p["id"]: e for p, e in zip(probes, q_embs)}

        per = {a: {} for a in ARMS}
        ctx_chars = {a: 0 for a in ARMS}
        for p in probes:
            q = p["question"]
            pe = Entity.create(q[:80], types=["Query"], description=q)
            emb = generate_embeddings([pe], st.embeddings)[0].embedding  # Titan: entity index space
            parity = [s["id"] for s in vector_query(f.driver, emb, vec, top_k=OVERFETCH)][:TOP_K]

            qe = q_by_id[p["id"]]
            ranked_props = sorted(props, key=lambda pr: -sum(a * b for a, b in zip(qe, prop_emb[pr["text"]])))
            hits = diversify_hits(
                [{"text": pr["text"], "entity_ids": pr["entity_ids"], "score": 0.0} for pr in ranked_props[:64]],
                PROP_TOP_K,
            )
            prop_eids = []
            for h in hits:
                for eid in h["entity_ids"]:
                    if eid not in prop_eids and eid not in parity:
                        prop_eids.append(eid)
            union = parity[: TOP_K - min(len(prop_eids), 4)] + prop_eids[:4]

            top_span = max(spans, key=lambda s: sum(a * b for a, b in zip(qe, span_emb[s["key"]])))
            window = _norm(top_span["text"])

            arm_def = {
                "parity": (parity, ""),
                "parity+props": (union, ""),
                "parity+props+window": (union, window),
            }
            golds = p["gold_evidence"]
            with f.driver.session() as sess:
                for a in ARMS:
                    ids, extra = arm_def[a]
                    ctx = _render_nodes(sess, ids)
                    if extra:
                        ctx = ctx + " " + extra
                    ctx_chars[a] += len(ctx)
                    per[a][p["id"]] = sum(_present(g, ctx) for g in golds) / len(golds)
            print(f"{p['id']}: " + " ".join(f"{a}={per[a][p['id']]:.2f}" for a in ARMS), flush=True)

        print("\nCOMPOSED FRONTIER:", flush=True)
        summary = {}
        n = len(probes)
        for a in ARMS:
            mean = sum(per[a].values()) / n
            full = sum(1 for v in per[a].values() if v == 1.0)
            growth = ctx_chars[a] / ctx_chars["parity"] - 1
            summary[a] = {"mean_recall": round(mean, 4), "fully_covered": full,
                          "context_growth": round(growth, 3),
                          "per_probe": {k: round(v, 4) for k, v in per[a].items()}}
            print(f"  {a}: mean {mean:.4f}, full {full}/24, ctx growth {growth:+.1%}", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/r34-composed-frontier-{ts}.json")
    out.write_text(json.dumps({
        "measurement": "R34 composed frontier (parity + H367B + H366 s900k1)",
        "generated": ts, "graph_uri": URI, "summary": summary,
    }, indent=2))
    print(f"\nCOMPOSED FRONTIER COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

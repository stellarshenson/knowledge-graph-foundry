"""R34-H366 QUERY-ANCHORED WINDOW ARM: the render that satisfies BOTH bar clauses.

Trunc arm verdict: head-truncation fails structurally - the golds sit deeper than
1200 chars into their chunks (P22 gold > 1200, P21 in (800,1200], P15's second
gold > 1200) while the 30% budget actually affords ~2800 chars/probe (entity ctx
averages ~9.4k chars). A query-anchored window - sub-spans ranked by query
similarity in bge-m3 space - can reach a gold ANYWHERE in a chunk within budget.

Spans: sliding windows over each chunk (SPAN chars, stride SPAN/2), embedded on
GPU 2 (cache results/r34/h366-span-embs-bgem3.jsonl). Per probe the top-K spans
by dot product are rendered after the entity blocks. Sweep (SPAN, K) in
{900, 1200} x {1, 2}. Bar: P21+P22 flip, zero regressions, growth <= 30%.
Entity channel unchanged (Titan query embedding, live index space). Writes: NONE.
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
from knowledge_graph_foundry.ingest.chunking import chunk_document  # noqa: E402
from knowledge_graph_foundry.ingest.readers import iter_source_files, read_document  # noqa: E402
from knowledge_graph_foundry.models import Entity  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

URI = "bolt://172.19.0.4:7687"
TOP_K = 16
SWEEP = [(900, 1), (900, 2), (1200, 1), (1200, 2)]  # (span chars, spans rendered)
CORPUS = Path("data/external/cpap-datasheets-and-manuals")
PROBES = Path("tests/probes/cpap-probe-set.yml")
EMB_MODEL = "BAAI/bge-m3"
CACHE = Path("results/r34/h366-span-embs-bgem3.jsonl")


def spans_of(text: str, span: int):
    stride = span // 2
    out = []
    for start in range(0, max(len(text) - stride, 1), stride):
        piece = text[start : start + span]
        if piece.strip():
            out.append((start, piece))
    return out


def main():
    settings = load_settings(Path("config-r29-v1.yml"))
    ex = settings.extraction

    chunks = []
    for f in iter_source_files(CORPUS):
        if f.suffix.lower() != ".pdf":
            continue
        try:
            doc = read_document(f, parser_union=ex.parser_union, glyph_normalization=ex.glyph_normalization)
            for ch in chunk_document(doc, ex.chunk_size, ex.chunk_overlap, ex.header_carryover):
                chunks.append(ch)
        except Exception as exc:
            print(f"skip {f.name}: {exc}", flush=True)
    print(f"chunk pool: {len(chunks)}", flush=True)

    # span pool per span-size, keyed for the cache
    pools = {}
    for span, _ in SWEEP:
        if span in pools:
            continue
        pool = []
        for ch in chunks:
            for start, piece in spans_of(ch.text, span):
                pool.append({"key": f"{ch.id}:{span}:{start}", "text": piece})
        pools[span] = pool
    print("span pools: " + ", ".join(f"s{k}={len(v)}" for k, v in pools.items()), flush=True)

    import torch  # noqa: F401
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMB_MODEL, device="cuda")
    model.max_seq_length = 8192
    model.half()

    cache = {}
    if CACHE.exists():
        for line in CACHE.read_text().splitlines():
            rec = json.loads(line)
            cache[rec["key"]] = rec["embedding"]
    todo = [s for pool in pools.values() for s in pool if s["key"] not in cache]
    if todo:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        embs = model.encode([s["text"] for s in todo], batch_size=16,
                            normalize_embeddings=True, show_progress_bar=False)
        with CACHE.open("a") as fh:
            for s, e in zip(todo, embs):
                cache[s["key"]] = [float(x) for x in e]
                fh.write(json.dumps({"key": s["key"], "model": EMB_MODEL, "embedding": cache[s["key"]]}) + "\n")
    print(f"span embeddings ready: {len(cache)} ({len(todo)} computed)", flush=True)

    probes = [p for p in yaml.safe_load(PROBES.read_text()) if p.get("gold_evidence")]
    q_embs = model.encode([p["question"] for p in probes], batch_size=8,
                          normalize_embeddings=True, show_progress_bar=False)
    q_emb_by_id = {p["id"]: e for p, e in zip(probes, q_embs)}

    base = load_settings(Path("config.yml"))
    vec = base.graphrag.vector_index_name
    st = deepcopy(base)
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = URI, "neo4j", "kgfoundry"
    st.graphrag.top_k = TOP_K

    per = {cfg: {} for cfg in SWEEP}
    ctx_chars = {cfg: 0 for cfg in SWEEP}
    base_chars = 0
    with Foundry(st) as f:
        for p in probes:
            q = p["question"]
            pe = Entity.create(q[:80], types=["Query"], description=q)
            emb = generate_embeddings([pe], st.embeddings)[0].embedding  # Titan: live entity index space
            seeds = [s["id"] for s in vector_query(f.driver, emb, vec, top_k=TOP_K)]
            with f.driver.session() as sess:
                entity_ctx = _render_nodes(sess, seeds)
            base_chars += len(entity_ctx)
            qe = q_emb_by_id[p["id"]]
            golds = p["gold_evidence"]
            for cfg in SWEEP:
                span, k = cfg
                ranked = sorted(pools[span],
                                key=lambda s: -sum(a * b for a, b in zip(qe, cache[s["key"]])))
                passage_ctx = _norm("\n".join(s["text"] for s in ranked[:k]))
                ctx = entity_ctx + " " + passage_ctx
                ctx_chars[cfg] += len(ctx)
                per[cfg][p["id"]] = sum(_present(g, ctx) for g in golds) / len(golds)
            print(f"{p['id']}: " + " ".join(f"s{s}k{k}={per[(s, k)][p['id']]:.2f}" for s, k in SWEEP), flush=True)

    print("\nWINDOW SWEEP:", flush=True)
    summary = {}
    for cfg in SWEEP:
        span, k = cfg
        mean = sum(per[cfg].values()) / len(per[cfg])
        full = sum(1 for v in per[cfg].values() if v == 1.0)
        growth = ctx_chars[cfg] / base_chars - 1
        summary[f"s{span}k{k}"] = {"span": span, "k": k, "mean_recall": round(mean, 4),
                                   "fully_covered": full, "context_growth": round(growth, 3),
                                   "per_probe": {kk: round(v, 4) for kk, v in per[cfg].items()}}
        print(f"  span={span} k={k}: mean {mean:.4f}, full {full}/24, ctx growth {growth:+.1%}", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/r34-h366-window-{ts}.json")
    out.write_text(json.dumps({
        "hypothesis": "R34-H366 (query-anchored window arm)", "generated": ts, "graph_uri": URI,
        "passage_embedder": EMB_MODEL, "sweep": [list(c) for c in SWEEP],
        "summary": summary,
    }, indent=2))
    print(f"\nH366 WINDOW ARM COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

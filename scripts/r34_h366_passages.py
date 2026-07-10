"""R34-H366 OFFLINE PROTOTYPE: passage nodes as retrieval targets (harness-side).

Passage channel embeds LOCALLY on GPU (user directive 2026-07-10: no Titan for new
bulk embedding compute; embedding models configurable - see acc-crit Embeddings):
BAAI/bge-m3 (1024-dim, 8192-token context - whole 2000-token chunks fit) on the
idle RTX 5000 Ada (nvidia-smi index 2). The ENTITY channel keeps the harness's
Titan query embedding because the live graph's entity index is Titan-space - the
control arm of the A/B must stay fixed; full local-space migration is an acc-crit
item, not a mid-experiment swap.

Per probe, top-M chunks by cosine (bge-m3 space) are rendered verbatim after the
entity blocks; recall@16 re-measured for M in {0,1,2,4}. M=0 must reproduce the
post-H365 baseline 0.8542.

Bar (registered): P21 and P22 flip at some M with zero regressions on the other
22 probes and context growth <= 30%. P08 predicted to stay 0.0 (gold never parsed
into any chunk). Graph writes: NONE.
"""

import os

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "2"  # RTX 5000 Ada 32GB, idle (GPU 1 holds the H363 ramp)
os.environ.setdefault("HF_HUB_OFFLINE", "1")  # model is cached; skip hub checks (stall trap)
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
M_SWEEP = [0, 1, 2, 4]
CORPUS = Path("data/external/cpap-datasheets-and-manuals")
PROBES = Path("tests/probes/cpap-probe-set.yml")
EMB_MODEL = "BAAI/bge-m3"  # local, GPU; 1024-dim dense
CACHE = Path("results/r34/h366-chunk-embs-bgem3.jsonl")


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

    import torch
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMB_MODEL, device="cuda")
    model.max_seq_length = 8192
    if torch.cuda.is_available():
        model.half()  # Ada sm_89: fp16 is the free +18% (my-gpu recipe)
    print(f"embedder: {EMB_MODEL} on {torch.cuda.get_device_name(0)}", flush=True)

    cache = {}
    if CACHE.exists():
        for line in CACHE.read_text().splitlines():
            rec = json.loads(line)
            cache[rec["id"]] = rec["embedding"]
    todo = [ch for ch in chunks if ch.id not in cache]
    if todo:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        embs = model.encode([ch.text for ch in todo], batch_size=8,
                            normalize_embeddings=True, show_progress_bar=False)
        with CACHE.open("a") as fh:
            for ch, e in zip(todo, embs):
                cache[ch.id] = [float(x) for x in e]
                fh.write(json.dumps({"id": ch.id, "model": EMB_MODEL, "embedding": cache[ch.id]}) + "\n")
    print(f"chunk embeddings ready: {len(cache)} ({len(todo)} computed)", flush=True)

    probes = [p for p in yaml.safe_load(PROBES.read_text()) if p.get("gold_evidence")]
    q_embs = model.encode([p["question"] for p in probes], batch_size=8,
                          normalize_embeddings=True, show_progress_bar=False)
    q_emb_by_id = {p["id"]: e for p, e in zip(probes, q_embs)}

    base = load_settings(Path("config.yml"))
    vec = base.graphrag.vector_index_name
    st = deepcopy(base)
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = URI, "neo4j", "kgfoundry"
    st.graphrag.top_k = TOP_K

    per = {m: {} for m in M_SWEEP}
    ctx_chars = {m: 0 for m in M_SWEEP}
    with Foundry(st) as f:
        for p in probes:
            q = p["question"]
            pe = Entity.create(q[:80], types=["Query"], description=q)
            emb = generate_embeddings([pe], st.embeddings)[0].embedding  # Titan: matches the live entity index space
            seeds = [s["id"] for s in vector_query(f.driver, emb, vec, top_k=TOP_K)]
            with f.driver.session() as sess:
                entity_ctx = _render_nodes(sess, seeds)
            qe = q_emb_by_id[p["id"]]
            ranked = sorted(chunks, key=lambda ch: -sum(a * b for a, b in zip(qe, cache[ch.id])))
            for m in M_SWEEP:
                passage_ctx = _norm("\n".join(ch.text for ch in ranked[:m]))
                ctx = entity_ctx + " " + passage_ctx
                ctx_chars[m] += len(ctx)
                golds = p["gold_evidence"]
                per[m][p["id"]] = sum(_present(g, ctx) for g in golds) / len(golds)
            print(f"{p['id']}: " + " ".join(f"M{m}={per[m][p['id']]:.2f}" for m in M_SWEEP), flush=True)

    print("\nSWEEP SUMMARY:", flush=True)
    summary = {}
    for m in M_SWEEP:
        mean = sum(per[m].values()) / len(per[m])
        full = sum(1 for v in per[m].values() if v == 1.0)
        growth = (ctx_chars[m] / ctx_chars[0] - 1) if ctx_chars[0] else 0
        summary[m] = {"mean_recall": round(mean, 4), "fully_covered": full,
                      "context_growth": round(growth, 3),
                      "per_probe": {k: round(v, 4) for k, v in per[m].items()}}
        print(f"  M={m}: mean {mean:.4f}, full {full}/24, ctx growth {growth:+.1%}", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/r34-h366-passages-{ts}.json")
    out.write_text(json.dumps({
        "hypothesis": "R34-H366", "generated": ts, "graph_uri": URI,
        "passage_embedder": EMB_MODEL, "chunk_pool": len(chunks), "m_sweep": M_SWEEP,
        "summary": {str(k): v for k, v in summary.items()},
    }, indent=2))
    print(f"\nH366 PROTOTYPE COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

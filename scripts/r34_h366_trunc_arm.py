"""R34-H366 BUDGETED-RENDER ARM: settle the <=30% context-growth clause at M=1.

The full-chunk sweep passed every recall clause (P21/P22 flip, P15 bonus, zero
regressions, P08 0.0 as predicted) but grew context +78% at M=1. This arm sweeps
head-truncation of the rendered chunk text at M=1: TRUNC=None reproduces the
full-chunk point (internal control), then 1200/800/500 chars. The clause is
settled by the largest TRUNC that keeps all three flips with zero regressions
inside the 30% budget - or shown unreachable by head-truncation.

Reuses results/r34/h366-chunk-embs-bgem3.jsonl (bge-m3 cache); only the 24 probe
questions are embedded fresh on GPU 2. Entity channel unchanged (Titan query
embedding, live index space). Graph writes: NONE.
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
M = 1
TRUNC_SWEEP = [None, 1200, 800, 500]  # chars of rendered chunk text; None = full chunk (control)
CORPUS = Path("data/external/cpap-datasheets-and-manuals")
PROBES = Path("tests/probes/cpap-probe-set.yml")
EMB_MODEL = "BAAI/bge-m3"
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

    cache = {}
    for line in CACHE.read_text().splitlines():
        rec = json.loads(line)
        cache[rec["id"]] = rec["embedding"]
    missing = [ch.id for ch in chunks if ch.id not in cache]
    if missing:
        raise SystemExit(f"cache missing {len(missing)} chunk embeddings - rerun r34_h366_passages.py")
    print(f"chunk embeddings from cache: {len(cache)}", flush=True)

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMB_MODEL, device="cuda")
    model.max_seq_length = 8192
    probes = [p for p in yaml.safe_load(PROBES.read_text()) if p.get("gold_evidence")]
    q_embs = model.encode([p["question"] for p in probes], batch_size=8,
                          normalize_embeddings=True, show_progress_bar=False)
    q_emb_by_id = {p["id"]: e for p, e in zip(probes, q_embs)}

    base = load_settings(Path("config.yml"))
    vec = base.graphrag.vector_index_name
    st = deepcopy(base)
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = URI, "neo4j", "kgfoundry"
    st.graphrag.top_k = TOP_K

    per = {t: {} for t in TRUNC_SWEEP}
    ctx_chars = {t: 0 for t in TRUNC_SWEEP}
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
            top = max(chunks, key=lambda ch: sum(a * b for a, b in zip(qe, cache[ch.id])))
            golds = p["gold_evidence"]
            for t in TRUNC_SWEEP:
                text = top.text if t is None else top.text[:t]
                ctx = entity_ctx + " " + _norm(text)
                ctx_chars[t] += len(ctx)
                per[t][p["id"]] = sum(_present(g, ctx) for g in golds) / len(golds)
            print(f"{p['id']}: " + " ".join(f"T{t}={per[t][p['id']]:.2f}" for t in TRUNC_SWEEP), flush=True)

    print("\nTRUNC SWEEP (M=1):", flush=True)
    summary = {}
    for t in TRUNC_SWEEP:
        mean = sum(per[t].values()) / len(per[t])
        full = sum(1 for v in per[t].values() if v == 1.0)
        growth = ctx_chars[t] / base_chars - 1
        summary[str(t)] = {"mean_recall": round(mean, 4), "fully_covered": full,
                           "context_growth": round(growth, 3),
                           "per_probe": {k: round(v, 4) for k, v in per[t].items()}}
        print(f"  TRUNC={t}: mean {mean:.4f}, full {full}/24, ctx growth {growth:+.1%}", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/r34-h366-trunc-{ts}.json")
    out.write_text(json.dumps({
        "hypothesis": "R34-H366 (budgeted-render arm)", "generated": ts, "graph_uri": URI,
        "passage_embedder": EMB_MODEL, "m": M, "trunc_sweep": [str(t) for t in TRUNC_SWEEP],
        "summary": summary,
    }, indent=2))
    print(f"\nH366 TRUNC ARM COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

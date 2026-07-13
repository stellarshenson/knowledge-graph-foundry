"""R35-H371 stage 3: the registered A/B on the 24 probes, engine-parity
instrument (DEF-14 overfetch default, factor stamped in the report).

Arms (all render the parity entity context first, then append channel chunks):
  base     - entity channel only (parity top-16)
  h366_M   - + top-M chunks by bge-m3 cosine (the post-H366 state, M=1/2/4)
  qg_M     - + top-M chunks via GATED question channel (Titan question embs)
  qu_M     - + top-M chunks via UNGATED question channel (Doc2Query-- clause)
  comp_M   - + h366(M) UNION gated-question(M) chunks (survives-with-H366 clause)

Question channel: the probe's Titan query embedding (identical to the entity
channel's) is dotted against the stored question embeddings; questions rank
chunks via their ANSWERABLE_FROM mapping (max question score per chunk).
"""

import os

os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "2"  # RTX 5000 Ada; GPU 1 holds vLLM
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import json  # noqa: E402
import sys  # noqa: E402
from copy import deepcopy  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

import yaml  # noqa: E402

sys.path.insert(0, "notebooks")
sys.path.insert(0, "src")
from h158_measure import _norm, _present, _render_nodes  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.extraction import generate_embeddings  # noqa: E402
from knowledge_graph_foundry.graph.graphrag import overfetch_seeds, vector_query  # noqa: E402
from knowledge_graph_foundry.models import Entity  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

URI = "bolt://172.19.0.100:7687"
TOP_K = 16
M_SWEEP = [1, 2, 4]
PROBES = Path("tests/probes/cpap-probe-set.yml")
CHUNK_CACHE = Path("tmp/cache/h366-chunk-embs-bgem3.jsonl")
EMBS = Path("tmp/results/r35/h371-question-embs.jsonl")
GATED = Path("tmp/results/r35/h371-gated.json")
EXTRA_QUESTIONS = [p for p in sys.argv[1:] if p.endswith(".json")]  # H372 add-ons


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def rank_chunks_by_questions(q_emb, questions, embs):
    """Chunks ordered by their best-matching question's score."""
    best: dict[str, float] = {}
    for key, meta in questions.items():
        s = dot(q_emb, embs[key])
        for cid in meta["chunks"]:
            if s > best.get(cid, -2.0):
                best[cid] = s
    return sorted(best, key=lambda c: -best[c])


def main():
    embs = {}
    for line in EMBS.read_text().splitlines():
        r = json.loads(line)
        embs[r["key"]] = r["embedding"]
    gated_doc = json.loads(GATED.read_text())
    gated_q = {k: v for k, v in gated_doc["gated"].items() if k in embs}
    ungated_q = {k: v for k, v in gated_doc["ungated"].items() if k in embs}
    for extra in EXTRA_QUESTIONS:  # H372 cross-doc questions ride the same channel
        doc = json.loads(Path(extra).read_text())
        for k, v in doc["gated"].items():
            if k in embs or v.get("embedding"):
                if v.get("embedding"):
                    embs[k] = v["embedding"]
                gated_q[k] = {"q": v["q"], "chunks": v["chunks"]}
                ungated_q[k] = {"q": v["q"], "chunks": v["chunks"]}
    print(f"question index: gated={len(gated_q)} ungated={len(ungated_q)}", flush=True)

    chunk_emb = {}
    for line in CHUNK_CACHE.read_text().splitlines():
        r = json.loads(line)
        chunk_emb[r["id"]] = r["embedding"]

    probes = [p for p in yaml.safe_load(PROBES.read_text()) if p.get("gold_evidence")]

    import torch  # noqa: F401
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("BAAI/bge-m3", device="cuda")
    model.max_seq_length = 8192
    model.half()
    bge_q = model.encode([p["question"] for p in probes], batch_size=8,
                         normalize_embeddings=True, show_progress_bar=False)
    bge_q = {p["id"]: e for p, e in zip(probes, bge_q)}

    base = load_settings(Path("config/config.yml"))
    vec = base.graphrag.vector_index_name
    factor = base.graphrag.overfetch_factor
    st = deepcopy(base)
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = URI, "neo4j", "kgfoundry"

    arms = ["base"] + [f"{a}_{m}" for a in ("h366", "qg", "qu", "comp") for m in M_SWEEP]
    per = {a: {} for a in arms}
    chars = {a: 0 for a in arms}
    with Foundry(st) as f:
        with f.driver.session() as s:
            chunk_text = {r["id"]: r["text"]
                          for r in s.run("MATCH (c:Chunk) RETURN c.id AS id, c.text AS text")}
        for p in probes:
            q = p["question"]
            pe = Entity.create(q[:80], types=["Query"], description=q)
            emb = generate_embeddings([pe], st.embeddings)[0].embedding  # Titan
            seeds = [r["id"] for r in overfetch_seeds(
                lambda k: vector_query(f.driver, emb, vec, top_k=k), TOP_K, factor)]
            with f.driver.session() as sess:
                entity_ctx = _render_nodes(sess, seeds)

            h366_rank = sorted(chunk_emb, key=lambda c: -dot(bge_q[p["id"]], chunk_emb[c]))
            qg_rank = rank_chunks_by_questions(emb, gated_q, embs)
            qu_rank = rank_chunks_by_questions(emb, ungated_q, embs)

            golds = p["gold_evidence"]

            def measure(arm, extra_chunks):
                ctx = entity_ctx + " " + _norm("\n".join(chunk_text[c] for c in extra_chunks))
                chars[arm] += len(ctx)
                per[arm][p["id"]] = round(sum(_present(g, ctx) for g in golds) / len(golds), 4)

            measure("base", [])
            for m in M_SWEEP:
                measure(f"h366_{m}", h366_rank[:m])
                measure(f"qg_{m}", qg_rank[:m])
                measure(f"qu_{m}", qu_rank[:m])
                comp = list(dict.fromkeys(h366_rank[:m] + qg_rank[:m]))
                measure(f"comp_{m}", comp)
            print(f"{p['id']}: base={per['base'][p['id']]} "
                  + " ".join(f"{a}_2={per[f'{a}_2'][p['id']]}" for a in ("h366", "qg", "qu", "comp")),
                  flush=True)

    summary = {}
    for a in arms:
        mean = round(sum(per[a].values()) / len(per[a]), 4)
        full = sum(1 for v in per[a].values() if v == 1.0)
        regress = [pid for pid, v in per[a].items() if v < per["base"][pid]]
        growth = round(chars[a] / chars["base"] - 1, 4)
        summary[a] = {"mean_recall": mean, "fully_covered": full,
                      "regressions_vs_base": regress, "context_growth": growth,
                      "per_probe": per[a]}
        print(f"{a}: mean={mean} full={full}/24 regress={regress or 'none'} growth={growth:+.1%}", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/experiments/adjudicated/r35-h371-questions-{ts}.json")
    out.write_text(json.dumps({
        "hypothesis": "R35-H371 question nodes as retrieval targets",
        "generated": ts, "graph_uri": URI,
        "instrument": "engine parity (DEF-14)", "top_k": TOP_K, "overfetch_factor": factor,
        "question_embedder": "amazon.titan-embed-text-v2:0 (harness query wrapping)",
        "gated_index_size": len(gated_q), "ungated_index_size": len(ungated_q),
        "extra_question_files": EXTRA_QUESTIONS,
        "m_sweep": M_SWEEP,
        "arms": summary,
    }, indent=2))
    print(f"\nH371 MEASURE COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

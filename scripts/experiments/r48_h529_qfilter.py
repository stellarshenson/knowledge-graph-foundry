"""R48-H529 doc2query-- filtering of the question channel.

Scores every KGFQuestion by cosine to its own ANSWERABLE_FROM chunk (chunk
texts embedded once through the shipped embedding channel; historical
retrieval-contribution term SKIPPED - per-question match history was never
persisted, recorded as a deviation). Prune sweep drops the bottom fraction;
each eligible probe's shipped render is replayed with its question block
re-resolved against the surviving set (channel M=1 emulation: top surviving
question by cosine). Criterion = prober instrument vs the paired baseline.

Registered: docs/experiments/kgf-redesign-experiments.md R48-H529.
Bars (adapted to this instrument, noted): CONFIRMED if >= 25% pruned with
pass rate within 1 probe of baseline and measurable question-block token
reduction; KILLED if the largest neutral prune < 10%.

Usage: python scripts/experiments/r48_h529_qfilter.py [config] [questions] [max]
Writes: reports/experiments/r48/h529-qfilter-<ts>.json
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, "notebooks")
sys.path.insert(0, "scripts/experiments")
import tiktoken  # noqa: E402
from r46_h499_screen import gold_titles, ingested_titles, load_slices  # noqa: E402
from r48_h514_gate import crit_pass  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.extraction import generate_embeddings  # noqa: E402
from knowledge_graph_foundry.models import Entity  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

CONFIG = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    "config/experiments/config-bench-medium.yml"
)
QUESTIONS = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
    "data/external/multihop-qa-benchmarks/2wikimultihopqa.json"
)
MAX = int(sys.argv[3]) if len(sys.argv) > 3 else 0
FRACTIONS = [0.10, 0.20, 0.30, 0.40, 0.50]
ENC = tiktoken.get_encoding("cl100k_base")


def toks(s: str) -> int:
    return len(ENC.encode(s))


def qblock(qtext: str, entities: list[str], chunks: list[str]) -> str:
    block = f"## Question match: {qtext}\n"
    if entities:
        block += "About: " + ", ".join(entities) + "\n"
    return block + "\n".join(c for c in chunks if c)


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bench = json.loads(QUESTIONS.read_text())
    st = load_settings(CONFIG)
    st.event_log = None
    with Foundry(st) as f:
        with f.driver.session() as s:
            qrows = s.run(
                "MATCH (q:KGFQuestion)-[:ANSWERABLE_FROM]->(c:Chunk) "
                "OPTIONAL MATCH (q)-[:ABOUT]->(e:Entity) "
                "RETURN q.id AS id, q.text AS text, q.embedding AS emb, "
                "collect(DISTINCT c.id) AS chunk_ids, "
                "collect(DISTINCT c.text) AS chunks, "
                "collect(DISTINCT e.name) AS entities"
            ).data()
            crows = s.run("MATCH (c:Chunk) RETURN c.id AS id, c.text AS text").data()
        print(f"h529 {run_id}: {len(qrows)} questions, {len(crows)} chunks", flush=True)

        # embed all chunk texts once through the shipped channel
        cents = [
            Entity.create(f"chunk-{r['id']}"[:80], types=["Chunk"], description=r["text"] or "")
            for r in crows
        ]
        cembs = {}
        B = 64
        for i in range(0, len(cents), B):
            for r, e in zip(crows[i:i + B], generate_embeddings(cents[i:i + B], st.embeddings)):
                cembs[r["id"]] = np.array(e.embedding, dtype=np.float32)
            if (i // B) % 4 == 0:
                print(f"chunk embed {i}/{len(cents)}", flush=True)

        qemb = np.array([r["emb"] for r in qrows], dtype=np.float32)
        qemb /= np.linalg.norm(qemb, axis=1, keepdims=True) + 1e-9
        scores = np.zeros(len(qrows))
        for i, r in enumerate(qrows):
            best = 0.0
            for cid in r["chunk_ids"]:
                ce = cembs.get(cid)
                if ce is None:
                    continue
                ce = ce / (np.linalg.norm(ce) + 1e-9)
                best = max(best, float(qemb[i] @ ce))
            scores[i] = best
        order = np.argsort(scores)  # ascending: bottom = prune first
        print(f"fidelity scores: p10={np.percentile(scores,10):.3f} "
              f"median={np.median(scores):.3f} p90={np.percentile(scores,90):.3f}", flush=True)

        titles = ingested_titles(f, load_slices())
        full = [
            q for q in bench if gold_titles(q) and all(t in titles for t in gold_titles(q))
        ]
        eligible = full[:MAX] if MAX else full
        print(f"{len(eligible)} eligible probes", flush=True)

        probes = []
        for k, q in enumerate(eligible):
            pe = Entity.create(q["question"][:80], types=["Query"], description=q["question"])
            qv = np.array(generate_embeddings([pe], st.embeddings)[0].embedding,
                          dtype=np.float32)
            qv /= np.linalg.norm(qv) + 1e-9
            res = f.probe(q["question"])
            blocks = res["context_lines"]
            base_blocks = [b for b in blocks if not b.startswith("## Question match:")]
            sims = qemb @ qv
            probes.append({"q": q, "sims": sims, "base_blocks": base_blocks})
            if (k + 1) % 20 == 0:
                print(f"[{k+1}/{len(eligible)}] probed", flush=True)

    results = []
    for frac in [0.0] + FRACTIONS:
        pruned = set(order[: int(frac * len(qrows))])
        passes, qtoks = 0, []
        changed = 0
        for p in probes:
            ranked = np.argsort(-p["sims"])
            top = next((i for i in ranked if i not in pruned), None)
            top_full = int(ranked[0])
            if top != top_full:
                changed += 1
            blocks = list(p["base_blocks"])
            if top is not None:
                r = qrows[int(top)]
                b = qblock(r["text"], r["entities"], r["chunks"])
                blocks.append(b)
                qtoks.append(toks(b))
            passes += bool(crit_pass(p["q"], blocks))
        results.append({
            "prune_fraction": frac,
            "pass": passes,
            "pass_rate": round(passes / len(probes), 4),
            "top_match_changed": changed,
            "qblock_tokens_p50": int(np.median(qtoks)) if qtoks else 0,
        })
        print(json.dumps(results[-1]), flush=True)

    out = {
        "run_id": run_id,
        "config": str(CONFIG),
        "n_questions": len(qrows),
        "n_probes": len(probes),
        "deviation": "retrieval-contribution term skipped (match history never persisted); "
        "fidelity = max cosine(question, own chunk); channel emulated at M=1 by "
        "replacing the shipped render's question block",
        "results": results,
        "bars": {"confirmed_prune_ge": 0.25, "killed_lt": 0.10,
                 "recall_within_probes": 1},
    }
    outdir = Path("reports/experiments/r48")
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"h529-qfilter-{run_id}.json"
    path.write_text(json.dumps(out, indent=1))
    print(f"WROTE {path}", flush=True)


if __name__ == "__main__":
    main()

"""R35-H371 stage 2: groundedness-gate the generated questions, embed them in
Titan space (the live query-embedding space - question-to-query matching), and
store the GATED set as provenance-marked KGFQuestion nodes on the pile.

Gate (Doc2Query-- clause): a question survives iff its generated answer is
present in its source chunk under the harness's own presence check - the
answer must be verbatim-grounded, so an ungrounded (hallucinated) pair fails.
Ungated embeddings are kept file-side only for the gated-vs-ungated A/B.

Graph writes: (:KGFQuestion {r35_prototype: true}) + ANSWERABLE_FROM/ABOUT
edges (r35_prototype: true) - identifiable and reversible, no Entity label.
"""

import json
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, "notebooks")
sys.path.insert(0, "src")
from h158_measure import _norm, _present  # noqa: E402
from neo4j import GraphDatabase  # noqa: E402

from knowledge_graph_foundry.extraction import generate_embeddings  # noqa: E402
from knowledge_graph_foundry.models import Entity  # noqa: E402
from knowledge_graph_foundry.settings import EmbeddingSettings  # noqa: E402

URI = "bolt://172.19.0.100:7687"
GEN = Path("tmp/results/r35/h371-questions.jsonl")
EMB_OUT = Path("tmp/results/r35/h371-question-embs.jsonl")
GATED_OUT = Path("tmp/results/r35/h371-gated.json")


def main():
    driver = GraphDatabase.driver(URI, auth=("neo4j", "kgfoundry"))
    with driver.session() as s:
        chunk_text = {
            r["id"]: r["text"] for r in s.run("MATCH (c:Chunk) RETURN c.id AS id, c.text AS text")
        }

    # gate + merge duplicates (same question text from several chunks)
    qmap: dict[str, dict] = {}
    n_pairs = n_gated = 0
    for line in GEN.read_text().splitlines():
        rec = json.loads(line)
        cid = rec["chunk_id"]
        ctx = _norm(chunk_text.get(cid, ""))
        for p in rec["questions"]:
            n_pairs += 1
            grounded = bool(ctx) and _present(p["a"], ctx)
            n_gated += grounded
            key = _norm(p["q"])
            ent = qmap.setdefault(key, {"q": p["q"], "answers": {}, "chunks": [], "gated_chunks": []})
            ent["chunks"].append(cid)
            ent["answers"][cid] = p["a"]
            if grounded:
                ent["gated_chunks"].append(cid)
    print(f"pairs: {n_pairs}, grounded: {n_gated} ({n_gated/n_pairs:.1%}), unique questions: {len(qmap)}", flush=True)

    # embed every unique question once, Titan, harness query wrapping
    texts = list(qmap)
    have = {}
    if EMB_OUT.exists():
        for line in EMB_OUT.read_text().splitlines():
            r = json.loads(line)
            have[r["key"]] = r["embedding"]
    todo = [k for k in texts if k not in have]
    print(f"embedding: {len(todo)} to compute ({len(have)} cached)", flush=True)
    cfg = EmbeddingSettings()  # bedrock Titan v2 - the live index/query space
    BATCH = 100
    EMB_OUT.parent.mkdir(parents=True, exist_ok=True)
    with EMB_OUT.open("a") as fh:
        for off in range(0, len(todo), BATCH):
            keys = todo[off : off + BATCH]
            ents = [Entity.create(qmap[k]["q"][:80], types=["Query"], description=qmap[k]["q"]) for k in keys]
            ents = generate_embeddings(ents, cfg)
            for k, e in zip(keys, ents):
                if not e.embedding:
                    print(f"EMBED MISS: {k[:60]}", flush=True)
                    continue
                have[k] = e.embedding
                fh.write(json.dumps({"key": k, "embedding": e.embedding}) + "\n")
            fh.flush()
            print(f"embedded {min(off+BATCH, len(todo))}/{len(todo)}", flush=True)

    gated = {k: v for k, v in qmap.items() if v["gated_chunks"] and k in have}
    ungated_index = {k: v for k, v in qmap.items() if k in have}
    GATED_OUT.write_text(json.dumps({
        "generated": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "n_pairs": n_pairs, "n_grounded_pairs": n_gated,
        "unique_questions": len(qmap),
        "gated_index_size": len(gated), "ungated_index_size": len(ungated_index),
        "gated": {k: {"q": v["q"], "chunks": v["gated_chunks"],
                      "answer": v["answers"][v["gated_chunks"][0]]} for k, v in gated.items()},
        "ungated": {k: {"q": v["q"], "chunks": sorted(set(v["chunks"]))} for k, v in ungated_index.items()},
    }, indent=1))
    print(f"gated index: {len(gated)}, ungated index: {len(ungated_index)} -> {GATED_OUT}", flush=True)

    # store gated questions as provenance-marked nodes
    with driver.session() as s:
        s.run("MATCH (q:KGFQuestion {r35_prototype: true, source: 'h371'}) DETACH DELETE q")
        rows = []
        for k, v in gated.items():
            qid = "q_" + sha256(k.encode()).hexdigest()[:16]
            rows.append({
                "id": qid, "text": v["q"], "answer": v["answers"][v["gated_chunks"][0]],
                "embedding": have[k], "chunks": v["gated_chunks"],
            })
        for off in range(0, len(rows), 200):
            s.run(
                "UNWIND $rows AS r "
                "CREATE (q:KGFQuestion {id: r.id, text: r.text, answer: r.answer, "
                "embedding: r.embedding, r35_prototype: true, source: 'h371'}) "
                "WITH q, r UNWIND r.chunks AS cid "
                "MATCH (c:Chunk {id: cid}) "
                "CREATE (q)-[:ANSWERABLE_FROM {r35_prototype: true}]->(c)",
                rows=rows[off : off + 200],
            )
        s.run(
            "MATCH (q:KGFQuestion {source: 'h371'})-[:ANSWERABLE_FROM]->(c:Chunk)"
            "<-[:MENTIONED_IN]-(e:Entity) "
            "WHERE size(e.name) >= 4 AND (toLower(q.text) CONTAINS toLower(e.name) "
            "OR toLower(q.answer) CONTAINS toLower(e.name)) "
            "WITH q, e LIMIT 100000 "
            "MERGE (q)-[r:ABOUT]->(e) SET r.r35_prototype = true"
        )
        n = s.run("MATCH (q:KGFQuestion) RETURN count(q) AS n").single()["n"]
        na = s.run("MATCH (:KGFQuestion)-[r:ABOUT]->() RETURN count(r) AS n").single()["n"]
        print(f"stored: {n} KGFQuestion nodes, {na} ABOUT edges", flush=True)
    driver.close()
    print("EMBED+STORE COMPLETE", flush=True)


if __name__ == "__main__":
    main()

"""R35-H373: questions double as audit probes - run every GATED question back
through the shipped retrieval channel (parity instrument); a question whose
grounded answer the graph cannot render is a gap-ledger entry.

Per registration the answerability check is one retrieval + present-check, no
LLM. Two verdict layers are recorded to make the manual adjudication honest:
  render_answerable - answer present in the question's own top-16 parity render
  graph_has_fact    - answer present ANYWHERE in the graph's entity surface
                      (bulk in-memory render of all entities): False means the
                      fact never made it out of the source into the graph - an
                      extraction/parse gap; True means a retrieval-side miss.

Ledger = grounded questions with render_answerable == False, ranked by top
seed similarity descending (near-miss gaps adjacent to known content first).
Graph writes: NONE.
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "notebooks")
sys.path.insert(0, "src")
from h158_measure import _norm, _present  # noqa: E402
from neo4j import GraphDatabase  # noqa: E402

URI = "bolt://172.19.0.100:7687"
TOP_K = 16
OVERFETCH = 4  # DEF-14 parity
EMBS = Path("results/r35/h371-question-embs.jsonl")
GATED = Path("results/r35/h371-gated.json")
LEDGER = Path("results/r35/h373-gap-ledger.jsonl")


def build_entity_blocks(session) -> dict[str, str]:
    props = {}
    for r in session.run(
        "MATCH (e:Entity) RETURN e.id AS id, e.name AS name, labels(e) AS types, "
        "e.description AS description, properties(e) AS props"
    ):
        spec = {k.removeprefix("prop_"): v for k, v in r["props"].items() if k.startswith("prop_")}
        props[r["id"]] = {
            "head": f"## {r['name']} ({', '.join(r['types'])})\n{r['description'] or ''}\n"
                    f"Properties: {json.dumps(spec, default=str)}",
            "rels": [],
        }
    for r in session.run(
        "MATCH (e:Entity)-[rel]-(n:Entity) WHERE rel.valid_to IS NULL "
        "AND type(rel) <> 'SIMILAR_TO' RETURN e.id AS id, type(rel) AS rel, n.name AS name"
    ):
        if r["id"] in props and len(props[r["id"]]["rels"]) < 15:
            props[r["id"]]["rels"].append(f"{r['rel']} -> {r['name']}")
    return {
        eid: _norm(v["head"] + "\nRelations: " + "; ".join(v["rels"]))
        for eid, v in props.items()
    }


def main():
    embs = {}
    for line in EMBS.read_text().splitlines():
        r = json.loads(line)
        embs[r["key"]] = r["embedding"]
    gated = {k: v for k, v in json.loads(GATED.read_text())["gated"].items() if k in embs}
    print(f"gated questions: {len(gated)}", flush=True)

    driver = GraphDatabase.driver(URI, auth=("neo4j", "kgfoundry"))
    with driver.session() as s:
        blocks = build_entity_blocks(s)
        chunk_text = {r["id"]: r["text"] for r in s.run("MATCH (c:Chunk) RETURN c.id AS id, c.text AS text")}
    global_ctx = " ".join(blocks.values())
    print(f"entity blocks: {len(blocks)}, global ctx: {len(global_ctx)} chars", flush=True)

    n_ans = n_gap = n_retrieval_miss = 0
    entries = []
    with driver.session() as s:
        for i, (key, meta) in enumerate(gated.items(), 1):
            res = s.run(
                "CALL db.index.vector.queryNodes('kgf_entity_embeddings', $k, $emb) "
                "YIELD node, score RETURN node.id AS id, score",
                k=TOP_K * OVERFETCH, emb=embs[key],
            ).data()[:TOP_K]
            ctx = " ".join(blocks.get(r["id"], "") for r in res)
            ans = meta["answer"]
            render_ok = _present(ans, ctx)
            if render_ok:
                n_ans += 1
            else:
                graph_has = _present(ans, global_ctx)
                n_retrieval_miss += graph_has
                n_gap += not graph_has
                entries.append({
                    "question": meta["q"], "answer": ans,
                    "chunks": meta["chunks"],
                    "top_score": round(res[0]["score"], 4) if res else 0.0,
                    "graph_has_fact": graph_has,
                    "chunk_snippet": chunk_text.get(meta["chunks"][0], "")[:300],
                })
            if i % 200 == 0:
                print(f"[{i}/{len(gated)}] answerable={n_ans} ledger={len(entries)}", flush=True)
    driver.close()

    entries.sort(key=lambda e: -e["top_score"])
    LEDGER.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    kw = defaultdict(int)
    for e in entries:
        for w in _norm(e["question"]).split():
            if len(w) > 4:
                kw[w] += 1
    out = Path(f"reports/r35-h373-ledger-{ts}.json")
    out.write_text(json.dumps({
        "hypothesis": "R35-H373 questions as audit probes (gap ledger)",
        "generated": ts, "graph_uri": URI,
        "instrument": "engine parity (DEF-14)", "top_k": TOP_K, "overfetch_factor": OVERFETCH,
        "gated_questions": len(gated),
        "render_answerable": n_ans,
        "ledger_entries": len(entries),
        "ledger_extraction_gaps": n_gap,
        "ledger_retrieval_misses": n_retrieval_miss,
        "top_keywords": dict(sorted(kw.items(), key=lambda x: -x[1])[:25]),
        "top_20": entries[:20],
    }, indent=2))
    print(f"answerable={n_ans}/{len(gated)}; ledger={len(entries)} "
          f"(extraction gaps={n_gap}, retrieval misses={n_retrieval_miss})", flush=True)
    print(f"H373 LEDGER COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

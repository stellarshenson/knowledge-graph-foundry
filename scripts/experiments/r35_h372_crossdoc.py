"""R35-H372: entity-scoped cross-document questions - generated over merged
multi-document evidence of co-typed entity PAIRS, the one registered object
that spans documents by construction (H354: no splitter can co-locate this).

Fanout cap (registered budget clause): pairs must share a non-Entity label
(co-type blocking) AND >= 1 normalized property-key stem, come from disjoint
document sets, and each entity joins at most MAX_PARTNERS pairs; total pairs
capped at MAX_PAIRS ranked by shared-stem count. No quadratic generation.

Gate: the generated comparison answer must be grounded in the merged evidence
(same presence check as H371's gate). Chunk mapping: each side contributes its
best MENTIONED_IN chunk containing the compared value, so one matched question
pulls BOTH documents' chunks into context.

Graph writes: (:KGFQuestion {r35_prototype: true, source: 'h372'}) only.
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from hashlib import sha256
from itertools import combinations
from pathlib import Path

sys.path.insert(0, "notebooks")
sys.path.insert(0, "src")
from h158_measure import _norm, _present  # noqa: E402
from neo4j import GraphDatabase  # noqa: E402

from knowledge_graph_foundry.extraction import generate_embeddings  # noqa: E402
from knowledge_graph_foundry.models import Entity  # noqa: E402
from knowledge_graph_foundry.settings import EmbeddingSettings  # noqa: E402

URI = "bolt://172.19.0.100:7687"
VLLM = "http://localhost:8010/v1/chat/completions"
MODEL = "gpt-oss-120b"
OUT = Path("tmp/results/r35/h372-gated.json")
PAIRS_OUT = Path("tmp/results/r35/h372-pairs.jsonl")
MAX_PAIRS = 150
MAX_PARTNERS = 6
TIMEOUT = 600

_STOP_SUFFIX = ("unit", "units", "kg", "g", "lb", "lbs", "cm", "mm", "value", "min", "max")


def stem(key: str) -> str:
    parts = [p for p in key.removeprefix("prop_").split("_") if p not in _STOP_SUFFIX]
    return parts[0] if parts else key


def call_llm(prompt: str) -> list[dict]:
    body = json.dumps({
        "model": MODEL, "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0, "max_tokens": 1200,
    }).encode()
    req = urllib.request.Request(VLLM, data=body, headers={"Content-Type": "application/json"})
    resp = json.load(urllib.request.urlopen(req, timeout=TIMEOUT))
    raw = resp["choices"][0]["message"]["content"]
    start, end = raw.find("["), raw.rfind("]")
    if start == -1:
        return []
    try:
        pairs = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return []
    return [{"q": str(p["q"]).strip(), "a": str(p["a"]).strip()}
            for p in pairs if isinstance(p, dict) and p.get("q") and p.get("a")]


PROMPT = (
    "Two products are described below with specifications extracted from two DIFFERENT "
    "documents. Generate exactly 2 comparison questions a user might ask that require BOTH "
    "products' values to answer (e.g. which is heavier/larger/quieter, how do they compare). "
    "Each answer must quote the exact values of BOTH products verbatim from the descriptions. "
    'Return ONLY a JSON array of objects with keys "q" and "a".\n\n'
    "PRODUCT A:\n{a}\n\nPRODUCT B:\n{b}"
)


def main():
    driver = GraphDatabase.driver(URI, auth=("neo4j", "kgfoundry"))
    with driver.session() as s:
        ents = s.run(
            "MATCH (e:Entity) WHERE any(k IN keys(e) WHERE k STARTS WITH 'prop_') "
            "AND size(coalesce(e.source_documents, [])) >= 1 "
            "RETURN e.id AS id, e.name AS name, labels(e) AS types, "
            "e.description AS description, properties(e) AS props, "
            "e.source_documents AS docs"
        ).data()
        mention = {}
        for r in s.run("MATCH (e:Entity)-[:MENTIONED_IN]->(c:Chunk) RETURN e.id AS eid, c.id AS cid"):
            mention.setdefault(r["eid"], []).append(r["cid"])
        chunk_text = {r["id"]: r["text"] for r in s.run("MATCH (c:Chunk) RETURN c.id AS id, c.text AS text")}

    cand = []
    for e in ents:
        stems = {}
        for k, v in e["props"].items():
            if k.startswith("prop_") and v not in (None, ""):
                stems.setdefault(stem(k), []).append((k.removeprefix("prop_"), str(v)))
        types = frozenset(t for t in e["types"] if t != "Entity")
        if stems and types:
            cand.append({**e, "stems": stems, "tset": types, "dset": frozenset(e["docs"])})
    print(f"candidate entities: {len(cand)}", flush=True)

    scored = []
    for a, b in combinations(cand, 2):
        if not (a["tset"] & b["tset"]):
            continue
        if a["dset"] & b["dset"] or a["dset"] == b["dset"]:
            continue  # must span documents by construction
        shared = set(a["stems"]) & set(b["stems"])
        if not shared:
            continue
        if _norm(a["name"]) == _norm(b["name"]):
            continue  # identity-variance pair, not a comparison pair
        scored.append((len(shared), a, b, sorted(shared)))
    scored.sort(key=lambda x: -x[0])
    used: dict[str, int] = {}
    pairs = []
    for n, a, b, shared in scored:
        if used.get(a["id"], 0) >= MAX_PARTNERS or used.get(b["id"], 0) >= MAX_PARTNERS:
            continue
        pairs.append((a, b, shared))
        used[a["id"]] = used.get(a["id"], 0) + 1
        used[b["id"]] = used.get(b["id"], 0) + 1
        if len(pairs) >= MAX_PAIRS:
            break
    print(f"pairs after blocking: {len(pairs)} (from {len(scored)} scored)", flush=True)

    def block(e, shared):
        spec = "; ".join(f"{k}: {v}" for st in shared for k, v in e["stems"][st])
        return f"{e['name']} ({', '.join(sorted(e['tset']))})\n{e['description'] or ''}\nSpecs: {spec}"

    done = set()
    if PAIRS_OUT.exists():
        for line in PAIRS_OUT.read_text().splitlines():
            done.add(json.loads(line)["pair"])
    with PAIRS_OUT.open("a") as fh:
        for i, (a, b, shared) in enumerate(pairs, 1):
            pid = f"{a['id']}|{b['id']}"
            if pid in done:
                continue
            evid_a, evid_b = block(a, shared), block(b, shared)
            try:
                qs = call_llm(PROMPT.format(a=evid_a, b=evid_b))
            except Exception as exc:
                qs = []
                print(f"[{i}] {pid} ERROR {str(exc)[:80]}", flush=True)
            fh.write(json.dumps({"pair": pid, "a_id": a["id"], "b_id": b["id"],
                                 "evidence": evid_a + "\n" + evid_b, "shared": shared,
                                 "questions": qs}) + "\n")
            fh.flush()
            if i % 20 == 0:
                print(f"[{i}/{len(pairs)}] generated", flush=True)

    # gate + chunk mapping
    ent_by_id = {e["id"]: e for e in cand}

    def side_chunk(eid, shared):
        e = ent_by_id.get(eid)
        cids = mention.get(eid, [])
        if e:
            values = [v for st in shared if st in e["stems"] for _, v in e["stems"][st]]
            for cid in cids:
                ctx = _norm(chunk_text.get(cid, ""))
                if any(_present(v, ctx) for v in values if re.search(r"\w", v)):
                    return cid
        return cids[0] if cids else None

    gated = {}
    n_pairs = n_gated = 0
    for line in PAIRS_OUT.read_text().splitlines():
        rec = json.loads(line)
        evid = _norm(rec["evidence"])
        for p in rec["questions"]:
            n_pairs += 1
            if not _present(p["a"], evid):
                continue
            n_gated += 1
            ca = side_chunk(rec["a_id"], rec["shared"])
            cb = side_chunk(rec["b_id"], rec["shared"])
            chunks = [c for c in dict.fromkeys([ca, cb]) if c]
            if len(chunks) < 2:
                continue  # both sides must contribute a document
            gated[_norm(p["q"])] = {"q": p["q"], "a": p["a"], "chunks": chunks,
                                    "entities": [rec["a_id"], rec["b_id"]]}
    print(f"generated QA: {n_pairs}, grounded: {n_gated}, two-sided gated: {len(gated)}", flush=True)

    cfg = EmbeddingSettings()
    keys = list(gated)
    for off in range(0, len(keys), 100):
        batch = keys[off : off + 100]
        es = [Entity.create(gated[k]["q"][:80], types=["Query"], description=gated[k]["q"]) for k in batch]
        es = generate_embeddings(es, cfg)
        for k, e in zip(batch, es):
            gated[k]["embedding"] = e.embedding
        print(f"embedded {min(off+100, len(keys))}/{len(keys)}", flush=True)
    gated = {k: v for k, v in gated.items() if v.get("embedding")}

    OUT.write_text(json.dumps({
        "generated": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "pairs_generated": n_pairs, "grounded": n_gated, "gated_two_sided": len(gated),
        "gated": gated,
    }, indent=1))
    print(f"-> {OUT}", flush=True)

    with driver.session() as s:
        s.run("MATCH (q:KGFQuestion {r35_prototype: true, source: 'h372'}) DETACH DELETE q")
        rows = [{"id": "q_" + sha256(k.encode()).hexdigest()[:16], "text": v["q"],
                 "answer": v["a"], "embedding": v["embedding"], "chunks": v["chunks"],
                 "entities": v["entities"]} for k, v in gated.items()]
        for off in range(0, len(rows), 200):
            s.run(
                "UNWIND $rows AS r "
                "CREATE (q:KGFQuestion {id: r.id, text: r.text, answer: r.answer, "
                "embedding: r.embedding, r35_prototype: true, source: 'h372'}) "
                "WITH q, r "
                "FOREACH (cid IN r.chunks | "
                " MERGE (c:Chunk {id: cid}) "
                " CREATE (q)-[:ANSWERABLE_FROM {r35_prototype: true}]->(c)) "
                "FOREACH (eid IN r.entities | "
                " MERGE (e:Entity {id: eid}) "
                " CREATE (q)-[:ABOUT {r35_prototype: true}]->(e))",
                rows=rows[off : off + 200],
            )
        n = s.run("MATCH (q:KGFQuestion {source:'h372'}) RETURN count(q) AS n").single()["n"]
        print(f"stored: {n} h372 KGFQuestion nodes", flush=True)
    driver.close()
    print("H372 GENERATION COMPLETE", flush=True)


if __name__ == "__main__":
    main()

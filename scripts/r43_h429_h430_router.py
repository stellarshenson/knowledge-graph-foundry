"""R43 router: H429 gold-path existence + H430 rank-margin trajectory on REG-1.

The round's forking verdict, fully offline:
  H429 - per document index t, do the REG-1 gold entities exist yet, and are
         film->director connected in the cumulative graph (same component +
         direct-neighborhood edge)? Path BROKE in (135,154] -> graph-side.
  H430 - vector-rank trajectory: the question's Titan embedding ranked
         against all entity embeddings restricted to entities born <= t;
         records each gold carrier's rank and the top-16 boundary margin.
         Path HELD while rank decayed past 16 -> retriever-side (crowding).

Usage: python scripts/r43_h429_h430_router.py
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path

from knowledge_graph_foundry import load_settings
from knowledge_graph_foundry.extraction import generate_embeddings
from knowledge_graph_foundry.models import Entity
from knowledge_graph_foundry.pipeline import Foundry

CONFIG = Path("config/experiments/config-bench-pilot.yml")
QUESTION = "Do both films Interview With A Hitman and The Last Coupon have the directors from the same country?"
GOLD_NAMES = ["Interview with a Hitman", "The Last Coupon", "Perry Bhandal", "Frank Launder"]
WINDOW = (103, 200)  # probe trajectory span; REG-1 transition (135, 154]
TOP_K = 16
OUT = Path("results/r43")


def cos(a, b):
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(y * y for y in b))
    return num / (da * db) if da and db else 0.0


def main():
    st = load_settings(CONFIG)
    st.event_log = None
    OUT.mkdir(parents=True, exist_ok=True)

    with Foundry(st) as f, f.driver.session() as s:
        docs = s.run("MATCH (d:KGFDocument) RETURN d.id AS id ORDER BY d.created_at").value()
        doc_order = {d: i + 1 for i, d in enumerate(docs)}
        ents = s.run(
            "MATCH (e:Entity) RETURN e.id AS id, e.name AS name, "
            "e.source_documents AS sd, e.embedding AS emb"
        ).data()
        rels = s.run(
            "MATCH (a:Entity)-[r]->(b:Entity) "
            "RETURN a.id AS a, b.id AS b, type(r) AS t, r.source_documents AS sd"
        ).data()
        q_emb = generate_embeddings(
            [Entity.create(QUESTION[:80], types=["Query"], description=QUESTION)],
            f.settings.embeddings,
        )[0].embedding

    def birth(sd):
        idxs = [doc_order[d] for d in (sd or []) if d in doc_order]
        return min(idxs) if idxs else None

    for e in ents:
        e["birth"] = birth(e["sd"])
    for r in rels:
        r["birth"] = birth(r["sd"])

    # gold nodes by exact-insensitive name match
    gold = {}
    for name in GOLD_NAMES:
        matches = [e for e in ents if (e["name"] or "").lower() == name.lower()]
        gold[name] = matches
        print(f"gold '{name}': {len(matches)} node(s), births {[m['birth'] for m in matches]}", flush=True)

    # similarity of the question to every embedded entity (fixed; ranking at
    # time t = rank among entities born <= t)
    sims = []
    for e in ents:
        if e["emb"] and e["birth"]:
            sims.append((cos(q_emb, e["emb"]), e["birth"], e["name"], e["id"]))
    sims.sort(reverse=True)

    gold_ids = {m["id"] for ms in gold.values() for m in ms}

    def connected(a_id, b_id, t):
        """BFS on edges born <= t."""
        if a_id == b_id:
            return True
        seen, frontier = {a_id}, [a_id]
        eligible = {}
        for r in rels:
            if r["birth"] and r["birth"] <= t:
                eligible.setdefault(r["a"], set()).add(r["b"])
                eligible.setdefault(r["b"], set()).add(r["a"])
        while frontier:
            nxt = []
            for n in frontier:
                for m in eligible.get(n, ()):
                    if m == b_id:
                        return True
                    if m not in seen:
                        seen.add(m)
                        nxt.append(m)
            frontier = nxt
        return False

    film_ids = [m["id"] for m in gold["Interview with a Hitman"]]
    dir1_ids = [m["id"] for m in gold["Perry Bhandal"]]
    film2_ids = [m["id"] for m in gold["The Last Coupon"]]
    dir2_ids = [m["id"] for m in gold["Frank Launder"]]

    def any_connected(ids_a, ids_b, t):
        # duplicate gold carriers (H107 class): a path via ANY carrier pair counts
        return any(connected(a, b, t) for a in ids_a for b in ids_b)

    def direct_edge_birth(ids_a, ids_b):
        # the 1-hop edge the render must emit - existence + birth index
        births = [r["birth"] for r in rels if r["birth"] and ((r["a"] in ids_a and r["b"] in ids_b) or (r["b"] in ids_a and r["a"] in ids_b))]
        return min(births) if births else None

    edge1_birth = direct_edge_birth(film_ids, dir1_ids)
    edge2_birth = direct_edge_birth(film2_ids, dir2_ids)
    print(f"direct film-director edges: pair1 birth={edge1_birth} pair2 birth={edge2_birth}", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = OUT / f"h429-h430-router-{ts}.jsonl"
    with out_path.open("w") as fh:
        for t in range(WINDOW[0], WINDOW[1] + 1):
            eligible = [x for x in sims if x[1] <= t]
            ranks = {}
            for rank, (sc, _b, name, eid) in enumerate(eligible, 1):
                if eid in gold_ids and name not in ranks:  # best rank per name (descending score order)
                    ranks[name] = rank
            cut_score = eligible[TOP_K - 1][0] if len(eligible) >= TOP_K else None
            path1 = any_connected(film_ids, dir1_ids, t) if film_ids and dir1_ids else False
            path2 = any_connected(film2_ids, dir2_ids, t) if film2_ids and dir2_ids else False
            rec = {
                "t": t,
                "gold_ranks": ranks,
                "topk_cut_score": round(cut_score, 4) if cut_score else None,
                "path_film1_dir1": path1,
                "path_film2_dir2": path2,
                "direct_edge1_born": edge1_birth is not None and edge1_birth <= t,
                "direct_edge2_born": edge2_birth is not None and edge2_birth <= t,
            }
            fh.write(json.dumps(rec) + "\n")
            if t in (103, 121, 135, 136, 145, 153, 154, 160, 176, 197, 200):
                print(f"t={t}: ranks={ranks} path1={path1} path2={path2}", flush=True)
    print(f"ROUTER COMPLETE -> {out_path}", flush=True)


if __name__ == "__main__":
    main()

"""R36-H380: outcome-linked worth - pass/fail co-retrieval counters price
derived objects from the harness's own verdict stream.

Episodes: the 24-probe harness replayed at four context budgets
(top_k in {8, 12, 16, 24}) = 96 probe-episodes over 4 harness configurations.
Retrieval is deterministic per config, so k-variation supplies the episode
diversity (different renders, different outcomes) that Memory-Worth gets from
traffic. Outcome = full gold coverage (recall == 1.0) for the episode.

Counters per rendered entity: n_pass / n_fail; worth = Laplace-smoothed
conditional success probability (n_pass + 1) / (n_pass + n_fail + 2).

Clauses (registration):
  (a) evacuating the bottom-decile-worth entities from the k=16 render costs
      ZERO recall (no probe regresses; freed slots pull up the next seeds)
  (b) the known-superseded object ('HC230 Product Range', the pre-H365
      property-carrying duplicate hub) lands in the bottom quartile of
      retrieved objects - reported honestly as uninformative if it is never
      retrieved (the REFUTED-sparse clause anticipates thin traffic)

Priceable class on this pile: entities-in-render only (propositions are not
stored; SIMILAR_TO edges are excluded from render by design).
"""

import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, "notebooks")
from h158_measure import _present, _render_nodes  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.extraction import generate_embeddings  # noqa: E402
from knowledge_graph_foundry.graph.graphrag import overfetch_seeds, vector_query  # noqa: E402
from knowledge_graph_foundry.models import Entity  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

URI = "bolt://172.19.0.100:7687"
PROBES = Path("tests/probes/cpap-probe-set.yml")
KS = [8, 12, 16, 24]
SUPERSEDED = "HC230 Product Range"


def episode(f, st, emb, k, excluded=frozenset()):
    vec = st.graphrag.vector_index_name
    factor = st.graphrag.overfetch_factor
    seeds = [
        s["id"]
        for s in overfetch_seeds(lambda kk: vector_query(f.driver, emb, vec, top_k=kk), 64, factor)
        if s["id"] not in excluded
    ][:k]
    with f.driver.session() as sess:
        ctx = _render_nodes(sess, seeds)
    return seeds, ctx


def main():
    base = load_settings(Path("config/config.yml"))
    st = deepcopy(base)
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = URI, "neo4j", "kgfoundry"
    probes = [p for p in yaml.safe_load(PROBES.read_text()) if p.get("gold_evidence")]

    embs = {}
    counters: dict[str, list[int]] = {}  # id -> [n_pass, n_fail]
    k16_recall = {}
    with Foundry(st) as f:
        for p in probes:
            pe = Entity.create(p["question"][:80], types=["Query"], description=p["question"])
            embs[p["id"]] = generate_embeddings([pe], st.embeddings)[0].embedding
        for k in KS:
            for p in probes:
                seeds, ctx = episode(f, st, embs[p["id"]], k)
                golds = p["gold_evidence"]
                recall = sum(_present(g, ctx) for g in golds) / len(golds)
                passed = recall == 1.0
                for eid in seeds:
                    counters.setdefault(eid, [0, 0])[0 if passed else 1] += 1
                if k == 16:
                    k16_recall[p["id"]] = round(recall, 4)
            print(f"k={k}: episodes done", flush=True)

        worth = {
            eid: (c[0] + 1) / (c[0] + c[1] + 2) for eid, c in counters.items()
        }
        ranked = sorted(worth, key=lambda e: worth[e])
        n = len(ranked)
        decile = set(ranked[: max(1, n // 10)])
        quartile_cut = n // 4

        with f.driver.session() as s:
            names = {
                r["id"]: r["name"]
                for r in s.run(
                    "MATCH (e:Entity) WHERE e.id IN $ids RETURN e.id AS id, e.name AS name",
                    ids=ranked,
                )
            }
            sup = s.run(
                "MATCH (e:Entity {name: $n}) RETURN e.id AS id", n=SUPERSEDED
            ).single()
        sup_id = sup["id"] if sup else None
        sup_rank = ranked.index(sup_id) if sup_id in worth else None

        # clause (a): evacuate bottom decile at k=16
        evac_recall = {}
        for p in probes:
            _, ctx = episode(f, st, embs[p["id"]], 16, excluded=frozenset(decile))
            golds = p["gold_evidence"]
            evac_recall[p["id"]] = round(sum(_present(g, ctx) for g in golds) / len(golds), 4)

    regressions = {
        p: (k16_recall[p], evac_recall[p]) for p in k16_recall if evac_recall[p] < k16_recall[p]
    }
    bottom = [
        {"id": e, "name": names.get(e), "worth": round(worth[e], 4), "n": sum(counters[e])}
        for e in ranked[:10]
    ]
    top = [
        {"id": e, "name": names.get(e), "worth": round(worth[e], 4), "n": sum(counters[e])}
        for e in ranked[-10:]
    ]
    print(f"priced entities: {n}; bottom decile: {len(decile)}", flush=True)
    print(f"superseded '{SUPERSEDED}': retrieved={sup_rank is not None}, rank={sup_rank}", flush=True)
    print(f"evacuation regressions (must be empty): {regressions}", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/experiments/adjudicated/r36-h380-worth-{ts}.json")
    out.write_text(
        json.dumps(
            {
                "hypothesis": "R36-H380 outcome-linked worth counters",
                "generated": ts,
                "graph_uri": URI,
                "episodes": len(KS) * len(probes),
                "configs": KS,
                "priced_entities": n,
                "superseded": {
                    "name": SUPERSEDED,
                    "retrieved": sup_rank is not None,
                    "rank": sup_rank,
                    "bottom_quartile": sup_rank is not None and sup_rank < quartile_cut,
                    "worth": round(worth[sup_id], 4) if sup_id in worth else None,
                },
                "bottom_10": bottom,
                "top_10": top,
                "k16_mean": round(sum(k16_recall.values()) / len(k16_recall), 4),
                "evacuated_mean": round(sum(evac_recall.values()) / len(evac_recall), 4),
                "regressions": {p: list(v) for p, v in regressions.items()},
                "k16_per_probe": k16_recall,
                "evacuated_per_probe": evac_recall,
            },
            indent=2,
        )
    )
    print(f"\nH380 WORTH COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

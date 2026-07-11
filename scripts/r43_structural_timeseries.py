"""R43 forensic instrument: the graph's structural time series over ingestion.

Reconstructs, OFFLINE and without re-ingesting, how the graph's structure
evolved document-by-document: entity/edge birth = the earliest ingestion
position among its source_documents (KGFDocument.created_at gives the
order). Sweeping the birth index yields per-document snapshots of the
cheap structural parameters; change-points in these series are then
aligned with the progressive-probe trajectory (e.g. the REG-1 window,
pass <= 135 docs -> fail >= 154) to test whether retrieval regressions
coincide with structural shifts.

Metrics per snapshot (all incremental, O(edges) total sweep):
  nodes, edges, density, mean/max degree, top-hub degree share,
  isolates, connected components, giant-component share

Usage: python scripts/r43_structural_timeseries.py [config.yml] [every_n]
Writes: results/r43/structural-timeseries-<ts>.jsonl (one record per
sampled doc index) + prints the largest single-step deltas.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from knowledge_graph_foundry import load_settings
from knowledge_graph_foundry.pipeline import Foundry

DEFAULT_CONFIG = Path("config/experiments/config-bench-pilot.yml")
OUT = Path("results/r43")


class UnionFind:
    def __init__(self):
        self.parent: dict[str, str] = {}
        self.size: dict[str, int] = {}
        self.components = 0

    def add(self, x: str) -> None:
        if x not in self.parent:
            self.parent[x] = x
            self.size[x] = 1
            self.components += 1

    def find(self, x: str) -> str:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.size[ra] += self.size[rb]
        self.components -= 1

    def giant(self) -> int:
        return max((self.size[r] for r in self.parent if self.parent[r] == r), default=0)


def birth_index(source_docs, doc_order: dict[str, int]):
    idxs = [doc_order[d] for d in (source_docs or []) if d in doc_order]
    return min(idxs) if idxs else None


def main():
    config = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONFIG
    every_n = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    st = load_settings(config)
    st.event_log = None
    OUT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = OUT / f"structural-timeseries-{ts}.jsonl"

    with Foundry(st) as f, f.driver.session() as s:
        docs = s.run(
            "MATCH (d:KGFDocument) RETURN d.id AS id ORDER BY d.created_at"
        ).value()
        doc_order = {d: i + 1 for i, d in enumerate(docs)}
        ents = s.run(
            "MATCH (e:Entity) RETURN e.id AS id, e.source_documents AS sd"
        ).data()
        rels = s.run(
            "MATCH (a:Entity)-[r]->(b:Entity) "
            "RETURN a.id AS a, b.id AS b, r.source_documents AS sd"
        ).data()
    print(f"{len(docs)} docs, {len(ents)} entities, {len(rels)} rels from {config}", flush=True)

    ent_births: dict[int, list[str]] = {}
    for e in ents:
        bi = birth_index(e["sd"], doc_order)
        if bi is not None:
            ent_births.setdefault(bi, []).append(e["id"])
    rel_births: dict[int, list[tuple[str, str]]] = {}
    unattributed = 0
    for r in rels:
        bi = birth_index(r["sd"], doc_order)
        if bi is None:
            unattributed += 1
            continue
        rel_births.setdefault(bi, []).append((r["a"], r["b"]))
    if unattributed:
        print(f"note: {unattributed} rels carry no attributable source_documents - excluded", flush=True)

    uf = UnionFind()
    degree: dict[str, int] = {}
    n_edges = 0
    prev = None
    deltas = []
    with out_path.open("w") as fh:
        for t in range(1, len(docs) + 1):
            for eid in ent_births.get(t, []):
                uf.add(eid)
                degree.setdefault(eid, 0)
            for a, b in rel_births.get(t, []):
                uf.add(a)
                uf.add(b)
                degree[a] = degree.get(a, 0) + 1
                degree[b] = degree.get(b, 0) + 1
                uf.union(a, b)
                n_edges += 1
            if t % every_n and t != len(docs):
                continue
            n = len(uf.parent)
            max_deg = max(degree.values(), default=0)
            giant = uf.giant()
            rec = {
                "doc_index": t,
                "nodes": n,
                "edges": n_edges,
                "density": round(2 * n_edges / (n * (n - 1)), 6) if n > 1 else 0,
                "mean_degree": round(2 * n_edges / n, 3) if n else 0,
                "max_degree": max_deg,
                "top_hub_share": round(max_deg / (2 * n_edges), 4) if n_edges else 0,
                "isolates": sum(1 for v in degree.values() if v == 0),
                "components": uf.components,
                "giant_share": round(giant / n, 4) if n else 0,
            }
            fh.write(json.dumps(rec) + "\n")
            if prev:
                d_giant = rec["giant_share"] - prev["giant_share"]
                d_comp = rec["components"] - prev["components"]
                deltas.append((abs(d_giant), t, f"giant_share {prev['giant_share']} -> {rec['giant_share']}, components {prev['components']} -> {rec['components']} ({d_comp:+d})"))
            prev = rec
    deltas.sort(reverse=True)
    print("largest structural steps (by giant-component share):", flush=True)
    for _, t, desc in deltas[:8]:
        print(f"  doc {t}: {desc}", flush=True)
    print(f"TIMESERIES COMPLETE -> {out_path}", flush=True)


if __name__ == "__main__":
    main()

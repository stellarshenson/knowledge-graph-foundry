"""R45 wide metric sweep (H469-H488): the temporary over-instrumentation.

Computes 20 metric families over the live pile - classic graph theory,
embedding-space, KGF-semantic, and exotic (Forman-Ricci curvature stands in
for Ollivier-Ricci as the combinatorial curvature proxy; spectral entropy is
truncated to the top-64 normalized-Laplacian eigenvalues - the SAME method
both runs, so the differential is valid). H484 (facts-per-entity) is taken
from the latest H389 certificate, not recomputed here.

Usage: python scripts/experiments/r45_metric_sweep.py <label>   (label: pre-repair | post-repair | pre-pass2 | post-pass2)
Writes: reports/experiments/r45/metric-sweep-<label>-<ts>.json
"""

import json
import statistics as st
import sys
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
import numpy as np
from scipy.sparse.linalg import eigsh

from knowledge_graph_foundry import load_settings
from knowledge_graph_foundry.pipeline import Foundry

CONFIG = Path("config/experiments/config-bench-pilot.yml")
OUT = Path("reports/experiments/r45")


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "unlabeled"
    st_cfg = load_settings(CONFIG)
    st_cfg.event_log = None
    OUT.mkdir(parents=True, exist_ok=True)

    with Foundry(st_cfg) as f, f.driver.session() as s:
        ents = s.run(
            "MATCH (e:Entity) RETURN e.id AS id, e.name AS name, "
            "size(keys(e)) AS nprops, size(coalesce(e.description,'')) AS dlen, "
            "size(coalesce(e.source_chunks,[])) AS nchunks"
        ).data()
        rels = s.run(
            "MATCH (a:Entity)-[r]->(b:Entity) RETURN a.id AS a, b.id AS b, type(r) AS t"
        ).data()

    G = nx.Graph()
    G.add_nodes_from(e["id"] for e in ents)
    G.add_edges_from((r["a"], r["b"]) for r in rels)
    n, m = G.number_of_nodes(), G.number_of_edges()
    degs = [d for _, d in G.degree()]
    comps = list(nx.connected_components(G))
    giant = max(comps, key=len) if comps else set()
    Gg = G.subgraph(giant)

    out = {"label": label, "nodes": n, "edges": m}
    # H469 degree moments
    out["H469_degree"] = {
        "mean": round(st.mean(degs), 3), "max": max(degs),
        "var": round(st.variance(degs), 3),
        "skew": round(float(np.mean(((np.array(degs) - np.mean(degs)) / (np.std(degs) or 1)) ** 3)), 3),
    }
    # H470 components
    out["H470_components"] = {
        "count": len(comps), "giant_share": round(len(giant) / n, 4),
        "isolates": sum(1 for d in degs if d == 0),
    }
    # H471 k-core
    core = nx.core_number(G)
    out["H471_kcore"] = {"max_core": max(core.values()), "core2_share": round(sum(1 for v in core.values() if v >= 2) / n, 4)}
    # H472 clustering
    out["H472_clustering"] = {
        "global": round(nx.transitivity(G), 5),
        "mean_local": round(nx.average_clustering(G), 5),
    }
    # H473 assortativity
    try:
        out["H473_assortativity"] = round(nx.degree_assortativity_coefficient(G), 4)
    except Exception:
        out["H473_assortativity"] = None
    # H474 spectral (top-16 normalized-Laplacian eigenvalues on the giant)
    L = nx.normalized_laplacian_matrix(Gg).astype(float)
    k = min(16, Gg.number_of_nodes() - 2)
    ev = sorted(eigsh(L, k=k, which="LM", return_eigenvectors=False, tol=1e-3).tolist())
    out["H474_spectrum_top"] = [round(x, 5) for x in ev[-6:]]
    # H475 hub condensation
    out["H475_hub"] = {"kmax_over_E": round(max(degs) / m, 5), "top_hub_share": round(max(degs) / (2 * m), 5)}
    # H476 sampled path length on the giant
    import random
    random.seed(42)
    nodes_g = list(Gg.nodes())
    pairs = [(random.choice(nodes_g), random.choice(nodes_g)) for _ in range(200)]
    ls = []
    for a, b in pairs:
        try:
            ls.append(nx.shortest_path_length(Gg, a, b))
        except Exception:
            pass
    out["H476_pathlen"] = {"mean_sampled": round(st.mean(ls), 3) if ls else None, "n": len(ls)}
    # H477 kNN hubness in embedding space is expensive; proxy via degree of
    # nearest-neighbor graph SKIPPED here - recorded from the seed-rank sweep
    # (H479 file) to keep the sweep offline. Marker for consistency:
    out["H477_hubness"] = "see H479 companion (query-side sweep)"
    # H480 property density
    out["H480_props"] = {
        "mean_props": round(st.mean(e["nprops"] for e in ents), 3),
        "mean_desc_len": round(st.mean(e["dlen"] for e in ents), 1),
        "p90_desc_len": sorted(e["dlen"] for e in ents)[int(0.9 * len(ents))],
    }
    # H481 relation entropy
    from collections import Counter
    tc = Counter(r["t"] for r in rels)
    total = sum(tc.values())
    ent_h = -sum((c / total) * np.log2(c / total) for c in tc.values())
    out["H481_rel_entropy"] = {"bits": round(float(ent_h), 4), "vocab": len(tc)}
    # H482 provenance density
    out["H482_provenance"] = {"mean_chunks": round(st.mean(e["nchunks"] for e in ents), 3)}
    # H483 orphans
    out["H483_orphans"] = {"isolate_share": round(sum(1 for d in degs if d == 0) / n, 4)}
    # H485 Heaps proxy: distinct name tokens vs total name tokens
    toks = [t for e in ents for t in (e["name"] or "").lower().split()]
    out["H485_heaps"] = {"type_token": round(len(set(toks)) / len(toks), 4), "tokens": len(toks)}
    # H486 Forman-Ricci curvature (combinatorial, sampled 500 edges)
    edges = list(G.edges())
    random.seed(43)
    sample = random.sample(edges, min(500, len(edges)))
    frc = [4 - G.degree(u) - G.degree(v) for u, v in sample]
    out["H486_forman_ricci"] = {"mean": round(st.mean(frc), 3), "p10": sorted(frc)[len(frc) // 10]}
    # H487 truncated von Neumann entropy (top-64 eigenvalues)
    k2 = min(64, Gg.number_of_nodes() - 2)
    ev2 = np.abs(eigsh(L, k=k2, which="LM", return_eigenvectors=False, tol=1e-3))
    p = ev2 / ev2.sum()
    out["H487_vn_entropy_trunc"] = round(float(-(p * np.log2(p + 1e-12)).sum()), 4)
    # H488 motif census
    tri = sum(nx.triangles(G).values()) // 3
    wedges = sum(d * (d - 1) // 2 for d in degs)
    out["H488_motifs"] = {"triangles": tri, "wedges": wedges, "tri_per_wedge": round(tri / wedges, 6) if wedges else None}

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = OUT / f"metric-sweep-{label}-{ts}.json"
    path.write_text(json.dumps(out, indent=2))
    print(f"R45 SWEEP [{label}] COMPLETE: {n} nodes / {m} edges -> {path}", flush=True)


if __name__ == "__main__":
    main()

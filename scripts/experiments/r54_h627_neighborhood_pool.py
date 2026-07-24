"""R54-H627: neighborhood-pooled retrieval index - FREE oracle gate.

Prices the ONE mechanism that transfers out of the awesome-graph-classification
"Spectral and Statistical Fingerprints" chapter (FEATHER, CIKM 2020): Ahat^r-weighted
pooling of node ATTRIBUTES into the node's own descriptor. Every other paper in that
chapter is a whole-graph descriptor (NetLSD/SLaQ/FGSD/NetSimile/LDP/de-Lara) or a
2-class discriminative subgraph (contrast subgraphs) and is fenced by H95/H474/H487/
H545/H556/H587/H598.

THE OPEN QUESTION (not covered by H582): H582 swapped the ENCODER while holding the
indexed FIELD constant (embeddings.py convention "type: name - description[:200]") and
found the ~0.60 dense carrier bound EMBEDDER-INVARIANT. Nobody has changed the FIELD.
A neighborhood-pooled index makes a node's retrieval key carry its neighbours' text, so
a bridge entity absent from the question text can be landed on DIRECTLY - and because a
vector index has no component structure, it can cross the 1,830-component archipelago
that R52 proved no query-time walk can cross ("cross-component proximity is 0 by
construction").

HONEST CONTROLS (H556 doctrine - the control is the strongest cheap incumbent, not a
strawman): every recovery is decomposed against what query-time expansion ALREADY gives
- seeds u 1-hop(seeds) and PPR top-15 (H64: PPR's top-15 is 99.4% seeds+1hop). A
carrier "recovered" by pooling that already sits in the base region is worth ZERO.

Arms (all over the SAME stored Titan vectors and the SAME fixed adjacency, pure numpy):
  base            - dense@16 on raw node text embeddings (harness gate: must reproduce
                    H582's Titan 0.6012 / H501's 0.5982)
  inherit-oracle-r - score(c) = max over N_r(c) u {c} of cos(q, e_w); the CEILING on the
                    single-neighbour-inheritance mechanism (not a bound on additive
                    pooling, which is why the mean/rw arms run too)
  meanpool-r1-a    - z_c = normalize((1-a) e_c + a (Ahat e)_c)
  rwpool-r2-a      - z_c = normalize((1-a) e_c + a (Ahat^2 e)_c)   [FEATHER first moment]

NOTE ON FEATHER PROPER: the characteristic-function transform (Ahat^r cos(x (x) Theta))
maps nodes into a cos/sin feature space in which a text QUERY has no image, so it breaks
query-node comparability and cannot serve as a retrieval key directly. What transfers is
the pooling OPERATOR (the paper's "first moment", the part FEATHER improves upon), plus
its corruption bound |Delta| <= 2 Ahat^r_{u,w} - the answer to H95's "structure actively
misleads" risk. Recorded so the round never overclaims the paper.

Pure offline: reads only the H582 cache (tmp/results/r47), no Neo4j, no GPU, no network.
Writes: reports/experiments/r54/h627-neighborhood-pool-<UTC ts>.json
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix, identity
from scipy.sparse.csgraph import connected_components

ROOT = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry")
CACHE = ROOT / "tmp/results/r47"
OUT = ROOT / "reports/experiments/r54"
SCREEN = ROOT / "reports/experiments/bench/r46-h499-screen-20260713T072044Z.jsonl"
QUESTIONS = ROOT / "data/external/multihop-qa-benchmarks/2wikimultihopqa.json"

TOP_K = 16
PPR_TOP_N = 15
DAMPING = 0.85
ITERS = 50
H582_TITAN_RECALL = 0.6012


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.casefold())


def ppr(adj, out_deg, seed_idx, n):
    p = np.zeros(n)
    p[seed_idx] = 1.0 / len(seed_idx)
    r = p.copy()
    for _ in range(ITERS):
        r = (1 - DAMPING) * p + DAMPING * (adj.T @ (r / out_deg))
    return r


def nbr_max(sims, indptr, indices, n):
    """score'(c) = max(score(c), max over 1-hop neighbours). Applied r times = N_r max."""
    out = sims.copy()
    for i in range(n):
        s, e = indptr[i], indptr[i + 1]
        if e > s:
            m = sims[indices[s:e]].max()
            if m > out[i]:
                out[i] = m
    return out


def topk_idx(scores, k):
    sd = np.argpartition(-scores, k)[:k]
    return [int(x) for x in sd[np.argsort(-scores[sd])]]


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)

    meta = json.loads((CACHE / "ents_meta.json").read_text())
    titan = np.load(CACHE / "titan_emb.npy")
    edges = json.loads((CACHE / "edges.json").read_text())
    n = len(meta)
    idx_of_id = {m["id"]: i for i, m in enumerate(meta)}
    name_norms = [_norm(m["name"]) if m["name"] else "" for m in meta]
    graph_norms = set(name_norms)
    name_row = {}
    for i, nn in enumerate(name_norms):
        name_row.setdefault(nn, i)

    ij = np.array([[idx_of_id[a], idx_of_id[b]] for a, b in edges
                   if a in idx_of_id and b in idx_of_id])
    adj = csr_matrix((np.ones(len(ij)), (ij[:, 0], ij[:, 1])), shape=(n, n))
    adj = ((adj + adj.T) > 0).astype(float).tocsr()
    out_deg = np.asarray(adj.sum(axis=1)).ravel()
    deg_safe = out_deg.copy()
    deg_safe[deg_safe == 0] = 1.0

    # component census (verifies the R52 archipelago finding on the same substrate)
    ncomp, comp_label = connected_components(adj, directed=False)
    comp_sizes = np.bincount(comp_label)
    lcc = int(comp_sizes.argmax())

    # Ahat = D^-1 A  (FEATHER's normalized adjacency = RW transition probabilities)
    Ahat = csr_matrix((1.0 / deg_safe, (np.arange(n), np.arange(n))), shape=(n, n)) @ adj

    titan_n = titan / np.linalg.norm(titan, axis=1, keepdims=True)
    A1 = Ahat @ titan_n
    A2 = Ahat @ A1

    def blend(base, prop, a):
        z = (1 - a) * base + a * prop
        nz = np.linalg.norm(z, axis=1, keepdims=True)
        nz[nz == 0] = 1.0
        return z / nz

    # ---- probes + carriers (identical convention to H501/H582) ----
    off_ids, off_seen = [], set()
    for line in SCREEN.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["arm"] == "off" and r["id"] not in off_seen:
            off_seen.add(r["id"])
            off_ids.append(r["id"])
    Q = {q.get("_id"): q for q in json.loads(QUESTIONS.read_text())}

    probe_emb = {}
    with np.load(CACHE / "titan_probe_emb.npz") as z:
        for pid in off_ids:
            if pid in z:
                v = z[pid].astype(np.float64)
                probe_emb[pid] = v / np.linalg.norm(v)
    probe_ids = [p for p in off_ids if p in probe_emb]

    carriers = []
    for pid in probe_ids:
        q = Q.get(pid)
        if not q:
            continue
        titles = []
        for item in (q.get("supporting_facts") or []):
            t = item[0] if isinstance(item, (list, tuple)) else item.get("title")
            if t and t not in titles:
                titles.append(t)
        for t in titles:
            tn = _norm(t)
            carriers.append({"probe": pid, "tnorm": tn,
                             "in_graph": tn in graph_norms,
                             "carrier_idx": name_row.get(tn)})

    # ---- base arm: seeds, regions, per-carrier hits ----
    base_seeds, base_region, base_seed_comps = {}, {}, {}
    for pid in probe_ids:
        sims = titan_n @ probe_emb[pid]
        sd = topk_idx(sims, TOP_K)
        base_seeds[pid] = sd
        hop = set(sd)
        for u in sd:
            hop |= set(adj.indices[adj.indptr[u]:adj.indptr[u + 1]].tolist())
        r = ppr(adj, deg_safe, sd, n)
        base_region[pid] = hop | set(np.argsort(-r)[:PPR_TOP_N].tolist())
        base_seed_comps[pid] = {int(comp_label[u]) for u in sd}

    def hits_for(seed_sets):
        return [1 if c["tnorm"] in {name_norms[i] for i in seed_sets[c["probe"]]} else 0
                for c in carriers]

    base_hits = hits_for(base_seeds)

    def run_arm(name, score_fn):
        seeds = {}
        for pid in probe_ids:
            seeds[pid] = topk_idx(score_fn(pid), TOP_K)
        hits = hits_for(seeds)
        rec_new, lost, beyond, cross = 0, 0, 0, 0
        beyond_ex, cross_ex = [], []
        for c, hb, ha in zip(carriers, base_hits, hits):
            if ha and not hb:
                rec_new += 1
                ci = c["carrier_idx"]
                if ci is not None and ci not in base_region[c["probe"]]:
                    beyond += 1
                    if int(comp_label[ci]) not in base_seed_comps[c["probe"]]:
                        cross += 1
                        if len(cross_ex) < 12:
                            cross_ex.append({"probe": c["probe"], "carrier": c["tnorm"],
                                             "comp_size": int(comp_sizes[comp_label[ci]])})
                    elif len(beyond_ex) < 12:
                        beyond_ex.append({"probe": c["probe"], "carrier": c["tnorm"]})
            if hb and not ha:
                lost += 1
        return {
            "arm": name,
            "carrier_recall@16": round(float(np.mean(hits)), 4),
            "delta_pts": round(100 * (float(np.mean(hits)) - float(np.mean(base_hits))), 2),
            "recovered": rec_new, "lost_to_dilution": lost,
            "recovered_beyond_base_region": beyond,
            "recovered_cross_component": cross,
            "cross_component_examples": cross_ex,
            "beyond_region_examples": beyond_ex,
        }

    results = [{"arm": "base(titan raw)",
                "carrier_recall@16": round(float(np.mean(base_hits)), 4),
                "delta_pts": 0.0, "recovered": 0, "lost_to_dilution": 0,
                "recovered_beyond_base_region": 0, "recovered_cross_component": 0,
                "cross_component_examples": [], "beyond_region_examples": []}]

    indptr, indices = adj.indptr, adj.indices
    for r_hops in (1, 2):
        def sf(pid, r_hops=r_hops):
            s = titan_n @ probe_emb[pid]
            for _ in range(r_hops):
                s = nbr_max(s, indptr, indices, n)
            return s
        results.append(run_arm(f"inherit-oracle-r{r_hops}", sf))

    for prop, tag in ((A1, "meanpool-r1"), (A2, "rwpool-r2")):
        for a in (0.25, 0.5, 0.75):
            Z = blend(titan_n, prop, a)
            def sf(pid, Z=Z):
                return Z @ probe_emb[pid]
            results.append(run_arm(f"{tag}-a{a}", sf))

    # ---- DECISIVE honest controls: is pooling just PPR/1-hop re-expressed? ----
    # H64 recorded that PPR at our scale is "not an expander but a lossy filter on the
    # 1-hop neighbourhood" and left the successor question open: WHICH 1-hop neighbours
    # matter. These arms answer it - both rank the SAME already-reachable region, one by
    # walk mass (incumbent query-time machinery) and one by pooled attributes.
    ppr_cache = {pid: ppr(adj, deg_safe, base_seeds[pid], n) for pid in probe_ids}

    def ppr_rank(pid):
        return ppr_cache[pid]

    def ppr_rank_exseeds(pid):
        s = ppr_cache[pid].copy()
        s[base_seeds[pid]] = -np.inf
        return s

    def onehop_raw_rerank(pid):
        """Expand seeds by 1 hop, rank the union by RAW cos - the trivial incumbent."""
        sims = titan_n @ probe_emb[pid]
        allowed = np.full(n, -np.inf)
        hop = set(base_seeds[pid])
        for u in base_seeds[pid]:
            hop |= set(adj.indices[adj.indptr[u]:adj.indptr[u + 1]].tolist())
        idx = np.fromiter(hop, dtype=int)
        allowed[idx] = sims[idx]
        return allowed

    results.append(run_arm("CONTROL ppr-rank", ppr_rank))
    results.append(run_arm("CONTROL ppr-exseeds", ppr_rank_exseeds))
    results.append(run_arm("CONTROL 1hop-raw-rerank", onehop_raw_rerank))

    # paired significance of every arm vs base, on the 326 carriers (H541 pairing)
    from scipy.stats import binomtest
    for r in results:
        b = r["lost_to_dilution"]
        c = r["recovered"]
        r["mcnemar_p"] = (1.0 if b + c == 0 else
                          round(float(binomtest(min(b, c), b + c, 0.5,
                                                alternative="two-sided").pvalue), 6))

    # ---- alpha shape + split-half stability (the alpha was picked on this same frozen
    # set, so price the selection rather than hide it) + paired bootstrap CI ----
    def hits_of(Z):
        seeds = {pid: topk_idx(Z @ probe_emb[pid], TOP_K) for pid in probe_ids}
        return np.array(hits_for(seeds), dtype=float)

    alpha_curve = []
    for a in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7):
        h = hits_of(blend(titan_n, A1, a))
        alpha_curve.append({"alpha": a, "recall": round(float(h.mean()), 4)})

    probe_index = {pid: k for k, pid in enumerate(probe_ids)}
    half = np.array([probe_index[c["probe"]] % 2 for c in carriers])
    split = {}
    for hh in (0, 1):
        m = half == hh
        best_a, best_v = None, -1
        for a in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7):
            v = float(hits_of(blend(titan_n, A1, a))[m].mean())
            if v > best_v:
                best_a, best_v = a, v
        other = half == (1 - hh)
        transfer = float(hits_of(blend(titan_n, A1, best_a))[other].mean())
        split[f"fit_half{hh}"] = {"best_alpha": best_a, "in_half": round(best_v, 4),
                                  "transfers_to_other_half": round(transfer, 4),
                                  "base_other_half": round(float(np.array(base_hits)[other].mean()), 4)}

    rng = np.random.default_rng(0)
    best_h = hits_of(blend(titan_n, A1, 0.5))
    ppr_h = np.array(hits_for({pid: topk_idx(ppr_cache[pid], TOP_K) for pid in probe_ids}), dtype=float)
    base_h = np.array(base_hits, dtype=float)
    ci = {}
    for tag, ref in (("vs_base", base_h), ("vs_ppr_control", ppr_h)):
        d = np.empty(5000)
        for i in range(5000):
            k = rng.integers(0, len(best_h), len(best_h))
            d[i] = best_h[k].mean() - ref[k].mean()
        lo, hi = np.percentile(d, [2.5, 97.5])
        ci[tag] = {"delta_pts": round(100 * float(best_h.mean() - ref.mean()), 2),
                   "ci95_pts": [round(100 * float(lo), 2), round(100 * float(hi), 2)]}

    ig = np.array([c["in_graph"] for c in carriers], dtype=bool)
    bh = np.array(base_hits, dtype=bool)
    headroom_ingraph = int((ig & ~bh).sum())

    # where do the missed in-graph carriers live? (archipelago accounting)
    miss_in_lcc = miss_out_lcc = 0
    for c, hb in zip(carriers, base_hits):
        if c["in_graph"] and not hb and c["carrier_idx"] is not None:
            if int(comp_label[c["carrier_idx"]]) == lcc:
                miss_in_lcc += 1
            else:
                miss_out_lcc += 1

    payload = {
        "hypothesis": "R54-H627",
        "run_id": run_id,
        "substrate": "medium 2wiki (6,626 entities), stored Titan vectors, H582 offline cache",
        "n_probes": len(probe_ids),
        "n_carriers": len(carriers),
        "n_carriers_in_graph": int(ig.sum()),
        "headroom_in_graph_missed_by_base": headroom_ingraph,
        "missed_in_graph_by_component": {"in_lcc": miss_in_lcc, "outside_lcc": miss_out_lcc},
        "harness_gate": {"base_recall": round(float(np.mean(base_hits)), 4),
                         "h582_titan_recall": H582_TITAN_RECALL,
                         "reproduces": abs(float(np.mean(base_hits)) - H582_TITAN_RECALL) < 0.02},
        "component_census": {"n_components": int(ncomp),
                             "lcc_size": int(comp_sizes[lcc]),
                             "lcc_share": round(float(comp_sizes[lcc] / n), 4),
                             "isolated_nodes": int((comp_sizes == 1).sum())},
        "arms": results,
        "alpha_curve": alpha_curve,
        "split_half_alpha_selection": split,
        "paired_bootstrap_meanpool_a0.5": ci,
    }
    path = OUT / f"h627-neighborhood-pool-{run_id}.json"
    path.write_text(json.dumps(payload, indent=1))
    print(json.dumps({k: v for k, v in payload.items() if k != "arms"}, indent=1), flush=True)
    for r in results:
        print(f"{r['arm']:>22}  recall {r['carrier_recall@16']:.4f}  "
              f"delta {r['delta_pts']:+.2f}pt  recovered {r['recovered']:>3}  "
              f"lost {r['lost_to_dilution']:>3}  beyond-region {r['recovered_beyond_base_region']:>3}  p={r['mcnemar_p']:<9.5g} "
              f"cross-comp {r['recovered_cross_component']:>3}", flush=True)
    print(f"\nwrote {path}", flush=True)


if __name__ == "__main__":
    main()

"""R57-H644 CRUX + H645-H650: the miss atlas - per-failure diagnostic coordinates.

The instrument (H644) computes a standardized coordinate vector for EVERY
(probe, gold-carrier) row on the frozen 132 OFF-arm probes (326 rows), with the
HIT population as the mandatory control. Axes span LINKER / DENSE / TRAVERSAL /
ENTITY-SIDE / QUERY-SIDE / JOIN-RENDER. The census claims H645-H650 are queries
over the atlas applying the registered bars EXACTLY.

FREE run: /opt/conda/bin/python, pure numpy/scipy/rapidfuzz over on-disk caches.
NO GPU, NO LLM, NO Neo4j, NO network. Reuses substrate loaders verbatim from
r50_h619_seedland_digs (load_substrate/build_anchors) and the H623 scored
candidate-list machinery (blend, per-query min-max norm, cand_floor 0.6,
cand_cap 15, max-gap detector).

Writes:
  reports/experiments/r57/h644-miss-atlas-rows-<ts>.jsonl   (326 coordinate rows)
  reports/experiments/r57/h644-miss-atlas-<ts>.json         (summary + H645-H650)
"""

import json
import re
import sys
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

ROOT = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry")
sys.path.insert(0, str(ROOT / "scripts/experiments"))

import r47_h582_embedder_swap as H       # noqa: E402  (_norm, ppr, TOP_K, CACHE)
import r50_h619_seedland_digs as R50     # noqa: E402  (load_substrate, build_anchors)
from rapidfuzz import fuzz, process      # noqa: E402

CACHE = ROOT / "tmp/results/r47"
OUT = ROOT / "reports/experiments/r57"
SPAN_CACHE = ROOT / "tmp/results/r50/h597_gliner_spans.json"
H619_ART = ROOT / "reports/experiments/r50/h619-stoplist-20260713T233206Z.json"
GOLDJOIN_V2 = ROOT / "reports/experiments/r55/h632-gold-join-20260724T075045Z.json"
GOLDJOIN_V3 = ROOT / "reports/experiments/r56/h635-type-gate-20260724T082828Z.json"
H620_JSON = ROOT / "reports/experiments/r50/h620-conversion-20260713T233256Z.json"
H620_CKPT = ROOT / "reports/experiments/r50/h620-conversion-20260713T233256Z.checkpoint.jsonl"

TOP_K = 16
PPR_TOP_N = 15
CAND_FLOOR = 0.6
CAND_CAP = 15
K1, B = 1.5, 0.75

# --- sanity pins (reproduce FIRST; abort on mismatch) -----------------------
PINS = {
    "base_dense16_carrier_recall": 0.6012,
    "maxgap_adaptive_k_reach_all": 0.8740,
    "join_r0": (288, 326),
    "join_v2": (313, 326),
    "join_v3": (314, 326),
    "n_components": 1830,
    "lcc_size": 3162,
    "isolated_nodes": 1426,
}


def tok(s):
    return re.findall(r"[a-z0-9]+", s.lower())


def norm01(scores):
    s = np.asarray(scores, dtype=float)
    lo, hi = s.min(), s.max()
    if hi - lo < 1e-12:
        return np.ones_like(s)
    return (s - lo) / (hi - lo)


def detect_maxgap(scores):
    """H623 verbatim: cut after the largest adjacent score drop. (cut_k, strength)."""
    s = np.asarray(scores, dtype=float)
    m = len(s)
    if m <= 1:
        return m, 1.0
    gaps = s[:-1] - s[1:]
    j = int(np.argmax(gaps))
    return j + 1, float(gaps[j])


def multi_source_bfs(indptr, indices, sources, n):
    """Unweighted min hop distance from any source node. inf if unreachable."""
    dist = np.full(n, np.inf)
    dq = deque()
    for s in sources:
        if dist[s] != 0:
            dist[s] = 0
            dq.append(s)
    while dq:
        u = dq.popleft()
        du = dist[u]
        for v in indices[indptr[u]:indptr[u + 1]]:
            if dist[v] == np.inf:
                dist[v] = du + 1
                dq.append(int(v))
    return dist


def hop_val(d):
    return None if not np.isfinite(d) else int(d)


def rank_auc(hit_vals, miss_vals):
    """AUC = P(hit_feature > miss_feature) with ties=0.5 (Mann-Whitney)."""
    hit_vals = [v for v in hit_vals if v is not None]
    miss_vals = [v for v in miss_vals if v is not None]
    if not hit_vals or not miss_vals:
        return None
    wins = 0.0
    for h in hit_vals:
        for m in miss_vals:
            if h > m:
                wins += 1
            elif h == m:
                wins += 0.5
    return round(wins / (len(hit_vals) * len(miss_vals)), 4)


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (round((c - half) / d, 4), round((c + half) / d, 4))


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731
    rows_path = OUT / f"h644-miss-atlas-rows-{run_id}.jsonl"
    summ_path = OUT / f"h644-miss-atlas-{run_id}.json"

    # ---------------- substrate ---------------------------------------------
    S = R50.load_substrate()
    n = S["n"]
    meta, name_row, name_norms = S["meta"], S["name_row"], S["name_norms"]
    carriers, off_ids, Q = S["carriers"], S["off_ids"], S["Q"]
    adj, out_deg = S["adj"], S["out_deg"]
    titan_n = S["titan_n"]
    probe_emb = S["titan_probe_n"]
    indptr, indices = adj.indptr, adj.indices
    true_deg = np.asarray(adj.sum(axis=1)).ravel().astype(int)   # honest degree
    titan_raw = np.load(CACHE / "titan_emb.npy")
    titan_l2 = np.linalg.norm(titan_raw, axis=1)                 # pre-normalization L2

    # component labels (R52 archipelago; H631 convention)
    ncomp, comp = connected_components(adj, directed=False)
    comp_sizes = np.bincount(comp)
    lcc = int(comp_sizes.argmax())

    # meanpool-r1 smoothing (H627 alpha=0.6)
    deg_safe = out_deg.copy()
    Ahat = csr_matrix((1.0 / deg_safe, (np.arange(n), np.arange(n))), shape=(n, n)) @ adj
    A1 = Ahat @ titan_n
    Z06 = (1 - 0.6) * titan_n + 0.6 * A1
    Z06 = Z06 / (np.linalg.norm(Z06, axis=1, keepdims=True) + 1e-9)

    # ---------------- goldjoin v2 / v3 accepted maps ------------------------
    v2 = json.loads(GOLDJOIN_V2.read_text())
    v2_map = {r["gold_title"]: r["matched_idx"]
              for r in v2["part_b_ladder"]["all_rows"] if r["disposition"] == "ACCEPTED"}
    v3rows = json.loads(GOLDJOIN_V3.read_text())["ladder_v3_gate_on"]["all_rows"]
    v3_map = {r["gold_title"]: r["matched_idx"]
              for r in v3rows if r["disposition"] == "ACCEPTED"}

    # ---------------- reasoning-role tag (bridge-role axis) -----------------
    # derived from 2wiki gold: evidence-triple subject/object membership (primary)
    # + supporting-fact order (fallback). bridge = pivot (obj of one triple, subj of
    # a later one); first-hop = source (subj only); terminal-answer = object only.
    def role_map_for(pid):
        q = Q.get(pid) or {}
        evs = q.get("evidences") or []
        subj = {H._norm(s_) for (s_, r_, o_) in evs}
        obj = {H._norm(o_) for (s_, r_, o_) in evs}
        titles = R50.gold_titles(q)
        out = {}
        for k, t in enumerate(titles):
            tn = H._norm(t)
            if tn in subj and tn in obj:
                out[t] = ("bridge", "evidence")
            elif tn in subj:
                out[t] = ("first-hop", "evidence")
            elif tn in obj:
                out[t] = ("terminal-answer", "evidence")
            else:
                # fallback: order in supporting_facts
                if len(titles) == 1:
                    out[t] = ("terminal-answer", "fallback_order")
                elif k == 0:
                    out[t] = ("first-hop", "fallback_order")
                elif k == len(titles) - 1:
                    out[t] = ("terminal-answer", "fallback_order")
                else:
                    out[t] = ("bridge", "fallback_order")
        return out
    role_of = {pid: role_map_for(pid) for pid in off_ids}

    # ---------------- H620 render buckets (FIRST-title replay, H631) ---------
    ck = [json.loads(l) for l in H620_CKPT.read_text().splitlines() if l.strip()]
    base_fail_pids = {r["pid"] for r in ck if r["arm"] == "base_b06" and not r["base_pass"]}
    h620 = json.loads(H620_JSON.read_text())
    recorded_base = h620["flip_table"]["base_b06"]["nonflip_failure_decomposition"]

    # ---------------- H623 scored candidate lists (per distinct span norm) ---
    lexicon = set(json.loads(H619_ART.read_text())["stoplist_lexicon"])  # noqa: F841 (kept for parity)
    docs = [tok(nn) for nn in name_norms]
    df = Counter()
    for dd in docs:
        for t in set(dd):
            df[t] += 1
    Nd = len(docs)
    dl = np.array([len(x) for x in docs], dtype=float)
    avgdl = dl.mean()
    idf = {t: np.log(1 + (Nd - c + 0.5) / (c + 0.5)) for t, c in df.items()}
    term_docs = defaultdict(list)
    for i, dd in enumerate(docs):
        for t, f in Counter(dd).items():
            term_docs[t].append((i, f))
    denom_base = K1 * (1 - B + B * dl / avgdl)
    bm25_cache = {}

    def bm25_term_vec(t):
        if t in bm25_cache:
            return bm25_cache[t]
        v = np.zeros(Nd)
        if t in idf:
            for i, f in term_docs[t]:
                v[i] = idf[t] * (f * (K1 + 1)) / (f + denom_base[i])
        bm25_cache[t] = v
        return v

    def bm25_score(qtoks):
        v = np.zeros(Nd)
        for t in set(qtoks):
            v += bm25_term_vec(t)
        return v

    names_arr = name_norms
    cl_cache = {}

    def candidate_list(span_norm):
        if span_norm in cl_cache:
            return cl_cache[span_norm]
        L = len(span_norm)
        fr = np.asarray(process.cdist([span_norm], names_arr, scorer=fuzz.ratio)[0]) / 100.0
        cont = np.zeros(Nd)
        if L >= 3:
            for i in range(Nd):
                nn = names_arr[i]
                if len(nn) >= 3 and (span_norm in nn or nn in span_norm):
                    cont[i] = min(len(nn), L) / max(len(nn), L)
        bm = bm25_score(tok(span_norm))
        bmn = bm / bm.max() if bm.max() > 0 else bm
        exact = np.zeros(Nd)
        if span_norm in name_row:
            exact[name_row[span_norm]] = 1.0
        blended = np.maximum.reduce([exact, cont, fr, bmn])
        idx = np.where(blended >= CAND_FLOOR)[0]
        if len(idx) == 0:
            idx = np.array([int(np.argmax(blended))])
        idx = idx[np.argsort(-blended[idx])][:CAND_CAP]
        res = (idx, blended[idx])
        cl_cache[span_norm] = res
        return res

    # per-probe spanrecs (H623): candidate pool + max-gap cut + gold targets
    spans_by_pid = json.loads(SPAN_CACHE.read_text())
    spanrecs = []
    for pid in off_ids:
        golds = set(S["gold_idx_of"].get(pid, []))
        for text, _g in spans_by_pid.get(pid, []):
            sn = H._norm(text)
            idx, blended = candidate_list(sn)
            ns = norm01(blended)
            cut_k, strength = detect_maxgap(ns)           # lambda=0 -> always fires
            spanrecs.append({
                "pid": pid, "span": text, "span_norm": sn,
                "cand_idx": [int(i) for i in idx.tolist()],
                "blended": [float(x) for x in blended.tolist()],
                "norm_scores": [float(x) for x in ns.tolist()],
                "cut_k": cut_k, "strength": strength,
                "gold_targets": sorted(int(i) for i in idx.tolist() if int(i) in golds),
            })
    log(f"spanrecs={len(spanrecs)} over {len(off_ids)} probes; distinct span pools={len(cl_cache)}")

    # ---------------- best-arm anchors (max-gap) + regions ------------------
    anchors_maxgap = defaultdict(set)   # pid -> kept candidate indices (best-arm linker)
    for r in spanrecs:
        for k in range(r["cut_k"]):
            anchors_maxgap[r["pid"]].add(r["cand_idx"][k])

    def onehop(seed_set):
        h = set()
        for u in seed_set:
            h.update(int(x) for x in indices[indptr[u]:indptr[u + 1]])
        return h

    dense_seeds = {pid: set(S["seeds_q"][pid]) for pid in off_ids}
    ppr_vec = {}
    reset_region = {}       # reset_region_union (reachability region)
    region_boundary = {}    # seeds u 1-hop u PPR-top15 (retrieved region for boundary dist)
    reach_comps = {}        # components touched by dense seeds + anchors
    for pid in off_ids:
        anc = anchors_maxgap.get(pid, set())
        ds = dense_seeds[pid]
        ppr_seeds = list(anc) if anc else list(ds)
        r = H.ppr(adj, out_deg, ppr_seeds, n)
        ppr_vec[pid] = r
        top15 = set(np.argsort(-r)[:PPR_TOP_N].tolist())
        reset_region[pid] = top15 | set(ppr_seeds) | ds
        region_boundary[pid] = ds | onehop(ds) | top15
        reach_comps[pid] = {int(comp[i]) for i in ds} | {int(comp[i]) for i in anc}

    # BFS distance caches per probe
    dist_seed = {pid: multi_source_bfs(indptr, indices, list(dense_seeds[pid]), n) for pid in off_ids}
    dist_anchor = {pid: (multi_source_bfs(indptr, indices, list(anchors_maxgap[pid]), n)
                         if anchors_maxgap.get(pid) else None) for pid in off_ids}
    dist_union = {pid: multi_source_bfs(indptr, indices,
                                        list(dense_seeds[pid] | anchors_maxgap.get(pid, set())), n)
                  for pid in off_ids}
    dist_region = {pid: multi_source_bfs(indptr, indices, list(region_boundary[pid]), n) for pid in off_ids}
    # per-probe elementwise MAX anchor->node distance (finite only), for query-side max hops
    max_anchor_dist = {}
    for pid in off_ids:
        anc = anchors_maxgap.get(pid, set())
        if not anc:
            max_anchor_dist[pid] = None
            continue
        acc = np.full(n, -1.0)
        for a_ in anc:
            dv = multi_source_bfs(indptr, indices, [a_], n)
            fin = np.isfinite(dv)
            acc[fin] = np.maximum(acc[fin], dv[fin])
        max_anchor_dist[pid] = acc  # -1 = unreachable from every anchor

    # dense full-depth ranks per probe (argsort over all 6626)
    dense_rank = {}
    sm_rank = {}
    dense_sims = {}
    rank16_cos = {}   # cosine of the rank-16 seed (cutoff seed)
    for pid in off_ids:
        sims = titan_n @ probe_emb[pid]
        order = np.argsort(-sims)
        rk = np.empty(n, dtype=int)
        rk[order] = np.arange(n)
        dense_rank[pid] = rk
        dense_sims[pid] = sims
        rank16_cos[pid] = float(sims[order[TOP_K - 1]])
        sims06 = Z06 @ probe_emb[pid]
        o6 = np.argsort(-sims06)
        rk6 = np.empty(n, dtype=int)
        rk6[o6] = np.arange(n)
        sm_rank[pid] = rk6

    # gold-target-best-span index: for each (pid, node) find span pool ranking it best
    span_by_pid = defaultdict(list)
    for r in spanrecs:
        span_by_pid[r["pid"]].append(r)

    def linker_axis(pid, cidx):
        """best span linkage for carrier node cidx at probe pid."""
        if cidx is None:
            return {"in_pool": None, "reason": "carrier_has_no_node"}
        best = None
        for r in span_by_pid.get(pid, []):
            if cidx in r["cand_idx"]:
                rank = r["cand_idx"].index(cidx)
                key = (rank, -r["norm_scores"][rank])
                if best is None or key < best[0]:
                    best = (key, r, rank)
        if best is None:
            return {"in_pool": False}
        _, r, rank = best
        ns = r["norm_scores"]
        cut_k = r["cut_k"]
        r0 = r["cand_idx"][0]
        outr = None
        if rank != 0:
            tie = abs(r["blended"][0] - r["blended"][rank]) < 1e-9
            outr = {"name": meta[r0]["name"], "degree": int(true_deg[r0]),
                    "relation": "exact-tie" if tie else "strictly-higher",
                    "score_gap": round(r["blended"][0] - r["blended"][rank], 4)}
        return {
            "in_pool": True, "span": r["span"], "cand_rank": rank,
            "norm_score": round(ns[rank], 4),
            "margin_to_rank0": round(ns[rank] - ns[0], 4),
            "kept_by_maxgap": rank < cut_k,
            "cut_k": cut_k, "signed_rank_dist_to_cut": rank - cut_k,
            "pool_size": len(r["cand_idx"]), "outranker": outr,
        }

    # ---------------- build the 326 coordinate rows -------------------------
    rows = []
    null_reasons = Counter()
    with rows_path.open("w") as fh:
        for c in carriers:
            pid = c["probe"]
            title = c["carrier"]
            in_graph = c["in_graph"]
            cidx = c["carrier_idx"]
            v2idx = cidx if in_graph else v2_map.get(title)
            v3idx = cidx if in_graph else v3_map.get(title)
            # effective node for geometry: v2 (mandatory) then fall through to v3 so
            # absent-from-graph means absence AFTER the hardened join (amendment 4)
            eff = v2idx if v2idx is not None else v3idx
            eff_join = ("r0-exact" if in_graph else "v2" if v2idx is not None
                        else "v3" if v3idx is not None else "none")
            join_r0 = in_graph
            join_v2 = v2idx is not None
            join_v3 = (v3idx is not None)
            role, role_prov = role_of[pid].get(title, ("unknown", "none"))

            ds = dense_seeds[pid]
            # ---- DENSE ----
            if eff is not None:
                draw = int(dense_rank[pid][eff])
                dense = {
                    "raw_rank_full": draw,
                    "signed_dist_to_16cut": draw - (TOP_K - 1),
                    "cos_margin_to_rank16_seed": round(float(dense_sims[pid][eff]) - rank16_cos[pid], 4),
                    "smoothed_rank_a06": int(sm_rank[pid][eff]),
                    "smoothed_minus_raw": int(sm_rank[pid][eff]) - draw,
                    "dense_hit": eff in ds,
                }
            else:
                dense = {k: None for k in ("raw_rank_full", "signed_dist_to_16cut",
                                           "cos_margin_to_rank16_seed", "smoothed_rank_a06",
                                           "smoothed_minus_raw")}
                dense["dense_hit"] = False
                dense["reason"] = "carrier_absent_no_v2_join"
                null_reasons["dense_no_node"] += 1

            # ---- TRAVERSAL ----
            if eff is not None:
                comp_id = int(comp[eff])
                same_comp = comp_id in reach_comps[pid]
                comp_status = "same-as-seeds" if same_comp else "cross"
                gh_seed = hop_val(dist_seed[pid][eff])
                gh_anchor = (hop_val(dist_anchor[pid][eff]) if dist_anchor[pid] is not None else None)
                in_region = eff in region_boundary[pid]
                bdist = 0 if in_region else hop_val(dist_region[pid][eff])
                r = ppr_vec[pid]
                ppr_order = np.argsort(-r)
                ppr_rank = int(np.where(ppr_order == eff)[0][0])
                # on-path: a neighbour of carrier in region is one hop closer to anchor union
                du = dist_union[pid]
                on_path = False
                if np.isfinite(du[eff]):
                    for w in indices[indptr[eff]:indptr[eff + 1]]:
                        if w in region_boundary[pid] and np.isfinite(du[w]) and du[w] == du[eff] - 1:
                            on_path = True
                            break
                    if eff in region_boundary[pid]:
                        on_path = True
                trav = {
                    "component_status": comp_status, "component_id": comp_id,
                    "component_size": int(comp_sizes[comp_id]), "in_lcc": comp_id == lcc,
                    "hops_nearest_seed": gh_seed,
                    "hops_nearest_anchor": gh_anchor,
                    "has_anchors": dist_anchor[pid] is not None,
                    "dist_to_region_boundary": bdist,
                    "inside_region_boundary": in_region,
                    "in_reset_region_union": eff in reset_region[pid],
                    "ppr_mass_rank": ppr_rank,
                    "ppr_signed_dist_to_top15": ppr_rank - (PPR_TOP_N - 1),
                    "on_path": on_path,
                }
                if gh_anchor is None and dist_anchor[pid] is not None:
                    trav["hops_nearest_anchor_reason"] = "carrier_unreachable_from_anchors"
                if not trav["has_anchors"]:
                    trav["hops_nearest_anchor_reason"] = "probe_has_no_maxgap_anchors"
            else:
                trav = {k: None for k in ("component_status", "component_id", "component_size",
                                          "in_lcc", "hops_nearest_seed", "hops_nearest_anchor",
                                          "dist_to_region_boundary", "inside_region_boundary",
                                          "in_reset_region_union",
                                          "ppr_mass_rank", "ppr_signed_dist_to_top15", "on_path")}
                trav["reason"] = "carrier_absent_no_v2_join"
                trav["has_anchors"] = dist_anchor[pid] is not None
                null_reasons["traversal_no_node"] += 1

            # ---- ENTITY-SIDE ----
            if eff is not None:
                descr = meta[eff]["descr"] or ""
                ent = {
                    "degree": int(true_deg[eff]),
                    "descr_present": bool(descr),
                    "descr_length": len(descr),
                    "name_length": len(meta[eff]["name"] or ""),
                    "alias_count": None,
                    "alias_reason": "no_alias_field_in_ents_meta",
                    "embedding_l2_norm_raw": round(float(titan_l2[eff]), 4),
                    "embedding_note": "L2 of stored titan_emb.npy BEFORE unit-normalization",
                }
                null_reasons["alias_null"] += 1
            else:
                ent = {k: None for k in ("degree", "descr_present", "descr_length",
                                         "name_length", "alias_count", "embedding_l2_norm_raw")}
                ent["reason"] = "carrier_absent_no_v2_join"
                null_reasons["entity_no_node"] += 1

            # ---- QUERY-SIDE ----
            anc = anchors_maxgap.get(pid, set())
            n_anchor = len(anc)
            q_min = q_max = None
            if eff is not None and anc:
                q_min = hop_val(dist_anchor[pid][eff])          # multi-source BFS gives the MIN
                mx = max_anchor_dist[pid][eff]
                q_max = int(mx) if mx >= 0 else None            # -1 = unreachable from every anchor
            hfu = (hop_val(dist_union[pid][eff]) if eff is not None else None)
            qside = {
                "linked_anchor_count": n_anchor,
                "min_anchor_to_carrier_hops": q_min,
                "max_anchor_to_carrier_hops": q_max,
                "hops_from_union": hfu,
            }
            if eff is None:
                qside["reason"] = "carrier_absent_no_v2_join"
            elif not anc:
                qside["min_anchor_to_carrier_hops"] = None
                qside["max_anchor_to_carrier_hops"] = None
                qside["anchor_hops_reason"] = "probe_has_no_maxgap_anchors"

            # ---- LINKER ----
            linker = linker_axis(pid, eff)

            # ---- JOIN / RENDER ----
            render_bucket = None
            if pid in base_fail_pids:
                # FIRST-title rule replay (H631): carrier_not_retrieved iff first gold
                # title's node is not in the base dense@16 node set; else the base_b06
                # non-retrieval bucket is rendered_answer_absent (only two base buckets)
                titles = R50.gold_titles(Q[pid])
                first_tn = H._norm(titles[0]) if titles else None
                first_idx = name_row.get(first_tn) if first_tn else None
                if first_idx is None or first_idx not in ds:
                    render_bucket = "carrier_not_retrieved"
                else:
                    render_bucket = "rendered_answer_absent"
            joinrender = {
                "join_r0_exact": join_r0,
                "join_v2": join_v2, "join_v2_version": "goldjoin-v2-20260724",
                "join_v3": join_v3, "join_v3_version": "goldjoin-v3-typegate-20260724",
                "v2_node_idx": v2idx, "v3_node_idx": v3idx,
                "eff_join_source": eff_join,
                "probe_in_47fail_panel": pid in base_fail_pids,
                "render_bucket": render_bucket,
                "render_position_note": ("not-computed: offline replay reconstructs only the "
                                         "dense@16 node-set membership (FIRST-title rule), not the "
                                         "assembled render context; Lost-in-the-Middle position axis "
                                         "SKIPPED per amendment-3 cheap-if-cheap rule"),
            }

            row = {
                "probe": pid, "carrier": title, "in_graph": in_graph,
                "carrier_idx": cidx, "eff_idx": eff, "eff_join_source": eff_join,
                "reasoning_role": role, "role_provenance": role_prov,
                "question_type": (Q.get(pid) or {}).get("type"),
                "linker": linker, "dense": dense, "traversal": trav,
                "entity": ent, "query": qside, "join_render": joinrender,
            }
            rows.append(row)
            fh.write(json.dumps(row) + "\n")

    log(f"wrote {len(rows)} atlas rows -> {rows_path}")

    # ======================= SANITY PINS ====================================
    # base dense@16 carrier recall (exact carrier_idx in dense seeds, 326 denom)
    base_hits = sum(1 for c in carriers
                    if c["in_graph"] and c["carrier_idx"] in dense_seeds[c["probe"]])
    base_recall = round(base_hits / len(carriers), 4)

    # max-gap adaptive-k reachability (reset_region_union, reach_pids)
    reach_pids = S["reach_pids"]
    reach_num = 0
    for pid in reach_pids:
        cis = S["probe_has_carrier"][pid]
        if cis and all(t in reset_region[pid] for t in cis):
            reach_num += 1
    reach_all = round(reach_num / len(reach_pids), 4)

    n_r0 = sum(1 for c in carriers if c["in_graph"])
    n_v2 = n_r0 + len(set(c["carrier"] for c in carriers if not c["in_graph"] and c["carrier"] in v2_map))
    n_v3 = n_r0 + len(set(c["carrier"] for c in carriers if not c["in_graph"] and c["carrier"] in v3_map))

    pins = {
        "base_dense16_carrier_recall": {"expected": 0.6012, "measured": base_recall,
                                        "ok": abs(base_recall - 0.6012) < 0.002},
        "maxgap_adaptive_k_reach_all": {"expected": 0.8740, "measured": reach_all,
                                        "n": len(reach_pids), "ok": abs(reach_all - 0.8740) < 0.002},
        "join_r0": {"expected": "288/326", "measured": f"{n_r0}/{len(carriers)}", "ok": n_r0 == 288},
        "join_v2": {"expected": "313/326", "measured": f"{n_v2}/{len(carriers)}", "ok": n_v2 == 313},
        "join_v3": {"expected": "314/326", "measured": f"{n_v3}/{len(carriers)}", "ok": n_v3 == 314},
        "components": {"expected": "1830/LCC 3162/iso 1426",
                       "measured": f"{ncomp}/LCC {int(comp_sizes[lcc])}/iso {int((comp_sizes == 1).sum())}",
                       "ok": ncomp == 1830 and int(comp_sizes[lcc]) == 3162 and int((comp_sizes == 1).sum()) == 1426},
    }
    pins_ok = all(v["ok"] for v in pins.values())
    log("PINS: " + json.dumps({k: (v["measured"], v["ok"]) for k, v in pins.items()}))
    if not pins_ok:
        summ = {"hypothesis": "R57-H644", "run_id": run_id, "ABORTED_PIN_MISMATCH": True,
                "sanity_pins": pins, "rows_artifact": str(rows_path)}
        summ_path.write_text(json.dumps(summ, indent=1, default=float))
        log(f"ABORT (pin mismatch) -> {summ_path}")
        return

    # ======================= HIT/MISS MARGINALS =============================
    # primary hit/miss: dense channel on the effective-v2 node (absent-no-join = miss)
    def is_dense_hit(row):
        return bool(row["dense"]["dense_hit"])
    hitrows = [r for r in rows if is_dense_hit(r)]
    missrows = [r for r in rows if not is_dense_hit(r)]

    def marg(rows_, get):
        vals = [get(r) for r in rows_]
        vals = [v for v in vals if v is not None]
        if not vals:
            return {"n": 0}
        if all(isinstance(v, bool) for v in vals):
            return {"n": len(vals), "true": sum(vals), "frac_true": round(sum(vals) / len(vals), 4)}
        arr = np.array(vals, dtype=float)
        return {"n": len(vals), "median": round(float(np.median(arr)), 3),
                "mean": round(float(arr.mean()), 3),
                "p25": round(float(np.percentile(arr, 25)), 3),
                "p75": round(float(np.percentile(arr, 75)), 3)}

    def pair(get):
        return {"miss": marg(missrows, get), "hit": marg(hitrows, get)}

    marginals = {
        "n_hit": len(hitrows), "n_miss": len(missrows),
        "dense_raw_rank_full": pair(lambda r: r["dense"]["raw_rank_full"]),
        "dense_smoothed_minus_raw": pair(lambda r: r["dense"]["smoothed_minus_raw"]),
        "traversal_component_size": pair(lambda r: r["traversal"]["component_size"]),
        "traversal_in_lcc": pair(lambda r: r["traversal"]["in_lcc"]),
        "traversal_hops_nearest_seed": pair(lambda r: r["traversal"]["hops_nearest_seed"]),
        "traversal_dist_to_region_boundary": pair(lambda r: r["traversal"]["dist_to_region_boundary"]),
        "traversal_on_path": pair(lambda r: r["traversal"]["on_path"]),
        "entity_degree": pair(lambda r: r["entity"]["degree"]),
        "entity_descr_length": pair(lambda r: r["entity"]["descr_length"]),
        "entity_descr_present": pair(lambda r: r["entity"]["descr_present"]),
        "entity_name_length": pair(lambda r: r["entity"]["name_length"]),
        "query_linked_anchor_count": pair(lambda r: r["query"]["linked_anchor_count"]),
        "query_hops_from_union": pair(lambda r: r["query"]["hops_from_union"]),
        "linker_in_pool": pair(lambda r: r["linker"].get("in_pool")),
        "linker_kept_by_maxgap": pair(lambda r: r["linker"].get("kept_by_maxgap")),
    }

    # ======================= H645 near-miss shelf ===========================
    # dense-missed carriers (with a node) at raw rank 17-64
    dmiss = [r for r in missrows if r["dense"]["raw_rank_full"] is not None]
    shelf = [r for r in dmiss if 16 <= r["dense"]["raw_rank_full"] <= 63]  # rank 17..64 (0-based 16..63)
    deep = [r for r in dmiss if r["dense"]["raw_rank_full"] >= 64]
    frac_shelf = round(len(shelf) / len(dmiss), 4) if dmiss else None
    h645_v = ("CONFIRMED" if frac_shelf is not None and frac_shelf >= 0.30
              else "KILLED" if frac_shelf is not None and frac_shelf < 0.15
              else "INDETERMINATE")
    h645 = {"verdict": h645_v, "frac_rank_17_64": frac_shelf,
            "n_dense_missed_with_node": len(dmiss),
            "n_shelf_17_64": len(shelf), "n_deep_ge64": len(deep),
            "bar": "CONFIRMED>=0.30, KILLED<0.15", "rank_convention": "1-based rank 17..64 = 0-based 16..63"}

    # ======================= H646 tie-loss census ===========================
    # anchor cases: (span, gold_target) where gold_target is in the span pool
    tie_loss = strictly = cut_adjacent = cut_deep = kept = 0
    case_rows = []
    for r in spanrecs:
        ns = r["norm_scores"]
        cut_k = r["cut_k"]
        for gt in r["gold_targets"]:
            gr = r["cand_idx"].index(gt)
            if gr < cut_k:
                kept += 1
                continue
            # gold is CUT. classify the loss
            top = r["blended"][0]
            gblend = r["blended"][gr]
            if abs(top - gblend) < 1e-9:
                tie_loss += 1
                cls = "exact_tie_loss"
            else:
                strictly += 1
                cls = "strictly_higher_outranked"
            if gr <= cut_k + 1:   # within +2 of cut (cut_k, cut_k+1)
                cut_adjacent += 1
                adj_cls = "cut_adjacent"
            else:
                cut_deep += 1
                adj_cls = "cut_deep"
            case_rows.append({"pid": r["pid"], "span": r["span"], "gold_idx": gt,
                              "gold_rank": gr, "cut_k": cut_k, "loss_class": cls,
                              "cut_proximity": adj_cls})
    # probe-level ceiling of a PERFECT tie-break: replay reachability resolving every
    # cut gold into the anchor set, recompute reset_region_union reach, count flips
    perfect_anchors = {pid: set(anchors_maxgap.get(pid, set())) for pid in off_ids}
    for cr in case_rows:
        perfect_anchors[cr["pid"]].add(cr["gold_idx"])
    reach_perfect = 0
    flipped = []
    base_reach_by_pid = {}
    for pid in reach_pids:
        cis = S["probe_has_carrier"][pid]
        base_ok = bool(cis) and all(t in reset_region[pid] for t in cis)
        base_reach_by_pid[pid] = base_ok
    for pid in reach_pids:
        anc = perfect_anchors.get(pid, set())
        ppr_seeds = list(anc) if anc else list(dense_seeds[pid])
        r = H.ppr(adj, out_deg, ppr_seeds, n)
        top15 = set(np.argsort(-r)[:PPR_TOP_N].tolist())
        reg = top15 | set(ppr_seeds) | dense_seeds[pid]
        cis = S["probe_has_carrier"][pid]
        ok = bool(cis) and all(t in reg for t in cis)
        reach_perfect += int(ok)
        if ok and not base_reach_by_pid[pid]:
            flipped.append(pid)
    h646 = {
        "n_anchor_cases_gold_in_pool": kept + tie_loss + strictly,
        "kept_by_maxgap": kept,
        "table_of_cut_gold": {"exact_tie_loss": tie_loss,
                              "strictly_higher_outranked": strictly,
                              "cut_adjacent_within+2": cut_adjacent, "cut_deep": cut_deep},
        "perfect_tiebreak_probe_ceiling": {
            "base_reach_num": sum(base_reach_by_pid.values()), "n_reach_pids": len(reach_pids),
            "perfect_reach_num": reach_perfect,
            "probes_flipped_to_reach": len(flipped), "flipped_pids": flipped,
            "note": ("replay: every cut gold added to the max-gap anchor set, reset_region_union "
                     "reachability recomputed; flips = probes newly all-carriers-reachable")},
        "cases_sample": case_rows[:25],
    }

    # ======================= H647 boundary proximity ========================
    # in-component missed carriers (best-arm reach miss, component shared w/ seeds/anchors)
    incomp_miss = []
    for r in rows:
        eff = r["eff_idx"]
        if eff is None:
            continue
        pid = r["probe"]
        if eff in reset_region[pid]:
            continue  # reached by best arm -> not a miss
        if r["traversal"]["component_status"] != "same-as-seeds":
            continue
        incomp_miss.append(r)
    b1 = [r for r in incomp_miss if r["traversal"]["dist_to_region_boundary"] == 1]
    frac_b1 = round(len(b1) / len(incomp_miss), 4) if incomp_miss else None
    onpath = sum(1 for r in incomp_miss if r["traversal"]["on_path"])
    h647_v = ("CONFIRMED" if frac_b1 is not None and frac_b1 >= 0.50
              else "KILLED" if frac_b1 is not None and frac_b1 < 0.25
              else "INDETERMINATE")
    # split by reasoning role (amendment 1: multi-hop failure is bridge-centric?)
    h647_by_role = {}
    for role in ("first-hop", "bridge", "terminal-answer"):
        sub = [r for r in incomp_miss if r["reasoning_role"] == role]
        if not sub:
            h647_by_role[role] = {"n": 0}
            continue
        sb1 = [r for r in sub if r["traversal"]["dist_to_region_boundary"] == 1]
        sop = sum(1 for r in sub if r["traversal"]["on_path"])
        h647_by_role[role] = {"n": len(sub), "n_boundary+1": len(sb1),
                              "frac_boundary+1": round(len(sb1) / len(sub), 4),
                              "on_path": sop, "off_path": len(sub) - sop}
    bdist_hist = Counter(r["traversal"]["dist_to_region_boundary"] for r in incomp_miss)
    h647 = {"verdict": h647_v, "n_in_component_missed": len(incomp_miss),
            "n_boundary_dist_1": len(b1), "frac_boundary+1": frac_b1,
            "boundary_dist_histogram": {str(k): v for k, v in sorted(bdist_hist.items(), key=lambda x: (x[0] is None, x[0]))},
            "on_path": onpath, "off_path": len(incomp_miss) - onpath,
            "by_reasoning_role": h647_by_role,
            "bar": "CONFIRMED>=0.50, KILLED<0.25",
            "region_reconciliation": (
                "'in-component missed' = carrier NOT in reset_region_union (the shipped best arm, "
                "PPR-top15 capped) yet its component is shared with a seed/anchor. Boundary distance "
                "is measured to the WIDER retrieved region seeds u 1-hop(seeds) u PPR-top15 (H644 axis "
                "def). A carrier at boundary-dist 0 is inside that 1-hop shell but outside the PPR-"
                "capped reset_region - so a full 1-hop expansion would already retrieve it; the loss "
                "is the PPR-top15 cap, not a missing walk hop"),
            "region_def": "seeds u 1-hop(seeds) u PPR-top15; boundary dist = BFS hops to nearest region node"}

    # ======================= H648 entity surfaceability =====================
    node_rows = [r for r in rows if r["eff_idx"] is not None]
    hit_n = [r for r in node_rows if r["dense"]["dense_hit"]]
    miss_n = [r for r in node_rows if not r["dense"]["dense_hit"]]
    auc_descr = rank_auc([r["entity"]["descr_length"] for r in hit_n],
                         [r["entity"]["descr_length"] for r in miss_n])
    auc_deg = rank_auc([r["entity"]["degree"] for r in hit_n],
                       [r["entity"]["degree"] for r in miss_n])
    best_auc = max([a for a in (auc_descr, auc_deg) if a is not None], default=None)
    h648_v = ("CONFIRMED" if best_auc is not None and best_auc >= 0.65
              else "KILLED" if (auc_descr is not None and auc_deg is not None
                                and auc_descr < 0.55 and auc_deg < 0.55)
              else "INDETERMINATE")
    h648 = {"verdict": h648_v, "auc_descr_length": auc_descr, "auc_degree": auc_deg,
            "direction": "AUC = P(hit_feature > miss_feature); >0.5 => hits richer/higher",
            "n_hit": len(hit_n), "n_miss": len(miss_n),
            "bar": "CONFIRMED>=0.65 either, KILLED<0.55 both"}

    # ======================= H649 query-insertion geometry ==================
    q_le2 = q_deep = q_disc = 0
    for r in missrows:
        hfu = r["query"]["hops_from_union"]
        if r["eff_idx"] is None or hfu is None:
            q_disc += 1
        elif hfu <= 2:
            q_le2 += 1
        else:
            q_deep += 1
    h649 = {"n_missed": len(missrows), "hops_from_union_le2": q_le2,
            "deeper_gt2": q_deep, "disconnected_or_absent": q_disc,
            "note": "union = max-gap anchors u dense@16 seeds; disconnected includes absent-no-join carriers"}

    # ======================= H650 partition =================================
    PRIORITY = ["absent-from-graph", "cross-component", "render-bucket",
                "tie-loss", "near-miss-shelf", "deep-dense-and-deep-walk", "other-with-note"]
    priority_rationale = (
        "Earlier class wins when a row matches several. Order = most-fundamental / "
        "upstream blocker first: (1) absent-from-graph - no node exists even after the "
        "mandatory v2 join, so nothing downstream can surface it (extraction defect); "
        "(2) cross-component - node exists but its component is disjoint from every seed "
        "and anchor component, an R52 structural wall no query-time walk crosses; "
        "(3) render-bucket - the carrier IS inside the reset_region_union node set "
        "(retrieval already succeeded) but the probe fails in the H620 render panel, so "
        "the loss is downstream of retrieval and its dense rank is moot; (4) tie-loss - "
        "the gold carrier sits in a span candidate pool but the max-gap linker cut picked "
        "a wrong entity, a named mechanism with a concrete pick-order fix; (5) near-miss-"
        "shelf - dense raw rank 17-64, the cheap rank-window lever; (6) deep-dense-and-"
        "deep-walk - dense rank>=64 AND not at region-boundary+1, genuinely deep on both "
        "channels; (7) other-with-note - residual, each carries a per-row note.")

    tie_case_by_pid_gold = {(cr["pid"], cr["gold_idx"]) for cr in case_rows}

    def matches(r, cls):
        """Independent membership test per class (amendment 2: overlap-aware)."""
        eff = r["eff_idx"]
        pid = r["probe"]
        if cls == "absent-from-graph":
            return eff is None
        if eff is None:
            return False
        if cls == "cross-component":
            return r["traversal"]["component_status"] == "cross"
        if cls == "render-bucket":
            return (eff in reset_region[pid] and
                    r["join_render"]["render_bucket"] in ("rendered_answer_absent", "retrieved_not_rendered"))
        if cls == "tie-loss":
            return (pid, eff) in tie_case_by_pid_gold
        draw = r["dense"]["raw_rank_full"]
        if cls == "near-miss-shelf":
            return draw is not None and 16 <= draw <= 63
        if cls == "deep-dense-and-deep-walk":
            bdist = r["traversal"]["dist_to_region_boundary"]
            return draw is not None and draw >= 64 and (bdist is None or bdist > 1)
        return False

    def classify(r):
        """Return (primary, secondaries, note). primary = first PRIORITY match."""
        hit_classes = [c for c in PRIORITY[:-1] if matches(r, c)]
        if not hit_classes:
            draw = r["dense"]["raw_rank_full"]
            note = (f"dense_rank={draw}, boundary_dist={r['traversal']['dist_to_region_boundary']}, "
                    f"in_region={r['eff_idx'] in reset_region[r['probe']] if r['eff_idx'] is not None else None}, "
                    f"comp={r['traversal']['component_status']}, in_pool={r['linker'].get('in_pool')}")
            return "other-with-note", [], note
        return hit_classes[0], hit_classes[1:], None

    # BEST-ARM per-carrier RETRIEVAL miss population: a carrier NOT delivered into the
    # reset_region_union best-arm region. Carriers the walk recovers (in the region) are
    # successes and excluded. Render is a PROBE-level downstream stage that needs the live
    # rru render path to attribute per-carrier, so it is NOT mixed here - it is reported as
    # a separate probe-level addendum (H620 rru_b10 residual, FREE from the recorded decomp).
    best_arm_miss_rows = []
    for r in rows:
        eff = r["eff_idx"]
        pid = r["probe"]
        reached = eff is not None and eff in reset_region[pid]
        if not reached:
            best_arm_miss_rows.append(r)

    partition = Counter()
    secondary_counts = Counter()      # class -> times it appears as a SECONDARY
    overlap_rows = 0                  # rows matching >1 class
    other_notes = []
    partition_by_half = {0: Counter(), 1: Counter()}
    probe_index = {pid: i for i, pid in enumerate(off_ids)}
    miss_assign = []
    for r in best_arm_miss_rows:
        cls, secondaries, note = classify(r)
        partition[cls] += 1
        for s in secondaries:
            secondary_counts[s] += 1
        if secondaries:
            overlap_rows += 1
        if cls == "other-with-note":
            other_notes.append({"probe": r["probe"], "carrier": r["carrier"], "note": note})
        half = probe_index[r["probe"]] % 2
        partition_by_half[half][cls] += 1
        miss_assign.append({"probe": r["probe"], "carrier": r["carrier"], "role": r["reasoning_role"],
                            "primary_class": cls, "secondary_classes": secondaries})
    unclassified = partition.get("__none__", 0)

    # split-half stability vs binomial (Wilson) bands on the pooled fraction
    n_miss = len(best_arm_miss_rows)
    n0 = sum(partition_by_half[0].values())
    n1 = sum(partition_by_half[1].values())
    stability = {}
    for cls in PRIORITY:
        k0, k1 = partition_by_half[0][cls], partition_by_half[1][cls]
        f0 = round(k0 / n0, 4) if n0 else None
        f1 = round(k1 / n1, 4) if n1 else None
        lo, hi = wilson(partition[cls], n_miss)
        agree = (f0 is not None and f1 is not None and
                 abs(f0 - f1) <= (hi - lo) if (lo is not None) else None)
        stability[cls] = {"pooled": partition[cls], "half0_frac": f0, "half1_frac": f1,
                          "pooled_wilson95": [lo, hi], "halves_within_band": bool(agree)}

    # role x primary-class cross-tab
    role_class = defaultdict(Counter)
    for a in miss_assign:
        role_class[a["role"]][a["primary_class"]] += 1

    # render-bucket class at PROBE granularity (best arm = rru_b10, the budget-1.0 DEF-fix):
    # probes the best arm still fails where retrieval succeeded but render dropped the answer
    rru_decomp = h620["flip_table"]["rru_b10"]["nonflip_failure_decomposition"]
    render_bucket_probe_level = {
        "best_arm": "rru_b10 (reset_region_union, render_budget=1.0)",
        "rendered_answer_absent_probes": rru_decomp.get("rendered_answer_absent", 0),
        "carrier_not_retrieved_probes": rru_decomp.get("carrier_not_retrieved", 0),
        "note": ("render-bucket is a probe-level downstream stage; per-carrier attribution needs "
                 "the live rru render path (not FREE). Reported here at probe grain from the H620 "
                 "rru_b10 recorded decomposition. The per-carrier partition above covers RETRIEVAL "
                 "misses only (carrier not in the reset_region_union region)."),
    }

    h650 = {
        "priority_order": PRIORITY, "priority_rationale": priority_rationale,
        "population": ("BEST-ARM per-carrier RETRIEVAL misses: carrier not delivered into the "
                       "reset_region_union region; carriers the walk recovers are successes and "
                       "excluded. render-bucket reported separately at probe grain (see addendum)."),
        "n_dense_misses_for_reference": len(missrows),
        "n_dense_misses_recovered_by_walk": sum(
            1 for r in rows if not r["dense"]["dense_hit"] and r["eff_idx"] is not None
            and r["traversal"]["in_reset_region_union"]),
        "render_bucket_probe_level_addendum": render_bucket_probe_level,
        "n_miss": n_miss, "partition": dict(partition), "unclassified": unclassified,
        "lands": unclassified == 0,
        "secondary_class_counts": dict(secondary_counts),
        "rows_matching_multiple_classes": overlap_rows,
        "overlap_note": ("RIA-2004 softening: crisp partition uses the documented priority order; "
                         "secondary_class_counts records every additional class a miss ALSO matches "
                         "(a row can be both near-miss-shelf and tie-loss, etc.)"),
        "role_x_primary_class": {k: dict(v) for k, v in role_class.items()},
        "other_notes": other_notes,
        "split_half_stability": stability,
        "split_half_note": "H540 bands: two half-fractions agree if |f0-f1| <= pooled Wilson-95 width",
    }

    # ---------------- bridge-role splits (amendment 1) ----------------------
    def role_breakdown(rowset):
        d = {}
        for role in ("first-hop", "bridge", "terminal-answer", "unknown"):
            sub = [r for r in rowset if r["reasoning_role"] == role]
            if not sub:
                continue
            d[role] = {
                "n": len(sub),
                "dense_hit_frac": round(sum(1 for r in sub if r["dense"]["dense_hit"]) / len(sub), 4),
                "in_pool_frac": marg(sub, lambda r: r["linker"].get("in_pool")),
            }
        return d
    bridge_role_splits = {
        "role_definitions": ("bridge = evidence pivot (obj of one triple, subj of a later); "
                             "first-hop = subject-only source; terminal-answer = object-only / "
                             "last supporting fact; provenance stamped per row (evidence vs "
                             "fallback_order)"),
        "role_counts_all_rows": dict(Counter(r["reasoning_role"] for r in rows)),
        "role_counts_miss": dict(Counter(r["reasoning_role"] for r in missrows)),
        "role_counts_hit": dict(Counter(r["reasoning_role"] for r in hitrows)),
        "dense_hit_rate_by_role": {
            role: round(sum(1 for r in rows if r["reasoning_role"] == role and r["dense"]["dense_hit"])
                        / max(1, sum(1 for r in rows if r["reasoning_role"] == role)), 4)
            for role in ("first-hop", "bridge", "terminal-answer", "unknown")
            if any(r["reasoning_role"] == role for r in rows)},
        "h647_boundary_by_role": h647["by_reasoning_role"],
        "miss_role_breakdown": role_breakdown(missrows),
    }

    # ---------------- summary payload ---------------------------------------
    summ = {
        "hypothesis": "R57-H644 + H645-H650", "run_id": run_id,
        "substrate": ("medium 2wiki (6,626 entities), frozen H582 cache tmp/results/r47 + "
                      "R50 H597 span cache; FREE numpy/scipy/rapidfuzz, no GPU/LLM/Neo4j/net"),
        "n_probes": len(off_ids), "n_carrier_rows": len(carriers),
        "sanity_pins": pins, "sanity_pins_ok": pins_ok,
        "null_reason_summary": dict(null_reasons),
        "hit_miss_marginals": marginals,
        "h645_near_miss_shelf": h645,
        "h646_tie_loss_census": h646,
        "h647_boundary_proximity": h647,
        "h648_entity_surfaceability": h648,
        "h649_query_insertion_geometry": h649,
        "h650_partition": h650,
        "bridge_role_splits": bridge_role_splits,
        "best_arm_definition": ("reset_region_union with max-gap scored linker anchors "
                                "(H623 detector:maxgap, lambda=0); reach_all reproduces 0.8740"),
        "rows_artifact": str(rows_path), "summary_artifact": str(summ_path),
        "script": "scripts/experiments/r57_h644_miss_atlas.py",
    }
    summ_path.write_text(json.dumps(summ, indent=1, default=float))

    # ---------------- console ----------------------------------------------
    log("\n==== R57 ATLAS SUMMARY ====")
    log(f"rows={len(rows)} hits={len(hitrows)} misses={len(missrows)}")
    log(f"H645 near-miss shelf: {h645_v} frac17-64={frac_shelf} "
        f"(shelf {len(shelf)}/deep {len(deep)} of {len(dmiss)})")
    log(f"H646 tie-loss: kept={kept} tie={tie_loss} strictly={strictly} "
        f"cut_adj={cut_adjacent} cut_deep={cut_deep} | perfect-tiebreak flips={len(flipped)}")
    log(f"H647 boundary: {h647_v} frac+1={frac_b1} ({len(b1)}/{len(incomp_miss)}) "
        f"on-path={onpath} off-path={len(incomp_miss)-onpath}")
    log(f"H648 surfaceability: {h648_v} AUC_descr={auc_descr} AUC_deg={auc_deg}")
    log(f"H649 query-geom: <=2 {q_le2} | >2 {q_deep} | disc/absent {q_disc} (of {len(missrows)})")
    log(f"H650 PARTITION (n_miss={n_miss}, unclassified={unclassified}):")
    for cls in PRIORITY:
        log(f"   {cls:>28}: {partition[cls]}")
    log(f"wrote {summ_path}")


if __name__ == "__main__":
    main()

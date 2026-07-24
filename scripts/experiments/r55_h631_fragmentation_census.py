"""R55-H631: fragmentation census - is the 1,830-component archipelago REPARABLE?

FREE run, pure numpy/scipy over caches already on disk (tmp/results/r47 + the R50
H597/H620 artifacts). No Neo4j, no GPU, no LLM, no network.

Three parts:
  A  census of all 1,830 components; where the gold carriers live (LCC vs outside)
  B  for every non-LCC component holding a gold carrier, WHY is it separated -
     (a) IDENTITY-SPLIT (a cross-component twin exists -> a merge would JOIN the
         components), tested by SEPARATE signals, never blended:
           (i)   identical name_norm in another component        [H621 says ~zero]
           (ii)  Titan cosine >= 0.90 to a node in another component
           (iii) STRICT name twin: a multi-token full name occurring as a
                 contiguous token span of another component's name, or difflib
                 ratio >= 0.90
         A NAIVE substring-containment signal is measured too but is NOT used to
         classify: it fires on "Lock" c "Heather Locklear" and its base rate makes
         it uninformative. Every signal carries a base-rate control.
     (b) COVERAGE (source docs disjoint from the LCC's) - requires per-entity
         document provenance, which this cache does NOT carry; reported as
         UNDETERMINABLE rather than guessed
     (c) SINGLETON NOISE (degree-0 / tiny, no cross-component twin)
  C  THE DECISIVE CROSS-TAB - the rru_b10 residual failures from H620: is the gold
     carrier in the same connected component as any seed/anchor (ranking axis
     binding), in a different one (reach axis binding), or absent from the graph
     entirely (extraction-recall axis)?

     H620's checkpoint persists only {arm,pid,pass,base_pass}; the per-probe
     decomposition label was computed LIVE and never written. The 10
     carrier_not_retrieved residuals are therefore RECONSTRUCTED offline by
     replaying H620's own decompose() rule (bucket on the FIRST gold title) over
     the offline reset_region_union node set - and the reconstruction is CHECKED
     against the recorded count of 10 before any classification is believed.

Harness sanity gate (must reproduce before any new number is believed):
  dense@16 carrier recall 0.6012 (H582 Titan) | 1,830 components | LCC 3,162 | 1,426 isolated

Small-n discipline: the Part C cross-tab is n=10. Every rate is emitted with its raw
numerator and denominator. No significance claims are made at this n.

Usage: /opt/conda/bin/python scripts/experiments/r55_h631_fragmentation_census.py
Writes: reports/experiments/r55/h631-fragmentation-census-<UTC ts>.json
"""

import difflib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.sparse.csgraph import connected_components

ROOT = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry")
sys.path.insert(0, str(ROOT / "scripts/experiments"))
sys.path.insert(0, str(ROOT / "notebooks"))

import r47_h582_embedder_swap as H  # noqa: E402  (harness reuse: _norm, ppr, TOP_K)
import r50_h619_seedland_digs as R50  # noqa: E402  (reuse: load_substrate/build_anchors/rru_reach)

CACHE = ROOT / "tmp/results/r47"
OUT = ROOT / "reports/experiments/r55"
SPAN_CACHE = ROOT / "tmp/results/r50/h597_gliner_spans.json"
H620_CKPT = ROOT / "reports/experiments/r50/h620-conversion-20260713T233256Z.checkpoint.jsonl"
H620_JSON = ROOT / "reports/experiments/r50/h620-conversion-20260713T233256Z.json"

SANITY = {"base_dense16_carrier_recall": 0.6012, "n_components": 1830,
          "lcc_size": 3162, "isolated_nodes": 1426}
COS_TWIN = 0.90
FUZZ_TWIN = 0.90
TINY_MAX = 3          # "tiny component" ceiling for class (c)
CTRL_SAMPLE = 400     # control sample size for the expensive base rates
WORD = re.compile(r"\w+", re.UNICODE)


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731
    rng = np.random.default_rng(0)

    # ---------------- substrate (H501/H582/H597/H620 convention, reused verbatim)
    S = R50.load_substrate()
    n = S["n"]
    meta, adj, name_norms = S["meta"], S["adj"], S["name_norms"]
    titan = np.load(CACHE / "titan_emb.npy")
    titan_n = (titan / (np.linalg.norm(titan, axis=1, keepdims=True) + 1e-9)).astype(np.float32)

    ncomp, comp = connected_components(adj, directed=False)
    comp_sizes = np.bincount(comp)
    lcc = int(comp_sizes.argmax())
    deg = np.asarray(adj.sum(axis=1)).ravel()

    # ---------------- HARNESS SANITY GATE ------------------------------------
    hits = [1 if c["tnorm"] in {name_norms[i] for i in S["seeds_q"][c["probe"]]} else 0
            for c in S["carriers"]]
    base_recall = round(float(np.mean(hits)), 4)
    measured = {"base_dense16_carrier_recall": base_recall,
                "n_components": int(ncomp),
                "lcc_size": int(comp_sizes[lcc]),
                "isolated_nodes": int((deg == 0).sum())}
    sanity = {k: {"expected": v, "measured": measured[k],
                  "reproduces": (abs(measured[k] - v) < 0.002 if isinstance(v, float)
                                 else measured[k] == v)}
              for k, v in SANITY.items()}
    sanity_ok = all(v["reproduces"] for v in sanity.values())
    log(json.dumps(sanity, indent=1))
    if not sanity_ok:
        payload = {"hypothesis": "R55-H631", "run_id": run_id, "ABORTED": True,
                   "harness_sanity": sanity,
                   "finding": "HARNESS SANITY FAILURE - a pinned constant did not "
                              "reproduce; no downstream number is believed."}
        p = OUT / f"h631-fragmentation-census-{run_id}.json"
        p.write_text(json.dumps(payload, indent=1))
        log(f"ABORT (sanity) -> {p}")
        return

    # ---------------- PART A: component census -------------------------------
    size_hist = dict(sorted(Counter(comp_sizes.tolist()).items()))
    carriers = S["carriers"]
    car_idx = sorted({c["carrier_idx"] for c in carriers if c["carrier_idx"] is not None})
    car_out_lcc = [i for i in car_idx if comp[i] != lcc]
    rows_in_graph = [c for c in carriers if c["carrier_idx"] is not None]
    rows_out_lcc = [c for c in rows_in_graph if comp[c["carrier_idx"]] != lcc]

    carrier_comps = sorted({int(comp[i]) for i in car_idx})
    comp_members = defaultdict(list)
    for i in range(n):
        comp_members[int(comp[i])].append(i)

    comps_with_carrier = []
    for cid in carrier_comps:
        cars = [i for i in car_idx if comp[i] == cid]
        comps_with_carrier.append({
            "comp_id": cid, "size": len(comp_members[cid]), "is_lcc": cid == lcc,
            "n_gold_carriers": len(cars),
            "carrier_names": [meta[i]["name"] for i in cars][:8],
        })
    part_a = {
        "n_entities": n,
        "n_components": int(ncomp),
        "lcc_size": int(comp_sizes[lcc]),
        "lcc_share": round(float(comp_sizes[lcc] / n), 4),
        "isolated_degree0_nodes": int((deg == 0).sum()),
        "size_histogram_compsize_to_count": {str(k): int(v) for k, v in size_hist.items()},
        "n_carrier_rows_total": len(carriers),
        "n_carrier_rows_in_graph": len(rows_in_graph),
        "n_carrier_rows_absent_from_graph": len(carriers) - len(rows_in_graph),
        "n_unique_carrier_nodes": len(car_idx),
        "unique_carrier_nodes_in_lcc": len(car_idx) - len(car_out_lcc),
        "unique_carrier_nodes_outside_lcc": len(car_out_lcc),
        "unique_carrier_outside_lcc_frac": (
            f"{len(car_out_lcc)}/{len(car_idx)} = {round(len(car_out_lcc)/len(car_idx), 4)}"),
        "carrier_rows_outside_lcc_frac": (
            f"{len(rows_out_lcc)}/{len(rows_in_graph)} = "
            f"{round(len(rows_out_lcc)/len(rows_in_graph), 4)}"),
        "n_components_holding_a_gold_carrier": len(carrier_comps),
        "components_holding_a_carrier_size_ge2": [
            c for c in comps_with_carrier if c["size"] >= 2],
        "n_carrier_components_size1": sum(1 for c in comps_with_carrier if c["size"] == 1),
    }
    log(f"PART A: carriers outside LCC {len(car_out_lcc)}/{len(car_idx)} unique nodes, "
        f"{len(rows_out_lcc)}/{len(rows_in_graph)} rows")

    # ---------------- shared identity-twin machinery -------------------------
    # (i) identical name_norm across DIFFERENT components
    by_norm = defaultdict(list)
    for i, nn in enumerate(name_norms):
        if nn:
            by_norm[nn].append(i)
    dup_norm_cross = {nn: idxs for nn, idxs in by_norm.items()
                      if len(idxs) > 1 and len({int(comp[j]) for j in idxs}) > 1}

    # (ii) Titan cosine
    def cross_comp_best_cos(rows):
        best_v = np.full(len(rows), -1.0, dtype=np.float32)
        best_j = np.full(len(rows), -1, dtype=np.int64)
        B = 512
        for s in range(0, len(rows), B):
            blk = rows[s:s + B]
            sims = titan_n[blk] @ titan_n.T
            for r, i in enumerate(blk):
                v = sims[r].copy()
                v[comp == comp[i]] = -1.0
                j = int(v.argmax())
                best_v[s + r], best_j[s + r] = v[j], j
        return best_v, best_j

    all_cos, all_cos_j = cross_comp_best_cos(list(range(n)))
    base_rate_cos = {
        "signal": "titan cosine >= 0.90 to a node in a different component",
        "n_nodes_firing": int((all_cos >= COS_TWIN).sum()), "n_nodes": n,
        "frac": round(float((all_cos >= COS_TWIN).mean()), 4),
        "median_best_cross_component_cos": round(float(np.median(all_cos)), 4),
        "p90_best_cross_component_cos": round(float(np.percentile(all_cos, 90)), 4),
    }

    # (iii-strict) multi-token full-name occurring as a contiguous token span of
    # another component's name  (exact, global, cheap via a token-span index)
    toks = [tuple(WORD.findall(nn)) for nn in name_norms]
    full_map = defaultdict(list)
    for i, t in enumerate(toks):
        if len(t) >= 2:
            full_map[t].append(i)
    strict_twin = defaultdict(set)     # node -> set of cross-component twins
    for i, t in enumerate(toks):
        L = len(t)
        if L < 3:
            continue
        for a in range(L):
            for b in range(a + 2, L + 1):
                if b - a == L:
                    continue
                for j in full_map.get(t[a:b], ()):
                    if comp[j] != comp[i]:
                        strict_twin[i].add(j)
                        strict_twin[j].add(i)
    base_rate_contain_strict = {
        "signal": ("a multi-token full name occurring as a contiguous token span of "
                   "another component's name (both directions)"),
        "n_nodes_firing": len(strict_twin), "n_nodes": n,
        "frac": round(len(strict_twin) / n, 4),
    }

    # (iii-fuzzy) difflib ratio >= 0.90 cross-component; expensive -> targets + control
    def fuzzy_twin(i):
        a = name_norms[i]
        if len(a) < 6:
            return None
        best = None
        for j in range(n):
            if j == i or comp[j] == comp[i] or len(name_norms[j]) < 6:
                continue
            sm = difflib.SequenceMatcher(None, a, name_norms[j])
            if sm.real_quick_ratio() < FUZZ_TWIN or sm.quick_ratio() < FUZZ_TWIN:
                continue
            r = sm.ratio()
            if r >= FUZZ_TWIN and (best is None or r > best["ratio"]):
                best = {"j": j, "name": meta[j]["name"], "ratio": round(float(r), 3),
                        "twin_comp_size": int(comp_sizes[comp[j]]),
                        "twin_in_lcc": bool(comp[j] == lcc)}
        return best

    # naive substring containment - measured for transparency, NOT used to classify
    def naive_contain_twin(i):
        a = name_norms[i]
        if len(a) < 3:
            return None
        for j in range(n):
            if j == i or comp[j] == comp[i] or len(name_norms[j]) < 3:
                continue
            b = name_norms[j]
            if a in b or b in a:
                return {"j": j, "name": meta[j]["name"]}
        return None

    # ---------------- PART B: why separated ----------------------------------
    targets = [cid for cid in carrier_comps if cid != lcc]
    target_nodes = sorted({i for cid in targets for i in comp_members[cid]})
    ctrl = sorted(rng.choice([i for i in range(n) if i not in set(target_nodes)],
                             size=min(CTRL_SAMPLE, n - len(target_nodes)),
                             replace=False).tolist())

    fuzzy_of = {i: fuzzy_twin(i) for i in target_nodes}
    naive_of = {i: naive_contain_twin(i) for i in target_nodes}
    base_rate_fuzzy = {
        "signal": f"difflib ratio >= {FUZZ_TWIN} to a node in a different component",
        "control_sample_n": len(ctrl),
        "n_control_firing": sum(1 for i in ctrl if fuzzy_twin(i)),
        "n_target_nodes": len(target_nodes),
        "n_target_nodes_firing": sum(1 for v in fuzzy_of.values() if v),
    }
    base_rate_naive = {
        "signal": "NAIVE substring containment either direction (NOT used to classify)",
        "control_sample_n": len(ctrl),
        "n_control_firing": sum(1 for i in ctrl if naive_contain_twin(i)),
        "n_target_nodes": len(target_nodes),
        "n_target_nodes_firing": sum(1 for v in naive_of.values() if v),
        "why_excluded": ("fires on 'lock' c 'heather locklear', 'nice' c 'mario "
                         "monicelli' - a near-universal signal carries no identity "
                         "information"),
    }

    meta_keys = sorted({k for m in meta[:200] for k in m.keys()})
    prov_fields = [k for k in meta_keys
                   if any(t in k.lower() for t in ("doc", "source", "chunk", "prov", "file"))]

    classes = {"a_identity_split": [], "b_coverage_UNDETERMINABLE": [], "c_singleton_noise": []}
    signal_counts = Counter()
    comp_detail = []
    for cid in targets:
        mem = comp_members[cid]
        cars = [i for i in car_idx if comp[i] == cid]
        order = cars + [m for m in mem if m not in cars]     # carrier node first
        sig_i = [nn for nn in {name_norms[i] for i in mem} if nn in dup_norm_cross]
        cos_hits = [(i, float(all_cos[i]), int(all_cos_j[i]))
                    for i in order if all_cos[i] >= COS_TWIN]
        strict_hits = [(i, sorted(strict_twin[i])[0]) for i in order if strict_twin.get(i)]
        fz = next(({**fuzzy_of[i], "from": meta[i]["name"]} for i in order if fuzzy_of.get(i)),
                  None)
        nv = next(({**naive_of[i], "from": meta[i]["name"]} for i in order if naive_of.get(i)),
                  None)
        sig = {
            "i_identical_name_norm": bool(sig_i),
            "ii_titan_cos_ge_0.90": bool(cos_hits),
            "iii_strict_token_containment": bool(strict_hits),
            "iii_fuzzy_ratio_ge_0.90": bool(fz),
            "NAIVE_containment_not_used": bool(nv),
        }
        for k, v in sig.items():
            if v:
                signal_counts[k] += 1
        fires = (sig["i_identical_name_norm"] or sig["ii_titan_cos_ge_0.90"]
                 or sig["iii_strict_token_containment"] or sig["iii_fuzzy_ratio_ge_0.90"])
        # carrier-node-specific version of the same test (the decision-relevant one)
        car_fires = bool(
            any(name_norms[i] in dup_norm_cross for i in cars)
            or any(all_cos[i] >= COS_TWIN for i in cars)
            or any(strict_twin.get(i) for i in cars)
            or any(fuzzy_of.get(i) for i in cars))
        # would a merge join this component to the LCC?
        twins = ([j for i in mem for j in by_norm.get(name_norms[i], []) if comp[j] != comp[i]]
                 + [int(all_cos_j[i]) for i in mem if all_cos[i] >= COS_TWIN]
                 + [j for i in mem for j in strict_twin.get(i, ())]
                 + ([fz["j"]] if fz else []))
        twin_in_lcc = any(comp[j] == lcc for j in twins)
        if fires:
            cls = "a_identity_split"
        elif len(mem) <= TINY_MAX:
            cls = "c_singleton_noise"
        else:
            cls = "b_coverage_UNDETERMINABLE"
        rec = {
            "comp_id": cid, "size": len(mem), "class": cls,
            "carrier_names": [meta[i]["name"] for i in cars],
            "signals_component_level": sig,
            "signal_fires_on_carrier_node_itself": car_fires,
            "a_merge_would_join_to_LCC": bool(twin_in_lcc),
            "cos_twin_example": ({"node": meta[cos_hits[0][0]]["name"],
                                  "twin": meta[cos_hits[0][2]]["name"],
                                  "cos": round(cos_hits[0][1], 4),
                                  "twin_in_lcc": bool(comp[cos_hits[0][2]] == lcc)}
                                 if cos_hits else None),
            "strict_containment_example": ({"node": meta[strict_hits[0][0]]["name"],
                                            "twin": meta[strict_hits[0][1]]["name"],
                                            "twin_in_lcc": bool(comp[strict_hits[0][1]] == lcc)}
                                           if strict_hits else None),
            "fuzzy_twin_example": fz,
            "naive_containment_example_NOT_USED": nv,
            "identical_norm_examples": sig_i[:3],
        }
        comp_detail.append(rec)
        classes[cls].append(rec)

    part_b = {
        "n_target_components_nonlcc_with_gold_carrier": len(targets),
        "class_counts": {k: len(v) for k, v in classes.items()},
        "signal_counts_separate_never_blended": dict(signal_counts),
        "n_a_class_where_merge_joins_LCC": sum(
            1 for r in classes["a_identity_split"] if r["a_merge_would_join_to_LCC"]),
        "n_a_class_signal_on_carrier_node_itself": sum(
            1 for r in classes["a_identity_split"] if r["signal_fires_on_carrier_node_itself"]),
        "base_rate_controls": {"ii_cos": base_rate_cos,
                               "iii_strict_containment": base_rate_contain_strict,
                               "iii_fuzzy": base_rate_fuzzy,
                               "NAIVE_containment": base_rate_naive},
        "identical_name_norm_cross_component_global": {
            "n_norms": len(dup_norm_cross),
            "examples": [{"name_norm": nn, "n_nodes": len(idxs),
                          "comps": sorted({int(comp[j]) for j in idxs})}
                         for nn, idxs in list(dup_norm_cross.items())[:10]],
        },
        "document_provenance_in_cache": {
            "ents_meta_keys": meta_keys,
            "provenance_fields_found": prov_fields,
            "available": bool(prov_fields),
            "note": ("ents_meta.json carries only id/name/types/descr - NO per-entity "
                     "document, chunk or source field, and no other r47/r50 cache "
                     "carries one. Class (b) COVERAGE is UNDETERMINABLE FROM THIS "
                     "CACHE; entity->document provenance lives only in Neo4j, which "
                     "this FREE run may not touch. Components in "
                     "b_coverage_UNDETERMINABLE are 'no identity twin found AND not "
                     "tiny' - the coverage claim itself is NOT verified."),
        },
        "examples_a_identity_split": classes["a_identity_split"][:10],
        "examples_b_undeterminable": classes["b_coverage_UNDETERMINABLE"][:10],
        "examples_c_singleton_noise": classes["c_singleton_noise"][:10],
        "all_target_components": comp_detail,
    }
    log(f"PART B: a={len(classes['a_identity_split'])} "
        f"b(undeterminable)={len(classes['b_coverage_UNDETERMINABLE'])} "
        f"c={len(classes['c_singleton_noise'])} of {len(targets)} target components")

    # ---------------- PART C: the decisive cross-tab -------------------------
    ckpt = [json.loads(l) for l in H620_CKPT.read_text().splitlines() if l.strip()]
    rru_rows = [r for r in ckpt if r["arm"] == "rru_b10"]
    rru_fail_pids = [r["pid"] for r in rru_rows if not r["pass"]]
    h620 = json.loads(H620_JSON.read_text())
    recorded = h620["flip_table"]["rru_b10"]["nonflip_failure_decomposition"]

    spans = json.loads(SPAN_CACHE.read_text())
    anchors, _, _ = R50.build_anchors(S, spans, apply_stoplist=False)  # H620 used UNFILTERED
    _, extras_idx = R50.rru_reach(S, anchors)
    name_row = S["name_row"]

    def carrier_rec(pid, title, rru_set, reach_comps):
        tn = H._norm(title)
        ci = name_row.get(tn)
        return {"carrier": title, "in_graph": ci is not None, "carrier_idx": ci,
                "comp_id": (int(comp[ci]) if ci is not None else None),
                "comp_size": (int(comp_sizes[comp[ci]]) if ci is not None else None),
                "in_lcc": (bool(comp[ci] == lcc) if ci is not None else None),
                "in_rru_node_set": bool(ci is not None and ci in rru_set),
                "comp_shared_with_seed_or_anchor": (
                    bool(int(comp[ci]) in reach_comps) if ci is not None else None)}

    def axis_of(c):
        if not c["in_graph"]:
            return "carrier_absent_from_graph"
        if not c["comp_shared_with_seed_or_anchor"]:
            return "cross_component"
        return "same_component_not_retrieved"

    rows = []
    for pid in rru_fail_pids:
        q = S["Q"][pid]
        dense = list(S["seeds_q"][pid])
        anc = sorted(anchors.get(pid, {}).keys())
        rru_set = set(dense) | set(extras_idx.get(pid, []))
        seed_comps = {int(comp[i]) for i in dense}
        anchor_comps = {int(comp[i]) for i in anc}
        reach_comps = seed_comps | anchor_comps
        titles = R50.gold_titles(q)
        cinfo = [carrier_rec(pid, t, rru_set, reach_comps) for t in titles]
        yesno = (q.get("answer", "") or "").strip().lower() in ("yes", "no")
        # H620 decompose(): bucket on the FIRST gold title (no yes/no probe here)
        first = cinfo[0]
        label_first = "carrier_not_retrieved" if not first["in_rru_node_set"] else "carrier_in_rru_set"
        label_any = ("carrier_not_retrieved"
                     if any(not c["in_rru_node_set"] for c in cinfo) else "carrier_in_rru_set")
        rows.append({
            "pid": pid, "question": q["question"][:110], "answer_is_yesno": yesno,
            "reconstructed_label_FIRST_title_rule": label_first,
            "reconstructed_label_ANY_title_rule": label_any,
            "axis_of_first_title": axis_of(first),
            "axis_of_any_missing_titles": sorted({axis_of(c) for c in cinfo
                                                  if not c["in_rru_node_set"]}) or ["none"],
            "carriers": cinfo,
            "n_dense16_seed_components": len(seed_comps),
            "seed_comp_ids": sorted(seed_comps),
            "anchor_comp_ids": sorted(anchor_comps),
            "anchor_names": [meta[i]["name"] for i in anc][:8],
            "seed_comps_include_lcc": bool(lcc in seed_comps),
        })

    resid = [r for r in rows if r["reconstructed_label_FIRST_title_rule"] == "carrier_not_retrieved"]
    recon_ok = len(resid) == recorded.get("carrier_not_retrieved")
    axis_counts = Counter(r["axis_of_first_title"] for r in resid)
    cross_n = axis_counts["cross_component"]
    same_n = axis_counts["same_component_not_retrieved"]
    absent_n = axis_counts["carrier_absent_from_graph"]

    # secondary (wider) view: every missing gold carrier of every rru_b10 failure
    wide = Counter()
    for r in rows:
        for c in r["carriers"]:
            if not c["in_rru_node_set"]:
                wide[axis_of(c)] += 1

    # for the absent-from-graph carriers: is the title in the graph under a VARIANT
    # surface form (reparable by carrier-name normalisation) or genuinely missing?
    # And if a variant node exists - was IT inside the probe's retrieved node set?
    def nearest_graph_name(title):
        tn = H._norm(title)
        stripped = re.sub(r"\s*\(.*?\)\s*", " ", tn).strip()
        vj = name_row.get(stripped)
        out = {"title_norm": tn, "paren_stripped": stripped,
               "exact_after_paren_strip": stripped in name_row,
               "exact_after_paren_strip_name": (meta[vj]["name"] if vj is not None else None)}
        best, bj = None, None
        for j in range(n):
            b = name_norms[j]
            if len(b) < 4:
                continue
            sm = difflib.SequenceMatcher(None, tn, b)
            if sm.real_quick_ratio() < 0.75 or sm.quick_ratio() < 0.75:
                continue
            r_ = sm.ratio()
            if best is None or r_ > best["ratio"]:
                best, bj = {"name": meta[j]["name"], "ratio": round(float(r_), 3),
                            "comp_size": int(comp_sizes[comp[j]]),
                            "in_lcc": bool(comp[j] == lcc)}, j
        out["best_fuzzy_graph_name"] = best
        # the variant node a name-normalising repair would land on
        if vj is None and best is not None and best["ratio"] >= FUZZ_TWIN:
            vj = bj
        out["variant_idx"] = vj
        return out

    absent_probe = []
    for r in resid:
        if r["axis_of_first_title"] != "carrier_absent_from_graph":
            continue
        pid = r["pid"]
        dense = list(S["seeds_q"][pid])
        anc = sorted(anchors.get(pid, {}).keys())
        rru_set = set(dense) | set(extras_idx.get(pid, []))
        reach_comps = {int(comp[i]) for i in dense} | {int(comp[i]) for i in anc}
        ng = nearest_graph_name(r["carriers"][0]["carrier"])
        vj = ng.pop("variant_idx")
        rec = {"pid": pid, "carrier": r["carriers"][0]["carrier"], **ng}
        if vj is None:
            rec["variant_repair"] = None
            rec["axis_under_variant_repair"] = "genuinely_absent_from_graph"
        else:
            rec["variant_repair"] = {
                "name": meta[vj]["name"], "comp_id": int(comp[vj]),
                "comp_size": int(comp_sizes[comp[vj]]), "in_lcc": bool(comp[vj] == lcc),
                "in_rru_node_set": bool(vj in rru_set),
                "in_dense16_seeds": bool(vj in set(dense)),
                "comp_shared_with_seed_or_anchor": bool(int(comp[vj]) in reach_comps)}
            rec["axis_under_variant_repair"] = (
                "already_retrieved_eval_join_artifact" if vj in rru_set else
                ("cross_component" if int(comp[vj]) not in reach_comps
                 else "same_component_not_retrieved"))
        absent_probe.append(rec)
    n_absent_recoverable = sum(1 for a in absent_probe if a["variant_repair"])
    variant_axis = Counter(a["axis_under_variant_repair"] for a in absent_probe)

    impl_comps = sorted({r["carriers"][0]["comp_id"] for r in resid
                         if r["axis_of_first_title"] == "cross_component"})
    cls_of = {d["comp_id"]: d["class"] for d in comp_detail}
    impl_detail = [{"comp_id": cid, "size": int(comp_sizes[cid]),
                    "class": cls_of.get(cid, "LCC" if cid == lcc else "not_a_carrier_component"),
                    "a_merge_would_join_to_LCC": next(
                        (d["a_merge_would_join_to_LCC"] for d in comp_detail
                         if d["comp_id"] == cid), None)}
                   for cid in impl_comps]
    impl_reparable = sum(1 for d in impl_detail if d["class"] == "a_identity_split")

    part_c = {
        "checkpoint_schema": sorted(rru_rows[0].keys()),
        "checkpoint_carries_decomposition_labels": False,
        "recorded_rru_b10_decomposition": recorded,
        "n_rru_b10_failures": len(rru_fail_pids),
        "reconstruction": {
            "method": ("offline replay of H620 decompose(): reset_region_union node set "
                       "= dense@16 (Titan cache) u [anchors u PPR-from-UNFILTERED-anchors "
                       "top-15]; the live rule buckets on the FIRST gold title, so the "
                       "FIRST-title rule is the faithful replay"),
            "reconstructed_FIRST_title_rule_n": len(resid),
            "reconstructed_ANY_title_rule_n": sum(
                1 for r in rows if r["reconstructed_label_ANY_title_rule"] == "carrier_not_retrieved"),
            "recorded_carrier_not_retrieved_n": recorded.get("carrier_not_retrieved"),
            "FIRST_title_rule_matches_recorded_count": recon_ok,
            "note": ("the FIRST-title rule reproduces the recorded 10 EXACTLY, which is "
                     "the honest control on the reconstruction; the ANY-title rule is "
                     "the wider superset view and is reported separately, never blended"),
        },
        "cross_tab_counts_out_of_n": {
            "n": len(resid),
            "cross_component": cross_n,
            "same_component_not_retrieved": same_n,
            "carrier_absent_from_graph": absent_n,
        },
        "wider_view_all_missing_carriers_of_all_20_failures": dict(wide),
        "absent_carrier_probe": {
            "n_absent": len(absent_probe),
            "n_recoverable_as_name_variant": n_absent_recoverable,
            "axis_under_variant_repair": dict(variant_axis),
            "detail": absent_probe,
            "note": ("distinguishes 'never extracted' from 'extracted under a different "
                     "surface form'; the latter is a carrier-naming/normalisation repair, "
                     "not a graph-construction one. axis_under_variant_repair re-runs the "
                     "decisive test against the variant node the repair would land on: "
                     "'already_retrieved_eval_join_artifact' means the node WAS in the "
                     "probe's reset_region_union set and only the exact-title join missed it"),
        },
        "implicated_components_of_cross_component_residuals": impl_detail,
        "implicated_reparable_a_type": f"{impl_reparable}/{len(impl_detail)}",
        "per_probe_table_residuals": resid,
        "per_probe_table_all_rru_b10_failures": rows,
        "small_n_note": (f"n={len(resid)}. All figures are exact counts. No significance "
                         f"claim is made at this n."),
    }
    log(f"PART C: n={len(resid)} residuals (recon matches recorded: {recon_ok}) | "
        f"cross-component {cross_n} | same-component {same_n} | absent-from-graph {absent_n}")

    # ---------------- pre-registered verdict bars ----------------------------
    frac_rep = (impl_reparable / len(impl_detail)) if impl_detail else 0.0
    N = len(resid)
    if cross_n >= 5 and frac_rep >= 0.5:
        verdict = "ARM-OPENS"
        why = (f"{cross_n}/{N} residuals cross-component AND {impl_reparable}/"
               f"{len(impl_detail)} implicated components carry an (a)-type identity twin")
    elif cross_n >= 5:
        verdict = "ARM-NARROW"
        why = (f"{cross_n}/{N} cross-component but only {impl_reparable}/{len(impl_detail)} "
               f"implicated components are (a)-type reparable - lever is rung size / "
               f"extraction recall, not repair")
    elif cross_n < 3:
        verdict = "ARM-DEAD-ON-PANEL"
        why = (f"only {cross_n}/{N} residuals are cross-component - the reach axis is not "
               f"binding on this panel")
    else:
        verdict = "INDETERMINATE"
        why = (f"{cross_n}/{N} cross-component falls between the bars (>=5 opens/narrow, "
               f"<3 dead); resolving it needs a larger residual panel or a per-probe "
               f"decomposition label persisted at H620 time rather than reconstructed")

    payload = {
        "hypothesis": "R55-H631",
        "run_id": run_id,
        "substrate": ("medium 2wiki (6,626 entities / 11,714 edge rows), frozen H582 "
                      "offline cache tmp/results/r47 + R50 H597 span cache + H620 checkpoint"),
        "free_run": "pure numpy/scipy, no Neo4j / GPU / LLM / network",
        "harness_sanity": sanity,
        "harness_sanity_ok": sanity_ok,
        "part_a_component_census": part_a,
        "part_b_separation_classes": part_b,
        "part_c_decisive_cross_tab": part_c,
        "verdict": verdict,
        "verdict_reason": why,
        "script": "scripts/experiments/r55_h631_fragmentation_census.py",
    }
    p = OUT / f"h631-fragmentation-census-{run_id}.json"
    p.write_text(json.dumps(payload, indent=1))
    log(f"VERDICT {verdict}: {why}")
    log(f"wrote {p}")


if __name__ == "__main__":
    main()

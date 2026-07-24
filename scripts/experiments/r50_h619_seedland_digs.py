"""R40x continuation (H619 + H620 + H621): cashing the seed-landing lever end-to-end.

Serves three registered hypotheses off the just-confirmed H597 reset_region_union
machinery (script r50_h597_anchor_link.py, artifact
reports/experiments/r50/h597-anchor-link-20260713T230634Z.json, span cache
tmp/results/r50/h597_gliner_spans.json). Baselines: reset_region_union all-golds
reachability 0.8661 / bridge 0.8511 / recall 0.6012 / oracle 0.898.

Subcommands (argv[1]):
  h619   deterministic role-word stop-list; filter anchor spans; re-run
         reset_region_union offline; before/after reachability + off-gold census.
         FAST offline replay over the h597 span cache + r47 adjacency (<2 min).
  h620   THE MONEY QUESTION - re-run the 132 OFF-arm probes with reset_region_union
         seeding injected into the LIVE probe path, deterministic h499 flip
         criterion, two render_budget arms (0.6 shipped, 1.0 DEF-fix). Detached.
  h621   collision census on medium + scout (bolt://172.19.0.8) + 6,118-doc
         forecast + tie-break vs gold. FAST (scout entity pull is read-only).

Neo4j STRICTLY read-only (MATCH/RETURN); h620 uses the live probe path whose PPR is
DISABLED in the shipped config (ppr_enabled=False) - GDS is never invoked. The
reset_region_union node set is injected by monkeypatching graphrag.overfetch_seeds
to APPEND the offline-computed reachable nodes (anchors + scipy-PPR-from-anchors)
below the dense seeds; no graph writes.

Usage: python scripts/experiments/r50_h619_seedland_digs.py {h619|h620|h621}
"""

import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix

sys.path.insert(0, "scripts/experiments")
sys.path.insert(0, "notebooks")
import r47_h582_embedder_swap as H  # noqa: E402  (harness reuse: _norm, ppr, mcnemar, arm_metrics)

ROOT = H.ROOT
CACHE = H.CACHE                      # tmp/results/r47
R50 = ROOT / "tmp/results/r50"
OUT = ROOT / "reports/experiments/r50"
SPAN_CACHE = R50 / "h597_gliner_spans.json"
TOP_K = H.TOP_K                      # 16
PPR_TOP_N = H.PPR_TOP_N              # 15
TITAN_TARGET = 0.6012
ISO_REACH_REF = 0.622
ORACLE_SEED_REACH = 0.898
RRU_REACH_REF = 0.8661               # H597 reset_region_union all-golds
RRU_BRIDGE_REF = 0.8511
OFFGOLD_BASE = 125                   # H597 census: 86 exact + 39 alias off-gold picks

# --- deterministic role/relation stop-list lexicon --------------------------
# Built from (a) the 2wiki off-probe evidence relation vocabulary (director 83,
# date of birth 70, father 24, place of birth 21, country of citizenship 18,
# spouse 14, place of death 10, performer 9, country 8, mother 7, composer 7,
# child 4, employer 2, sibling 2, cause of death 1, place of detention 1,
# founded by 1, publisher 1, educated at 2, inception 3, publication date 12,
# country of origin 6) and (b) the H597 wrong-pick census (Director x46,
# Composer, Mother, Place of birth). Single-word role NOUNS + the multi-word
# relation PHRASES; these are relation words a query never anchors ON, only
# ASKS BY - so exact-matching them to a same-named generic hub entity is a
# pure distractor seed.
ROLE_STOP = {
    # single-word role nouns (+ plurals)
    "director", "directors", "composer", "composers", "performer", "performers",
    "father", "fathers", "mother", "mothers", "spouse", "spouses",
    "child", "children", "sibling", "siblings", "publisher", "publishers",
    "employer", "employers", "founder", "founders", "producer", "producers",
    "writer", "writers", "author", "authors", "husband", "wife",
    "son", "daughter", "parent", "parents",
    # multi-word relation phrases (census + template)
    "date of birth", "date of death", "place of birth", "place of death",
    "cause of death", "country of citizenship", "country of origin",
    "place of detention", "publication date", "country", "inception",
    "educated at", "founded by", "citizenship", "nationality",
}


def region(r, seeds):
    return set(np.argsort(-r)[:PPR_TOP_N].tolist()) | set(seeds)


def frac(num, den):
    return round(num / den, 4) if den else None


def gold_titles(q):
    sf = q.get("supporting_facts") or []
    ts = []
    for it in sf:
        t = it[0] if isinstance(it, (list, tuple)) else it.get("title")
        if t and t not in ts:
            ts.append(t)
    return ts


# ============================================================================
#  shared medium substrate (H582/H583/H597 harness)
# ============================================================================
def load_substrate():
    meta = json.loads((CACHE / "ents_meta.json").read_text())
    titan = np.load(CACHE / "titan_emb.npy")
    edges = json.loads((CACHE / "edges.json").read_text())
    n = len(meta)
    idx_of_id = {m["id"]: i for i, m in enumerate(meta)}
    name_norms = [H._norm(m["name"]) if m["name"] else "" for m in meta]
    graph_norms = set(name_norms)
    name_row = {}
    for i, nn in enumerate(name_norms):
        name_row.setdefault(nn, i)

    ij = np.array([[idx_of_id[a], idx_of_id[b]] for a, b in edges
                   if a in idx_of_id and b in idx_of_id])
    adj = csr_matrix((np.ones(len(ij)), (ij[:, 0], ij[:, 1])), shape=(n, n))
    adj = ((adj + adj.T) > 0).astype(float).tocsr()
    out_deg = np.asarray(adj.sum(axis=1)).ravel()
    out_deg[out_deg == 0] = 1.0

    off_ids = [json.loads(l)["id"] for l in H.SCREEN.read_text().splitlines()
               if l.strip() and json.loads(l)["arm"] == "off"]
    off_pass = {json.loads(l)["id"]: json.loads(l)["pass"]
                for l in H.SCREEN.read_text().splitlines()
                if l.strip() and json.loads(l)["arm"] == "off"}
    Q = {q.get("_id"): q for q in json.loads(H.QUESTIONS.read_text())}
    probes = [Q[i] for i in off_ids if i in Q]

    carriers = []
    for pid in off_ids:
        q = Q.get(pid)
        if not q:
            continue
        for t in gold_titles(q):
            tn = H._norm(t)
            carriers.append({"probe": pid, "carrier": t, "tnorm": tn,
                             "in_graph": tn in graph_norms, "carrier_idx": name_row.get(tn)})

    # offline dense@16 seeds (Titan cache) - identical to H597
    d = np.load(CACHE / "titan_probe_emb.npz", allow_pickle=True)
    titan_probe = {pid: d[pid] for pid in off_ids}
    titan_n = titan / (np.linalg.norm(titan, axis=1, keepdims=True) + 1e-9)
    titan_probe_n = {pid: v / (np.linalg.norm(v) + 1e-9) for pid, v in titan_probe.items()}
    seeds_q = {}
    for pid in off_ids:
        sims = titan_n @ titan_probe_n[pid]
        seeds_q[pid] = [int(x) for x in np.argsort(-sims)[:TOP_K]]

    # gold source / bridge / all-gold idxs per probe (H583 convention)
    src_of, bridge_of, gold_idx_of = {}, {}, {}
    for q in probes:
        pid = q["_id"]
        evs = q.get("evidences") or []
        subs = {H._norm(s_) for (s_, r_, o_) in evs}
        objs = {H._norm(o_) for (s_, r_, o_) in evs}
        srcs, brs, golds = [], [], []
        for t in gold_titles(q):
            tn = H._norm(t)
            ci = name_row.get(tn)
            if ci is None:
                continue
            golds.append(ci)
            if tn in objs:
                brs.append(ci)
            else:
                srcs.append(ci)
        src_of[pid], bridge_of[pid], gold_idx_of[pid] = srcs, brs, golds

    probe_has_carrier = {pid: [c["carrier_idx"] for c in carriers
                               if c["probe"] == pid and c["in_graph"]] for pid in off_ids}
    reach_pids = [pid for pid in off_ids if probe_has_carrier[pid]]

    return dict(meta=meta, n=n, name_norms=name_norms, name_row=name_row,
                graph_norms=graph_norms, adj=adj, out_deg=out_deg,
                off_ids=off_ids, off_pass=off_pass, Q=Q, carriers=carriers,
                seeds_q=seeds_q, src_of=src_of, bridge_of=bridge_of,
                gold_idx_of=gold_idx_of, probe_has_carrier=probe_has_carrier,
                reach_pids=reach_pids, titan_n=titan_n, titan_probe_n=titan_probe_n)


# ------- H597 linker (exact + alias), with optional span stop-list filter -----
def build_anchors(S, spans_by_pid, apply_stoplist):
    meta, name_row, name_norms, n = S["meta"], S["name_row"], S["name_norms"], S["n"]
    name_len = [len(s) for s in name_norms]
    nonempty_idx = [i for i in range(n) if name_len[i] >= 3]

    def alias_link(span_norm):
        if len(span_norm) < 3:
            return None
        cands = [i for i in nonempty_idx
                 if span_norm in name_norms[i] or name_norms[i] in span_norm]
        if not cands:
            return None
        return min(cands, key=lambda i: (abs(name_len[i] - len(span_norm)), i))

    anchors = {}          # pid -> {idx: prov}
    filtered_spans = {}   # pid -> [span_norm dropped]
    kept_spans = {}
    for pid in S["off_ids"]:
        sp = spans_by_pid.get(pid, [])
        snorms = [H._norm(s[0]) for s in sp]
        dropped, kept = [], []
        for sn in snorms:
            if apply_stoplist and sn in ROLE_STOP:
                dropped.append(sn)
            else:
                kept.append(sn)
        filtered_spans[pid] = dropped
        kept_spans[pid] = kept
        ex, al = {}, {}
        for sn in kept:
            if sn in name_row:
                ex[name_row[sn]] = "exact"
        for sn in kept:
            if sn in name_row:
                continue
            idx = alias_link(sn)
            if idx is not None and idx not in ex:
                al[idx] = "alias"
        prov = dict(ex)
        for idx in al:
            prov.setdefault(idx, "alias")
        anchors[pid] = prov
    return anchors, filtered_spans, kept_spans


# ------- reset_region_union reachability (H597 run_variant verbatim) ----------
def rru_reach(S, anchors):
    """Return per-probe {all,bridge,has_bridge} and per-probe extra idxs (region
    nodes beyond dense@16) for the reset_region_union fusion."""
    adj, out_deg, n = S["adj"], S["out_deg"], S["n"]
    reach = {}
    extras = {}
    for pid in S["reach_pids"] + [p for p in S["off_ids"] if p not in S["reach_pids"]]:
        la = list(anchors.get(pid, {}).keys())
        dense = list(S["seeds_q"][pid])
        ppr_seeds = la if la else dense
        r = H.ppr(adj, out_deg, ppr_seeds, n)
        reg = region(r, ppr_seeds) | set(dense)
        extras[pid] = sorted(reg - set(dense))
        cis = S["probe_has_carrier"].get(pid, [])
        if not cis:
            continue
        brs = [b for b in S["bridge_of"][pid] if b is not None]
        reach[pid] = {
            "all": bool(cis) and all(t in reg for t in cis),
            "has_bridge": len(brs) > 0,
            "bridge": (all(t in reg for t in brs) if brs else None),
        }
    return reach, extras


def reach_rate(S, reach, key="all", subset_bridge=False):
    pids = [p for p in S["reach_pids"] if (not subset_bridge or reach[p]["has_bridge"])]
    vals = [reach[p][key] for p in pids if reach[p][key] is not None]
    return frac(sum(vals), len(vals)), len(vals)


def offgold_count(S, anchors):
    """Count off-gold wrong-picks across all linked anchors (H597 census defn)."""
    cnt = Counter()
    examples = []
    for pid in S["off_ids"]:
        golds = set(S["gold_idx_of"].get(pid, []))
        for idx, pv in anchors.get(pid, {}).items():
            if idx in golds:
                cnt["gold"] += 1
            else:
                cnt["off_gold"] += 1
                if len(examples) < 25:
                    examples.append({"probe": pid, "name": S["meta"][idx]["name"]})
    return cnt, examples


# ============================================================================
#  H619
# ============================================================================
def run_h619():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    S = load_substrate()
    spans = json.loads(SPAN_CACHE.read_text())

    anc_unf, _, _ = build_anchors(S, spans, apply_stoplist=False)
    anc_flt, dropped, kept = build_anchors(S, spans, apply_stoplist=True)

    reach_unf, _ = rru_reach(S, anc_unf)
    reach_flt, _ = rru_reach(S, anc_flt)

    unf_all, unf_n = reach_rate(S, reach_unf)
    flt_all, flt_n = reach_rate(S, reach_flt)
    unf_br, _ = reach_rate(S, reach_unf, "bridge", True)
    flt_br, _ = reach_rate(S, reach_flt, "bridge", True)

    og_unf, _ = offgold_count(S, anc_unf)
    og_flt, og_flt_ex = offgold_count(S, anc_flt)

    # paired regression: probes reachable unfiltered but NOT filtered -> which
    # dropped role-word was load-bearing
    load_bearing = []
    for pid in S["reach_pids"]:
        if reach_unf[pid]["all"] and not reach_flt[pid]["all"]:
            load_bearing.append({"probe": pid, "dropped_spans": dropped.get(pid, []),
                                 "question": S["Q"][pid]["question"][:90]})
    gained = [pid for pid in S["reach_pids"]
              if reach_flt[pid]["all"] and not reach_unf[pid]["all"]]

    # harness sanity: unfiltered must reproduce H597 reset_region_union 0.8661
    harness_ok = abs(unf_all - RRU_REACH_REF) <= 0.005
    n_dropped_spans = sum(len(v) for v in dropped.values())
    dropped_hist = Counter(s for v in dropped.values() for s in v)

    reach_ok = flt_all >= 0.88
    offgold_ok = og_flt["off_gold"] < 40
    no_regress = len(load_bearing) == 0
    confirmed = reach_ok and no_regress and offgold_ok
    killed = flt_all < unf_all - 0.005  # filtering LOSES reachability
    verdict = ("CONFIRMED" if confirmed else
               ("KILLED" if killed else "INDETERMINATE"))

    clauses = [
        {"clause": "filtered reset_region_union all-golds reachability >= 0.88",
         "predicted": ">= 0.88",
         "measured": f"{flt_all} (unfiltered {unf_all}, delta {round((flt_all-unf_all)*100,2)}pp)",
         "holds": bool(reach_ok)},
        {"clause": "off-gold picks < 40 (from 125 unfiltered)",
         "predicted": "< 40",
         "measured": f"{og_flt['off_gold']} (unfiltered {og_unf['off_gold']})",
         "holds": bool(offgold_ok)},
        {"clause": "zero paired reachability regressions (no load-bearing role-word)",
         "predicted": 0, "measured": len(load_bearing),
         "holds": bool(no_regress)},
        {"clause": "KILL: filtering loses reachability vs unfiltered",
         "predicted": "kill if filtered < unfiltered",
         "measured": f"filtered {flt_all} vs unfiltered {unf_all}",
         "holds": bool(killed)},
    ]

    result = {
        "run_id": run_id, "hypothesis": "R40x-H619",
        "harness_sanity": {"unfiltered_rru_reach_all": unf_all, "h597_ref": RRU_REACH_REF,
                           "reproduced": bool(harness_ok), "n_reach_probes": unf_n},
        "stoplist_lexicon": sorted(ROLE_STOP),
        "lexicon_provenance": "2wiki off-probe evidence relation vocabulary + H597 wrong-pick census",
        "n_spans_dropped": n_dropped_spans,
        "dropped_span_histogram": dict(dropped_hist.most_common()),
        "reachability": {
            "unfiltered": {"all": unf_all, "bridge": unf_br, "n": unf_n},
            "filtered": {"all": flt_all, "bridge": flt_br, "n": flt_n},
            "delta_all_pp": round((flt_all - unf_all) * 100, 2),
            "delta_bridge_pp": round((flt_br - unf_br) * 100, 2) if (flt_br and unf_br) else None,
            "gap_to_oracle_pp": round((ORACLE_SEED_REACH - flt_all) * 100, 2),
        },
        "offgold_census": {
            "unfiltered": dict(og_unf), "filtered": dict(og_flt),
            "offgold_reduction_pct": round((1 - og_flt["off_gold"] / max(og_unf["off_gold"], 1)) * 100, 1),
            "filtered_offgold_examples": og_flt_ex,
        },
        "load_bearing_role_words": load_bearing,
        "probes_gained_by_filter": gained,
        "clauses": clauses,
        "proposed_verdict": verdict,
        "artifact": None, "script": "scripts/experiments/r50_h619_seedland_digs.py",
    }
    path = OUT / f"h619-stoplist-{run_id}.json"
    result["artifact"] = str(path)
    path.write_text(json.dumps(result, indent=1))
    print("H619 VERDICT " + json.dumps({"verdict": verdict, "filtered_reach": flt_all,
                                        "unfiltered_reach": unf_all,
                                        "offgold": f"{og_flt['off_gold']} (from {og_unf['off_gold']})",
                                        "load_bearing": len(load_bearing),
                                        "harness_ok": harness_ok}), flush=True)
    print(f"WROTE {path}", flush=True)
    return result


# ============================================================================
#  H620 - live probe-path conversion, dual render-budget arms
# ============================================================================
def _resolve_answer_node(q):
    evs = q.get("evidences") or []
    return evs[-1][2] if evs else None


def run_h620(use_filtered=None):
    from r46_h499_screen import score  # deterministic h499 flip criterion
    from h158_measure import _norm as h_norm, _present
    from knowledge_graph_foundry import load_settings
    from knowledge_graph_foundry.pipeline import Foundry
    import knowledge_graph_foundry.graph.graphrag as GR

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731

    S = load_substrate()
    spans = json.loads(SPAN_CACHE.read_text())

    # H619 decides filtered vs unfiltered anchors
    h619 = run_h619()
    if use_filtered is None:
        use_filtered = (h619["proposed_verdict"] == "CONFIRMED")
    anchors, _, _ = build_anchors(S, spans, apply_stoplist=use_filtered)
    _, extras_idx = rru_reach(S, anchors)
    log(f"H620 {run_id}: anchors={'FILTERED' if use_filtered else 'UNFILTERED'} "
        f"(H619 {h619['proposed_verdict']})")

    # entity dicts for the extras (name/types/description from cache; render
    # fetches props/relations/aliases LIVE by id)
    meta = S["meta"]
    def extra_nodes(pid):
        out = []
        for idx in extras_idx.get(pid, []):
            m = meta[idx]
            out.append({"id": m["id"], "name": m["name"],
                        "types": [t for t in (m["types"] or []) if t != "Entity"] or m["types"] or [],
                        "description": m["descr"] or ""})
        return out

    # ---- monkeypatch overfetch_seeds: append extras below dense seeds --------
    _orig_overfetch = GR.overfetch_seeds
    STATE = {"extras": []}

    def patched_overfetch(query_fn, top_k, factor):
        seeds = _orig_overfetch(query_fn, top_k, factor)   # live dense@16
        ex = STATE["extras"]
        if not ex:
            return seeds
        dense_ids = {s["id"] for s in seeds}
        min_dense = min((s.get("score", 0.0) for s in seeds), default=0.0)
        add = []
        for k, e in enumerate(ex):
            if e["id"] in dense_ids:
                continue
            node = dict(e)
            node["score"] = min_dense - 1e-4 * (k + 1)  # strictly below dense, ordered
            add.append(node)
        return seeds + add
    GR.overfetch_seeds = patched_overfetch

    ckpt = OUT / f"h620-conversion-{run_id}.checkpoint.jsonl"

    def probe_arm(f, q, budget, inject):
        f.settings.graphrag.render_budget = budget
        STATE["extras"] = extra_nodes(q["_id"]) if inject else []
        res = f.probe(q["question"])
        STATE["extras"] = []
        sc = score(q, res)
        ctx = h_norm(" ".join(res["context_lines"]))
        return sc["pass"], res, ctx

    def decompose(q, res, ctx):
        """carrier_not_retrieved | retrieved_not_rendered | rendered_answer_absent"""
        ans = q.get("answer", "")
        yesno = (ans or "").strip().lower() in ("yes", "no")
        supporting = {h_norm(x) for x in res["supporting_names"]}
        ctx_blocks_lc = " ".join(res["context_lines"]).lower()
        # decomposition unit = gold supporting titles (carriers) not yet covered
        missing = []
        for t in gold_titles(q):
            tn = h_norm(t)
            title_in_ctx = _present(t, ctx)
            if yesno and title_in_ctx:
                continue
            in_set = tn in supporting
            block_rendered = f"## {t} (".lower() in ctx_blocks_lc
            missing.append({"carrier": t, "in_node_set": in_set,
                            "block_rendered": block_rendered})
        # bucket by the dominant failure of the first uncovered carrier
        if not missing:
            return "no_missing_carrier"
        m = missing[0]
        if not m["in_node_set"]:
            return "carrier_not_retrieved"
        if not m["block_rendered"]:
            return "retrieved_not_rendered"
        return "rendered_answer_absent"

    st = load_settings(H.CONFIG)
    st.event_log = None
    st.questions.enabled = False  # OFF arm (85/47 baseline)

    off_ids = S["off_ids"]
    base_pass = {pid: S["off_pass"][pid] for pid in off_ids}
    fails = [pid for pid in off_ids if not base_pass[pid]]
    passes = [pid for pid in off_ids if base_pass[pid]]
    log(f"H620 baseline: {len(passes)} pass / {len(fails)} fail (target 85/47)")

    arms = [("base_b06", 0.6, False), ("base_b10", 1.0, False),
            ("rru_b06", 0.6, True), ("rru_b10", 1.0, True)]
    results = {a[0]: {} for a in arms}
    decomp = {a[0]: {} for a in arms}

    try:
        with Foundry(st) as f, ckpt.open("w") as ck:
            for arm, budget, inject in arms:
                np_pass = 0
                for k, pid in enumerate(off_ids):
                    q = S["Q"][pid]
                    p, res, ctx = probe_arm(f, q, budget, inject)
                    results[arm][pid] = bool(p)
                    if not p:
                        decomp[arm][pid] = decompose(q, res, ctx)
                    np_pass += int(bool(p))
                    ck.write(json.dumps({"arm": arm, "pid": pid, "pass": bool(p),
                                         "base_pass": base_pass[pid]}) + "\n")
                    ck.flush()
                    if (k + 1) % 44 == 0:
                        log(f"  {arm} [{k+1}/{len(off_ids)}] pass_so_far={np_pass}")
                log(f"ARM {arm}: {np_pass}/{len(off_ids)} pass "
                    f"(budget={budget} inject={inject})")
    finally:
        GR.overfetch_seeds = _orig_overfetch

    # ---- harness sanity: base_b06 must reproduce 85/47 ----------------------
    def arm_pass_n(arm):
        return sum(results[arm].values())
    base06_n = arm_pass_n("base_b06")
    base10_n = arm_pass_n("base_b10")
    # which base reproduces the 85/47 screen exactly on the pass SET
    base06_match = sum(1 for pid in off_ids if results["base_b06"][pid] == base_pass[pid])
    base10_match = sum(1 for pid in off_ids if results["base_b10"][pid] == base_pass[pid])
    harness_ok = base06_match == len(off_ids)  # base@0.6 == shipped screen
    validated_base = "base_b06" if harness_ok else (
        "base_b10" if base10_match == len(off_ids) else "NONE")

    # ---- flip table (vs the 85/47 screen baseline) --------------------------
    def flips_and_regr(arm):
        flips = [pid for pid in fails if results[arm][pid]]        # fail->pass
        regr = [pid for pid in passes if not results[arm][pid]]     # pass->fail
        return flips, regr

    flip_table = {}
    for arm in ("base_b06", "base_b10", "rru_b06", "rru_b10"):
        fl, rg = flips_and_regr(arm)
        db = Counter(decomp[arm].get(pid, "?") for pid in fails if not results[arm][pid])
        flip_table[arm] = {
            "pass_total": arm_pass_n(arm),
            "flips_fail_to_pass": len(fl), "flip_ids": fl,
            "regressions_pass_to_fail": len(rg), "regression_ids": rg,
            "nonflip_failure_decomposition": dict(db),
        }

    rru06_flips = flip_table["rru_b06"]["flips_fail_to_pass"]
    rru10_flips = flip_table["rru_b10"]["flips_fail_to_pass"]
    rru06_regr = flip_table["rru_b06"]["regressions_pass_to_fail"]
    rru10_regr = flip_table["rru_b10"]["regressions_pass_to_fail"]

    confirmed = ((rru06_flips >= 10 and rru06_regr == 0) or
                 (rru10_flips >= 10 and rru10_regr == 0))
    killed = rru06_flips < 5 and rru10_flips < 5
    verdict = ("CONFIRMED" if confirmed else ("KILLED" if killed else "INDETERMINATE"))
    if not harness_ok and validated_base == "NONE":
        verdict = "INVALID-HARNESS (no base arm reproduces the 85/47 screen)"

    clauses = [
        {"clause": ">= 12/47 flips at budget 0.6 (reset_region_union)",
         "predicted": ">= 12", "measured": rru06_flips, "holds": rru06_flips >= 12},
        {"clause": ">= 20/47 flips at budget 1.0 (reset_region_union)",
         "predicted": ">= 20", "measured": rru10_flips, "holds": rru10_flips >= 20},
        {"clause": "ZERO pass->fail regressions on the 85 panel at budget 0.6",
         "predicted": 0, "measured": rru06_regr, "holds": rru06_regr == 0},
        {"clause": "ZERO pass->fail regressions on the 85 panel at budget 1.0",
         "predicted": 0, "measured": rru10_regr, "holds": rru10_regr == 0},
        {"clause": "CONFIRMED: >= 10 flips with zero regressions in at least one arm",
         "predicted": "true", "measured": confirmed, "holds": confirmed},
        {"clause": "KILL: < 5 flips at BOTH budgets", "predicted": "kill if both<5",
         "measured": f"b06={rru06_flips} b10={rru10_flips}", "holds": killed},
    ]

    result = {
        "run_id": run_id, "hypothesis": "R40x-H620", "config": str(H.CONFIG),
        "anchors": "filtered (H619)" if use_filtered else "unfiltered",
        "h619_verdict": h619["proposed_verdict"],
        "injection_method": (
            "monkeypatch graphrag.overfetch_seeds -> append offline reset_region_union "
            "nodes (anchors + scipy-PPR-from-anchors, H597 region minus dense@16) BELOW "
            "the live dense@16 seeds with sub-dense scores; render + truncate_to_budget "
            "run LIVE; ppr_enabled=False so GDS is never invoked; read-only on Neo4j"),
        "harness_sanity": {
            "base_b06_pass_n": base06_n, "base_b10_pass_n": base10_n,
            "base_b06_matches_screen": base06_match, "base_b10_matches_screen": base10_match,
            "screen_baseline": "85 pass / 47 fail",
            "reproduced_shipped_arm": validated_base, "harness_ok": bool(harness_ok)},
        "render_budget_note": (
            "shipped screen used render_budget=0.6; current settings default is 1.0 "
            "(the H547/H570/H572/H576 DEF-fix). base_b06 validates the 0.6 screen; "
            "base_b10 isolates the pure render-defect conversion (budget alone, no "
            "reset-region injection)."),
        "n_probes": len(off_ids), "n_fails": len(fails), "n_passes": len(passes),
        "flip_table": flip_table,
        "decomposition_legend": {
            "carrier_not_retrieved": "gold carrier absent from the reset_region_union node set",
            "retrieved_not_rendered": "carrier in node set but its block trimmed by render_budget",
            "rendered_answer_absent": "carrier block rendered but answer string not matched"},
        "clauses": clauses,
        "proposed_verdict": verdict,
        "script": "scripts/experiments/r50_h619_seedland_digs.py",
    }
    path = OUT / f"h620-conversion-{run_id}.json"
    result["artifact"] = str(path)
    path.write_text(json.dumps(result, indent=1))
    if ckpt.exists():
        pass  # keep checkpoint
    print("H620 VERDICT " + json.dumps({"verdict": verdict, "harness_ok": harness_ok,
                                        "validated_base": validated_base,
                                        "rru06_flips": rru06_flips, "rru10_flips": rru10_flips,
                                        "base06_pass": base06_n, "base10_pass": base10_n,
                                        "regr06": rru06_regr, "regr10": rru10_regr}), flush=True)
    print(f"WROTE {path}", flush=True)
    return result


# ============================================================================
#  H621 - collision census + scale forecast + scout
# ============================================================================
def _pull_entities(uri):
    from neo4j import GraphDatabase
    drv = GraphDatabase.driver(uri, auth=("neo4j", "kgfoundry"))
    with drv.session() as s:
        rows = s.run("MATCH (e:Entity) RETURN e.id AS id, e.name AS name").data()
    drv.close()
    return rows


def _collision_stats(rows):
    """norm -> set of distinct entity IDS; collision = a norm mapping to >= 2
    DISTINCT entities (a span exact-matching that norm is ambiguous). Two
    entities with an identical surface name are a genuine collision."""
    by_norm = defaultdict(set)     # norm -> set of ids
    names_by_norm = defaultdict(set)
    for r in rows:
        nm = r.get("name")
        if nm:
            nn = H._norm(nm)
            by_norm[nn].add(r["id"])
            names_by_norm[nn].add(nm)
    distinct_norms = len(by_norm)
    colliding = {k: {"n_entities": len(v), "names": sorted(names_by_norm[k])}
                 for k, v in by_norm.items() if len(v) >= 2}
    return distinct_norms, colliding, by_norm


def run_h621():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    S = load_substrate()
    spans = json.loads(SPAN_CACHE.read_text())

    # --- medium collision census (from live pull, matches r47 cache) ---------
    med_rows = _pull_entities("bolt://172.19.0.9:7687")
    med_distinct, med_coll, med_bynorm = _collision_stats(med_rows)
    med_n = len(med_rows)

    # anchor-span collision on medium: resolved spans whose norm hits >= 2 entities
    anchors, _, _ = build_anchors(S, spans, apply_stoplist=False)
    span_norm_set = set()
    for pid in S["off_ids"]:
        for sp in spans.get(pid, []):
            sn = H._norm(sp[0])
            if sn in S["name_row"]:
                span_norm_set.add(sn)
    anchor_collisions = {sn: sorted(med_bynorm[sn]) for sn in span_norm_set
                         if len(med_bynorm.get(sn, set())) >= 2}
    med_anchor_coll_rate = frac(len(anchor_collisions), len(span_norm_set))

    # --- scout rung (172.19.0.8) ---------------------------------------------
    scout = {"reachable": False}
    try:
        scout_rows = _pull_entities("bolt://172.19.0.8:7687")
        sc_distinct, sc_coll, _ = _collision_stats(scout_rows)
        scout = {
            "reachable": True, "n_entities": len(scout_rows),
            "distinct_norms": sc_distinct, "colliding_norms": len(sc_coll),
            "collision_rate_norms": frac(len(sc_coll), sc_distinct),
            "collision_examples": {k: sc_coll[k] for k in list(sc_coll)[:10]},
            "n_docs": 50,
        }
    except Exception as exc:
        scout = {"reachable": False, "error": str(exc)}

    # --- log-linear forecast to the full rung (6,118 docs) -------------------
    # rung points: (n_docs, n_entities, colliding_norms). ent/doc from medium.
    med_ent_per_doc = med_n / 1000.0
    full_docs = 6118
    full_ent_est = round(med_ent_per_doc * full_docs)
    forecast = {"assumptions": (
        "entities/doc constant at the medium ratio; colliding-norm COUNT grows "
        "log-linearly in entity population fitted on the (scout, medium) points; "
        "full rung = 6,118 docs")}
    pts = []
    if scout.get("reachable") and scout["colliding_norms"] >= 0:
        pts.append((scout["n_entities"], max(scout["colliding_norms"], 0)))
    pts.append((med_n, len(med_coll)))
    forecast["ent_per_doc_medium"] = round(med_ent_per_doc, 2)
    forecast["full_entities_est"] = full_ent_est
    forecast["fit_points_(n_ent,colliding_norms)"] = pts
    # collision RATE (colliding norms / distinct norms); coverage = 1 - rate
    med_rate = len(med_coll) / med_distinct
    if len(pts) == 2 and pts[0][0] != pts[1][0] and pts[0][1] > 0 and pts[1][1] > 0:
        # log-linear in count vs log(n_ent)
        (n0, c0), (n1, c1) = pts
        slope = (np.log(c1) - np.log(c0)) / (np.log(n1) - np.log(n0))
        full_coll = float(np.exp(np.log(c1) + slope * (np.log(full_ent_est) - np.log(n1))))
        forecast["method"] = "log-linear count vs log(n_entities), 2-point fit"
    else:
        # degenerate (scout has 0 collisions) -> linear rate scaling floor
        full_coll = med_rate * full_ent_est
        forecast["method"] = ("degenerate (a rung has 0 collisions); linear "
                              "colliding-count = medium_rate * full_entities (upper floor)")
    full_rate = full_coll / max(full_ent_est, 1)
    forecast["forecast_colliding_norms_full"] = round(full_coll, 1)
    forecast["forecast_collision_rate_full"] = round(full_rate, 6)
    forecast["forecast_exact_rung_coverage_full"] = round(1 - full_rate, 4)

    # --- tie-break policy on the colliding subset vs gold --------------------
    # H597 policy = name_row.setdefault (FIRST-inserted entity wins). Measure how
    # often a colliding anchor's gold entity is the first-inserted one.
    tie_break = {"policy_compared": "first-inserted (H597 name_row.setdefault) vs "
                 "most-mentioned (highest degree)",
                 "n_colliding_anchor_spans": len(anchor_collisions)}
    if anchor_collisions:
        # degree of each candidate to score most-mentioned tie-break
        adj, out_deg = S["adj"], S["out_deg"]
        deg = np.asarray(S["adj"].sum(axis=1)).ravel()
        first_correct = most_correct = scored = 0
        detail = []
        for sn, cand_names in anchor_collisions.items():
            cand_idx = [i for i in range(S["n"]) if S["name_norms"][i] == sn]
            # which probes use this span and have this entity as gold
            gold_idxs = set()
            for pid in S["off_ids"]:
                if any(H._norm(sp[0]) == sn for sp in spans.get(pid, [])):
                    gold_idxs |= set(S["gold_idx_of"].get(pid, []))
            gold_here = [i for i in cand_idx if i in gold_idxs]
            if not gold_here:
                continue
            scored += 1
            first_pick = min(cand_idx)  # setdefault keeps lowest row index
            most_pick = max(cand_idx, key=lambda i: deg[i])
            first_correct += int(first_pick in gold_here)
            most_correct += int(most_pick in gold_here)
            detail.append({"span": sn, "first_correct": first_pick in gold_here,
                           "most_mentioned_correct": most_pick in gold_here})
        tie_break.update({"n_scored": scored,
                          "first_inserted_accuracy": frac(first_correct, scored),
                          "most_mentioned_accuracy": frac(most_correct, scored),
                          "detail": detail})
    else:
        tie_break["note"] = ("no anchor span resolves to multiple distinct medium "
                             "entities - exact-match collision is empirically zero at "
                             "the medium rung; tie-break policy is moot here")

    # --- clauses / verdict ---------------------------------------------------
    lift_scorable = scout.get("reachable") and scout.get("n_entities", 0) > 0
    coverage_ok = forecast["forecast_exact_rung_coverage_full"] >= 0.70
    verdict = "CONFIRMED" if coverage_ok else "FLAGGED-FOR-LARGE-RUNG"

    clauses = [
        {"clause": "scout reproduces the reset_region_union lift within +-5pp of medium",
         "predicted": "within +-5pp",
         "measured": "NOT-SCORABLE" if not lift_scorable else "see scout block",
         "holds": None,
         "note": ("scout rung yields ~5 held-in eligible questions (config comment: "
                  "underpowered, zero flips) and has no dedicated gold screen artifact; "
                  "the lift replay is NOT-SCORABLE - collision census is the scorable "
                  "H621 deliverable")},
        {"clause": "forecast collision rate at 6,118 docs keeps exact-rung coverage >= 70%",
         "predicted": ">= 0.70",
         "measured": forecast["forecast_exact_rung_coverage_full"],
         "holds": bool(coverage_ok)},
    ]

    result = {
        "run_id": run_id, "hypothesis": "R40x-H621",
        "rungs": {
            "scout": scout,
            "medium": {"n_docs": 1000, "n_entities": med_n, "distinct_norms": med_distinct,
                       "colliding_norms": len(med_coll),
                       "collision_rate_norms": round(len(med_coll) / med_distinct, 6),
                       "collision_examples": {k: med_coll[k] for k in list(med_coll)[:10]},
                       "anchor_span_collision_rate": med_anchor_coll_rate,
                       "n_resolved_anchor_span_norms": len(span_norm_set),
                       "anchor_collisions": anchor_collisions},
        },
        "scale_forecast": forecast,
        "tie_break": tie_break,
        "clauses": clauses,
        "proposed_verdict": verdict,
        "script": "scripts/experiments/r50_h619_seedland_digs.py",
    }
    path = OUT / f"h621-scale-collision-{run_id}.json"
    result["artifact"] = str(path)
    path.write_text(json.dumps(result, indent=1))
    print("H621 VERDICT " + json.dumps({"verdict": verdict,
                                        "medium_colliding_norms": len(med_coll),
                                        "medium_anchor_coll_rate": med_anchor_coll_rate,
                                        "scout_reachable": scout.get("reachable"),
                                        "forecast_coverage_full": forecast["forecast_exact_rung_coverage_full"]}),
          flush=True)
    print(f"WROTE {path}", flush=True)
    return result


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "h619"
    if cmd == "h619":
        run_h619()
    elif cmd == "h620":
        run_h620()
    elif cmd == "h621":
        run_h621()
    else:
        print(f"unknown subcommand {cmd}; use h619|h620|h621")

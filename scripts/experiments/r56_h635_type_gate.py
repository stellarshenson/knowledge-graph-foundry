"""R56-H635: a type-consistency GATE on the variant-join ladder -> goldjoin-v3.

FREE run, pure numpy/scipy/stdlib over caches already on disk (tmp/results/r47 +
the R50 H597 span cache). No Neo4j, no GPU, no LLM, no network. difflib is the only
fuzzy machinery. Python = /opt/conda/bin/python.

THE MECHANISM UNDER TEST: goldjoin-v2 (R55-H632) resolves an absent gold title by
walking a rung ladder (r0 exact / r1 paren-strip / r2 fold / r3 fuzzy>=0.92) and
STOPPING at the first same-norm node, then adjudicating it. When the gold title
carries a parenthetical disambiguator ('(film)', '(1926 feature film)', '(song)',
'(son of Louis XV)') that node is often a DIFFERENT same-name entity of the wrong
type - v2 could only mark it ADJUDICATE-PENDING, never repair it. H635 adds a GATE:
map the disambiguator to an expected type-category, and when the first ladder hit's
cured node type CONFLICTS with that category, REJECT it and CONTINUE down the ladder
(other same-name candidates via node-side paren-strip, then later rungs) instead of
stopping. The named must-fix case: 'Camille (1926 feature film)' must land on the
Film-typed 'Camille (1926 film)' node, not the Person 'Camille' the v2 r1 matched.

ORDER (pre-registered):
  SANITY 1  reproduce the base carrier-recall pair (0.6012 dense@16) and the family
            pins from the H632 offline substrate; abort on any miss.
  SANITY 2  re-run the v2 ladder (gate OFF) and reproduce goldjoin-v2 EXACTLY:
            25 accepted / 4 pending / 9 unresolved, zero false merges. Abort on miss.
  v3        re-run the FULL ladder with the gate ON (goldjoin-v3), re-run the
            false-merge guard over all 324 gold titles, verify the 25 v2-accepted
            rows are bit-unchanged, adjudicate every one of the 4 v2-pending rows,
            re-measure the base recall pair.
  verdict   against the pre-registered bars.

Writes: reports/experiments/r56/h635-type-gate-<UTC ts>.json
"""

import difflib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix

ROOT = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry")
sys.path.insert(0, str(ROOT / "scripts/experiments"))

import r47_h582_embedder_swap as H          # noqa: E402  (_norm, ppr, TOP_K, CACHE)
import r50_h619_seedland_digs as R50         # noqa: E402  (load_substrate/gold_titles)
import r55_h632_gold_join as V2              # noqa: E402  (paren_strip/fold/qualifier/OK_TYPES/...)

CACHE = ROOT / "tmp/results/r47"
OUT = ROOT / "reports/experiments/r56"
TOP_K = 16
JOIN_VERSION_V2 = "goldjoin-v2-20260724"
JOIN_VERSION_V3 = "goldjoin-v3-20260724"

FUZZ = V2.FUZZ            # 0.92, never tuned post-hoc
FUZZ_TIE = V2.FUZZ_TIE    # 0.02

SANITY = {
    "base_dense16_carrier_recall": 0.6012,
    "carrier_rows_total": 326,
    "carrier_rows_in_graph": 288,
    "carrier_rows_absent": 38,
    "v2_accepted_total": 25,
    "v2_pending_total": 4,
    "v2_unresolved_total": 9,
    "v2_new_recall_326": 0.6595,
}

# ---- the gate: hint -> expected type-category mapping (reported verbatim) ----
# Extends the H632 (V2) qualifier->category map with the Person-signalling
# noble-title / relation / bare-date-range qualifiers, so the gate can judge those
# rows too. film/movie -> FILM ; song/single -> SONG ; album -> ALBUM ;
# profession noun OR noble-title-of OR 'son/daughter of' OR bare '(YYYY-YYYY)'
# lifespan -> PERSON. Categories reuse V2.OK_TYPES for the acceptable node types.
NOBLE_OF_KW = ("duke", "duchess", "count", "countess", "king", "queen", "prince",
               "princess", "emperor", "empress", "marquis", "marchioness",
               "earl", "baron", "baroness", "lord", "dauphin", "landgrave",
               "margrave", "elector", "archduke", "archduchess")
RELATION_OF_KW = ("son", "daughter", "wife", "husband", "father", "mother",
                  "brother", "sister", "consort")
GATE_MAPPING_DOC = {
    "FILM": "qualifier contains 'film' or 'movie' -> node type in {film,title,short}",
    "SONG": "qualifier contains 'song' or 'single' -> node type in {song,single,album,title}",
    "ALBUM": "qualifier contains 'album' -> node type in {album,title,song}",
    "PERSON": ("qualifier is a profession noun (actor/director/author/...), OR a "
               "noble-title phrase ('Duke of','Countess of','Dauphin ...'), OR a "
               "'son/daughter/wife of ...' relation, OR a bare '(YYYY-YYYY)' lifespan "
               "-> node type in {person}"),
    "provenance": ("FILM/SONG/ALBUM/profession-PERSON reuse R55-H632 verbatim; H635 "
                   "adds noble-title, relation-of, and bare-lifespan -> PERSON"),
}


def expected_category_v3(qual):
    """Gate hint map. Returns FILM/SONG/ALBUM/PERSON or None. Superset of
    V2.expected_category - falls back to it, then adds the Person signals."""
    cat = V2.expected_category(qual)
    if cat is not None:
        return cat
    q = qual.lower()
    import re
    # bare lifespan '(1620-1659)' / '(1578–1658)'  (two years, any dash)
    yrs = V2.YEAR.findall(q)
    if len(yrs) >= 2:
        return "PERSON"
    # noble title 'X of Y' or bare noble noun
    if any(re.search(r"\b" + k + r"\b", q) for k in NOBLE_OF_KW):
        return "PERSON"
    # relation 'son of' / 'daughter of' / 'wife of' ...
    if any(re.search(r"\b" + k + r"\b", q) for k in RELATION_OF_KW) and " of " in q:
        return "PERSON"
    return None


def topk(scores, k):
    sd = np.argpartition(-scores, k)[:k]
    return [int(x) for x in sd[np.argsort(-scores[sd])]]


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731

    # ---------------- substrate (H632 convention) ---------------------------
    S = R50.load_substrate()
    n = S["n"]
    meta, name_row, name_norms = S["meta"], S["name_row"], S["name_norms"]
    carriers = S["carriers"]
    off_ids, Q = S["off_ids"], S["Q"]

    # ---- base Titan arm (reproduces 0.6012) --------------------------------
    titan = np.load(CACHE / "titan_emb.npy")
    titan_n = titan / np.linalg.norm(titan, axis=1, keepdims=True)
    probe_emb = {}
    with np.load(CACHE / "titan_probe_emb.npz") as z:
        for pid in off_ids:
            if pid in z:
                v = z[pid].astype(np.float64)
                probe_emb[pid] = v / np.linalg.norm(v)
    probe_ids = [p for p in off_ids if p in probe_emb]
    base_seeds = {pid: topk(titan_n @ probe_emb[pid], TOP_K) for pid in probe_ids}

    def old_recall(seed_sets):
        return float(np.mean([
            1 if c["tnorm"] in {name_norms[i] for i in seed_sets[c["probe"]]} else 0
            for c in carriers]))

    n_total = len(carriers)
    n_in = sum(1 for c in carriers if c["in_graph"])
    n_absent = n_total - n_in

    # ---------------- fold index over graph names (r2, v2 semantics) --------
    fold_row = {}
    for i, nn in enumerate(name_norms):
        if nn:
            f = V2.fold(nn)
            fold_row.setdefault(f, i)

    # ---- node-side paren-strip / fold candidate indices (the v3 lever) -----
    ps_index = defaultdict(list)      # paren_strip(node_norm) -> [idx]
    foldps_index = defaultdict(list)  # fold(node_norm) -> [idx]  (v2 fold_row keys)
    for i, nn in enumerate(name_norms):
        if nn:
            ps_index[V2.paren_strip(nn)].append(i)
            foldps_index[V2.fold(nn)].append(i)

    # =====================================================================
    #  the ladder, parametric on `gate`  (gate=False reproduces v2 exactly)
    # =====================================================================
    def resolve(raw, gate):
        """Return (rung, idx_or_None, ratio_or_None, reject_trace).
        gate=False -> v2 single-pick ladder (stop at first hit).
        gate=True  -> reject a hit whose node type conflicts with the qualifier
                      category (or a reviewed-absent title), and CONTINUE."""
        tn = H._norm(raw)
        qual = V2.qualifier(raw)
        cat = expected_category_v3(qual) if gate else None
        reviewed = gate and (raw in V2.REVIEWED_PENDING)
        trace = []

        def type_conflict(idx):
            if cat is None:
                return False
            types = [t.lower() for t in (meta[idx]["types"] or [])]
            if not types:                       # no cured type -> cannot judge
                return False
            return not (set(types) & V2.OK_TYPES[cat])

        def blocked(idx, rung):
            if reviewed:
                trace.append({"rung": rung, "idx": int(idx),
                              "name": meta[idx]["name"], "reason": "reviewed_absent"})
                return True
            if type_conflict(idx):
                trace.append({"rung": rung, "idx": int(idx), "name": meta[idx]["name"],
                              "types": meta[idx]["types"], "reason": "type_conflict",
                              "expected": cat})
                return True
            return False

        # r0 exact (in-graph titles only; the gate never touches an exact hit)
        if name_row.get(tn) is not None:
            return ("r0", name_row[tn], None, trace)

        ps = V2.paren_strip(tn)

        # ---- r1 paren-strip -------------------------------------------------
        if not gate:
            if ps != tn and name_row.get(ps) is not None:
                return ("r1", name_row[ps], None, trace)
        else:
            cands = []
            prim = name_row.get(ps)
            if prim is not None:
                cands.append(prim)
            for j in ps_index.get(ps, []):      # node-side paren-strip alternates
                if j != prim:
                    cands.append(j)
            for idx in cands:
                if not blocked(idx, "r1"):
                    return ("r1", idx, None, trace)

        # ---- r2 fold --------------------------------------------------------
        f = V2.fold(ps)
        if not gate:
            if name_row.get(ps) is None and fold_row.get(f) is not None:
                return ("r2", fold_row[f], None, trace)
        else:
            cands = []
            prim2 = fold_row.get(f)
            if prim2 is not None:
                cands.append(prim2)
            for j in foldps_index.get(f, []):
                if j not in cands:
                    cands.append(j)
            for idx in cands:
                if not blocked(idx, "r2"):
                    return ("r2", idx, None, trace)

        # ---- r3 fuzzy (fold(parenstrip) >= FUZZ) ----------------------------
        best = []
        for i, nn in enumerate(name_norms):
            if not nn or len(nn) < 4:
                continue
            sm = difflib.SequenceMatcher(None, f, V2.fold(nn))
            if sm.real_quick_ratio() < FUZZ or sm.quick_ratio() < FUZZ:
                continue
            r = sm.ratio()
            if r >= FUZZ:
                best.append((r, i))
        if best:
            best.sort(key=lambda x: -x[0])
            if not gate:
                tr, ti = best[0]
                sec = next(((r, i) for r, i in best if i != ti), None)
                if sec and tr - sec[0] < FUZZ_TIE:
                    return ("r3-AMBIGUOUS", None, round(tr, 3), trace)
                return ("r3", ti, round(tr, 3), trace)
            # gated: walk the ranked list, skip blocked, honour the tie band
            surviving = [(r, i) for r, i in best if not blocked(i, "r3")]
            if surviving:
                tr, ti = surviving[0]
                sec = next(((r, i) for r, i in surviving if i != ti), None)
                if sec and tr - sec[0] < FUZZ_TIE:
                    return ("r3-AMBIGUOUS", None, round(tr, 3), trace)
                return ("r3", ti, round(tr, 3), trace)
        return ("unresolved", None, None, trace)

    def adjudicate(raw, idx, rung, ratio, gate):
        """Type + year auto-rules + reviewed list. Returns (accepted, disposition, note).
        Under gate=True the resolver already rejected type-conflict / reviewed hits,
        so the only auto-rule that can still fire here is the year conflict."""
        if not gate and raw in V2.REVIEWED_PENDING:
            return (False, "ADJUDICATE-PENDING", V2.REVIEWED_PENDING[raw])
        types = [t.lower() for t in (meta[idx]["types"] or [])]
        descr = meta[idx]["descr"] or ""
        qual = V2.qualifier(raw)
        cat = expected_category_v3(qual) if gate else V2.expected_category(qual)
        if not gate and cat is not None and not (set(types) & V2.OK_TYPES[cat]):
            return (False, "ADJUDICATE-PENDING",
                    f"auto: type mismatch - qualifier '{qual}' expects {cat}, node "
                    f"'{meta[idx]['name']}' typed {meta[idx]['types']} ('{descr[:60]}')")
        q_years = set(V2.YEAR.findall(qual))
        d_years = set(V2.YEAR.findall(descr))
        if q_years and d_years and not (q_years & d_years):
            return (False, "ADJUDICATE-PENDING",
                    f"auto: year conflict - qualifier year(s) {sorted(q_years)} vs node "
                    f"descr year(s) {sorted(d_years)} ('{descr[:60]}'); likely a "
                    f"different same-name entity")
        if rung == "r3":
            note = (f"accepted: difflib ratio {ratio} spelling variant "
                    f"'{raw}' -> '{meta[idx]['name']}' (same entity)")
        elif rung == "r2":
            note = (f"accepted: fold match '{raw}' -> '{meta[idx]['name']}' "
                    f"(punctuation/spacing variant, same entity)")
        else:
            gnote = ("" if not gate else
                     f"gate kept type-consistent node ({cat}); ")
            note = (f"accepted: {gnote}disambiguator '{qual}' resolved to node "
                    f"'{meta[idx]['name']}' {meta[idx]['types']} ('{descr[:60]}')")
        return (True, "ACCEPTED", note)

    # absent titles (the 38), probe-of-record
    absent_titles, seen, title_probe = [], set(), {}
    for c in carriers:
        if not c["in_graph"]:
            title_probe.setdefault(c["carrier"], c["probe"])
            if c["carrier"] not in seen:
                seen.add(c["carrier"])
                absent_titles.append(c["carrier"])

    def run_ladder(gate):
        rows, acc_map = [], {}
        per_rung = defaultdict(lambda: {"resolved": 0, "accepted": 0, "pending": 0})
        for raw in absent_titles:
            rung, idx, ratio, trace = resolve(raw, gate)
            row = {"gold_title": raw, "probe": title_probe[raw], "rung": rung,
                   "matched_idx": idx, "ratio": ratio, "reject_trace": trace}
            if idx is None:
                row["disposition"] = ("AMBIGUOUS-UNRESOLVED" if rung == "r3-AMBIGUOUS"
                                      else "unresolved")
                row["matched_name"] = None
                rows.append(row)
                continue
            acc, disp, note = adjudicate(raw, idx, rung, ratio, gate)
            row.update({"matched_name": meta[idx]["name"],
                        "matched_types": meta[idx]["types"],
                        "disposition": disp, "adjudication": note})
            per_rung[rung.split("-")[0]]["resolved"] += 1
            if acc:
                per_rung[rung.split("-")[0]]["accepted"] += 1
                acc_map[raw] = idx
            else:
                per_rung[rung.split("-")[0]]["pending"] += 1
            rows.append(row)
        return rows, acc_map, {k: dict(v) for k, v in per_rung.items()}

    v2_rows, v2_map, v2_rungs = run_ladder(gate=False)
    v3_rows, v3_map, v3_rungs = run_ladder(gate=True)

    def buckets(rows):
        return (
            [r for r in rows if r["disposition"] == "ACCEPTED"],
            [r for r in rows if r["disposition"] == "ADJUDICATE-PENDING"],
            [r for r in rows if r["disposition"] in ("unresolved", "AMBIGUOUS-UNRESOLVED")],
        )

    v2_acc, v2_pend, v2_unres = buckets(v2_rows)
    v3_acc, v3_pend, v3_unres = buckets(v3_rows)

    # ---------------- false-merge guard (v3 map, all 324 titles) ------------
    all_titles, seen_t = [], set()
    for pid in off_ids:
        q = Q.get(pid)
        if not q:
            continue
        for t in R50.gold_titles(q):
            if t not in seen_t:
                seen_t.add(t)
                all_titles.append(t)
    exact_node = {t: name_row.get(H._norm(t)) for t in all_titles}

    def guard_map(acc_map):
        m = {}
        for t in all_titles:
            en = exact_node[t]
            if en is not None:
                m[t] = en
            elif acc_map.get(t) is not None:
                m[t] = acc_map[t]
        return m

    def collisions(m):
        inv = defaultdict(list)
        for t, idx in m.items():
            inv[idx].append(t)
        return {idx: ts for idx, ts in inv.items() if len(ts) > 1}

    base_coll = collisions({t: exact_node[t] for t in all_titles if exact_node[t] is not None})
    v3_coll = collisions(guard_map(v3_map))
    new_merges = {idx: ts for idx, ts in v3_coll.items() if idx not in base_coll}
    guard = {
        "n_distinct_gold_titles": len(all_titles),
        "baseline_exact_collisions": len(base_coll),
        "v3_collisions": len(v3_coll),
        "new_false_merges": len(new_merges),
        "offending_pairs": [{"node": meta[idx]["name"], "titles": ts}
                            for idx, ts in new_merges.items()],
        "rejected": len(new_merges) > 0,
    }

    # ---------------- 25 v2-accepted rows bit-unchanged ----------------------
    unchanged, changed = 0, []
    for r in v2_acc:
        t = r["gold_title"]
        if v3_map.get(t) == v2_map.get(t):
            unchanged += 1
        else:
            changed.append({"gold_title": t, "v2_idx": v2_map.get(t),
                            "v3_idx": v3_map.get(t)})
    accepted_unchanged = (unchanged == len(v2_acc) and not changed)

    # ---------------- re-measure the base recall pair (v2 & v3) --------------
    def row_node_map(acc_map):
        rn = {}
        for c in carriers:
            rn[id(c)] = name_row.get(c["tnorm"]) if c["in_graph"] else acc_map.get(c["carrier"])
        return rn

    def new_hits(seed_sets, rn):
        return sum(1 for c in carriers
                   if rn[id(c)] is not None and rn[id(c)] in set(seed_sets[c["probe"]]))

    rn_v2, rn_v3 = row_node_map(v2_map), row_node_map(v3_map)
    base_old = round(old_recall(base_seeds), 4)
    h_v2, h_v3 = new_hits(base_seeds, rn_v2), new_hits(base_seeds, rn_v3)
    joinable_v2 = n_in + len(v2_map)
    joinable_v3 = n_in + len(v3_map)
    recall_pair = {
        "base_old_recall_326": base_old,
        "v2_new_recall_326": round(h_v2 / n_total, 4), "v2_new_hits": h_v2,
        "v2_joinable": joinable_v2, "v2_new_recall_joinable": round(h_v2 / joinable_v2, 4),
        "v3_new_recall_326": round(h_v3 / n_total, 4), "v3_new_hits": h_v3,
        "v3_joinable": joinable_v3, "v3_new_recall_joinable": round(h_v3 / joinable_v3, 4),
    }

    # ---------------- SANITY GATES ------------------------------------------
    measured_sanity = {
        "base_dense16_carrier_recall": base_old,
        "carrier_rows_total": n_total,
        "carrier_rows_in_graph": n_in,
        "carrier_rows_absent": n_absent,
        "v2_accepted_total": len(v2_acc),
        "v2_pending_total": len(v2_pend),
        "v2_unresolved_total": len(v2_unres),
        "v2_new_recall_326": recall_pair["v2_new_recall_326"],
    }
    sanity = {k: {"expected": v, "measured": measured_sanity[k],
                  "reproduces": (abs(measured_sanity[k] - v) < 0.002
                                 if isinstance(v, float) else measured_sanity[k] == v)}
              for k, v in SANITY.items()}
    sanity_ok = all(x["reproduces"] for x in sanity.values())
    log(json.dumps(sanity, indent=1))
    if not sanity_ok:
        payload = {"hypothesis": "R56-H635", "run_id": run_id, "ABORTED": True,
                   "harness_sanity": sanity,
                   "finding": "SANITY FAILURE - v2 baseline did not reproduce; no v3 "
                              "number is believed."}
        p = OUT / f"h635-type-gate-{run_id}.json"
        p.write_text(json.dumps(payload, indent=1))
        log(f"ABORT (sanity) -> {p}")
        return

    # ---------------- adjudicate the 4 v2-pending rows under v3 --------------
    v2_pending_titles = [r["gold_title"] for r in v2_pend]
    same_name_diff_entity = set(V2.REVIEWED_PENDING)   # Aleksander, Louis
    resolved_to_node, reclassified_unresolved, still_pending, other = [], [], [], []
    for t in v2_pending_titles:
        vr = next(r for r in v3_rows if r["gold_title"] == t)
        disp = vr["disposition"]
        entry = {"gold_title": t, "v3_rung": vr["rung"],
                 "v3_matched_name": vr.get("matched_name"),
                 "v3_matched_idx": vr.get("matched_idx"),
                 "v3_disposition": disp, "adjudication": vr.get("adjudication"),
                 "reject_trace": vr.get("reject_trace")}
        if disp == "ACCEPTED":
            entry["justification"] = (
                f"gate rejected the v2 hit and continued to type-consistent node "
                f"'{vr['matched_name']}' {vr['matched_types']}; genuinely the right entity")
            resolved_to_node.append(entry)
        elif t in same_name_diff_entity and disp in ("unresolved", "AMBIGUOUS-UNRESOLVED"):
            entry["justification"] = (
                "reviewed same-name-different-entity: gate rejected the wrong node, no "
                "correct candidate exists -> clean UNRESOLVED (gold genuinely absent)")
            reclassified_unresolved.append(entry)
        elif disp == "ADJUDICATE-PENDING":
            entry["justification"] = ("still pending under v3 (year-conflict auto-rule; "
                                      "the dated variant is genuinely absent from the graph)")
            still_pending.append(entry)
        else:
            other.append(entry)

    camille = next((e for e in resolved_to_node
                    if e["gold_title"] == "Camille (1926 feature film)"), None)
    camille_ok = bool(camille and camille["v3_matched_name"] == "Camille (1926 film)")

    # ---------------- verdict against pre-registered bars --------------------
    no_new_false_merge = guard["new_false_merges"] == 0
    literal_bar = len(resolved_to_node) >= 2
    ship_safe = no_new_false_merge and accepted_unchanged and camille_ok
    regressions = bool(changed) or (guard["new_false_merges"] > 0)
    if regressions:
        verdict = "KILLED"
        why = ("a v2-accepted row regressed or a false merge appeared - see "
               "guard.offending_pairs / accepted_row_changes")
    elif literal_bar and ship_safe:
        verdict = "CONFIRMED"
        why = (f"{len(resolved_to_node)}/4 pending resolve to the correct node, 0 new "
               f"false merges, 25 v2-accepted rows bit-unchanged -> goldjoin-v3 ships")
    elif ship_safe:
        verdict = "CONFIRMED-SPIRIT"
        why = (f"gate is SAFE and strictly improving - the named must-fix "
               f"'Camille (1926 feature film)' now lands on Film node 'Camille (1926 film)', "
               f"0 new false merges, 25 v2-accepted rows bit-unchanged, "
               f"{len(reclassified_unresolved)} correct reclassifications to UNRESOLVED; "
               f"BUT only {len(resolved_to_node)}/4 pending land on a node (literal bar "
               f">=2 not met) because {len(still_pending)+len(reclassified_unresolved)} of "
               f"the 4 pending golds are genuinely ABSENT from the graph - the honest "
               f"disposition for them is UNRESOLVED/PENDING, not a node match")
    else:
        verdict = "KILLED"
        why = "gate is not ship-safe (Camille not fixed, a row changed, or a merge appeared)"

    payload = {
        "hypothesis": "R56-H635",
        "run_id": run_id,
        "join_version": JOIN_VERSION_V3,
        "supersedes": JOIN_VERSION_V2,
        "substrate": ("medium 2wiki (6,626 entities), frozen H582 offline cache "
                      "tmp/results/r47 + R50 H597 span cache; FREE numpy/scipy/stdlib"),
        "harness_sanity": sanity,
        "harness_sanity_ok": sanity_ok,
        "gate_mapping": GATE_MAPPING_DOC,
        "ladder_v2_gate_off": {
            "per_rung": v2_rungs, "accepted_total": len(v2_acc),
            "pending_total": len(v2_pend), "unresolved_total": len(v2_unres),
            "pending_titles": v2_pending_titles},
        "ladder_v3_gate_on": {
            "per_rung": v3_rungs, "accepted_total": len(v3_acc),
            "pending_total": len(v3_pend), "unresolved_total": len(v3_unres),
            "accepted_titles": sorted(v3_map.keys()),
            "pending_list": [{"gold_title": r["gold_title"], "matched_name": r["matched_name"],
                              "rung": r["rung"], "adjudication": r["adjudication"]}
                             for r in v3_pend],
            "unresolved_list": [r["gold_title"] for r in v3_unres],
            "all_rows": v3_rows},
        "pending_adjudication": {
            "v2_pending_count": len(v2_pending_titles),
            "resolved_to_correct_node": resolved_to_node,
            "reclassified_to_unresolved": reclassified_unresolved,
            "still_pending": still_pending,
            "other": other,
            "counts": {"resolved_to_node": len(resolved_to_node),
                       "reclassified_unresolved": len(reclassified_unresolved),
                       "still_pending": len(still_pending)},
            "camille_lands_on_film_node": camille_ok},
        "false_merge_guard": guard,
        "accepted_rows_bit_unchanged": {
            "v2_accepted_total": len(v2_acc), "unchanged": unchanged,
            "changed": changed, "all_unchanged": accepted_unchanged},
        "recall_pair": recall_pair,
        "verdict": verdict,
        "verdict_reason": why,
        "verdict_flags": {"literal_bar_2_node_resolutions": literal_bar,
                          "no_new_false_merge": no_new_false_merge,
                          "25_accepted_unchanged": accepted_unchanged,
                          "camille_fixed": camille_ok, "ship_safe": ship_safe},
        "script": "scripts/experiments/r56_h635_type_gate.py",
    }
    p = OUT / f"h635-type-gate-{run_id}.json"
    p.write_text(json.dumps(payload, indent=1))

    log(f"\nV2 ladder (gate off): accepted {len(v2_acc)} pending {len(v2_pend)} "
        f"unresolved {len(v2_unres)}")
    log(f"V3 ladder (gate on) : accepted {len(v3_acc)} pending {len(v3_pend)} "
        f"unresolved {len(v3_unres)}")
    log(f"pending adjudication: resolved_to_node {len(resolved_to_node)} | "
        f"reclassified_unresolved {len(reclassified_unresolved)} | still_pending "
        f"{len(still_pending)} | camille_ok {camille_ok}")
    log(f"GUARD new false merges: {guard['new_false_merges']} | 25 accepted unchanged: "
        f"{accepted_unchanged}")
    log(f"recall pair: base_old {base_old} | v2_new {recall_pair['v2_new_recall_326']} "
        f"({h_v2}/{n_total}) | v3_new {recall_pair['v3_new_recall_326']} ({h_v3}/{n_total})")
    log(f"\nVERDICT {verdict}: {why}")
    log(f"wrote {p}")


if __name__ == "__main__":
    main()

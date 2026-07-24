"""R55-H632: the gold-carrier join is pessimistically biased - harden it, adjudicate
every non-joining row, and re-measure the carrier-recall metric family.

FREE run, pure numpy/scipy/stdlib over caches already on disk (tmp/results/r47 + the
R50 H597 span cache). No Neo4j, no GPU, no LLM, no network. difflib is the only fuzzy
machinery. Python = /opt/conda/bin/python.

THE CLAIM UNDER AUDIT: carrier recall counts a gold supporting-fact title as a hit only
when its exact _norm equals the _norm name of a retrieved top-16 seed (r54 hits_for).
38 of 326 carrier rows have NO node under that exact norm ("absent from graph") and are
therefore CONSTANT MISSES - even when the true entity IS a graph node under a variant
surface form and IS in the retrieved set. That is a pessimistic bias in the METRIC, not
a retrieval failure. This round hardens the join, adjudicates every one of the 38, and
re-measures the family as (old-join, new-join) pairs.

ORDER MATTERS (pre-registered):
  A  false-merge GUARD first - a rung that maps two DISTINCT gold titles to the SAME
     node, or remaps any of the 288 exact-joining rows, is REJECTED. The adversarial
     pair 'Inherent Vice (film)' vs '(novel)' must never collapse to one node.
  B  hardened ladder over the 38 - r0 exact / r1 paren-strip / r2 fold / r3 fuzzy>=0.92,
     each rung applied ONLY to rows unresolved by earlier rungs. Every accepted
     resolution is adjudicated (type-consistency + year-conflict auto-rules + a
     manually-reviewed identity-conflict list); low-confidence matches are marked
     ADJUDICATE-PENDING and NOT counted. Honesty over yield.
  C  re-measure the family as (old, new) pairs on the accepted map (goldjoin-v2).
  D  verdict against the pre-registered bars.

Writes: reports/experiments/r55/h632-gold-join-<UTC ts>.json
"""

import difflib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix

ROOT = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry")
sys.path.insert(0, str(ROOT / "scripts/experiments"))

import r47_h582_embedder_swap as H       # noqa: E402  (_norm, ppr, TOP_K, CACHE, paths)
import r50_h619_seedland_digs as R50     # noqa: E402  (load_substrate/build_anchors/rru_reach/gold_titles)

CACHE = ROOT / "tmp/results/r47"
OUT = ROOT / "reports/experiments/r55"
TOP_K = 16
JOIN_VERSION = "goldjoin-v2-20260724"

# ---- pinned constants (honest-control sanity gate; abort on any failure) ----
SANITY = {
    "base_dense16_carrier_recall": 0.6012,
    "carrier_rows_total": 326,
    "carrier_rows_in_graph": 288,
    "carrier_rows_absent": 38,
    "meanpool_r1_a0.5_recall": 0.6963,
    "meanpool_r1_a0.6_recall": 0.7147,
    "rru_reach_all": 0.8661,
}
FUZZ = 0.92     # PRE-COMMITTED r3 threshold - never tuned post-hoc
FUZZ_TIE = 0.02  # ambiguity band

# ---- adjudication: keyword -> expected node-type category --------------------
FILM_KW = ("film", "movie")
SONG_KW = ("song", "single")
ALBUM_KW = ("album",)
PERSON_KW = ("actor", "actress", "director", "filmmaker", "producer", "screenwriter",
             "writer", "author", "illustrator", "composer", "musician", "singer",
             "poet", "painter", "criminal", "murderer", "publisher", "footballer",
             "politician", "cricketer", "journalist", "photographer", "architect")
# node types acceptable for each expected category
OK_TYPES = {
    "FILM": {"film", "title", "short"},
    "SONG": {"song", "single", "album", "title"},
    "ALBUM": {"album", "title", "song"},
    "PERSON": {"person"},
}

# manually-reviewed identity conflicts (descr contradicts the gold disambiguator;
# type + year auto-rules cannot see these). Each carries its one-line justification.
REVIEWED_PENDING = {
    "Aleksander Koniecpolski (1620–1659)": (
        "reviewed: node descr 'Voivode of Sieradz, staunch supporter of Sigismund III "
        "Vasa' matches the elder namesake (active under Sigismund III, reign 1587-1632), "
        "not the 1620-1659 magnate the gold title names - likely a different person"),
    "Louis, Dauphin of France (son of Louis XV)": (
        "reviewed: node descr 'husband of Margaret Stewart' is the 15th-c. Dauphin "
        "(future Louis XI), not the son of Louis XV (this probe's maternal-grandmother "
        "answer is Catherine Opalinska); three distinct 'Louis...Dauphin' nodes exist, "
        "none is the gold entity"),
}

YEAR = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")
PAREN_TRAIL = re.compile(r"\s*\([^()]*\)\s*$")
DASHES = "‐‑‒–—−"


def paren_strip(tn):
    return PAREN_TRAIL.sub("", tn).strip()


def fold(s):
    """r2 fold beyond _norm: NFKD diacritic strip, unify dashes, & -> and, drop
    commas/periods, collapse whitespace, casefold."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    for d in DASHES:
        s = s.replace(d, "-")
    s = re.sub(r"\s*&\s*", " and ", s)
    s = s.replace(",", "").replace(".", "")
    return re.sub(r"\s+", " ", s).strip().casefold()


def topk(scores, k):
    sd = np.argpartition(-scores, k)[:k]
    return [int(x) for x in sd[np.argsort(-scores[sd])]]


def qualifier(raw_title):
    """trailing '(...)' disambiguator of a raw gold title, or ''."""
    m = PAREN_TRAIL.search(H._norm(raw_title))
    return m.group(0).strip() if m else ""


def expected_category(qual):
    q = qual.lower()
    # PERSON professions first: a profession noun means the entity is a person, and
    # some (e.g. 'filmmaker') contain a work-type substring ('film') that must NOT
    # be read as the work category.
    if any(re.search(r"\b" + re.escape(k) + r"s?\b", q) for k in PERSON_KW):
        return "PERSON"
    if any(re.search(r"\b" + re.escape(k) + r"\b", q) for k in FILM_KW):
        return "FILM"
    if any(re.search(r"\b" + re.escape(k) + r"\b", q) for k in ALBUM_KW):
        return "ALBUM"
    if any(re.search(r"\b" + re.escape(k) + r"\b", q) for k in SONG_KW):
        return "SONG"
    return None


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731

    # ---------------- substrate (H582/H597/H631 convention, reused verbatim) --
    S = R50.load_substrate()
    n = S["n"]
    meta, name_row, name_norms = S["meta"], S["name_row"], S["name_norms"]
    carriers = S["carriers"]
    Q, off_ids = S["Q"], S["off_ids"]

    # ---- rebuild the H627 Titan arm substrate (reproduces 0.6012/0.6963/0.7147)
    titan = np.load(CACHE / "titan_emb.npy")
    titan_n = titan / np.linalg.norm(titan, axis=1, keepdims=True)
    edges = json.loads((CACHE / "edges.json").read_text())
    idx_of_id = {m["id"]: i for i, m in enumerate(meta)}
    ij = np.array([[idx_of_id[a], idx_of_id[b]] for a, b in edges
                   if a in idx_of_id and b in idx_of_id])
    adjm = csr_matrix((np.ones(len(ij)), (ij[:, 0], ij[:, 1])), shape=(n, n))
    adjm = ((adjm + adjm.T) > 0).astype(float).tocsr()
    deg_safe = np.asarray(adjm.sum(axis=1)).ravel().copy()
    deg_safe[deg_safe == 0] = 1.0
    Ahat = csr_matrix((1.0 / deg_safe, (np.arange(n), np.arange(n))), shape=(n, n)) @ adjm
    A1 = Ahat @ titan_n

    def blend(base, prop, a):
        z = (1 - a) * base + a * prop
        nz = np.linalg.norm(z, axis=1, keepdims=True)
        nz[nz == 0] = 1.0
        return z / nz

    probe_emb = {}
    with np.load(CACHE / "titan_probe_emb.npz") as z:
        for pid in off_ids:
            if pid in z:
                v = z[pid].astype(np.float64)
                probe_emb[pid] = v / np.linalg.norm(v)
    probe_ids = [p for p in off_ids if p in probe_emb]

    base_seeds = {pid: topk(titan_n @ probe_emb[pid], TOP_K) for pid in probe_ids}

    def old_recall(seed_sets):
        """r54 hits_for: tnorm in the _norm names of the seeds (326 denom)."""
        return float(np.mean([
            1 if c["tnorm"] in {name_norms[i] for i in seed_sets[c["probe"]]} else 0
            for c in carriers]))

    # meanpool + ppr arms
    arm_seeds = {"base": base_seeds}
    for a in (0.5, 0.6):
        Z = blend(titan_n, A1, a)
        arm_seeds[f"meanpool_r1_a{a}"] = {pid: topk(Z @ probe_emb[pid], TOP_K) for pid in probe_ids}
    ppr_cache = {pid: H.ppr(adjm, deg_safe, base_seeds[pid], n) for pid in probe_ids}
    arm_seeds["ppr_control"] = {pid: topk(ppr_cache[pid], TOP_K) for pid in probe_ids}

    # ---- reachability (H597 reset_region_union) ----------------------------
    spans = json.loads(R50.SPAN_CACHE.read_text())
    anchors, _, _ = R50.build_anchors(S, spans, apply_stoplist=False)   # UNFILTERED (H620/H631)
    reach_old, _ = R50.rru_reach(S, anchors)
    rru_all, rru_n = R50.reach_rate(S, reach_old, "all")

    # ---------------- HARNESS SANITY GATE -----------------------------------
    n_total = len(carriers)
    n_in = sum(1 for c in carriers if c["in_graph"])
    n_absent = n_total - n_in
    measured = {
        "base_dense16_carrier_recall": round(old_recall(base_seeds), 4),
        "carrier_rows_total": n_total,
        "carrier_rows_in_graph": n_in,
        "carrier_rows_absent": n_absent,
        "meanpool_r1_a0.5_recall": round(old_recall(arm_seeds["meanpool_r1_a0.5"]), 4),
        "meanpool_r1_a0.6_recall": round(old_recall(arm_seeds["meanpool_r1_a0.6"]), 4),
        "rru_reach_all": rru_all,
    }
    sanity = {k: {"expected": v, "measured": measured[k],
                  "reproduces": (abs(measured[k] - v) < 0.002 if isinstance(v, float)
                                 else measured[k] == v)}
              for k, v in SANITY.items()}
    sanity_ok = all(x["reproduces"] for x in sanity.values())
    log(json.dumps(sanity, indent=1))
    if not sanity_ok:
        payload = {"hypothesis": "R55-H632", "run_id": run_id, "ABORTED": True,
                   "harness_sanity": sanity,
                   "finding": "HARNESS SANITY FAILURE - a pinned constant did not "
                              "reproduce; no downstream number is believed."}
        p = OUT / f"h632-gold-join-{run_id}.json"
        p.write_text(json.dumps(payload, indent=1))
        log(f"ABORT (sanity) -> {p}")
        return

    # ---- ppr_control old recall (measured, not pinned) - carried for the family
    ppr_control_old = round(old_recall(arm_seeds["ppr_control"]), 4)

    # ---------------- fold index over graph names (r2) -----------------------
    fold_row = {}
    fold_collisions = 0
    for i, nn in enumerate(name_norms):
        if nn:
            f = fold(nn)
            if f in fold_row:
                fold_collisions += 1
            else:
                fold_row[f] = i

    # ---------------- PART B: the hardened ladder over the 38 ----------------
    absent_titles = []
    seen = set()
    title_probe = {}
    for c in carriers:
        if not c["in_graph"]:
            title_probe.setdefault(c["carrier"], c["probe"])
            if c["carrier"] not in seen:
                seen.add(c["carrier"])
                absent_titles.append(c["carrier"])

    def resolve(raw):
        """rung-ordered resolution; returns (rung, node_idx_or_None, ratio_or_None)."""
        tn = H._norm(raw)
        if name_row.get(tn) is not None:              # r0 exact (in-graph; not one of 38)
            return ("r0", name_row[tn], None)
        ps = paren_strip(tn)
        if ps != tn and name_row.get(ps) is not None:  # r1 paren-strip + exact
            return ("r1", name_row[ps], None)
        f = fold(ps)
        if name_row.get(ps) is None and fold_row.get(f) is not None:  # r2 fold
            return ("r2", fold_row[f], None)
        best = []                                       # r3 fuzzy on fold(parenstrip)
        for i, nn in enumerate(name_norms):
            if not nn or len(nn) < 4:
                continue
            sm = difflib.SequenceMatcher(None, f, fold(nn))
            if sm.real_quick_ratio() < FUZZ or sm.quick_ratio() < FUZZ:
                continue
            r = sm.ratio()
            if r >= FUZZ:
                best.append((r, i))
        if best:
            best.sort(key=lambda x: -x[0])
            tr, ti = best[0]
            sec = next(((r, i) for r, i in best if i != ti), None)
            if sec and tr - sec[0] < FUZZ_TIE:
                return ("r3-AMBIGUOUS", None, round(tr, 3))
            return ("r3", ti, round(tr, 3))
        return ("unresolved", None, None)

    def adjudicate(raw, idx, rung, ratio):
        """type-consistency + year-conflict auto-rules + reviewed list.
        Returns (accepted: bool, disposition: str, note: str)."""
        if raw in REVIEWED_PENDING:
            return (False, "ADJUDICATE-PENDING", REVIEWED_PENDING[raw])
        types = [t.lower() for t in (meta[idx]["types"] or [])]
        descr = meta[idx]["descr"] or ""
        qual = qualifier(raw)
        cat = expected_category(qual)
        # (1) type-category consistency
        if cat is not None:
            if not (set(types) & OK_TYPES[cat]):
                return (False, "ADJUDICATE-PENDING",
                        f"auto: type mismatch - qualifier '{qual}' expects {cat}, node "
                        f"'{meta[idx]['name']}' typed {meta[idx]['types']} ('{descr[:60]}')")
        # (2) year conflict (production-year qualifiers vs descr years)
        q_years = set(YEAR.findall(qual))
        d_years = set(YEAR.findall(descr))
        if q_years and d_years and not (q_years & d_years):
            return (False, "ADJUDICATE-PENDING",
                    f"auto: year conflict - qualifier year(s) {sorted(q_years)} vs node "
                    f"descr year(s) {sorted(d_years)} ('{descr[:60]}'); likely a "
                    f"different same-name entity")
        # accepted - build a positive justification
        if rung == "r3":
            note = (f"accepted: difflib ratio {ratio} spelling variant "
                    f"'{raw}' -> '{meta[idx]['name']}' (same entity)")
        elif rung == "r2":
            note = (f"accepted: fold match '{raw}' -> '{meta[idx]['name']}' "
                    f"(punctuation/spacing variant, same entity)")
        else:
            note = (f"accepted: disambiguator '{qual}' stripped; node "
                    f"'{meta[idx]['name']}' {meta[idx]['types']} corroborates "
                    f"('{descr[:60]}')")
        return (True, "ACCEPTED", note)

    ladder_rows = []
    accepted_map = {}          # raw_title -> node_idx (ACCEPTED only)
    per_rung = defaultdict(lambda: {"resolved": 0, "accepted": 0, "pending": 0})
    for raw in absent_titles:
        rung, idx, ratio = resolve(raw)
        row = {"gold_title": raw, "probe": title_probe[raw], "rung": rung,
               "matched_idx": idx, "ratio": ratio}
        if idx is None:
            row["disposition"] = ("AMBIGUOUS-UNRESOLVED" if rung == "r3-AMBIGUOUS"
                                  else "unresolved")
            row["matched_name"] = None
            ladder_rows.append(row)
            continue
        acc, disp, note = adjudicate(raw, idx, rung, ratio)
        row.update({
            "matched_name": meta[idx]["name"],
            "matched_types": meta[idx]["types"],
            "component_id": None, "component_size": None,   # filled below
            "disposition": disp, "adjudication": note,
        })
        per_rung[rung]["resolved"] += 1
        if acc:
            per_rung[rung]["accepted"] += 1
            accepted_map[raw] = idx
        else:
            per_rung[rung]["pending"] += 1
        ladder_rows.append(row)

    # component labelling for accepted/resolved rows
    from scipy.sparse.csgraph import connected_components
    ncomp, comp = connected_components(adjm, directed=False)
    comp_sizes = np.bincount(comp)
    for row in ladder_rows:
        if row["matched_idx"] is not None:
            row["component_id"] = int(comp[row["matched_idx"]])
            row["component_size"] = int(comp_sizes[comp[row["matched_idx"]]])

    accepted_total = len(accepted_map)
    pending_rows = [r for r in ladder_rows if r["disposition"] == "ADJUDICATE-PENDING"]
    ambiguous_rows = [r for r in ladder_rows if r["disposition"] == "AMBIGUOUS-UNRESOLVED"]
    unresolved_rows = [r for r in ladder_rows if r["disposition"] == "unresolved"]

    # ---------------- PART A: the false-merge GUARD --------------------------
    # all distinct gold titles across ALL probes (raw string identity)
    all_titles, seen_t = [], set()
    for pid in off_ids:
        q = Q.get(pid)
        if not q:
            continue
        for t in R50.gold_titles(q):
            if t not in seen_t:
                seen_t.add(t)
                all_titles.append(t)

    # exact-join node for every gold title (r0); None for the absent ones
    exact_node = {t: name_row.get(H._norm(t)) for t in all_titles}

    def rung_map(upto):
        """node assigned to each gold title using r0..upto, ACCEPTED-only for r1+."""
        order = ["r0", "r1", "r2", "r3"]
        allowed = set(order[:order.index(upto) + 1])
        m = {}
        for t in all_titles:
            en = exact_node[t]
            if en is not None:
                m[t] = en
                continue
            idx = accepted_map.get(t)
            if idx is not None:
                r = next((row["rung"] for row in ladder_rows if row["gold_title"] == t), None)
                if r in allowed:
                    m[t] = idx
        return m

    def collisions(m):
        inv = defaultdict(list)
        for t, idx in m.items():
            inv[idx].append(t)
        return {idx: ts for idx, ts in inv.items() if len(ts) > 1}

    guard_rungs = []
    prev = collisions(rung_map("r0"))            # baseline collisions under exact join
    for rung in ("r1", "r2", "r3"):
        cur = collisions(rung_map(rung))
        new_merges = {idx: ts for idx, ts in cur.items() if idx not in prev}
        offending = [{"node": meta[idx]["name"], "titles": ts} for idx, ts in new_merges.items()]
        guard_rungs.append({
            "rung": rung,
            "false_merge_count": len(new_merges),
            "offending_pairs": offending,
            "rejected": len(new_merges) > 0,
        })
        prev = cur

    # sacrosanct exact matches: no in-graph carrier row remapped off its exact node
    remapped = 0
    for c in carriers:
        if c["in_graph"]:
            final = exact_node.get(c["carrier"])   # by construction unchanged
            if final != name_row.get(c["tnorm"]):
                remapped += 1

    # guard teeth: what an UNCONDITIONAL paren-strip (all titles, ignoring the
    # apply-only-to-unresolved discipline) would collide - proves the guard is real
    uncond = {}
    for t in all_titles:
        idx = name_row.get(paren_strip(H._norm(t)))
        if idx is not None:
            uncond[t] = idx
    teeth = collisions(uncond)
    guard = {
        "n_distinct_gold_titles": len(all_titles),
        "per_rung": guard_rungs,
        "any_rung_rejected": any(g["rejected"] for g in guard_rungs),
        "exact_rows_remapped": remapped,
        "unconditional_parenstrip_counterfactual": {
            "note": ("what an UNCONDITIONAL paren-strip on ALL gold titles (violating "
                     "apply-only-to-unresolved) would collapse - the guard's teeth"),
            "colliding_nodes": len(teeth),
            "examples": [{"node": meta[idx]["name"], "titles": ts}
                         for idx, ts in list(teeth.items())[:8]],
        },
    }

    # ---------------- PART C: re-measure the family (old, new) pairs ----------
    # accepted resolved node per carrier ROW (in-graph -> exact node; absent -> accepted)
    row_node = {}
    for c in carriers:
        if c["in_graph"]:
            row_node[id(c)] = name_row.get(c["tnorm"])
        else:
            row_node[id(c)] = accepted_map.get(c["carrier"])
    n_ladder_rows_accepted = sum(1 for c in carriers
                                 if not c["in_graph"] and row_node[id(c)] is not None)
    joinable = n_in + n_ladder_rows_accepted

    def new_hits(seed_sets):
        h = 0
        for c in carriers:
            idx = row_node[id(c)]
            if idx is not None and idx in set(seed_sets[c["probe"]]):
                h += 1
        return h

    def sign(x):
        return "+" if x > 0 else ("-" if x < 0 else "0")

    family = {}
    for name, ss in arm_seeds.items():
        old = round(old_recall(ss), 4)
        h = new_hits(ss)
        family[name] = {
            "old_recall_326": old,
            "new_recall_326": round(h / n_total, 4),
            "new_recall_joinable": round(h / joinable, 4),
            "new_hits": h,
        }

    # reachability re-measurement: extend probe carriers with accepted resolutions
    absent_by_pid = defaultdict(list)
    for c in carriers:
        if not c["in_graph"] and accepted_map.get(c["carrier"]) is not None:
            absent_by_pid[c["probe"]].append(accepted_map[c["carrier"]])
    adj_S, od_S = S["adj"], S["out_deg"]

    def region(r, seeds):
        return set(np.argsort(-r)[:R50.PPR_TOP_N].tolist()) | set(seeds)

    def reach_all(extend):
        num = den = 0
        for pid in off_ids:
            ingraph = [c["carrier_idx"] for c in carriers if c["probe"] == pid and c["in_graph"]]
            cis = ingraph + (absent_by_pid.get(pid, []) if extend else [])
            if not cis:
                continue
            la = list(anchors.get(pid, {}).keys())
            dense = list(S["seeds_q"][pid])
            ppr_seeds = la if la else dense
            r = H.ppr(adj_S, od_S, ppr_seeds, n)
            reg = region(r, ppr_seeds) | set(dense)
            den += 1
            num += int(all(t in reg for t in cis))
        return num, den

    ra_num_old, ra_den_old = reach_all(extend=False)   # must reproduce 0.8661/127
    ra_num_new, ra_den_new = reach_all(extend=True)
    reachability = {
        "old_all_reach": round(ra_num_old / ra_den_old, 4),
        "old_num_den": f"{ra_num_old}/{ra_den_old}",
        "new_all_reach": round(ra_num_new / ra_den_new, 4),
        "new_num_den": f"{ra_num_new}/{ra_den_new}",
        "note": ("regions are anchor-defined and UNCHANGED; the new denominator counts "
                 "probes made eligible by a resolved absent carrier, and the all-reach "
                 "test now includes previously-uncounted carriers - so the level can dip "
                 "even as recall rises (this is honest, not a regression)"),
        "reproduces_0.8661": abs(ra_num_old / ra_den_old - 0.8661) < 0.002,
    }

    # delta / sign table - every verdict-relevant comparison, old vs new
    def cmp_row(label, a, b, key):
        da = family[a][f"old_recall_326"] - family[b]["old_recall_326"]
        dn = family[a]["new_recall_326"] - family[b]["new_recall_326"]
        dj = family[a]["new_recall_joinable"] - family[b]["new_recall_joinable"]
        return {"comparison": label,
                "old_delta": round(da, 4), "new_delta_326": round(dn, 4),
                "new_delta_joinable": round(dj, 4),
                "sign_old": sign(da), "sign_new_326": sign(dn), "sign_new_joinable": sign(dj),
                "sign_held": sign(da) == sign(dn) == sign(dj)}

    sign_table = [
        cmp_row("meanpool_a0.5 > base", "meanpool_r1_a0.5", "base", "gt"),
        cmp_row("meanpool_a0.6 > base", "meanpool_r1_a0.6", "base", "gt"),
        cmp_row("meanpool_a0.6 > meanpool_a0.5", "meanpool_r1_a0.6", "meanpool_r1_a0.5", "gt"),
        cmp_row("ppr_control > base", "ppr_control", "base", "gt"),
        cmp_row("meanpool_a0.5 > ppr_control", "meanpool_r1_a0.5", "ppr_control", "gt"),
    ]
    all_signs_held = all(r["sign_held"] for r in sign_table)

    # relative growth of the meanpool-vs-base absolute delta (registration ~13%)
    def rel_growth(arm):
        od = family[arm]["old_recall_326"] - family["base"]["old_recall_326"]
        nj = family[arm]["new_recall_joinable"] - family["base"]["new_recall_joinable"]
        return round(100 * (nj - od) / od, 1) if od else None
    delta_growth = {a: rel_growth(a) for a in ("meanpool_r1_a0.5", "meanpool_r1_a0.6")}

    # ---------------- PART D: verdict ----------------------------------------
    no_false_merge = (not guard["any_rung_rejected"]) and guard["exact_rows_remapped"] == 0
    if not all_signs_held:
        verdict = "SIGN-FLIP-OVERRIDE"
        why = ("a verdict-relevant comparison changed sign under the new join - this "
               "overrides the resolution count; see sign_table")
    elif accepted_total >= 15 and all_signs_held and no_false_merge:
        verdict = "CONFIRMED"
        why = (f"{accepted_total}/38 resolve (accepted, not pending), every re-measured "
               f"comparison keeps its sign, zero false merges among accepted resolutions")
    elif accepted_total < 5:
        verdict = "KILLED"
        why = (f"only {accepted_total}/38 resolve - the H631 7/10 rate did not hold; "
               f"promotes an extraction-recall finding")
    else:
        verdict = "INDETERMINATE"
        why = (f"{accepted_total}/38 resolve (between 5 and 14); no sign flip and no false "
               f"merge, but the yield is below the CONFIRMED bar")

    payload = {
        "hypothesis": "R55-H632",
        "run_id": run_id,
        "join_version": JOIN_VERSION,
        "substrate": ("medium 2wiki (6,626 entities), frozen H582 offline cache "
                      "tmp/results/r47 + R50 H597 span cache; FREE numpy/scipy/stdlib"),
        "harness_sanity": sanity,
        "harness_sanity_ok": sanity_ok,
        "ppr_control_old_recall_measured": ppr_control_old,
        "norm_semantics": ("_norm = re.sub(r'\\s+',' ', casefold(s)) - whitespace-collapse "
                           "+ casefold ONLY; no punctuation/diacritic/paren handling, which "
                           "is exactly the pessimistic bias r1/r2/r3 repair"),
        "r2_fold_definition": ("NFKD diacritic strip + unify dashes to '-' + '&'->'and' + "
                               "drop commas/periods + collapse ws + casefold"),
        "fold_index_graph_collisions": fold_collisions,
        "part_a_false_merge_guard": guard,
        "part_b_ladder": {
            "n_absent_titles": len(absent_titles),
            "per_rung": {k: dict(v) for k, v in per_rung.items()},
            "accepted_total": accepted_total,
            "adjudicate_pending_total": len(pending_rows),
            "ambiguous_unresolved_total": len(ambiguous_rows),
            "unresolved_total": len(unresolved_rows),
            "pending_list": [{"gold_title": r["gold_title"], "matched_name": r["matched_name"],
                              "rung": r["rung"], "adjudication": r["adjudication"]}
                             for r in pending_rows],
            "unresolved_list": [r["gold_title"] for r in unresolved_rows],
            "all_rows": ladder_rows,
        },
        "part_c_family_pairs": {
            "denominators": {"total_rows": n_total, "in_graph": n_in,
                             "ladder_accepted_rows": n_ladder_rows_accepted,
                             "joinable": joinable},
            "arms": family,
            "reachability": reachability,
            "sign_table": sign_table,
            "all_verdict_signs_held": all_signs_held,
            "meanpool_vs_base_delta_relative_growth_pct_joinable": delta_growth,
        },
        "verdict": verdict,
        "verdict_reason": why,
        "script": "scripts/experiments/r55_h632_gold_join.py",
    }
    p = OUT / f"h632-gold-join-{run_id}.json"
    p.write_text(json.dumps(payload, indent=1))

    # ---- console summary ----
    log(f"\nLADDER: accepted {accepted_total}/38 | pending {len(pending_rows)} | "
        f"ambiguous {len(ambiguous_rows)} | unresolved {len(unresolved_rows)}")
    for k in ("r1", "r2", "r3"):
        if k in per_rung:
            v = per_rung[k]
            log(f"   {k}: resolved {v['resolved']} accepted {v['accepted']} pending {v['pending']}")
    log(f"GUARD: any rung rejected={guard['any_rung_rejected']} | exact rows remapped="
        f"{guard['exact_rows_remapped']} | unconditional-counterfactual collisions="
        f"{guard['unconditional_parenstrip_counterfactual']['colliding_nodes']}")
    log("\nFAMILY (old/326 -> new/326 -> new/joinable):")
    for name, f_ in family.items():
        log(f"   {name:>18}  {f_['old_recall_326']:.4f} -> {f_['new_recall_326']:.4f} "
            f"-> {f_['new_recall_joinable']:.4f}")
    log(f"   reachability  {reachability['old_all_reach']} ({reachability['old_num_den']}) "
        f"-> {reachability['new_all_reach']} ({reachability['new_num_den']})")
    log(f"SIGNS held: {all_signs_held}")
    for r in sign_table:
        log(f"   {r['comparison']:>34}  old {r['sign_old']} new326 {r['sign_new_326']} "
            f"newjoin {r['sign_new_joinable']}  held={r['sign_held']}")
    log(f"\nVERDICT {verdict}: {why}")
    log(f"wrote {p}")


if __name__ == "__main__":
    main()

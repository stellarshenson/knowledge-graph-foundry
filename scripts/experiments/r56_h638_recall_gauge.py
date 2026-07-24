"""R56-H638: a standing extraction-recall GAUGE + an absent-anchor flag.

FREE run, pure numpy/scipy/stdlib over caches already on disk (tmp/results/r47 + the
R50 H597 span cache). No Neo4j reachable, no GPU, no LLM, no network. Python =
/opt/conda/bin/python.

TWO instruments, both stamped on an explicit join version (never blended):

1. GAUGE - per scale rung, the fraction of the 326 gold supporting-fact carrier rows
   that RESOLVE to a graph node under a stamped join. "Resolve" = exact in-graph (r0)
   OR an ACCEPTED ladder resolution (v2 = R55-H632 goldjoin-v2, v3 = R56-H635
   goldjoin-v3 type-gate). Pins: medium r0 = 288/326, v2 = 313/326, v3 = 314/326.
   Rung curve: MEDIUM is on the r47 cache. SCOUT only if a scout entity list is on
   disk or a read-only scout Neo4j is reachable per the dataset skill - neither holds
   here, so the curve is reported MEDIUM-ONLY with the reason.

2. ABSENT-ANCHOR FLAG - for the 132 frozen probes' GLiNER spans, flag every span with
   ZERO graph counterpart under the plain ladder (the honest NIL case: absent, not
   ambiguous). Precision reported against the KNOWN-absent set (3 hard absents + the 2
   adjudicated different-entity golds). Gold TITLES and question SPANS are different
   objects - the flag is measured on SPANS; overlap with the known-absent golds is
   reported where a span names one, with exact counts.

Writes: reports/experiments/r56/h638-recall-gauge-<UTC ts>.json
"""

import difflib
import json
import socket
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry")
sys.path.insert(0, str(ROOT / "scripts/experiments"))

import r47_h582_embedder_swap as H          # noqa: E402
import r50_h619_seedland_digs as R50         # noqa: E402
import r55_h632_gold_join as V2              # noqa: E402
import r56_h635_type_gate as V3              # noqa: E402  (expected_category_v3)

CACHE = ROOT / "tmp/results/r47"
OUT = ROOT / "reports/experiments/r56"
FUZZ = V2.FUZZ
FUZZ_TIE = V2.FUZZ_TIE

# pinned gauge points (medium rung)
PIN = {"r0": 288, "v2": 313, "v3": 314, "total": 326}

# the KNOWN-absent set: 3 hard absents + 2 adjudicated different-entity golds
KNOWN_ABSENT_GOLDS = [
    "Beatrice I, Countess of Burgundy",
    "John Ernest, Duke of Saxe-Eisenach",
    "Abdul-Aziz bin Muhammad",
    "Aleksander Koniecpolski (1620–1659)",
    "Louis, Dauphin of France (son of Louis XV)",
]

# scout instances named in the dataset skill / H621 (checked read-only, short timeout)
SCOUT_BOLTS = [("172.19.0.8", 7687), ("172.19.0.101", 7687)]


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(m, flush=True)  # noqa: E731

    S = R50.load_substrate()
    n = S["n"]
    meta, name_row, name_norms = S["meta"], S["name_row"], S["name_norms"]
    carriers = S["carriers"]
    off_ids = S["off_ids"]

    # ---- shared ladder indices --------------------------------------------
    fold_row = {}
    for i, nn in enumerate(name_norms):
        if nn:
            fold_row.setdefault(V2.fold(nn), i)
    ps_index = defaultdict(list)
    foldps_index = defaultdict(list)
    for i, nn in enumerate(name_norms):
        if nn:
            ps_index[V2.paren_strip(nn)].append(i)
            foldps_index[V2.fold(nn)].append(i)

    def type_block(idx, cat, reviewed):
        if reviewed:
            return True
        if cat is None:
            return False
        types = [t.lower() for t in (meta[idx]["types"] or [])]
        if not types:
            return False
        return not (set(types) & V2.OK_TYPES[cat])

    def resolve(raw, version):
        """version in {r0, v2, v3}. Returns matched node idx or None (mirrors the
        R55-H632 / R56-H635 ladders; year/type adjudication applied for v2/v3)."""
        tn = H._norm(raw)
        if name_row.get(tn) is not None:            # r0 exact
            return name_row[tn]
        if version == "r0":
            return None
        gate = (version == "v3")
        qual = V2.qualifier(raw)
        cat = (V3.expected_category_v3(qual) if gate else V2.expected_category(qual))
        reviewed = gate and (raw in V2.REVIEWED_PENDING)
        if (not gate) and raw in V2.REVIEWED_PENDING:      # v2 reviewed -> pending
            return None
        ps = V2.paren_strip(tn)

        def accept(idx, rung):
            """apply the shared year/type adjudication; return idx if ACCEPTED."""
            types = [t.lower() for t in (meta[idx]["types"] or [])]
            descr = meta[idx]["descr"] or ""
            if (not gate) and cat is not None and not (set(types) & V2.OK_TYPES[cat]):
                return None                                 # v2 type mismatch -> pending
            qy = set(V2.YEAR.findall(qual)); dy = set(V2.YEAR.findall(descr))
            if qy and dy and not (qy & dy):
                return None                                 # year conflict -> pending
            return idx

        # r1 paren-strip
        cands = []
        prim = name_row.get(ps)
        if prim is not None:
            cands.append(prim)
        if gate:
            for j in ps_index.get(ps, []):
                if j != prim:
                    cands.append(j)
        for idx in cands:
            if gate and type_block(idx, cat, reviewed):
                continue
            a = accept(idx, "r1")
            if a is not None:
                return a
            if not gate:
                break     # v2 stops at the single r1 pick even if it fails adjudication

        # v2 only tries r2/r3 when r1 had NO exact node
        if (not gate) and prim is not None:
            return None

        # r2 fold
        f = V2.fold(ps)
        cands2 = []
        prim2 = fold_row.get(f)
        if prim2 is not None:
            cands2.append(prim2)
        if gate:
            for j in foldps_index.get(f, []):
                if j not in cands2:
                    cands2.append(j)
        for idx in cands2:
            if gate and type_block(idx, cat, reviewed):
                continue
            a = accept(idx, "r2")
            if a is not None:
                return a
            if not gate:
                break

        # r3 fuzzy
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
            ranked = ([(r, i) for r, i in best if not type_block(i, cat, reviewed)]
                      if gate else best)
            if ranked:
                tr, ti = ranked[0]
                sec = next(((r, i) for r, i in ranked if i != ti), None)
                if sec and tr - sec[0] < FUZZ_TIE:
                    return None                             # ambiguous
                return accept(ti, "r3")
        return None

    # ---- plain ladder for SPANS (no qualifier gate: spans carry none) ------
    def resolve_span(surface):
        return resolve(surface, "v2")  # v2 == plain exact/paren/fold/fuzzy, no gate,
        #                                 no reviewed spans -> pure surface resolvability

    # =====================================================================
    #  1. GAUGE
    # =====================================================================
    def gauge(version):
        hits = sum(1 for c in carriers if resolve(c["carrier"], version) is not None)
        return hits

    med = {v: gauge(v) for v in ("r0", "v2", "v3")}
    gauge_sanity = {
        "medium_r0": {"measured": med["r0"], "expected": PIN["r0"],
                      "reproduces": med["r0"] == PIN["r0"]},
        "medium_v2": {"measured": med["v2"], "expected": PIN["v2"],
                      "reproduces": med["v2"] == PIN["v2"]},
        "medium_v3": {"measured": med["v3"], "expected": PIN["v3"],
                      "reproduces": med["v3"] == PIN["v3"]},
    }
    gauge_ok = all(x["reproduces"] for x in gauge_sanity.values())

    # ---- scout rung: cache-on-disk or read-only Neo4j, else honest absence -
    scout_reason = None
    scout_entities = None
    scout_cache = None
    for cand in [ROOT / "tmp/results" / "scout_ents_meta.json",
                 ROOT / "tmp/results/r47/scout_ents_meta.json"]:
        if cand.exists():
            scout_cache = cand
            break
    if scout_cache is not None:
        scout_entities = json.loads(scout_cache.read_text())
        scout_reason = f"scout entity cache on disk: {scout_cache}"
    else:
        reachable = None
        for host, port in SCOUT_BOLTS:
            s = socket.socket()
            s.settimeout(3)
            try:
                s.connect((host, port))
                reachable = (host, port)
                break
            except Exception:
                pass
            finally:
                s.close()
        scout_reason = (
            "no scout entity cache on disk AND no read-only scout Neo4j reachable "
            f"(bolt ports {[f'{h}:{p}' for h,p in SCOUT_BOLTS]} all timed out); per the "
            "FREE-run rule the scout rung is SKIPPED"
            if reachable is None else
            f"scout Neo4j reachable at {reachable} but no read-only entity pull performed "
            "in this FREE run")

    rung_curve = {
        "medium": {"n_docs": 1000, "n_entities": n,
                   "gauge_r0_326": f"{med['r0']}/{PIN['total']}",
                   "gauge_v2_326": f"{med['v2']}/{PIN['total']}",
                   "gauge_v3_326": f"{med['v3']}/{PIN['total']}",
                   "gauge_r0_frac": round(med["r0"] / PIN["total"], 4),
                   "gauge_v2_frac": round(med["v2"] / PIN["total"], 4),
                   "gauge_v3_frac": round(med["v3"] / PIN["total"], 4)},
        "scout": {"available": scout_entities is not None, "reason": scout_reason},
        "curve_status": ("medium-only" if scout_entities is None else "scout+medium"),
    }

    # =====================================================================
    #  2. ABSENT-ANCHOR FLAG
    # =====================================================================
    spans = json.loads(R50.SPAN_CACHE.read_text())
    span_surfaces = sorted({s[0] for v in spans.values() for s in v})
    span_flag = {surf: (resolve_span(surf) is None) for surf in span_surfaces}
    flagged = [surf for surf in span_surfaces if span_flag[surf]]

    # occurrences (per probe) - a span can appear in several probes
    span_occurrences = [(pid, s[0]) for pid, v in spans.items() for s in v]
    n_occ = len(span_occurrences)
    n_occ_flagged = sum(1 for pid, surf in span_occurrences if span_flag.get(surf))

    # ---- overlap with the known-absent golds -------------------------------
    def naming_spans(gold):
        gn = H._norm(gold)
        out = []
        for surf in span_surfaces:
            sn = H._norm(surf)
            if sn in gn or gn in sn or sn.split(",")[0] == gn.split(",")[0]:
                out.append(surf)
        return out

    known_detail = []
    correctly_flagged_surface_absent = 0
    missed_entity_absent_surface_present = 0
    for gold in KNOWN_ABSENT_GOLDS:
        ns = naming_spans(gold)
        rows = []
        for surf in ns:
            resolved_idx = resolve_span(surf)
            flged = span_flag[surf]
            rows.append({"span": surf, "flagged_absent": flged,
                         "resolves_to": (meta[resolved_idx]["name"] if resolved_idx is not None else None)})
            if flged:
                correctly_flagged_surface_absent += 1
            else:
                missed_entity_absent_surface_present += 1
        known_detail.append({
            "gold": gold, "gold_in_graph_exact": H._norm(gold) in set(name_norms),
            "naming_spans": rows,
            "any_naming_span_flagged": any(r["flagged_absent"] for r in rows)})

    n_known_naming_spans = correctly_flagged_surface_absent + missed_entity_absent_surface_present
    # precision here = of the spans that name a known-absent gold, the fraction the flag
    # correctly marks absent. Misses are the honest TITLE-vs-SPAN gap: a wrong same-name
    # node makes the surface resolvable even though the specific gold entity is absent.
    flag_precision_on_known = (round(correctly_flagged_surface_absent / n_known_naming_spans, 4)
                               if n_known_naming_spans else None)
    golds_with_a_flagged_span = sum(1 for d in known_detail if d["any_naming_span_flagged"])

    # =====================================================================
    #  verdict
    # =====================================================================
    lands = gauge_ok  # r0 == 288 and v2 == 313 (and v3 == 314) reproduced
    verdict = "LANDS" if lands else "DEFECT-NON-REPRODUCTION"
    why = ("gauge reproduces medium r0 288/326, v2 313/326 and v3 314/326 exactly; rung "
           "curve reported medium-only (scout unavailable, reason stated); absent-anchor "
           "flag precision on the known-absent set stated"
           if lands else
           "GAUGE DID NOT REPRODUCE a pinned point - see gauge_sanity; this is a defect "
           "finding in the standing instrument, not a data result")

    payload = {
        "hypothesis": "R56-H638",
        "run_id": run_id,
        "consumes": "R56-H635 goldjoin-v3 (CONFIRMED-SPIRIT: gate ship-safe)",
        "substrate": ("medium 2wiki (6,626 entities), frozen H582 offline cache "
                      "tmp/results/r47 + R50 H597 span cache; FREE numpy/scipy/stdlib"),
        "join_versions_stamped": ["r0-exact", "goldjoin-v2-20260724", "goldjoin-v3-20260724"],
        "gauge_sanity": gauge_sanity,
        "gauge_sanity_ok": gauge_ok,
        "gauge_definition": ("per rung: count of the 326 gold carrier rows that RESOLVE to "
                             "a graph node under a stamped join (r0 = exact in-graph; v2/v3 "
                             "= exact + ACCEPTED ladder resolution); pairs, never blended"),
        "rung_curve": rung_curve,
        "absent_anchor_flag": {
            "definition": ("a GLiNER span is flagged ABSENT when the plain ladder "
                           "(r0 exact / r1 paren-strip / r2 fold / r3 fuzzy>=0.92) returns "
                           "no graph node - the honest NIL case, absent not ambiguous"),
            "n_distinct_span_surfaces": len(span_surfaces),
            "n_flagged_absent_surfaces": len(flagged),
            "flagged_surface_rate": round(len(flagged) / len(span_surfaces), 4),
            "n_span_occurrences": n_occ,
            "n_span_occurrences_flagged": n_occ_flagged,
            "flagged_surfaces": flagged,
            "known_absent_set": KNOWN_ABSENT_GOLDS,
            "known_absent_overlap": known_detail,
            "n_known_naming_spans": n_known_naming_spans,
            "flag_precision_on_known": flag_precision_on_known,
            "flag_precision_definition": (
                "of the spans that NAME a known-absent gold, the fraction the flag marks "
                "absent; a MISS means a wrong same-name node made the surface resolvable "
                "even though the specific gold entity is absent (the TITLE-vs-SPAN gap)"),
            "correctly_flagged_surface_absent": correctly_flagged_surface_absent,
            "missed_entity_absent_surface_present": missed_entity_absent_surface_present,
            "known_golds_with_a_flagged_naming_span": golds_with_a_flagged_span,
            "title_vs_span_note": (
                "gold TITLES and question SPANS are different objects: e.g. the gold "
                "'Aleksander Koniecpolski (1620-1659)' is absent, but the span "
                "'Aleksander Koniecpolski' resolves to a same-name node (the elder "
                "namesake) so it is NOT flagged; the flag detects SURFACE absence, not "
                "wrong-entity absence"),
        },
        "verdict": verdict,
        "verdict_reason": why,
        "script": "scripts/experiments/r56_h638_recall_gauge.py",
    }
    p = OUT / f"h638-recall-gauge-{run_id}.json"
    p.write_text(json.dumps(payload, indent=1))

    log(f"GAUGE medium: r0 {med['r0']}/326  v2 {med['v2']}/326  v3 {med['v3']}/326  "
        f"(reproduces pins: {gauge_ok})")
    log(f"rung curve: {rung_curve['curve_status']} - {scout_reason}")
    log(f"FLAG: {len(flagged)}/{len(span_surfaces)} span surfaces flagged absent; "
        f"{n_occ_flagged}/{n_occ} occurrences")
    log(f"known-absent overlap: {n_known_naming_spans} naming spans, "
        f"{correctly_flagged_surface_absent} correctly flagged, "
        f"{missed_entity_absent_surface_present} missed (surface present); "
        f"precision_on_known {flag_precision_on_known}")
    log(f"\nVERDICT {verdict}: {why}")
    log(f"wrote {p}")


if __name__ == "__main__":
    main()

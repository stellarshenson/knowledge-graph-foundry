"""R49-H560 / H561: repair-at-ingest carrier availability, deterministic offline replay.

H560 - is the CORRECT carrier already present in the prefix-graph at ingest time?
  Clock = KGFDocument.created_at (ms epoch) ascending -> per-doc ingest index.
  present-at-ingest := (correct carrier entity's first-appearance doc index) <= (repair doc index).
  Correct carrier: name_match rows -> ledger `entity` id; fallback rows -> gold_carrier.

H561 - does restricting carrier selection to the just-extracted same-doc entity set
  (entities MENTIONED_IN the repair doc's chunk) resolve the 12 fallback cases via the
  deterministic name-match convention from r49_carrier_bakeoff.py
  (name_in_win = entity_name.lower() in window.lower(); window = "<doc_title>. <span>")?
  A case resolves := name-match yields EXACTLY the gold carrier (unique match == gold;
  a tie or wrong pick = fail; for gold=null artifacts, zero matches = correct abstain).
  Secondary: the bakeoff's H569 anchor tie-break (longest matched name) reported for color.

Graph: R45 pilot pile bolt://172.19.0.101:7687 (read-only, MATCH/RETURN only).
Usage: .venv/bin/python scripts/experiments/r49_h560_rai_avail.py
Writes: reports/experiments/r49/h560-rai-avail-<ts>.json, h561-rai-samedoc-<ts>.json
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase

BOLT = "bolt://172.19.0.101:7687"
AUTH = ("neo4j", "kgfoundry")
GOLD = Path("reports/experiments/r49/carrier-gold-12.json")
LEDGER = Path("reports/experiments/r45/repair-ledger.jsonl")
OUTDIR = Path("reports/experiments/r49")


def window(case: dict) -> str:
    return f"{case.get('doc_title','')}. {case.get('span','')}"


def main() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    gold = json.loads(GOLD.read_text())["cases"]
    ledger = [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]
    repairs = [r for r in ledger if r.get("carrier_selection") in ("name_match", "fallback_largest")]
    n_name = sum(r["carrier_selection"] == "name_match" for r in repairs)
    n_fb = sum(r["carrier_selection"] == "fallback_largest" for r in repairs)
    uniq_facts = len({r["fact"] for r in repairs})

    d = GraphDatabase.driver(BOLT, auth=AUTH)
    with d.session() as s:
        # ingest clock: doc id -> ingest index by created_at asc
        docs = s.run("MATCH (n:KGFDocument) RETURN n.id AS id, n.created_at AS ca").data()
        order = sorted(docs, key=lambda x: (x["ca"], x["id"]))
        idx = {r["id"]: i for i, r in enumerate(order)}
        name_of = {r["id"]: None for r in docs}
        for r in s.run("MATCH (n:KGFDocument) RETURN n.id AS id, n.name AS nm").data():
            name_of[r["id"]] = r["nm"]

        def first_idx_by_entity_id(eid):
            rows = s.run(
                "MATCH (e:Entity {id:$eid})-[:MENTIONED_IN]->(:Chunk)-[:PART_OF]->(dd:KGFDocument) "
                "RETURN collect(DISTINCT dd.id) AS docs", eid=eid).single()["docs"]
            idxs = [idx[x] for x in rows if x in idx]
            return (min(idxs) if idxs else None), rows

        def resolve_gold_entity(doc_id, gold_name):
            # exact name within same-doc set first, then global exact name
            r = s.run(
                "MATCH (e:Entity {name:$nm})-[:MENTIONED_IN]->(:Chunk)-[:PART_OF]->(dd:KGFDocument {id:$doc}) "
                "RETURN e.id AS id LIMIT 1", nm=gold_name, doc=doc_id).single()
            if r:
                return r["id"], "samedoc_exact"
            r = s.run("MATCH (e:Entity {name:$nm}) RETURN e.id AS id LIMIT 1", nm=gold_name).single()
            return (r["id"], "global_exact") if r else (None, "unresolved")

        # ---------------- H560 ----------------
        h560_rows = []
        for r in repairs:
            doc_id = r["doc"]
            rep_idx = idx.get(doc_id)
            sel = r["carrier_selection"]
            if sel == "name_match":
                carrier_name = r.get("entity_name")
                fi, mdocs = first_idx_by_entity_id(r["entity"])
                gold_class = None
                resolve = "ledger_entity_id"
            else:  # fallback_largest -> use gold carrier
                gc = next((c for c in gold if c["doc"] == doc_id and c["fact"] == r["fact"]), None)
                if gc is None:  # fall back to matching by doc only
                    gc = next((c for c in gold if c["doc"] == doc_id), None)
                gold_class = gc["gold_class"] if gc else None
                carrier_name = gc["gold_carrier"] if gc else None
                if carrier_name is None:
                    fi, mdocs, resolve = None, [], "artifact_no_carrier"
                else:
                    eid, resolve = resolve_gold_entity(doc_id, carrier_name)
                    fi, mdocs = first_idx_by_entity_id(eid) if eid else (None, [])
            present = (fi is not None and rep_idx is not None and fi <= rep_idx)
            h560_rows.append({
                "fact": r["fact"][:70], "doc": doc_id, "doc_name": name_of.get(doc_id),
                "carrier_selection": sel, "correct_carrier": carrier_name,
                "gold_class": gold_class, "carrier_resolution": resolve,
                "repair_doc_idx": rep_idx, "carrier_first_idx": fi,
                "n_mention_docs": len(mdocs),
                "present_at_ingest": bool(present) if carrier_name is not None else None,
            })

        # ---------------- H561 ----------------
        h561_rows = []
        samedoc_cache = {}
        for c in gold:
            doc_id = c["doc"]
            if doc_id not in samedoc_cache:
                ents = s.run(
                    "MATCH (e:Entity)-[:MENTIONED_IN]->(:Chunk)-[:PART_OF]->(dd:KGFDocument {id:$doc}) "
                    "RETURN DISTINCT e.name AS name", doc=doc_id).data()
                samedoc_cache[doc_id] = sorted({e["name"] for e in ents})
            cand = samedoc_cache[doc_id]
            win = window(c).lower()
            matched = [nm for nm in cand if nm.lower() in win]
            gold_name = c["gold_carrier"]
            # strict: unique match == gold (or, for gold=null, zero matches)
            if gold_name is None:
                strict = (len(matched) == 0)
            else:
                strict = (len(matched) == 1 and matched[0].lower() == gold_name.lower())
            # anchor tie-break (H569): longest matched name
            anchor = max(matched, key=len) if matched else None
            if gold_name is None:
                anchor_ok = anchor is None
            else:
                anchor_ok = anchor is not None and anchor.lower() == gold_name.lower()
            gold_in_match = (gold_name is None and not matched) or (
                gold_name is not None and any(m.lower() == gold_name.lower() for m in matched))
            h561_rows.append({
                "fact": c["fact"][:70], "doc": doc_id, "doc_title": c["doc_title"],
                "gold_carrier": gold_name, "gold_class": c["gold_class"],
                "n_samedoc_ents": len(cand), "name_matches": matched,
                "n_matches": len(matched),
                "strict_resolves": strict, "gold_in_matched_set": gold_in_match,
                "anchor_longest_pick": anchor, "anchor_resolves": anchor_ok,
            })
    d.close()

    # ---- H560 aggregates ----
    carrier_bearing = [r for r in h560_rows if r["correct_carrier"] is not None]
    artifacts = [r for r in h560_rows if r["correct_carrier"] is None]
    present_cb = sum(r["present_at_ingest"] for r in carrier_bearing)
    fb_rows = [r for r in h560_rows if r["carrier_selection"] == "fallback_largest"]
    fb_present = sum(bool(r["present_at_ingest"]) for r in fb_rows)
    pct_over47 = present_cb / len(repairs)
    pct_over_cb = present_cb / len(carrier_bearing)
    h560 = {
        "hypothesis": "R49-H560", "ts": ts, "graph": BOLT,
        "ingest_clock": "KGFDocument.created_at ascending (monotonic, graph-native; preferred over corpus-row order)",
        "corpus_composition": "pilot-200 (200) -> medium-rows200-999 (800) -> full-rows1000-6118 (173) = 1173 docs",
        "counts": {"repair_rows": len(repairs), "name_match": n_name, "fallback_largest": n_fb,
                   "unique_facts": uniq_facts, "carrier_bearing": len(carrier_bearing),
                   "artifact_no_carrier": len(artifacts)},
        "clause_A_all_repairs": {
            "predicted": ">= 85% of 47 repairs have correct carrier present-at-ingest",
            "present_count": present_cb, "denominator_47": len(repairs),
            "pct_over_47_strict": round(pct_over47, 4),
            "denominator_carrier_bearing": len(carrier_bearing),
            "pct_over_carrier_bearing": round(pct_over_cb, 4)},
        "clause_B_fallback12": {
            "predicted": ">= 6/12 fallback cases have correct carrier present-at-ingest",
            "present_count": fb_present, "denominator": len(fb_rows)},
        "rows": h560_rows,
    }
    # ---- H561 aggregates ----
    strict_n = sum(r["strict_resolves"] for r in h561_rows)
    anchor_n = sum(r["anchor_resolves"] for r in h561_rows)
    recall_n = sum(r["gold_in_matched_set"] for r in h561_rows)
    h561 = {
        "hypothesis": "R49-H561", "ts": ts, "graph": BOLT,
        "name_match_convention": "name_in_win = entity_name.lower() in window.lower(); window = '<doc_title>. <span>' (r49_carrier_bakeoff.py)",
        "resolve_definition": "strict: unique name-match == gold (or zero matches for gold=null artifact)",
        "counts": {"n_cases": len(h561_rows)},
        "clause": {
            "predicted": ">= 8/12 resolve correctly under same-doc name-match",
            "strict_resolves": strict_n, "denominator": len(h561_rows),
            "anchor_longest_tiebreak_resolves": anchor_n,
            "gold_present_in_matched_set": recall_n},
        "rows": h561_rows,
    }

    OUTDIR.mkdir(parents=True, exist_ok=True)
    p560 = OUTDIR / f"h560-rai-avail-{ts}.json"
    p561 = OUTDIR / f"h561-rai-samedoc-{ts}.json"
    p560.write_text(json.dumps(h560, indent=1, ensure_ascii=False))
    p561.write_text(json.dumps(h561, indent=1, ensure_ascii=False))
    print("H560 present/47:", present_cb, "/", len(repairs),
          f"({pct_over47:.1%}); over carrier-bearing {present_cb}/{len(carrier_bearing)} ({pct_over_cb:.1%})")
    print("H560 fallback present:", fb_present, "/", len(fb_rows))
    print("H561 strict resolves:", strict_n, "/", len(h561_rows),
          "| anchor-longest:", anchor_n, "/", len(h561_rows),
          "| gold-in-set:", recall_n, "/", len(h561_rows))
    print("WROTE", p560)
    print("WROTE", p561)


if __name__ == "__main__":
    main()

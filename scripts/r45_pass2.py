"""R45/H450 pass-2 differential: targeted re-extraction of ABSENT-miss documents.

Stage A (H450 verdict): every unique ABSENT (doc, miss) pair across the H448
decompositions gets its document re-extracted ONCE (live engine, cured
ontology, production extract_chunk); each miss fact is tested against the
FRESH EMISSIONS with the certificate term-share rule (>= 0.8). Prediction:
>= 30% of true misses appear on pass 2 (R22-H231 economics).

Stage B (R45 differential substrate): all pass-2 emissions for the target
documents load through the production post-cure path (_embed + _stable_load,
resolution against the live graph) so the post-pass-2 dump + metric sweep can
price the differential. Pre-pass-2 state = the post-repair REFERENCE graph.

Usage: python scripts/r45_pass2.py [--dry-run]   (--dry-run: Stage A only, no load)
Writes: results/r45/pass2-<ts>.jsonl (one record per miss: doc, fact, hit,
matched-in) + a stage-B load summary record.
"""

import glob
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from knowledge_graph_foundry import load_settings
from knowledge_graph_foundry.extraction.extractor import extract_chunk
from knowledge_graph_foundry.models import Chunk, Ontology
from knowledge_graph_foundry.pipeline import Foundry

sys.path.insert(0, str(Path(__file__).parent))
from r39_h389_coverage_audit import supported  # noqa: E402 - certificate term-share rule

CONFIG = Path("config/experiments/config-bench-pilot.yml")
OUT = Path("results/r45")
DECOMPS = "results/r44/h448-decomposition-*.jsonl"


def absent_targets() -> dict[str, list[str]]:
    seen: set[tuple[str, str]] = set()
    docs: dict[str, list[str]] = {}
    for fp in sorted(glob.glob(DECOMPS)):
        for line in open(fp):
            if not line.strip():
                continue
            r = json.loads(line)
            if r["class"] == "ABSENT" and (r["doc"], r["miss"]) not in seen:
                seen.add((r["doc"], r["miss"]))
                docs.setdefault(r["doc"], []).append(r["miss"])
    return docs


def emission_text(result) -> str:
    parts = []
    for e in result.entities:
        parts.append(e.name)
        parts.append(e.description or "")
        parts.append(json.dumps({k: v for k, v in (e.properties or {}).items() if isinstance(v, str)}))
    by_id = {e.id: e.name for e in result.entities}
    for r in result.relationships:
        parts.append(f"{by_id.get(r.source_id, '')} {r.type} {by_id.get(r.target_id, '')}")
    return " ".join(parts)


def main():
    dry_run = "--dry-run" in sys.argv
    targets = absent_targets()
    n_facts = sum(len(v) for v in targets.values())
    print(f"pass-2 targets: {n_facts} ABSENT facts across {len(targets)} docs (dry_run={dry_run})", flush=True)

    st = load_settings(CONFIG)
    st.event_log = None
    OUT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = OUT / f"pass2-{ts}.jsonl"

    with Foundry(st) as f, f.driver.session() as s, out_path.open("w") as fh:
        state = f._load_state()
        if not state or not state.get("ontology"):
            raise SystemExit("no cured ontology on the target instance")
        ontology = Ontology(**state["ontology"])
        purpose = state.get("purpose", "")
        calibrator = f._make_calibrator(state)
        engine = f.extraction_engine

        chunk_rows = []
        for doc_id in targets:
            rows = s.run(
                "MATCH (c:Chunk)-[:PART_OF]->(d:KGFDocument {id: $d}) "
                "RETURN c.id AS id, c.index AS idx, c.text AS text",
                d=doc_id,
            ).data()
            for r in rows:
                chunk_rows.append(Chunk(
                    id=r["id"], document_id=doc_id, index=r["idx"] or 0,
                    text=r["text"] or "", token_count=len((r["text"] or "").split()),
                ))
        print(f"re-extracting {len(chunk_rows)} chunks", flush=True)

        def one(chunk):
            return chunk.document_id, extract_chunk(chunk, purpose, ontology, engine, st.extraction)

        by_doc: dict[str, list] = {}
        with ThreadPoolExecutor(max_workers=8) as pool:
            for doc_id, res in pool.map(one, chunk_rows):
                by_doc.setdefault(doc_id, []).append(res)

        hits = 0
        for doc_id, misses in targets.items():
            text = " ".join(emission_text(r) for r in by_doc.get(doc_id, []))
            for miss in misses:
                hit = supported(miss, text)
                hits += hit
                fh.write(json.dumps({"doc": doc_id, "fact": miss, "pass2_hit": bool(hit)}) + "\n")
        rate = hits / n_facts if n_facts else 0.0
        print(f"H450: {hits}/{n_facts} = {rate * 100:.1f}% of ABSENT misses in fresh emissions (bar >= 30%)", flush=True)

        loaded = {"docs": 0, "entities": 0, "relationships": 0}
        if not dry_run:
            for doc_id, results in by_doc.items():
                ents = [e for r in results for e in r.entities]
                rels = [rel for r in results for rel in r.relationships]
                if not ents:
                    continue
                ents = f._embed(ents)
                f._stable_load(ents, rels, ontology, calibrator)
                loaded["docs"] += 1
                loaded["entities"] += len(ents)
                loaded["relationships"] += len(rels)
            print(f"stage B loaded: {loaded}", flush=True)
        fh.write(json.dumps({"summary": True, "hits": hits, "total": n_facts,
                             "rate": round(rate, 4), "loaded": loaded, "ts": ts}) + "\n")
    print(f"PASS-2 COMPLETE -> {out_path}", flush=True)


if __name__ == "__main__":
    main()

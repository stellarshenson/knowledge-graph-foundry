"""R32-H354 CENSUS GATE: weigh the chunking failure classes before changing any splitter.

Offline, no GPU. Classifies every gold-evidence string of every FAILED probe
(freshest per-probe recall map) into the registered failure classes:

  (i)   in-chunk emission miss - gold has carrier chunks; extraction misses it
        (split deterministic/stochastic using the H353 6-pass emission record)
  (ii)  seam-straddling - gold present in the raw document, absent from every chunk
  (iii) no co-occurrence window - a multi-evidence probe whose golds never share a chunk
  (iv)  subject-sparsity - gold absent from BOTH document text and chunks (H21 class:
        named once/nowhere, referenced pronominally)
  (v)   table-severed - gold inside a table region whose table spans a chunk boundary

Mass accounting: each failed probe contributes (1 - recall) failure mass, split
equally across its gold strings; a gold's mass lands on its class. GATE (registered):
each R32 hypothesis runs only if its target class carries >= 10% of residual mass.

Output: reports/experiments/adjudicated/r32-h354-census-<ts>.json + printed class table.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, "notebooks")
from h158_measure import _present  # noqa: E402 - the harness's own matcher

from knowledge_graph_foundry.ingest.chunking import _find_tables, chunk_document  # noqa: E402
from knowledge_graph_foundry.ingest.readers import iter_source_files, read_document  # noqa: E402
from knowledge_graph_foundry.settings import load_settings  # noqa: E402

CONFIG = Path("config/experiments/config-r29-v1.yml")
CORPUS = Path("data/external/cpap-datasheets-and-manuals")
PROBES = Path("tests/probes/cpap-probe-set.yml")
RECALL_REPORT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports/experiments/adjudicated/h212-v2-recall-rerun.json")  # freshest per-probe map
H353_CHUNKS = Path("tmp/results/r31/h353-chunks.jsonl")  # 6-pass emission record


def main():
    settings = load_settings(CONFIG)
    ex = settings.extraction

    docs = {}  # doc text by source filename
    chunks = []  # (chunk, source filename)
    for f in iter_source_files(CORPUS):
        if f.suffix.lower() != ".pdf":
            continue
        try:
            doc = read_document(f, parser_union=ex.parser_union, glyph_normalization=ex.glyph_normalization)
            docs[f.name] = doc.text
            for ch in chunk_document(doc, ex.chunk_size, ex.chunk_overlap, ex.header_carryover):
                chunks.append((ch, f.name))
        except Exception as exc:
            print(f"skip {f.name}: {exc}", flush=True)
    print(f"pool: {len(chunks)} chunks, {len(docs)} documents", flush=True)

    probes = {p["id"]: p for p in yaml.safe_load(PROBES.read_text()) if p.get("gold_evidence")}
    per_probe = json.load(RECALL_REPORT.open())["per_probe"]
    failed = {pid: 1 - r for pid, r in per_probe.items() if r < 1.0 and pid in probes}
    print(f"failed probes: {sorted(failed)} (mass {sum(failed.values()):.2f})", flush=True)

    emission = {}  # gold -> emitted-in-k-of-6-passes (max over chunks), from H353
    if H353_CHUNKS.exists():
        records = [json.loads(x) for x in H353_CHUNKS.read_text().splitlines()]
        all_golds = {g for p in probes.values() for g in p["gold_evidence"]}
        for g in all_golds:
            best = 0
            for r in records:
                hits = sum(1 for p in r["passes"] if _present(g, p["emission"]))
                best = max(best, hits)
            emission[g] = best

    def classify(gold: str, probe: dict) -> str:
        carriers = [(ch, src) for ch, src in chunks if _present(gold, ch.text)]
        in_docs = [name for name, text in docs.items() if _present(gold, text)]
        if carriers:
            # co-occurrence check for multi-evidence probes: any chunk carrying
            # this gold AND a sibling gold?
            sibs = [g for g in probe["gold_evidence"] if g != gold]
            if sibs and not any(
                any(_present(s, ch.text) for s in sibs) for ch, _ in chunks
                if _present(gold, ch.text)
            ):
                # intra- vs cross-document: chunking can only co-window golds
                # that share a document; comparison probes spanning documents
                # are retrieval-side, unreachable by any splitter
                same_doc = any(
                    _present(gold, text) and any(_present(s, text) for s in sibs)
                    for text in docs.values()
                )
                return "iii_no_cooccurrence_intradoc" if same_doc else "iii_cross_document"
            k = emission.get(gold)
            if k == 0:
                return "i_emission_deterministic"
            if k is not None and k < 6:
                return "i_emission_stochastic"
            return "i_emission_covered"  # carried + always emitted: failure is downstream of extraction
        if in_docs:
            # in document, in no chunk: severed - table or plain seam?
            for name in in_docs:
                for t in _find_tables(docs[name]):
                    seg = "\n".join([t["header"], t["separator"], *t["rows"]])
                    if _present(gold, seg):
                        return "v_table_severed"
            return "ii_seam_straddled"
        # absent from every extracted document text: the READER never produced
        # it - parse/glyph loss, upstream of chunking (true class-iv subject
        # sparsity would need the gold present in the doc but only pronominal
        # in chunks; zero such cases distinguish themselves here)
        return "parse_loss_reader"

    masses, detail = {}, []
    for pid, mass in sorted(failed.items()):
        golds = probes[pid]["gold_evidence"]
        share = mass / len(golds)
        for g in golds:
            cls = classify(g, probes[pid])
            masses[cls] = masses.get(cls, 0.0) + share
            detail.append({"probe": pid, "gold": g, "class": cls, "mass": round(share, 3)})
            print(f"  {pid} [{cls}] {g!r} (+{share:.3f})", flush=True)

    total = sum(masses.values())
    print("\nCLASS MASSES (share of residual failure mass):", flush=True)
    for cls, m in sorted(masses.items(), key=lambda kv: -kv[1]):
        print(f"  {cls:28s} {m:.3f}  ({m / total:.1%})", flush=True)

    gates = {
        "H355_size (i stochastic+deterministic)": ["i_emission_deterministic", "i_emission_stochastic"],
        "H356_doc_relation_pass (iii intra-doc)": ["iii_no_cooccurrence_intradoc"],
        "H357_subject_injection (iv)": ["iv_subject_sparsity"],
        "H358_coref_escalation (iv)": ["iv_subject_sparsity"],
        "H359_sat_boundaries (ii)": ["ii_seam_straddled"],
        "H360_atomic_tables (v)": ["v_table_severed"],
        "H361_section_windows (ii + iii intra-doc)": ["ii_seam_straddled", "iii_no_cooccurrence_intradoc"],
    }
    verdicts = {}
    print("\nGATE VERDICTS (>= 10% of residual mass to live):", flush=True)
    for hyp, classes in gates.items():
        share = sum(masses.get(c, 0.0) for c in classes) / total if total else 0.0
        verdicts[hyp] = {"share": round(share, 4), "lives": share >= 0.10}
        print(f"  {hyp:44s} {share:6.1%}  -> {'LIVES' if share >= 0.10 else 'KILLED'}", flush=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/experiments/adjudicated/r32-h354-census-{ts}.json")
    out.write_text(
        json.dumps(
            {
                "hypothesis": "R32-H354",
                "generated": ts,
                "recall_report": str(RECALL_REPORT),
                "failed_probes": {k: round(v, 3) for k, v in failed.items()},
                "class_masses": {k: round(v, 4) for k, v in masses.items()},
                "gate_verdicts": verdicts,
                "detail": detail,
            },
            indent=2,
        )
    )
    print(f"\nH354 CENSUS COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

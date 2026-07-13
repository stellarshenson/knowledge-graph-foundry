"""R39-H389: extraction-coverage certificate - the graph measures what it missed.

Per-document audit (KGGen-MINE pattern, ODKE+ Grounder check):
  1. FACT PROBES - for each chunk of a document, the LLM generates k short,
     verbatim-grounded fact statements from the chunk text alone; each probe
     is groundedness-gated (every content token of the probe must appear in
     the chunk text after normalization) - ungrounded generations are
     discarded, so the probe set cannot hallucinate the source
  2. SUPPORT TEST - each surviving probe is tested against the graph:
     direct support = the probe's key terms are covered by the document's
     entity names/descriptions/properties or its passage spans; entailment
     support (optional, LLM) adjudicates the remainder in a later arm
  3. CERTIFICATE - per-document coverage = supported / probes, plus the
     named miss list -> reports/experiments/r39/h389-coverage-<pile>.jsonl and the gap
     ledger; the acceptance bar checks reproducibility (+-2%) and that known
     failure classes are rediscovered blind

The deterministic gates and the certificate computation now live in
`knowledge_graph_foundry.graph.audit`; this script drives them over a live
graph. The gate names are re-exported for the coverage-audit unit test.

Usage: python scripts/experiments/r39_h389_coverage_audit.py <config.yml> [doc_limit]
Runs AT SCALE BOUNDARIES (not during ingest - the generator contends for
the same LLM the extractor saturates).
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from knowledge_graph_foundry import load_settings
from knowledge_graph_foundry.engines import create_engine
from knowledge_graph_foundry.graph.audit import (  # noqa: F401  (re-exported for tests)
    PROBES_PER_CHUNK,
    content_terms,
    corpus_summary,
    document_certificate,
    generate_probes,
    grounded,
    supported,
)
from knowledge_graph_foundry.pipeline import Foundry

DEFAULT_CONFIG = Path("config/experiments/config-bench-pilot.yml")
OUT = Path("reports/experiments/r39")


def doc_graph_texts(session, doc_id: str) -> tuple[str, str]:
    """Two SEPARATE support corpora (adversarial finding A5/D1/M1: spans
    tile the full chunk text, so groundedness-gated probes are span-supported
    BY CONSTRUCTION - folding them together makes coverage ~1.0 tautologically).
    Returns (entity_text, span_text); the CERTIFICATE keys on entity_text."""
    ents = session.run(
        "MATCH (e:Entity) WHERE $d IN e.source_documents "
        "RETURN e.name AS n, e.description AS de, properties(e) AS p",
        d=doc_id,
    ).data()
    spans = session.run(
        "MATCH (p:KGFPassage)-[:PART_OF]->(:Chunk)-[:PART_OF]->(:KGFDocument {id: $d}) "
        "RETURN p.text AS t",
        d=doc_id,
    ).value()
    parts = []
    for e in ents:
        parts.append(e["n"] or "")
        parts.append(e["de"] or "")
        parts.append(json.dumps({k: v for k, v in (e["p"] or {}).items() if isinstance(v, str)}))
    return " ".join(parts), " ".join(t or "" for t in spans)


def main():
    config = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONFIG
    doc_limit = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    st = load_settings(config)
    st.event_log = None
    engine = create_engine(st.llm)
    OUT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = OUT / f"h389-coverage-{ts}.jsonl"

    with Foundry(st) as f, f.driver.session() as s:
        docs = s.run(
            "MATCH (c:Chunk)-[:PART_OF]->(d:KGFDocument) "
            "RETURN d.id AS id, d.name AS name, collect(c.text) AS chunks "
            "ORDER BY d.id LIMIT $n",
            n=doc_limit,
        ).data()
        print(f"auditing {len(docs)} documents from {config}", flush=True)
        certs = []
        for i, doc in enumerate(docs):
            ent_text, span_text = doc_graph_texts(s, doc["id"])
            probes = []
            for chunk in doc["chunks"]:
                probes.extend(generate_probes(engine, chunk))
            # ENTITY/PROPERTY support - the certificate metric
            cert = document_certificate(probes, ent_text)
            span_supported = sum(supported(p, span_text) for p in probes)
            certs.append(cert)
            rec = {
                "doc": doc["id"],
                "name": doc["name"],
                "probes": cert["probes"],
                "coverage": cert["coverage"],
                "span_coverage": (
                    round(span_supported / cert["probes"], 4) if cert["probes"] else None
                ),
                "misses": cert["missing_spans"],
            }
            with out_path.open("a") as fh:
                fh.write(json.dumps(rec) + "\n")
            print(
                f"[{i + 1}/{len(docs)}] {doc['name']}: coverage={cert['coverage']} "
                f"span_cov={rec['span_coverage']} misses={len(cert['missing_spans'])}",
                flush=True,
            )
        summary = corpus_summary(certs)
        print(
            f"H389 AUDIT COMPLETE: overall coverage {summary['coverage']} "
            f"({summary['supported']}/{summary['probes']}) -> {out_path}",
            flush=True,
        )


if __name__ == "__main__":
    main()

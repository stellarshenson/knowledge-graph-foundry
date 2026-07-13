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

Usage: python scripts/experiments/r39_h389_coverage_audit.py <config.yml> [doc_limit]
Runs AT SCALE BOUNDARIES (not during ingest - the generator contends for
the same LLM the extractor saturates).
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from knowledge_graph_foundry import load_settings
from knowledge_graph_foundry.engines import create_engine
from knowledge_graph_foundry.pipeline import Foundry

DEFAULT_CONFIG = Path("config/experiments/config-bench-pilot.yml")
PROBES_PER_CHUNK = 5
OUT = Path("reports/experiments/r39")

_STOP = frozenset(
    "a an the of in on at to for with and or is are was were be been has have had by from as its it this that".split()
)


def _norm_terms(s: str) -> str:
    # NOTE: strips non-alphanumerics (term matching) - deliberately DIFFERENT
    # from notebooks/h158_measure._norm which only squeezes whitespace
    return re.sub(r"[^a-z0-9 ]", " ", s.lower())


def content_terms(s: str) -> list[str]:
    # numeric tokens kept regardless of length - spec-value misses (the P08
    # '9.0W' class) are exactly short numerics (adversarial finding A4/D-minor)
    return [
        t for t in _norm_terms(s).split()
        if t not in _STOP and (len(t) > 2 or any(ch.isdigit() for ch in t))
    ]


def grounded(probe: str, chunk_text: str) -> bool:
    """Groundedness gate: every content term of the probe appears in the
    chunk - the probe set cannot claim what the source does not say."""
    chunk_terms = set(_norm_terms(chunk_text).split())
    terms = content_terms(probe)
    return bool(terms) and all(t in chunk_terms for t in terms)


def supported(probe: str, graph_text: str, threshold: float = 0.8) -> bool:
    """Direct support test: share of the probe's content terms present in
    the document's graph rendering (entities + properties + spans)."""
    terms = content_terms(probe)
    if not terms:
        return False
    graph_terms = set(_norm_terms(graph_text).split())
    return sum(t in graph_terms for t in terms) / len(terms) >= threshold


GEN_SYSTEM = (
    "You extract short factual statements from text. Each statement must use ONLY "
    "words that literally appear in the given text - no paraphrase, no synonyms, no "
    "inference. One statement per line, no numbering, at most {k} statements."
)


def generate_probes(engine, chunk_text: str, k: int = PROBES_PER_CHUNK) -> list[str]:
    raw = engine.complete_text(
        GEN_SYSTEM.format(k=k),
        f"Text:\n{chunk_text}\n\nStatements (verbatim words only):",
    )
    probes = [ln.strip("-* ").strip() for ln in raw.splitlines() if ln.strip()]
    return [p for p in probes if grounded(p, chunk_text)][:k]


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
        total_probes = total_supported = 0
        for i, doc in enumerate(docs):
            ent_text, span_text = doc_graph_texts(s, doc["id"])
            probes, misses = [], []
            span_supported = 0
            for chunk in doc["chunks"]:
                for p in generate_probes(engine, chunk):
                    probes.append(p)
                    if supported(p, ent_text):
                        total_supported += 1
                    else:
                        misses.append(p)
                    if supported(p, span_text):
                        span_supported += 1
            total_probes += len(probes)
            coverage = round(1 - len(misses) / len(probes), 4) if probes else None
            rec = {
                "doc": doc["id"],
                "name": doc["name"],
                "probes": len(probes),
                "coverage": coverage,  # ENTITY/PROPERTY support - the certificate metric
                "span_coverage": round(span_supported / len(probes), 4) if probes else None,
                "misses": misses,
            }
            with out_path.open("a") as fh:
                fh.write(json.dumps(rec) + "\n")
            print(f"[{i+1}/{len(docs)}] {doc['name']}: coverage={coverage} span_cov={rec['span_coverage']} misses={len(misses)}", flush=True)
        overall = round(total_supported / total_probes, 4) if total_probes else None
        print(f"H389 AUDIT COMPLETE: overall coverage {overall} ({total_supported}/{total_probes}) -> {out_path}", flush=True)


if __name__ == "__main__":
    main()

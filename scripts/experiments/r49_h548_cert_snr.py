"""R49-H548: certificate SNR - can the H389 coverage certificate's per-doc
signal be separated from its per-doc measurement noise?

Runs N independent recomputes of the H389 coverage certificate over a FROZEN
graph (identical doc set every pass; the graph rendering is cached once so the
ONLY variance source is the judge LLM). Per-doc coverage std across the N
recomputes = per-doc measurement noise; compared offline against the per-doc
repair lift derived from the R45 pile to decide whether an ingest gate keyed on
the certificate can tell needs-repair from noise at per-doc granularity.

READ-ONLY on Neo4j (MATCH only). Certificate machinery is imported verbatim
from scripts/experiments/r39_h389_coverage_audit.py so a recompute matches the
reference certificate exactly - the deviation from the reference is solely the
outer N-recompute loop and the cached graph rendering.

Usage: python scripts/experiments/r49_h548_cert_snr.py <config.yml> <N> [doc_limit]
"""

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from knowledge_graph_foundry import load_settings
from knowledge_graph_foundry.engines import create_engine
from knowledge_graph_foundry.pipeline import Foundry

# import the r39 certificate machinery verbatim (module has no import side effects)
_R39 = Path("scripts/experiments/r39_h389_coverage_audit.py")
_spec = importlib.util.spec_from_file_location("r39_audit", _R39)
r39 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r39)

OUT = Path("reports/experiments/r49")


def main():
    config = Path(sys.argv[1])
    n_recompute = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    doc_limit = int(sys.argv[3]) if len(sys.argv) > 3 else 50
    st = load_settings(config)
    st.event_log = None
    engine = create_engine(st.llm)
    OUT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = OUT / f"h548-recompute-{ts}.jsonl"
    print(
        f"H548 cert-SNR: N={n_recompute} recomputes, doc_limit={doc_limit}, config={config}",
        flush=True,
    )
    print(f"checkpoint -> {out_path}", flush=True)

    with Foundry(st) as f, f.driver.session() as s:
        docs = s.run(
            "MATCH (c:Chunk)-[:PART_OF]->(d:KGFDocument) "
            "RETURN d.id AS id, d.name AS name, collect(c.text) AS chunks "
            "ORDER BY d.id LIMIT $n",
            n=doc_limit,
        ).data()
        print(f"frozen doc set: {len(docs)} documents", flush=True)
        # cache graph renderings ONCE - the graph is frozen, so doc_graph_texts is
        # deterministic; caching isolates the variance to the judge LLM alone
        graph_texts = {d["id"]: r39.doc_graph_texts(s, d["id"]) for d in docs}

        for rc in range(n_recompute):
            rc_probes = rc_supported = 0
            for doc in docs:
                ent_text, span_text = graph_texts[doc["id"]]
                probes, misses = [], []
                span_supported = 0
                for chunk in doc["chunks"]:
                    for p in r39.generate_probes(engine, chunk):
                        probes.append(p)
                        if r39.supported(p, ent_text):
                            rc_supported += 1
                        else:
                            misses.append(p)
                        if r39.supported(p, span_text):
                            span_supported += 1
                rc_probes += len(probes)
                coverage = round(1 - len(misses) / len(probes), 4) if probes else None
                rec = {
                    "recompute": rc,
                    "doc": doc["id"],
                    "name": doc["name"],
                    "probes": len(probes),
                    "coverage": coverage,
                    "span_coverage": round(span_supported / len(probes), 4) if probes else None,
                    "misses": misses,
                }
                with out_path.open("a") as fh:
                    fh.write(json.dumps(rec) + "\n")
            overall = round(rc_supported / rc_probes, 4) if rc_probes else None
            print(
                f"[recompute {rc + 1}/{n_recompute}] overall coverage={overall} "
                f"({rc_supported}/{rc_probes})",
                flush=True,
            )
    print(f"H548 RECOMPUTES COMPLETE -> {out_path}", flush=True)


if __name__ == "__main__":
    main()

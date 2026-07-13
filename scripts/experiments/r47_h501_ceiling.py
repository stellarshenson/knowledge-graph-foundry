"""R47-H501 retrieval ceiling gate: does dense@16 already cover GLiNER's carriers?

Pure set arithmetic, no LLM. For every eligible question: dense top-16 seeds
via the shipped vector index; gold carriers = gold-title entities in the
graph; GLiNER (urchade/gliner_multi-v2.1, the H260 asset) spans extracted
from the QUESTION text - a carrier is GLiNER-reachable when a span matches
its name (normalized containment either way). Carriers partition spec
(code-like: digits / model-code pattern) vs prose. Reported quantities:
dense carrier recall (overall/spec/prose), fraction of GLiNER-visible spec
carriers already inside dense top-16, and the achievable fused lift bound
|dense-miss AND GLiNER-reachable| / |gold carriers|.

Registered: docs/experiments/kgf-redesign-experiments.md R47-H501.
Bars: NULL CONFIRMED (retrieval domain closes) if bounded lift < +2.0 pts;
domain OPENS if dense spec-slice recall < 0.85. 2wiki is prose-heavy - an
empty/small spec slice is itself a finding and is reported, not hidden.

Usage: python scripts/experiments/r47_h501_ceiling.py [config] [questions.json] [max]
Writes: reports/experiments/r47/h501-ceiling-<ts>.json
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "notebooks")
sys.path.insert(0, "scripts/experiments")
from h158_measure import _norm  # noqa: E402
from r46_h499_screen import gold_titles, ingested_titles, load_slices  # noqa: E402

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.extraction import generate_embeddings  # noqa: E402
from knowledge_graph_foundry.models import Entity  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

CONFIG = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    "config/experiments/config-bench-medium.yml"
)
QUESTIONS = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
    "data/external/multihop-qa-benchmarks/2wikimultihopqa.json"
)
MAX = int(sys.argv[3]) if len(sys.argv) > 3 else 0

GLINER_MODEL = "urchade/gliner_multi-v2.1"
GLINER_LABELS = ["person", "organization", "location", "creative work", "date", "event"]
GLINER_THRESHOLD = 0.3
SPEC = re.compile(r"\d|[A-Z]{2,}\d|\b[A-Z]+-\d")


def reachable(carrier_norm: str, spans: list[str]) -> bool:
    return any(
        s == carrier_norm or s in carrier_norm or carrier_norm in s
        for s in spans
        if len(s) >= 3
    )


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    questions = json.loads(QUESTIONS.read_text())
    st = load_settings(CONFIG)
    st.event_log = None
    top_k = st.graphrag.top_k

    from gliner import GLiNER  # heavy import last

    print(f"h501 {run_id}: loading GLiNER {GLINER_MODEL}", flush=True)
    model = GLiNER.from_pretrained(GLINER_MODEL)

    carriers = []  # one row per (question, gold carrier)
    with Foundry(st) as f:
        with f.driver.session() as s:
            names = {_norm(r["name"]) for r in s.run("MATCH (e:Entity) RETURN e.name AS name")}
        titles = ingested_titles(f, load_slices())
        full = [
            q for q in questions if gold_titles(q) and all(t in titles for t in gold_titles(q))
        ]
        eligible = full[:MAX] if MAX else full
        print(f"{len(eligible)} eligible questions", flush=True)

        from knowledge_graph_foundry.graph.graphrag import vector_query  # noqa: E402

        for k, q in enumerate(eligible):
            qid = q.get("_id") or q["question"][:60]
            probe = Entity.create(q["question"][:80], types=["Query"], description=q["question"])
            qv = generate_embeddings([probe], st.embeddings)[0].embedding
            seeds = vector_query(f.driver, qv, st.graphrag.vector_index_name, top_k=top_k)
            seed_norms = {_norm(s["name"]) for s in seeds}
            spans = [
                _norm(e["text"])
                for e in model.predict_entities(
                    q["question"], GLINER_LABELS, threshold=GLINER_THRESHOLD
                )
            ]
            for t in gold_titles(q):
                tn = _norm(t)
                carriers.append(
                    {
                        "id": qid,
                        "carrier": t,
                        "in_graph": tn in names,
                        "spec": bool(SPEC.search(t)),
                        "dense_hit": tn in seed_norms,
                        "gliner_reachable": reachable(tn, spans),
                    }
                )
            if (k + 1) % 20 == 0:
                print(f"[{k+1}/{len(eligible)}] processed", flush=True)

    def recall(rows):
        return round(sum(r["dense_hit"] for r in rows) / len(rows), 4) if rows else None

    spec_rows = [c for c in carriers if c["spec"]]
    prose_rows = [c for c in carriers if not c["spec"]]
    gliner_spec = [c for c in spec_rows if c["gliner_reachable"]]
    miss_and_reach = [c for c in carriers if not c["dense_hit"] and c["gliner_reachable"]]
    summary = {
        "run_id": run_id,
        "config": str(CONFIG),
        "n_questions": len({c["id"] for c in carriers}),
        "n_carriers": len(carriers),
        "n_spec": len(spec_rows),
        "n_prose": len(prose_rows),
        "dense16_carrier_recall": recall(carriers),
        "dense16_spec_recall": recall(spec_rows),
        "dense16_prose_recall": recall(prose_rows),
        "gliner_spec_in_dense16": round(
            sum(c["dense_hit"] for c in gliner_spec) / len(gliner_spec), 4
        ) if gliner_spec else None,
        "gliner_reachable_fraction": round(
            sum(c["gliner_reachable"] for c in carriers) / len(carriers), 4
        ) if carriers else None,
        "fused_lift_bound": round(len(miss_and_reach) / len(carriers), 4)
        if carriers else None,
        "bars": {"null_confirmed_lift_lt": 0.02, "domain_opens_spec_recall_lt": 0.85},
    }
    out = Path("reports/experiments/r47")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"h501-ceiling-{run_id}.json"
    path.write_text(json.dumps({"summary": summary, "rows": carriers}, indent=1))
    print("SUMMARY " + json.dumps(summary), flush=True)
    print(f"WROTE {path}", flush=True)


if __name__ == "__main__":
    main()

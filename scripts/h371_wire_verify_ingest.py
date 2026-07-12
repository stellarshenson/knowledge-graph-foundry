"""H371 wiring verification - ingest arm: a real 3-document ingest with
questions.enabled=true (the shipped default) against a THROWAWAY scratch
Neo4j (kgf-h371-scratch, 172.19.0.8) and the local vLLM (gpt-oss-120b).
Verifies KGFQuestion nodes, ANSWERABLE_FROM/ABOUT edges and the question
vector index appear with sane counts through the shipped ingest path.
The container is removed by the driver after the report lands.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from knowledge_graph_foundry import load_settings
from knowledge_graph_foundry.pipeline import Foundry
from knowledge_graph_foundry.settings import LLMSettings

SCRATCH_URI = "bolt://172.19.0.8:7687"  # throwaway kgf-h371-scratch (hub network)
CORPUS = Path(sys.argv[1])
PURPOSE = "compare CPAP machines"


def main():
    st = load_settings(Path("config/config.yml"))
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = SCRATCH_URI, "neo4j", "kgfoundry"
    # R30 standing rule: timeout 3600 ALWAYS on the shared vLLM
    st.llm = LLMSettings(
        engine="local-gpu",
        model="gpt-oss-120b",
        base_url="http://localhost:8010/v1",
        temperature=0.0,
        timeout=3600,
    )
    st.extraction_llm = None
    assert st.questions.enabled, "shipped default expected"
    print(f"scratch: {st.neo4j.uri}, questions: {st.questions}", flush=True)

    with Foundry(st) as f:
        f.wipe()
        f.init_project(PURPOSE)
        summary = f.ingest(CORPUS)
        print(f"ingest summary: {summary}", flush=True)
        with f.driver.session() as s:
            counts = {
                "documents": s.run("MATCH (d:KGFDocument) RETURN count(d) AS n").single()["n"],
                "chunks": s.run("MATCH (c:Chunk) RETURN count(c) AS n").single()["n"],
                "entities": s.run("MATCH (e:Entity) RETURN count(e) AS n").single()["n"],
                "questions": s.run("MATCH (q:KGFQuestion) RETURN count(q) AS n").single()["n"],
                "answerable_from": s.run(
                    "MATCH (:KGFQuestion)-[r:ANSWERABLE_FROM]->(:Chunk) RETURN count(r) AS n"
                ).single()["n"],
                "about": s.run(
                    "MATCH (:KGFQuestion)-[r:ABOUT]->(:Entity) RETURN count(r) AS n"
                ).single()["n"],
                "questions_with_embedding": s.run(
                    "MATCH (q:KGFQuestion) WHERE q.embedding IS NOT NULL RETURN count(q) AS n"
                ).single()["n"],
                "provenance_source_ingest": s.run(
                    "MATCH (q:KGFQuestion {source: 'ingest'}) RETURN count(q) AS n"
                ).single()["n"],
            }
            index_present = any(
                r["name"] == st.questions.index_name for r in s.run("SHOW INDEXES YIELD name")
            )
            samples = s.run(
                "MATCH (q:KGFQuestion) RETURN q.text AS text, q.answer AS answer LIMIT 5"
            ).data()
        # the channel end-to-end on the fresh pile: shipped probe() read path
        probe = f.probe("What pressure range does the DreamStation deliver?")
        question_blocks = [
            line for line in probe["context_lines"] if line.startswith("## Question match:")
        ]

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {
        "verification": "H371 wiring - ingest arm (throwaway scratch)",
        "generated": ts,
        "graph_uri": SCRATCH_URI,
        "corpus": str(CORPUS),
        "ingest_summary": summary,
        "counts": counts,
        "question_index_present": index_present,
        "sample_questions": samples,
        "probe_question_blocks": question_blocks,
    }
    out = Path(f"reports/h371-wire-ingest-{ts}.json")
    out.write_text(json.dumps(report, indent=2))
    print(f"\nH371 INGEST VERIFY COMPLETE: {counts} index={index_present} -> {out}", flush=True)


if __name__ == "__main__":
    main()

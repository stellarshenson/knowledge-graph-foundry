"""Scout-rung smoke verification (task #83): counts, question channel, probe, timing."""

import json
import sys
from datetime import datetime
from pathlib import Path

PROJ = Path("/home/lab/workspace/learning/projects/knowledge-graph-foundry")
sys.path.insert(0, str(PROJ / "src"))

out: dict = {"verification": {}}

# --- graph counts ------------------------------------------------------------
from neo4j import GraphDatabase  # noqa: E402

drv = GraphDatabase.driver("bolt://172.19.0.8:7687", auth=("neo4j", "kgfoundry"))
with drv.session() as s:
    counts = {}
    counts["nodes_total"] = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
    counts["entities"] = s.run("MATCH (e:Entity) RETURN count(e) AS c").single()["c"]
    counts["chunks"] = s.run("MATCH (c:Chunk) RETURN count(c) AS c").single()["c"]
    counts["documents"] = s.run("MATCH (d:Document) RETURN count(d) AS c").single()["c"]
    counts["relationships_total"] = s.run(
        "MATCH ()-[r]->() RETURN count(r) AS c"
    ).single()["c"]
    counts["kgf_questions"] = s.run(
        "MATCH (q:KGFQuestion) RETURN count(q) AS c"
    ).single()["c"]
    counts["kgf_questions_source_ingest"] = s.run(
        "MATCH (q:KGFQuestion {source:'ingest'}) RETURN count(q) AS c"
    ).single()["c"]
    counts["answerable_from_edges"] = s.run(
        "MATCH (:KGFQuestion)-[r:ANSWERABLE_FROM]->(:Chunk) RETURN count(r) AS c"
    ).single()["c"]
    counts["about_edges"] = s.run(
        "MATCH (:KGFQuestion)-[r:ABOUT]->(:Entity) RETURN count(r) AS c"
    ).single()["c"]
    qpc = s.run(
        "MATCH (q:KGFQuestion)-[:ANSWERABLE_FROM]->(c:Chunk) "
        "WITH c, count(q) AS n RETURN avg(n) AS mean, min(n) AS mn, max(n) AS mx, "
        "count(c) AS chunks_with_questions"
    ).single()
    counts["questions_per_chunk"] = {
        "mean": round(qpc["mean"], 2) if qpc["mean"] is not None else None,
        "min": qpc["mn"],
        "max": qpc["mx"],
        "chunks_with_questions": qpc["chunks_with_questions"],
    }
    idx = s.run(
        "SHOW INDEXES YIELD name, type, state WHERE name = 'kgf_question_embeddings' "
        "RETURN name, type, state"
    ).data()
    counts["question_vector_index"] = idx
    labels = s.run(
        "MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c ORDER BY c DESC"
    ).data()
    counts["labels"] = {r["l"]: r["c"] for r in labels}
drv.close()
out["counts"] = counts

v = out["verification"]
v["entities_nonzero"] = "PASS" if counts["entities"] > 0 else "FAIL"
v["relationships_nonzero"] = "PASS" if counts["relationships_total"] > 0 else "FAIL"
v["questions_present"] = "PASS" if counts["kgf_questions"] > 0 else "FAIL"
v["questions_all_source_ingest"] = (
    "PASS"
    if counts["kgf_questions"] == counts["kgf_questions_source_ingest"]
    and counts["kgf_questions"] > 0
    else "FAIL"
)
v["answerable_from_edges"] = "PASS" if counts["answerable_from_edges"] > 0 else "FAIL"
v["about_edges"] = "PASS" if counts["about_edges"] > 0 else "FAIL"
v["question_vector_index_online"] = (
    "PASS"
    if any(i["state"] == "ONLINE" for i in counts["question_vector_index"])
    else "FAIL"
)

# --- per-passage timing from event log ---------------------------------------
events = []
with open(PROJ / "logs/bench-scout-events.jsonl") as f:
    for line in f:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
starts, durs = [], []
for e in events:
    if e.get("event") == "document.started":
        starts.append(datetime.fromisoformat(e["ts"]))
    elif e.get("event") == "document.completed" and starts:
        durs.append((datetime.fromisoformat(e["ts"]) - starts.pop()).total_seconds())
skipped = sum(1 for e in events if e.get("event") == "document.skipped")
out["timing"] = {
    "passages_completed": len(durs),
    "passages_skipped": skipped,
    "per_passage_mean_s": round(sum(durs) / len(durs), 1) if durs else None,
    "per_passage_min_s": round(min(durs), 1) if durs else None,
    "per_passage_max_s": round(max(durs), 1) if durs else None,
    "total_wallclock_s": round(sum(durs), 1) if durs else None,
}
qgen = sum(1 for e in events if e.get("event") == "questions.generated")
qstored = [e for e in events if e.get("event") == "questions.stored"]
out["question_events"] = {
    "questions.generated": qgen,
    "questions.stored": len(qstored),
    "questions.linked": sum(1 for e in events if e.get("event") == "questions.linked"),
}

# --- engine probe ------------------------------------------------------------
from knowledge_graph_foundry.settings import load_settings  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

settings = load_settings(PROJ / "config/experiments/config-bench-scout.yml")
out["effective_neo4j_uri"] = settings.neo4j.uri
foundry = Foundry(settings)
question = "Who was the husband of Teutberga?"
res = foundry.probe(question)
foundry.close()
qmatch_blocks = [
    ln for ln in res["context_lines"] if ln.startswith("## Question match:")
]
out["probe"] = {
    "question": question,
    "context_lines": len(res["context_lines"]),
    "supporting_names": res["supporting_names"][:15],
    "question_match_blocks": len(qmatch_blocks),
    "first_question_match": qmatch_blocks[0][:300] if qmatch_blocks else None,
    "coverage": res.get("coverage"),
}
v["probe_question_match_block"] = "PASS" if qmatch_blocks else "FAIL"
v["effective_uri_is_throwaway"] = (
    "PASS" if "172.19.0.8" in settings.neo4j.uri else "FAIL"
)

print(json.dumps(out, indent=2, default=str))

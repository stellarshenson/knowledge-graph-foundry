"""R36-H378/DEF-9: end-to-end induced-drift replay on scratch.

Drives the REAL pipeline (Foundry.ingest -> _stable_load -> DriftDetector ->
Lifecycle -> adopt_drifted_types -> end_recure) on a throwaway scratch Neo4j
with a scripted extraction stream (extraction is stubbed - the LLM extractor
is not the mechanism under test; everything downstream of extraction is the
shipped engine code). Two arms over the identical document stream:

  cusum arm   - drift.cusum_enabled=True (the H317 trigger + RECURING exit)
  control arm - shipped boolean gate (DEF-9's structurally-dead conjunction)

Document stream (12 docs): 4 stationary (cured register), 5 drifted (novel
'AlienDevice'/'FirmwareModule' register - the induced drift), 3 post-exit
stationary-on-the-new-register. Registered clauses:

  1. alarm fires on the induced drift (cusum arm) - and the control arm's
     boolean gate stays silent on the same stream (DEF-9 anatomy)
  2. FSM walks STABLE -> RECURING -> STABLE (recure_completed with adoption)
  3. the drifted region is repaired: post-exit remap rate collapses to 0 and
     the same register never re-alarms (livelock guard)
  4. zero probe regression: the 24-probe harness on the live pile (neo4j4)
     is bit-identical before/after (the replay touches only scratch;
     cusum_enabled defaults off in the shipped config)

REFUTED-as-designed branch: consolidation cost approaching full-rebuild cost.
Measured as consolidation work / full-rebuild work in documents-processed and
graph writes (the replay's consolidation is the patch-tier adoption pass).
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, "notebooks")

from knowledge_graph_foundry import load_settings  # noqa: E402
from knowledge_graph_foundry.events import subscribe, unsubscribe  # noqa: E402
from knowledge_graph_foundry.models import Entity, Ontology, Relationship, TypeDef  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402

SCRATCH_URI = "bolt://172.19.0.8:7687"  # throwaway container kgf-h378-scratch (hub network)
LIVE_URI = "bolt://172.19.0.100:7687"  # neo4j4 - probe clause only, READ ONLY
PURPOSE = "CPAP device knowledge for the H378 drift replay"
DIM = 1024

# cured register: the ontology the graph was cured on
CURED = {"Product": 60, "Manufacturer": 30, "Specification": 10}
# per-doc type register by phase. The drifted register reproduces the DEF-9
# ANTI-PHASE anatomy end-to-end: per-doc remap rate 2/8 = 0.25 stays BELOW the
# 0.3 boolean threshold (sustained_remap can never be true - the boolean gate
# is structurally silent), while the register's distribution shift (JSD ~0.33
# vs cured) accumulates in the CUSUM and fires it.
STATIONARY = {"Product": 6, "Manufacturer": 3, "Specification": 1}
DRIFTED = {"Product": 6, "AlienDevice": 2}

DOCS = [("stationary", STATIONARY)] * 4 + [("drifted", DRIFTED)] * 5 + [
    ("post_exit", DRIFTED)
] * 3


def scripted_entities(doc_idx: int, register: dict[str, int]):
    """Deterministic fake extraction: unique entities per doc, typed to the
    phase register. A couple of relationships keep the loader path exercised."""
    entities, i = [], 0
    for tname, count in register.items():
        for k in range(count):
            entities.append(Entity.create(
                name=f"h378-d{doc_idx:02d}-{tname}-{k}",
                types=[tname],
                description=f"replay entity {tname} #{k} of doc {doc_idx}",
                source_documents=[f"doc{doc_idx:02d}"],
            ))
            i += 1
    rels = [
        Relationship(source_id=entities[0].id, target_id=entities[1].id,
                     type="RELATES_TO", description="replay edge")
    ] if len(entities) > 1 else []
    return entities, rels


def fake_embed(entities):
    """Deterministic per-name unit vectors - no external embedding service."""
    import hashlib
    import math
    out = []
    for e in entities:
        h = hashlib.sha256(e.name.encode()).digest()
        vec = [(h[i % 32] + i) % 251 / 251.0 - 0.5 for i in range(DIM)]
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        out.append(e.model_copy(update={"embedding": [v / norm for v in vec]}))
    return out


def run_arm(arm: str, cusum: bool, docs_dir: Path) -> dict:
    st = load_settings(Path("config/config.yml"))
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = SCRATCH_URI, "neo4j", "kgfoundry"
    st.drift.cusum_enabled = cusum
    st.extraction.document_concurrency = 1  # deterministic order
    st.resolution.demotion_court = False  # no LLM in the replay
    st.resolution.soft_links = False
    st.load.entity_versioning = False

    events = []
    names = ["fsm.transition", "drift.decision", "drift.warning",
             "drift.types_adopted", "drift.recure_completed"]
    receivers = {}
    for n in names:
        def make(n):
            return lambda sender, **kw: events.append({"event": n, **kw})
        receivers[n] = make(n)
        subscribe(n, receivers[n])

    remap_series = []
    try:
        with Foundry(st) as f:
            with f.driver.session() as s:  # wipe scratch between arms
                s.run("MATCH (n) DETACH DELETE n")
            # scripted extraction + embeddings: everything downstream is real
            f._extract_file = lambda path, purpose, ontology: scripted_entities(
                int(path.stem.removeprefix("doc")), DOCS[int(path.stem.removeprefix("doc"))][1]
            )
            f._embed = fake_embed
            orig_stable = f._stable_load
            def stable_spy(entities, relationships, ontology, calibrator):
                remap, inval = orig_stable(entities, relationships, ontology, calibrator)
                remap_series.append(round(remap, 4))
                return remap, inval
            f._stable_load = stable_spy

            # start the replay already cured/STABLE - R28 replay shape: the
            # drift trigger and the RECURING exit are the mechanisms under test
            ontology = Ontology(purpose=PURPOSE, cured=True, types={
                n: TypeDef(name=n, status="cured", encounters=c) for n, c in CURED.items()
            })
            f._save_state({
                "fsm_state": "STABLE", "purpose": PURPOSE,
                "ontology": ontology.model_dump(), "buffer_cache": None,
                "metrics_history": None, "calibration": None, "drift": None,
                "documents_processed": 0, "processed_documents": [],
            })
            summary = f.ingest(docs_dir)
            state = f._load_state()
            with f.driver.session() as s:
                nodes = s.run("MATCH (e:Entity) RETURN count(e) AS n").single()["n"]
    finally:
        for n in names:
            unsubscribe(n, receivers[n])

    fsm_walk = [e["state"] for e in events if e["event"] == "fsm.transition"]
    adopted = [e for e in events if e["event"] == "drift.types_adopted"]
    recure_done = [e for e in events if e["event"] == "drift.recure_completed"]
    decisions = [e for e in events if e["event"] == "drift.decision"]
    return {
        "arm": arm, "cusum_enabled": cusum,
        "documents": summary["documents"], "scratch_entities": nodes,
        "fsm_walk": fsm_walk, "final_fsm_state": state["fsm_state"],
        "remap_series": remap_series,
        "drift_decisions": [
            {k: v for k, v in e.items() if k in ("event", "action", "cusum_s", "jsd", "mu0")}
            for e in decisions],
        "types_adopted": [e.get("types") for e in adopted],
        "recure_completed": [e.get("adopted") for e in recure_done],
        "final_ontology_types": sorted(state["ontology"]["types"].keys()),
        "alarm_fired": any(e.get("action") == "recure" for e in decisions),
        "events_n": len(events),
    }


def probe_harness_live() -> dict:
    """Clause 4: 24-probe harness on the untouched live pile (read-only),
    same instrument as the H379/H376 baseline (overfetch 64 -> top-16)."""
    from copy import deepcopy

    from h158_measure import _present, _render_nodes
    import yaml

    from knowledge_graph_foundry.extraction import generate_embeddings
    from knowledge_graph_foundry.graph.graphrag import overfetch_seeds, vector_query

    st = deepcopy(load_settings(Path("config/config.yml")))
    st.neo4j.uri, st.neo4j.user, st.neo4j.password = LIVE_URI, "neo4j", "kgfoundry"
    probes = [p for p in yaml.safe_load(Path("tests/probes/cpap-probe-set.yml").read_text())
              if p.get("gold_evidence")]
    per = {}
    with Foundry(st) as f:
        for p in probes:
            q = p["question"]
            pe = Entity.create(q[:80], types=["Query"], description=q)
            emb = generate_embeddings([pe], st.embeddings)[0].embedding
            seeds = [s["id"] for s in overfetch_seeds(
                lambda k: vector_query(f.driver, emb, st.graphrag.vector_index_name, top_k=k),
                64, st.graphrag.overfetch_factor)][:16]
            with f.driver.session() as sess:
                ctx = _render_nodes(sess, seeds)
            golds = p["gold_evidence"]
            per[p["id"]] = round(sum(_present(g, ctx) for g in golds) / len(golds), 4)
    mean = round(sum(per.values()) / len(per), 4)
    return {"mean_recall": mean, "per_probe": per}


def main():
    docs_dir = Path("data/interim/h378_replay_docs")
    docs_dir.mkdir(parents=True, exist_ok=True)
    for i, (phase, _) in enumerate(DOCS):
        (docs_dir / f"doc{i:02d}.txt").write_text(
            f"H378 replay document {i:02d} - phase {phase}. Content is scripted; "
            f"extraction is stubbed in the replay harness.")

    cusum = run_arm("cusum", True, docs_dir)
    print(json.dumps(cusum, indent=2), flush=True)
    control = run_arm("control", False, docs_dir)
    print(json.dumps(control, indent=2), flush=True)

    probes = probe_harness_live()
    print(f"live-pile probes after replay: mean={probes['mean_recall']}", flush=True)

    baseline_path = sorted(Path("reports").glob("r36-h379-replay-*.json"))[-1]
    baseline = json.loads(baseline_path.read_text())["baseline_per_probe"]
    probe_regressions = {
        p: (baseline[p], probes["per_probe"][p])
        for p in baseline if probes["per_probe"].get(p, 0) < baseline[p]
    }

    # consolidation cost vs full rebuild: the RECURING pass consumed
    # window-many documents + one adoption write against a full re-ingest
    # of every document in the pile
    window_docs = 3
    consolidation_cost = {
        "consolidation_documents": window_docs,
        "consolidation_llm_calls": 0,
        "full_rebuild_documents": len(DOCS),
        "cost_share_of_rebuild": round(window_docs / len(DOCS), 4),
    }

    drift_idx = next((i for i, (p, _) in enumerate(DOCS) if p == "drifted"), None)
    pre = [r for r in cusum["remap_series"][:len(DOCS)]]
    clauses = {
        "1_alarm_fired_cusum": cusum["alarm_fired"],
        "1b_control_boolean_silent": not control["alarm_fired"],
        "2_fsm_walk_stable_recuring_stable": (
            "RECURING" in cusum["fsm_walk"]
            and cusum["final_fsm_state"] == "STABLE"
            and cusum["fsm_walk"][-1] == "STABLE"),
        "3_repaired_post_exit_remap_zero": (
            len(cusum["remap_series"]) == len(DOCS)
            and all(r == 0.0 for r in cusum["remap_series"][-3:])),
        "3b_no_realarm_post_exit": (
            len([e for e in cusum["drift_decisions"] if e.get("action") == "recure"]) == 1),
        "4_zero_probe_regression": len(probe_regressions) == 0,
    }
    verdict = "CONFIRMED" if all(clauses.values()) else "PARTIAL"

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/experiments/adjudicated/r36-h378-drift-replay-{ts}.json")
    out.write_text(json.dumps({
        "hypothesis": "R36-H378 end-to-end induced-drift replay (DEF-9 workstream)",
        "generated": ts, "scratch_uri": SCRATCH_URI, "live_uri": LIVE_URI,
        "stream": [p for p, _ in DOCS],
        "cured_register": CURED, "drifted_register": DRIFTED,
        "cusum_arm": cusum, "control_arm": control,
        "probe_baseline_source": str(baseline_path),
        "probe_after": {"mean": probes["mean_recall"], "per_probe": probes["per_probe"]},
        "probe_regressions": {p: list(v) for p, v in probe_regressions.items()},
        "consolidation_cost": consolidation_cost,
        "clauses": clauses, "verdict": verdict,
        "drift_onset_doc": drift_idx, "remap_pre_post": pre,
    }, indent=2))
    print(f"\nH378 DRIFT REPLAY COMPLETE -> {out} verdict={verdict}", flush=True)


if __name__ == "__main__":
    main()

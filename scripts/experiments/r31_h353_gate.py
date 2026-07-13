"""R31-H353 GATE: union's mechanism verdict on gold-carrier chunks only.

Decides whether union-of-K is worth ANY full ingest (H349) at ~1/20 the cost:
6 independent extraction passes over just the chunks that carry the 24 probes'
gold evidence, then offline union/variance analysis:

  - emission coverage: is the gold string present in a pass's emitted
    entities/relationships (names, descriptions, property values)? Uses the
    H158 harness's own `_present` matcher, so "emitted" here means exactly
    what "retrievable" means at graph level
  - coverage curve: single (mean of 6) / union-2 (3 disjoint pairs) /
    union-3 (2 disjoint triples) / union-6 ceiling  [R22-H231 instrument]
  - variance curve: mean pairwise entity-name Jaccard distance across the
    6 singles vs across the union-2 samples vs union-3 samples

GATE (pre-registered): proceed to H349's 3+3 full ingests only if
  union-2 coverage >= single + 0.25  AND  JD(union-2) <= 0.75 x JD(single);
else H349 closes REFUTED with zero ingests spent.

Concurrency comes from the R30 ramp output (best chunks/min step), fallback 16.
Checkpoints per chunk to tmp/results/r31/h353-chunks.jsonl (detached-compute rule).

Usage: python scripts/experiments/r31_h353_gate.py
"""

import itertools
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, "notebooks")
from h158_measure import _present  # noqa: E402 - the harness's own matcher

from knowledge_graph_foundry.engines import create_engine  # noqa: E402
from knowledge_graph_foundry.extraction.extractor import extract_chunk  # noqa: E402
from knowledge_graph_foundry.ingest.chunking import chunk_document  # noqa: E402
from knowledge_graph_foundry.ingest.readers import iter_source_files, read_document  # noqa: E402
from knowledge_graph_foundry.models import Ontology  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402
from knowledge_graph_foundry.settings import load_settings  # noqa: E402

CONFIG = Path("config/experiments/config-r31-gate.yml")  # r29-v1 + llm.timeout 3600 (R30: p50 > 600s from c~32 -> silent retries)
CORPUS = Path("data/external/cpap-datasheets-and-manuals")
PROBES = Path("tests/probes/cpap-probe-set.yml")
RAMP_STEPS = Path("reports/experiments/r30/ramp-steps.jsonl")
CHECKPOINT = Path("tmp/results/r31/h353-chunks.jsonl")
PASSES = 6
CARRIERS_PER_GOLD = 3


def knee_concurrency() -> int:
    if not RAMP_STEPS.exists():
        return 16
    steps = [json.loads(x) for x in RAMP_STEPS.read_text().splitlines()]
    best = max(steps, key=lambda s: s["chunks_per_min"])
    return int(best["concurrency"])


def emission_text(result) -> str:
    parts = []
    for e in result.entities:
        parts.append(e.name)
        parts.append(e.description)
        parts.extend(str(v) for v in e.properties.values())
    for r in result.relationships:
        parts.append(r.type)
        parts.append(r.description)
    return " | ".join(p for p in parts if p)


def mean_pairwise_jd(sets: list[set]) -> float:
    pairs = list(itertools.combinations(range(len(sets)), 2))
    if not pairs:
        return 0.0
    total = 0.0
    for i, j in pairs:
        union = sets[i] | sets[j]
        total += 1 - (len(sets[i] & sets[j]) / len(union)) if union else 0.0
    return total / len(pairs)


def main():
    settings = load_settings(CONFIG)
    settings.event_log = None
    state = Foundry(settings)._load_state()
    if not state or not state.get("ontology"):
        raise SystemExit("no ontology on neo4j4 - gate needs the production type system")
    ontology = Ontology(**state["ontology"])
    purpose = state.get("purpose", "")
    engine = create_engine(settings.llm)
    ex = settings.extraction  # union_k stays 1: the gate unions offline

    probes = [p for p in yaml.safe_load(PROBES.read_text()) if p.get("gold_evidence")]
    golds = sorted({g for p in probes for g in p["gold_evidence"]})
    print(f"golds: {len(golds)} evidence strings from {len(probes)} probes", flush=True)

    chunks = []
    for f in iter_source_files(CORPUS):
        if f.suffix.lower() != ".pdf":
            continue
        try:
            doc = read_document(f, parser_union=ex.parser_union, glyph_normalization=ex.glyph_normalization)
            chunks.extend(chunk_document(doc, ex.chunk_size, ex.chunk_overlap, ex.header_carryover))
        except Exception as exc:
            print(f"skip {f.name}: {exc}", flush=True)

    carriers: dict[str, list] = {}
    chunk_set: dict[str, object] = {}
    for g in golds:
        found = [c for c in chunks if _present(g, c.text)][:CARRIERS_PER_GOLD]
        carriers[g] = [c.id for c in found]
        for c in found:
            chunk_set[c.id] = c
    uncarried = [g for g in golds if not carriers[g]]
    work = list(chunk_set.values())
    print(
        f"carriers: {len(work)} unique chunks cover {len(golds) - len(uncarried)}/{len(golds)} golds"
        f" (no carrier: {uncarried})",
        flush=True,
    )

    concurrency = knee_concurrency()
    print(f"extraction concurrency (R30 knee or fallback): {concurrency}", flush=True)

    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    done_ids = set()
    if CHECKPOINT.exists():  # resume: skip chunks already measured
        done_ids = {json.loads(x)["chunk_id"] for x in CHECKPOINT.read_text().splitlines()}
        work = [c for c in work if c.id not in done_ids]
        print(f"resume: {len(done_ids)} chunks cached, {len(work)} to run", flush=True)

    lock = threading.Lock()
    done_count = [0]

    def run_chunk(chunk):
        passes = []
        for _ in range(PASSES):
            try:
                res = extract_chunk(chunk, purpose, ontology, engine, ex)
                passes.append(
                    {
                        "entity_names": sorted({e.name for e in res.entities}),
                        "emission": emission_text(res),
                    }
                )
            except Exception as exc:
                passes.append({"entity_names": [], "emission": "", "error": str(exc)})
        rec = {"chunk_id": chunk.id, "passes": passes}
        with lock:
            with CHECKPOINT.open("a") as fh:
                fh.write(json.dumps(rec) + "\n")
            done_count[0] += 1
            print(f"chunk {done_count[0]}/{len(work)} done ({chunk.id})", flush=True)

    # each worker owns one chunk's 6 serial passes; chunks run concurrently -
    # aggregate in-flight ~= concurrency (the knee), per the max-GPU rule
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        list(pool.map(run_chunk, work))

    # ---- offline analysis over ALL checkpointed chunks ----
    records = [json.loads(x) for x in CHECKPOINT.read_text().splitlines()]
    by_id = {r["chunk_id"]: r for r in records}

    def covered(g: str, sample_passes: list[int]) -> bool:
        return any(
            any(_present(g, by_id[cid]["passes"][i]["emission"]) for i in sample_passes)
            for cid in carriers[g]
            if cid in by_id
        )

    carried = [g for g in golds if carriers[g]]
    singles = [[i] for i in range(PASSES)]
    union2 = [[0, 1], [2, 3], [4, 5]]
    union3 = [[0, 1, 2], [3, 4, 5]]
    union6 = [list(range(PASSES))]

    def coverage(samples):
        vals = [sum(covered(g, s) for g in carried) / len(carried) for s in samples]
        return sum(vals) / len(vals)

    cov = {
        "single": round(coverage(singles), 4),
        "union2": round(coverage(union2), 4),
        "union3": round(coverage(union3), 4),
        "union6_ceiling": round(coverage(union6), 4),
    }

    def jd_for(samples):
        jds = []
        for r in records:
            sets = [
                set().union(*(set(r["passes"][i]["entity_names"]) for i in s)) for s in samples
            ]
            jds.append(mean_pairwise_jd(sets))
        return sum(jds) / len(jds)

    jd = {
        "single": round(jd_for(singles), 4),
        "union2": round(jd_for(union2), 4),
        "union3": round(jd_for(union3), 4),
    }

    gain = cov["union2"] - cov["single"]
    jd_ratio = jd["union2"] / jd["single"] if jd["single"] else 1.0
    gate_pass = gain >= 0.25 and jd_ratio <= 0.75

    print("-" * 60, flush=True)
    print(f"coverage: {cov}", flush=True)
    print(f"jaccard distance: {jd}  (union2/single = {jd_ratio:.3f})", flush=True)
    print(
        f"GATE: gain {gain:+.3f} (bar +0.25) AND jd ratio {jd_ratio:.3f} (bar <= 0.75) "
        f"-> {'PASS - run H349 full ingests' if gate_pass else 'FAIL - H349 closes REFUTED, zero ingests'}",
        flush=True,
    )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/experiments/adjudicated/r31-h353-gate-{ts}.json")
    out.write_text(
        json.dumps(
            {
                "hypothesis": "R31-H353",
                "generated": ts,
                "passes": PASSES,
                "concurrency": concurrency,
                "chunks_measured": len(records),
                "golds_carried": len(carried),
                "golds_uncarried": uncarried,
                "coverage": cov,
                "jd": jd,
                "union2_gain": round(gain, 4),
                "jd_ratio_union2": round(jd_ratio, 4),
                "gate": "PASS" if gate_pass else "FAIL",
            },
            indent=2,
        )
    )
    print(f"H353 GATE COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

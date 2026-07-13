"""R31-H352: enumeration-dense chunks need a hard budget - two-arm standalone replay.

The H240b catalog document (product_and_solutions_catalog.pdf - worst document in
every recorded run: 105.6 min in h240b-enum, 76 min / 430 dangling warnings in
r29-v2-run2) is replayed standalone through two extraction arms:

  baseline  - the SHIPPED recipe exactly as configured (enumerate + candidates
              extraction + 1 gleaning round), extract_chunk per chunk
  budgeted  - enumeration-density detection per chunk (list-marker + variant/part-
              number token ratio); dense chunks are split into bounded sub-lists
              (SUBLIST_LINES non-blank lines each, section-heading context
              re-printed), ONE extraction pass per sub-list, NO enumeration
              stage, NO gleaning; non-dense chunks run the shipped recipe

Both arms run at the same in-flight LLM request budget (extraction.concurrency
from the config, shipped 8). Measured per arm: wall-clock, logical LLM call
count, per-call latency and output size, dangling-relationship warning count
(same emit path as the engine), entity/relationship volume, and emission recall
on catalog-carried gold evidence (H353's own _present matcher).

NOTE on probes: no probe in tests/probes/cpap-probe-set.yml names the catalog
document as a source - the "catalog-derived probes" are the gold-evidence
probes whose evidence strings are carried by the catalog's own chunks
(surface-form match, H353 carrier convention). This is stated in the report.

The GPU is shared with other executors: a sampler thread records the vLLM
num_requests_running gauge each minute so external load during each arm is
visible; call count + generated output size are the contention-free proxies.

Checkpoints per chunk to tmp/results/r31/h352-{arm}.jsonl (detached-compute rule);
on resume completed chunks are skipped and the arm's wall-clock is flagged
tainted (call latencies remain valid).

Usage: python scripts/experiments/r31_h352_replay.py
"""

import json
import re
import statistics
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, "notebooks")
from h158_measure import _present  # noqa: E402 - the harness's own matcher

from knowledge_graph_foundry.engines import create_engine  # noqa: E402
from knowledge_graph_foundry.events import emit, subscribe, unsubscribe, enable_event_log, disable_event_log  # noqa: E402
from knowledge_graph_foundry.extraction.extractor import (  # noqa: E402
    WireExtraction,
    extract_chunk,
    normalize_relationship_type,
)
from knowledge_graph_foundry.extraction.prompts import extraction_messages  # noqa: E402
from knowledge_graph_foundry.ingest.chunking import chunk_document  # noqa: E402
from knowledge_graph_foundry.ingest.readers import read_document  # noqa: E402
from knowledge_graph_foundry.models import Entity, ExtractionResult, Ontology, Relationship, entity_id  # noqa: E402
from knowledge_graph_foundry.ontology.seed import normalize_type_name  # noqa: E402
from knowledge_graph_foundry.pipeline import Foundry  # noqa: E402
from knowledge_graph_foundry.settings import load_settings  # noqa: E402

CONFIG = Path("config/experiments/config-r31-gate.yml")  # r29 shipped semantics + t3600
DOC = Path("data/external/cpap-datasheets-and-manuals/product_and_solutions_catalog.pdf")
PROBES = Path("tests/probes/cpap-probe-set.yml")
RESULTS = Path("tmp/results/r31")
METRICS_URL = "http://localhost:8010/metrics"

# --- budgeted-recipe knobs (the registered lever, prototyped script-side) ---
DENSITY_THRESHOLD = 0.30  # (list-marker lines + part-number tokens) / non-blank lines
SUBLIST_LINES = 30  # bounded sub-list size, one extraction pass each

_LIST_MARKER = re.compile(r"^\s*(?:[-*•]|\|\s?|\d+[.)]\s)")
# part/order-number tokens: bare numeric part codes (1078758) or code compounds (HH1234-56, 1.5mm codes excluded)
_CODE_TOKEN = re.compile(r"\b(?:[A-Z]{0,4}\d{5,}|[A-Z0-9]*[A-Z]\d[A-Z0-9]*|[A-Z0-9]+(?:[-/][A-Z0-9]+)+)\b")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s")


def enumeration_density(text: str) -> float:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return 0.0
    marker_lines = sum(bool(_LIST_MARKER.match(line)) for line in lines)
    code_tokens = len(_CODE_TOKEN.findall(text))
    return (marker_lines + code_tokens) / len(lines)


def split_sublists(text: str) -> list[str]:
    """Bounded sub-lists of non-blank lines; section headings re-printed as context."""
    lines = [line for line in text.splitlines() if line.strip()]
    headings = [line for line in lines if _HEADING.match(line)][:3]
    context = "\n".join(headings)
    sublists = []
    for start in range(0, len(lines), SUBLIST_LINES):
        body = "\n".join(lines[start : start + SUBLIST_LINES])
        sublists.append(f"{context}\n\n{body}" if context and start > 0 else body)
    return sublists


class CountingEngine:
    """Delegates to the real engine, recording per-call wall time and output size."""

    def __init__(self, engine):
        self._engine = engine
        self.name = engine.name
        self.records: list[dict] = []
        self._lock = threading.Lock()

    def _record(self, kind: str, dt: float, out_chars: int) -> None:
        with self._lock:
            self.records.append({"kind": kind, "seconds": round(dt, 2), "out_chars": out_chars})

    def complete(self, messages, response_model):
        t0 = time.monotonic()
        result = self._engine.complete(messages, response_model)
        self._record("complete", time.monotonic() - t0, len(result.model_dump_json()))
        return result

    def complete_text(self, system: str, user: str) -> str:
        t0 = time.monotonic()
        raw = self._engine.complete_text(system, user)
        self._record("complete_text", time.monotonic() - t0, len(raw))
        return raw


def wire_to_result(wire: WireExtraction, chunk) -> ExtractionResult:
    """Same wire->domain conversion + dangling validation as extract_chunk (same emit)."""
    entities = [
        Entity.create(
            name=we.name,
            types=[normalize_type_name(t) for t in we.types],
            description=we.description,
            properties=dict(we.properties),
            source_documents=[chunk.document_id],
            source_chunks=[chunk.id],
        )
        for we in wire.entities
    ]
    known_ids = {e.id for e in entities}
    relationships = []
    for wr in wire.relationships:
        source_id, target_id = entity_id(wr.source), entity_id(wr.target)
        if source_id not in known_ids or target_id not in known_ids:
            emit(
                "extraction.warning",
                reason=f"dangling relationship: {wr.source} -[{wr.type}]-> {wr.target}",
                chunk=chunk.id,
            )
            continue
        if source_id == target_id:
            emit(
                "extraction.warning",
                reason=f"self-referencing relationship on {wr.source}",
                chunk=chunk.id,
            )
            continue
        relationships.append(
            Relationship(
                source_id=source_id,
                target_id=target_id,
                type=normalize_relationship_type(wr.type),
                description=wr.description,
                source_documents=[chunk.document_id],
                source_chunks=[chunk.id],
            )
        )
    return ExtractionResult(entities=entities, relationships=relationships)


def merge_wires(wires: list[WireExtraction]) -> WireExtraction:
    """Dedup across sub-list passes - same keys as _gather_wire."""
    merged = WireExtraction()
    seen_entities: set[str] = set()
    seen_relationships: set[tuple[str, str, str]] = set()
    for wire in wires:
        for we in wire.entities:
            eid = entity_id(we.name)
            if eid in seen_entities:
                continue
            seen_entities.add(eid)
            merged.entities.append(we)
        for wr in wire.relationships:
            key = (entity_id(wr.source), entity_id(wr.target), normalize_relationship_type(wr.type))
            if key in seen_relationships:
                continue
            seen_relationships.add(key)
            merged.relationships.append(wr)
    return merged


def emission_text(result: ExtractionResult) -> str:
    parts = []
    for e in result.entities:
        parts.append(e.name)
        parts.append(e.description)
        parts.extend(str(v) for v in e.properties.values())
    for r in result.relationships:
        parts.append(r.type)
        parts.append(r.description)
    return " | ".join(p for p in parts if p)


def result_to_record(chunk_id: str, result: ExtractionResult, **extra) -> dict:
    return {
        "chunk_id": chunk_id,
        "entities": len(result.entities),
        "relationships": len(result.relationships),
        "emission": emission_text(result),
        **extra,
    }


def sample_server_load(stop: threading.Event, samples: list) -> None:
    while not stop.wait(60):
        try:
            with urllib.request.urlopen(METRICS_URL, timeout=10) as resp:
                body = resp.read().decode()
            m = re.search(r'num_requests_running\{[^}]*\}\s+([\d.]+)', body)
            samples.append({"ts": datetime.now(timezone.utc).isoformat(), "running": float(m.group(1)) if m else None})
        except Exception:
            samples.append({"ts": datetime.now(timezone.utc).isoformat(), "running": None})


def latency_stats(records: list[dict]) -> dict:
    if not records:
        return {}
    secs = sorted(r["seconds"] for r in records)
    return {
        "calls": len(secs),
        "mean_s": round(statistics.mean(secs), 1),
        "p50_s": round(secs[len(secs) // 2], 1),
        "p90_s": round(secs[int(len(secs) * 0.9)], 1),
        "max_s": round(secs[-1], 1),
        "total_out_chars": sum(r["out_chars"] for r in records),
    }


def run_arm(arm: str, chunks, purpose, ontology, engine_cfg, ex, concurrency: int) -> dict:
    checkpoint = RESULTS / f"h352-{arm}.jsonl"
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    done: dict[str, dict] = {}
    if checkpoint.exists():
        for line in checkpoint.read_text().splitlines():
            rec = json.loads(line)
            done[rec["chunk_id"]] = rec
    resumed = bool(done)
    work = [c for c in chunks if c.id not in done]
    print(f"[{arm}] {len(done)} chunks cached, {len(work)} to run", flush=True)

    warnings: list[str] = []
    warn_lock = threading.Lock()

    def on_warning(sender, **payload):
        with warn_lock:
            warnings.append(payload.get("reason", ""))

    engine = CountingEngine(create_engine(engine_cfg))
    subscribe("extraction.warning", on_warning)
    enable_event_log(f"logs/r31-h352-{arm}-events.jsonl")
    io_lock = threading.Lock()

    def checkpoint_write(rec: dict) -> None:
        with io_lock:
            with checkpoint.open("a") as fh:
                fh.write(json.dumps(rec) + "\n")
            done[rec["chunk_id"]] = rec
            n = len(done)
        print(f"[{arm}] chunk {n}/{len(chunks)} done ({rec['chunk_id']})", flush=True)

    def run_baseline_chunk(chunk):
        try:
            result = extract_chunk(chunk, purpose, ontology, engine, ex)
            checkpoint_write(result_to_record(chunk.id, result))
        except Exception as exc:
            checkpoint_write({"chunk_id": chunk.id, "entities": 0, "relationships": 0, "emission": "", "error": str(exc)})

    stop = threading.Event()
    load_samples: list = []
    sampler = threading.Thread(target=sample_server_load, args=(stop, load_samples), daemon=True)
    sampler.start()
    t0 = time.monotonic()

    dense_ids: list[str] = []
    sublist_counts: dict[str, int] = {}

    if arm == "baseline":
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            list(pool.map(run_baseline_chunk, work))
    else:  # budgeted: flatten dense-chunk sub-lists into the same in-flight budget
        dense_ids = [c.id for c in chunks if enumeration_density(c.text) >= DENSITY_THRESHOLD]
        print(f"[{arm}] dense chunks: {len(dense_ids)}/{len(chunks)} at threshold {DENSITY_THRESHOLD}", flush=True)
        wires: dict[str, list] = {}
        pending: dict[str, int] = {}
        state_lock = threading.Lock()

        def finish_dense(chunk):
            wire = merge_wires([w for w in wires[chunk.id] if w is not None])
            result = wire_to_result(wire, chunk)
            checkpoint_write(
                result_to_record(chunk.id, result, dense=True, sublists=sublist_counts[chunk.id])
            )

        def run_sublist(chunk, index, subtext):
            try:
                wire = engine.complete(extraction_messages(subtext, purpose, ontology), WireExtraction)
            except Exception as exc:
                wire = None
                with warn_lock:
                    warnings.append(f"sublist extraction failed: {exc}")
            finish = False
            with state_lock:
                wires[chunk.id][index] = wire
                pending[chunk.id] -= 1
                finish = pending[chunk.id] == 0
            if finish:
                finish_dense(chunk)

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            for chunk in work:
                if chunk.id in dense_ids:
                    subs = split_sublists(chunk.text)
                    sublist_counts[chunk.id] = len(subs)
                    wires[chunk.id] = [None] * len(subs)
                    pending[chunk.id] = len(subs)
                    for i, sub in enumerate(subs):
                        pool.submit(run_sublist, chunk, i, sub)
                else:
                    pool.submit(run_baseline_chunk, chunk)

    wall = time.monotonic() - t0
    stop.set()
    disable_event_log()
    unsubscribe("extraction.warning", on_warning)

    dangling = sum(1 for w in warnings if w.startswith("dangling relationship"))
    records = [done[c.id] for c in chunks if c.id in done]
    return {
        "arm": arm,
        "wall_clock_s": round(wall, 1),
        "wall_clock_tainted_by_resume": resumed,
        "chunks": len(records),
        "chunk_errors": sum(1 for r in records if r.get("error")),
        "llm_calls": len(engine.records),
        "latency": latency_stats(engine.records),
        "warnings_total": len(warnings),
        "warnings_dangling": dangling,
        "entities": sum(r["entities"] for r in records),
        "relationships": sum(r["relationships"] for r in records),
        "dense_chunks": len(dense_ids),
        "sublists_total": sum(sublist_counts.values()),
        "server_load_samples": load_samples,
        "_records": records,
    }


def recall_on_catalog_golds(records: list[dict], carried: dict[str, list], probes: list[dict]) -> dict:
    emission_all = " | ".join(r["emission"] for r in records)
    covered = {g: _present(g, emission_all) for g in carried}
    probe_recall = {}
    for p in probes:
        catalog_golds = [g for g in p["gold_evidence"] if g in carried]
        if catalog_golds:
            probe_recall[p["id"]] = sum(covered[g] for g in catalog_golds) / len(catalog_golds)
    return {
        "golds_carried": len(carried),
        "golds_covered": sum(covered.values()),
        "gold_recall": round(sum(covered.values()) / len(carried), 4) if carried else None,
        "missed_golds": sorted(g for g, ok in covered.items() if not ok),
        "probe_recall_mean": round(sum(probe_recall.values()) / len(probe_recall), 4) if probe_recall else None,
        "per_probe": {k: round(v, 4) for k, v in sorted(probe_recall.items())},
    }


def main():
    settings = load_settings(CONFIG)
    settings.event_log = None
    ex = settings.extraction
    concurrency = ex.concurrency
    print(f"config {CONFIG}, recipe={ex.recipe}, gleaning_rounds={ex.gleaning_rounds}, concurrency={concurrency}", flush=True)

    state = Foundry(settings)._load_state()
    if not state or not state.get("ontology"):
        raise SystemExit("no ontology state on the pinned Neo4j - replay needs the production type system")
    ontology = Ontology(**state["ontology"])
    purpose = state.get("purpose", "")

    doc = read_document(DOC, parser_union=ex.parser_union, glyph_normalization=ex.glyph_normalization)
    chunks = chunk_document(doc, ex.chunk_size, ex.chunk_overlap, ex.header_carryover)
    print(f"document {DOC.name}: {len(doc.text)} chars, {len(chunks)} chunks", flush=True)

    probes = [p for p in yaml.safe_load(PROBES.read_text()) if p.get("gold_evidence")]
    golds = sorted({g for p in probes for g in p["gold_evidence"]})
    carried = {}
    for g in golds:
        hits = [c.id for c in chunks if _present(g, c.text)]
        if hits:
            carried[g] = hits
    print(f"catalog-carried golds: {len(carried)}/{len(golds)}", flush=True)

    arms = {}
    for arm in ("baseline", "budgeted"):
        print(f"=== arm: {arm} ===", flush=True)
        arms[arm] = run_arm(arm, chunks, purpose, ontology, settings.llm, ex, concurrency)
        arms[arm]["recall"] = recall_on_catalog_golds(arms[arm].pop("_records"), carried, probes)
        print(json.dumps({k: v for k, v in arms[arm].items() if k != "server_load_samples"}, indent=2), flush=True)

    base, budg = arms["baseline"], arms["budgeted"]
    wall_ratio = budg["wall_clock_s"] / base["wall_clock_s"] if base["wall_clock_s"] else None
    if budg["warnings_dangling"]:
        warn_ratio = base["warnings_dangling"] / budg["warnings_dangling"]
    else:
        warn_ratio = "inf" if base["warnings_dangling"] else None
    recall_delta = (
        budg["recall"]["probe_recall_mean"] - base["recall"]["probe_recall_mean"]
        if budg["recall"]["probe_recall_mean"] is not None and base["recall"]["probe_recall_mean"] is not None
        else None
    )
    clauses = {
        "wall_clock_le_one_third": wall_ratio is not None and wall_ratio <= 1 / 3,
        "recall_within_minus_0_02": recall_delta is not None and recall_delta >= -0.02,
        "warnings_5x_down": warn_ratio == "inf" or (isinstance(warn_ratio, float) and warn_ratio >= 5),
    }
    verdict = "PASS" if all(clauses.values()) else "FAIL"

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/experiments/adjudicated/r31-h352-{ts}.json")
    out.write_text(
        json.dumps(
            {
                "hypothesis": "R31-H352",
                "generated": ts,
                "document": str(DOC),
                "config": str(CONFIG),
                "concurrency_in_flight_both_arms": concurrency,
                "density_threshold": DENSITY_THRESHOLD,
                "sublist_lines": SUBLIST_LINES,
                "probe_note": (
                    "no probe names the catalog document as a source; recall is measured on "
                    "gold-evidence probes whose evidence strings are carried by the catalog's "
                    "own chunks (H353 carrier convention, _present matcher)"
                ),
                "gpu_contention_note": (
                    "vLLM shared with other executors; server_load_samples record external "
                    "in-flight requests per arm; llm_calls and total_out_chars are the "
                    "contention-free proxies"
                ),
                "baseline": base,
                "budgeted": budg,
                "wall_clock_ratio": round(wall_ratio, 4) if wall_ratio is not None else None,
                "dangling_warning_ratio_base_over_budgeted": (
                    round(warn_ratio, 2) if isinstance(warn_ratio, float) else warn_ratio
                ),
                "probe_recall_delta": round(recall_delta, 4) if recall_delta is not None else None,
                "clauses": clauses,
                "verdict": verdict,
            },
            indent=2,
        )
    )
    print(f"H352 REPLAY COMPLETE -> {out} verdict={verdict}", flush=True)


if __name__ == "__main__":
    main()

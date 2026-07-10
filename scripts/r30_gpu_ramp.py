"""R30-H341/H342: per-doc concurrency ramp on the real extraction workload.

Drives the REAL per-chunk extraction path (`extract_chunk`, enumerate recipe,
production ontology from the neo4j4 metanode) against the local vLLM
gpt-oss-120b at a fixed ladder of concurrency steps, measuring per step:

  - chunk completions in the window (client goodput - the H346 control signal)
  - vLLM prompt+generation token deltas -> aggregate tok/s (comparable to the
    8,232 tok/s b64 ceiling, my-gpu r6)
  - per-request latencies (persisted raw - H342's 0-drop concurrency x timeout
    frontier falls out analytically: drop-rate(c, t) = fraction of latencies > t)
  - errors, plus max observed server running/waiting

H341 knee/plateau and H347's detector run offline over this output. Checkpoints
every step to results/r30/ramp-steps.jsonl (detached-compute rule).

Usage: python scripts/r30_gpu_ramp.py [step ...]   (default ladder 1..64)
"""

import itertools
import json
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from knowledge_graph_foundry.extraction.extractor import extract_chunk
from knowledge_graph_foundry.engines import create_engine
from knowledge_graph_foundry.ingest.chunking import chunk_document
from knowledge_graph_foundry.ingest.readers import iter_source_files, read_document
from knowledge_graph_foundry.models import Ontology
from knowledge_graph_foundry.pipeline import Foundry
from knowledge_graph_foundry.settings import load_settings

CONFIG = Path("config-r29-v1.yml")  # composed default engine, enumerate recipe
CORPUS = Path("data/external/cpap-datasheets-and-manuals")
METRICS_URL = "http://localhost:8010/metrics"
STEPS = [int(a) for a in sys.argv[1:]] or [1, 2, 4, 8, 16, 24, 32, 48, 64]
WARMUP_S = 20
WINDOW_S = 90
CHECKPOINT = Path("results/r30/ramp-steps.jsonl")


def server_counters() -> dict:
    with urllib.request.urlopen(METRICS_URL, timeout=5) as r:
        text = r.read().decode()
    out = {}
    for line in text.splitlines():
        for key, name in (
            ("prompt", "vllm:prompt_tokens_total"),
            ("generation", "vllm:generation_tokens_total"),
            ("running", "vllm:num_requests_running"),
            ("waiting", "vllm:num_requests_waiting{"),
        ):
            if line.startswith(name):
                out[key] = float(line.rsplit(" ", 1)[1])
    return out


def main():
    settings = load_settings(CONFIG)
    settings.event_log = None  # no JSONL sink for the ramp

    # production ontology from the neo4j4 metanode (v2-run2 final state)
    state = Foundry(settings)._load_state()
    if not state or not state.get("ontology"):
        raise SystemExit("no ontology on neo4j4 - ramp needs the production type system")
    ontology = Ontology(**state["ontology"])
    purpose = state.get("purpose", "")
    print(f"ontology: {len(ontology.types)} types, cured={ontology.cured}", flush=True)

    engine = create_engine(settings.llm)
    ex = settings.extraction

    chunks = []
    for f in iter_source_files(CORPUS):
        if f.suffix.lower() != ".pdf":
            continue
        try:
            doc = read_document(f, parser_union=ex.parser_union, glyph_normalization=ex.glyph_normalization)
            chunks.extend(chunk_document(doc, ex.chunk_size, ex.chunk_overlap, ex.header_carryover))
        except Exception as exc:
            print(f"skip {f.name}: {exc}", flush=True)
    if len(chunks) < 50:
        raise SystemExit(f"only {len(chunks)} chunks - corpus parse failed")
    print(f"chunk pool: {len(chunks)} chunks from {CORPUS}", flush=True)

    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    chunk_cycle = itertools.cycle(chunks)
    all_steps = []

    for c in STEPS:
        lock = threading.Lock()
        latencies, errors = [], [0]
        window_completions = [0]
        stop = threading.Event()
        t_measure_start = [0.0]
        peak = {"running": 0.0, "waiting": 0.0}

        def work():
            while not stop.is_set():
                with lock:
                    chunk = next(chunk_cycle)
                t0 = time.monotonic()
                try:
                    extract_chunk(chunk, purpose, ontology, engine, ex)
                    ok = True
                except Exception:
                    ok = False
                dt = time.monotonic() - t0
                with lock:
                    if not ok:
                        errors[0] += 1
                    latencies.append(round(dt, 2))
                    if t_measure_start[0] and time.monotonic() >= t_measure_start[0] and ok:
                        window_completions[0] += 1

        pool = ThreadPoolExecutor(max_workers=c, thread_name_prefix=f"ramp-c{c}")
        for _ in range(c):
            pool.submit(work)

        time.sleep(WARMUP_S)
        t_measure_start[0] = time.monotonic()
        start_counters = server_counters()
        t_end = time.monotonic() + WINDOW_S
        while time.monotonic() < t_end:
            time.sleep(5)
            try:
                s = server_counters()
                peak["running"] = max(peak["running"], s.get("running", 0))
                peak["waiting"] = max(peak["waiting"], s.get("waiting", 0))
            except Exception:
                pass
        end_counters = server_counters()
        stop.set()
        drain0 = time.monotonic()
        pool.shutdown(wait=True)  # in-flight requests finish; their latencies count for H342
        drain = time.monotonic() - drain0

        tok = (end_counters.get("prompt", 0) - start_counters.get("prompt", 0)) + (
            end_counters.get("generation", 0) - start_counters.get("generation", 0)
        )
        gen = end_counters.get("generation", 0) - start_counters.get("generation", 0)
        step = {
            "concurrency": c,
            "window_s": WINDOW_S,
            "completions_in_window": window_completions[0],
            "chunks_per_min": round(window_completions[0] * 60 / WINDOW_S, 2),
            "tok_s_total": round(tok / WINDOW_S, 1),
            "tok_s_generation": round(gen / WINDOW_S, 1),
            "errors": errors[0],
            "latencies_s": latencies,
            "peak_running": peak["running"],
            "peak_waiting": peak["waiting"],
            "drain_s": round(drain, 1),
        }
        all_steps.append(step)
        with CHECKPOINT.open("a") as fh:
            fh.write(json.dumps(step) + "\n")
        print(
            f"STEP c={c}: {step['chunks_per_min']} chunks/min, {step['tok_s_total']} tok/s total "
            f"({step['tok_s_generation']} gen), errors={errors[0]}, peak run/wait={peak['running']:.0f}/{peak['waiting']:.0f}",
            flush=True,
        )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/r30-ramp-{ts}.json")
    out.write_text(
        json.dumps(
            {
                "hypothesis": "R30-H341/H342",
                "generated": ts,
                "config": str(CONFIG),
                "chunk_pool": len(chunks),
                "warmup_s": WARMUP_S,
                "steps": all_steps,
            },
            indent=2,
        )
    )
    print(f"RAMP COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

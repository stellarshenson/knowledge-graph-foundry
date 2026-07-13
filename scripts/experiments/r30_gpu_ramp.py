"""R30-H363 (supersedes the H341 run of this script): clean concurrency ramp.

The H341 run self-invalidated its goodput column (90s wall window < one chunk's
357s+ lifetime) and contaminated tok/s above c~24 (p50 wall > t600 -> silent
client retries). This extension repairs the instrument per the H363 registration:

  - COMPLETION-SIZED windows: per rung, warmup = every worker banks 1 chunk,
    measurement window = every worker banks 3 MORE (window completions >= 3c)
  - t=3600 via config/experiments/config-r31-gate.yml so every request is single-attempt
  - per-ATTEMPT reconciliation: engine.calls (logical calls at the engine
    boundary) vs vLLM request_success_total delta; excess = hidden attempts
    (HTTP retries + instructor validation re-asks) - the H362 blind spot
  - per-request latencies persisted raw as before

Outputs: reports/experiments/r30/h363-steps.jsonl (checkpoint), reports/experiments/adjudicated/r30-h363-ramp-<ts>.json.
H347's knee detectors run offline over this output.

Usage: python scripts/experiments/r30_gpu_ramp.py [step ...]   (default ladder 16..96)
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

CONFIG = Path("config/experiments/config-r31-gate.yml")  # r29-v1 + llm.timeout 3600 (single-attempt regime)
CORPUS = Path("data/external/cpap-datasheets-and-manuals")
METRICS_URL = "http://localhost:8010/metrics"
STEPS = [int(a) for a in sys.argv[1:]] or [16, 24, 32, 48, 64, 96]
WARMUP_COMPLETIONS = 1  # per worker: first chunk = steady-state reached
WINDOW_COMPLETIONS = 3  # per worker: measured chunks (window total >= 3c, the H363 bar)
CHECKPOINT = Path("reports/experiments/r30/h363-steps.jsonl")


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
            ("success", "vllm:request_success_total"),
        ):
            if line.startswith(name):
                out[key] = out.get(key, 0.0) + float(line.rsplit(" ", 1)[1])
    return out


def main():
    settings = load_settings(CONFIG)
    settings.event_log = None  # no JSONL sink for the ramp

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
        counts = [0] * c  # completions per worker (ok or error - lifetime is what windows need)
        stop = threading.Event()

        def work(idx: int):
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
                    counts[idx] += 1

        pool = ThreadPoolExecutor(max_workers=c, thread_name_prefix=f"ramp-c{c}")
        t_rung = time.monotonic()
        for i in range(c):
            pool.submit(work, i)

        def wait_until(target: list, phase: str) -> None:
            while True:
                time.sleep(10)
                with lock:
                    done = min(counts[i] - target[i] for i in range(c))
                if done >= (WARMUP_COMPLETIONS if phase == "warmup" else WINDOW_COMPLETIONS):
                    return

        # warmup: every worker banks its first chunk
        wait_until([0] * c, "warmup")
        with lock:
            base = counts[:]
            base_lat_n = len(latencies)
        warmup_s = time.monotonic() - t_rung
        start_counters = server_counters()
        calls_start = engine.calls
        t_win = time.monotonic()
        peak = {"running": 0.0, "waiting": 0.0}

        # window: every worker banks WINDOW_COMPLETIONS more
        while True:
            time.sleep(10)
            try:
                s = server_counters()
                peak["running"] = max(peak["running"], s.get("running", 0))
                peak["waiting"] = max(peak["waiting"], s.get("waiting", 0))
            except Exception:
                pass
            with lock:
                done = min(counts[i] - base[i] for i in range(c))
            if done >= WINDOW_COMPLETIONS:
                break
        window_s = time.monotonic() - t_win
        end_counters = server_counters()
        calls_end = engine.calls
        with lock:
            window_completions = sum(counts) - sum(base)
            window_latencies = latencies[base_lat_n:]

        stop.set()
        drain0 = time.monotonic()
        pool.shutdown(wait=True)
        drain = time.monotonic() - drain0

        tok = (end_counters.get("prompt", 0) - start_counters.get("prompt", 0)) + (
            end_counters.get("generation", 0) - start_counters.get("generation", 0)
        )
        gen = end_counters.get("generation", 0) - start_counters.get("generation", 0)
        server_reqs = end_counters.get("success", 0) - start_counters.get("success", 0)
        client_calls = calls_end - calls_start
        step = {
            "concurrency": c,
            "warmup_s": round(warmup_s, 1),
            "window_s": round(window_s, 1),
            "completions_in_window": window_completions,
            "chunks_per_min": round(window_completions * 60 / window_s, 2),
            "tok_s_total": round(tok / window_s, 1),
            "tok_s_generation": round(gen / window_s, 1),
            "client_calls_window": client_calls,
            "server_requests_window": server_reqs,
            "hidden_attempts": round(server_reqs - client_calls, 1),
            "errors": errors[0],
            "latencies_s": window_latencies,
            "peak_running": peak["running"],
            "peak_waiting": peak["waiting"],
            "drain_s": round(drain, 1),
        }
        all_steps.append(step)
        with CHECKPOINT.open("a") as fh:
            fh.write(json.dumps(step) + "\n")
        print(
            f"STEP c={c}: {step['chunks_per_min']} chunks/min ({window_completions} in {window_s:.0f}s), "
            f"{step['tok_s_total']} tok/s total ({step['tok_s_generation']} gen), "
            f"hidden_attempts={step['hidden_attempts']}, errors={errors[0]}, "
            f"peak run/wait={peak['running']:.0f}/{peak['waiting']:.0f}",
            flush=True,
        )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/experiments/adjudicated/r30-h363-ramp-{ts}.json")
    out.write_text(
        json.dumps(
            {
                "hypothesis": "R30-H363",
                "generated": ts,
                "config": str(CONFIG),
                "chunk_pool": len(chunks),
                "warmup_completions_per_worker": WARMUP_COMPLETIONS,
                "window_completions_per_worker": WINDOW_COMPLETIONS,
                "steps": all_steps,
            },
            indent=2,
        )
    )
    print(f"H363 RAMP COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

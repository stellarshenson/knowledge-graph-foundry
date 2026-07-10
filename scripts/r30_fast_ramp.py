"""R30-H388: steady-state counter windows replace completion-gated rungs.

Same client, chunk pool, counters, and per-attempt reconciliation as
scripts/r30_gpu_ramp.py (H363) - only the window logic is swapped:

  - warmup: sum of completions >= max(c/2, 8) AND rolling 2-min counter
    tok/s stable within 10% (two consecutive readings) - de-synchronized
    steady state, no straggler gate
  - window: fixed 600s counter delta with an occupancy guard - min
    num_requests_running sampled through the window must stay >= 0.95c,
    else the rung is marked tainted (report and re-run by hand)

Outputs: results/r30/h388-fast-steps.jsonl (checkpoint),
reports/r30-h388-fast-ramp-<ts>.json. Parity is judged against the closed
H363 STEPs in results/r30/h363-steps.jsonl; H347's knee detectors run
offline over the merged curve.

Usage: python scripts/r30_fast_ramp.py [step ...]   (default ladder 32 48 64 96 128)
"""

import itertools
import json
import sys
import threading
import time
import urllib.request
from collections import deque
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

CONFIG = Path("config-r31-gate.yml")  # r29-v1 + llm.timeout 3600 (single-attempt regime)
CORPUS = Path("data/external/cpap-datasheets-and-manuals")
METRICS_URL = "http://localhost:8010/metrics"
STEPS = [int(a) for a in sys.argv[1:]] or [32, 48, 64, 96, 128]
WINDOW_S = 600  # fixed counter-delta window (the H388 lever)
STABLE_TOL = 0.10  # rolling 2-min tok/s agreement that ends warmup
OCCUPANCY_FLOOR = 0.95  # min running / c through the window, else tainted
CHECKPOINT = Path("results/r30/h388-fast-steps.jsonl")


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
        completions = [0]
        stop = threading.Event()

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
                    completions[0] += 1

        pool = ThreadPoolExecutor(max_workers=c, thread_name_prefix=f"fast-c{c}")
        t_rung = time.monotonic()
        for _ in range(c):
            pool.submit(work)

        # warmup: enough turnover to de-synchronize + rolling counter rate stable.
        # samples: (t, prompt+generation) every 15s; rate over the trailing ~2 min
        min_completions = max(c // 2, 8)
        samples = deque(maxlen=9)  # 9 x 15s = trailing 2 min
        prev_rate = None
        while True:
            time.sleep(15)
            try:
                s = server_counters()
            except Exception:
                continue
            samples.append((time.monotonic(), s.get("prompt", 0) + s.get("generation", 0)))
            with lock:
                done = completions[0]
            if done < min_completions or len(samples) < samples.maxlen:
                continue
            (t0, tok0), (t1, tok1) = samples[0], samples[-1]
            rate = (tok1 - tok0) / (t1 - t0)
            if prev_rate and rate > 0 and abs(rate - prev_rate) / prev_rate <= STABLE_TOL:
                break
            prev_rate = rate
        warmup_s = time.monotonic() - t_rung

        with lock:
            base_completions = completions[0]
            base_lat_n = len(latencies)
        start_counters = server_counters()
        calls_start = engine.calls
        t_win = time.monotonic()
        occupancy = {"min_running": float("inf"), "peak_waiting": 0.0}

        # window: fixed WINDOW_S, occupancy sampled every 10s
        while time.monotonic() - t_win < WINDOW_S:
            time.sleep(10)
            try:
                s = server_counters()
                occupancy["min_running"] = min(occupancy["min_running"], s.get("running", 0))
                occupancy["peak_waiting"] = max(occupancy["peak_waiting"], s.get("waiting", 0))
            except Exception:
                pass
        window_s = time.monotonic() - t_win
        end_counters = server_counters()
        calls_end = engine.calls
        with lock:
            window_completions = completions[0] - base_completions
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
        tainted = occupancy["min_running"] < OCCUPANCY_FLOOR * c
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
            "min_running": occupancy["min_running"],
            "peak_waiting": occupancy["peak_waiting"],
            "tainted": tainted,
            "drain_s": round(drain, 1),
        }
        all_steps.append(step)
        with CHECKPOINT.open("a") as fh:
            fh.write(json.dumps(step) + "\n")
        print(
            f"FAST STEP c={c}: {step['tok_s_total']} tok/s total ({step['tok_s_generation']} gen), "
            f"{step['chunks_per_min']} chunks/min ({window_completions} in {window_s:.0f}s window, "
            f"warmup {warmup_s:.0f}s), hidden_attempts={step['hidden_attempts']}, errors={errors[0]}, "
            f"min run/peak wait={occupancy['min_running']:.0f}/{occupancy['peak_waiting']:.0f}"
            f"{' TAINTED' if tainted else ''}",
            flush=True,
        )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(f"reports/r30-h388-fast-ramp-{ts}.json")
    out.write_text(
        json.dumps(
            {
                "hypothesis": "R30-H388",
                "generated": ts,
                "config": str(CONFIG),
                "chunk_pool": len(chunks),
                "window_s": WINDOW_S,
                "stable_tol": STABLE_TOL,
                "occupancy_floor": OCCUPANCY_FLOOR,
                "steps": all_steps,
            },
            indent=2,
        )
    )
    print(f"H388 FAST RAMP COMPLETE -> {out}", flush=True)


if __name__ == "__main__":
    main()

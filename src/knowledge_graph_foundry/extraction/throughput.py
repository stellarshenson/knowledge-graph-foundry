"""R30-H362 throughput calibration: the engine remembers its knee.

A per-setup cache maps the full inference identity (engine type -> endpoint
-> model ID -> extraction-config hash) to a measured operating point (knee
concurrency, tok/s, chunks/min, latency envelope). Ingest warm-starts at the
cached knee and verifies it against the entry's own variance band inside the
first measurement window (trust-but-verify); a cold or lost cache falls back
to a doubling ramp with early exit. Probe methodology = the H388 fast rung
(stability-gated warmup + fixed counter window with an occupancy guard),
CONFIRMED at <= 1/3 the completion-gated wall cost with work-rate parity
0.6% (see kgf-redesign-experiments.md R30-H388).

Calibration metrics are generation tok/s and chunks/min - total tok/s
carries prompt-mix composition noise at short windows (H388 caveat).
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger

DEFAULT_CACHE_PATH = Path("reports/throughput-cache.json")
BAND_SIGMA = 3.0  # warm-start verification band width
EWMA_ALPHA = 0.3  # cross-run smoothing of the cached expectation
RAMP_EARLY_EXIT_GAIN = 0.20  # doubling gains under this end the cold ramp
KNEE_GOODPUT_SHARE = 0.90  # knee = smallest c within this share of peak


def setup_key(engine: str, endpoint: str, model: str, extraction_config: dict) -> str:
    """One entry per full inference identity; switching setups selects a
    different entry, never invalidates others."""
    cfg = hashlib.sha256(
        json.dumps(extraction_config, sort_keys=True).encode()
    ).hexdigest()[:12]
    return f"{engine}::{endpoint}::{model}::{cfg}"


class ThroughputCache:
    """JSON-file cache of calibration entries, keyed by setup identity."""

    def __init__(self, path: Path | str | None = None):
        # default resolved at call time so tests can repoint the module path
        self.path = Path(path) if path is not None else DEFAULT_CACHE_PATH

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning(f"throughput cache unreadable at {self.path} - cold path")
            return {}

    def get(self, key: str) -> Optional[dict]:
        return self._read().get(key)

    def put(self, key: str, entry: dict) -> None:
        data = self._read()
        data[key] = entry
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2))

    def smooth(self, key: str, measured: dict) -> dict:
        """EWMA-update the cached expectation across runs (never mid-run).
        A provenance flip to `measured` happens on the first real window."""
        prior = self.get(key)
        if not prior or prior.get("provenance") == "shipped":
            entry = {**measured, "provenance": "measured"}
        else:
            entry = dict(prior)
            for f in ("tok_s_generation", "chunks_per_min"):
                if f in measured and f in prior:
                    entry[f] = round(
                        EWMA_ALPHA * measured[f] + (1 - EWMA_ALPHA) * prior[f], 4
                    )
            entry.update(
                {k: v for k, v in measured.items() if k not in ("tok_s_generation", "chunks_per_min")}
            )
            entry["provenance"] = "measured"
        self.put(key, entry)
        return entry


def in_band(entry: dict, window_chunks_per_min: float, sigma: float = BAND_SIGMA) -> bool:
    """Warm-start verification: the first real window's work rate against the
    entry's own variance band. In band -> the run itself is the verification;
    out of band -> recalibrate and replace the entry."""
    mean = entry.get("chunks_per_min")
    spread = entry.get("chunks_per_min_std") or (0.15 * mean if mean else None)
    if mean is None or spread is None:
        return False
    return abs(window_chunks_per_min - mean) <= sigma * spread


def cold_ramp(
    probe: Callable[[int], dict],
    start: int = 1,
    max_concurrency: int = 256,
    early_exit_gain: float = RAMP_EARLY_EXIT_GAIN,
) -> dict:
    """Cold-path doubling ramp (1, 2, 4...) with early exit when a doubling
    gains under ``early_exit_gain``; knee = smallest concurrency within
    ``KNEE_GOODPUT_SHARE`` of peak goodput. ``probe(c)`` runs one H388 fast
    rung and returns at least {tok_s_generation, chunks_per_min, tainted}.
    A tainted rung (occupancy guard) marks the capacity cliff - the ramp
    stops and the knee is chosen below it."""
    points: list[tuple[int, dict]] = []
    c = start
    prev_gen = None
    while c <= max_concurrency:
        step = probe(c)
        logger.info(
            f"throughput ramp c={c}: gen {step.get('tok_s_generation')} tok/s, "
            f"{step.get('chunks_per_min')} chunks/min"
            f"{' TAINTED' if step.get('tainted') else ''}"
        )
        if step.get("tainted"):
            break  # capacity cliff - nothing above is occupancy-clean
        points.append((c, step))
        gen = step.get("tok_s_generation") or 0.0
        if prev_gen is not None and prev_gen > 0 and (gen - prev_gen) / prev_gen < early_exit_gain:
            break
        prev_gen = gen
        c *= 2
    if not points:
        raise RuntimeError("throughput ramp produced no clean rung")
    peak = max(p[1].get("tok_s_generation") or 0.0 for p in points)
    for c, step in points:  # smallest c within the goodput share of peak
        if (step.get("tok_s_generation") or 0.0) >= KNEE_GOODPUT_SHARE * peak:
            return {"knee_concurrency": c, **step}
    c, step = points[-1]
    return {"knee_concurrency": c, **step}

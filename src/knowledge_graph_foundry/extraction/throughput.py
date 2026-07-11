"""R30-H362 throughput calibration: the engine remembers its knee.

A per-setup cache maps an inference-identity key (engine type -> endpoint ->
model ID -> {recipe, timeout} hash) to a measured operating point.

SHIPPED TODAY: ingest warm-starts at the cached concurrency
(`Foundry._extraction_concurrency`); a cache miss falls back to the
configured integer with a log line. NOT YET WIRED (helpers below exist for
the pending H362 clauses, no production caller yet): the in-window band
verification (`in_band`), the cold doubling ramp (`cold_ramp` - also needs a
production probe routine extracted from scripts/r30_fast_ramp.py), and the
EWMA cross-run update (`smooth`). The H362 verdict is withheld until those
clauses run (see kgf-redesign-experiments.md R30-H362).

Calibration metrics are generation tok/s and chunks/min - total tok/s
carries prompt-mix composition noise at short windows (H388 caveat; note
chunks/min itself shows ~20%+ relative spread across repeat windows, so
single-window agreements are not parity evidence).
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger

from knowledge_graph_foundry.config import PROJ_ROOT

# absolute: a detached ingest launched off-root must not silently miss the
# cache and fall back to the configured default (14x throughput loss)
DEFAULT_CACHE_PATH = PROJ_ROOT / "reports" / "throughput-cache.json"
BAND_SIGMA = 3.0  # warm-start verification band width
EWMA_ALPHA = 0.3  # cross-run smoothing of the cached expectation
RAMP_EARLY_EXIT_GAIN = 0.20  # doubling gains under this end the cold ramp
KNEE_GOODPUT_SHARE = 0.90  # cold-ramp knee rule (share-of-peak); NOTE: cached entries store the adjudicated plateau operating point instead - align before wiring (#64)


def setup_key(engine: str, endpoint: str, model: str, extraction_config: dict) -> str:
    """One entry per inference identity; switching setups selects a
    different entry, never invalidates others. NOTE: the identity hash
    covers {recipe, timeout} only (see setup_key_from_settings) - prompt,
    chunking and max_tokens changes reuse the entry; widen deliberately, in
    ONE place, if that ever bites."""
    cfg = hashlib.sha256(
        json.dumps(extraction_config, sort_keys=True).encode()
    ).hexdigest()[:12]
    return f"{engine}::{endpoint}::{model}::{cfg}"


def setup_key_from_settings(settings) -> str:
    """THE canonical key builder - every producer and consumer (pipeline,
    seeders, tests) must key through this one function; hand-built key dicts
    already forked the live cache once (orphan seed entry, 2026-07-11)."""
    llm = settings.llm
    return setup_key(
        llm.engine,
        llm.base_url or llm.region or "",
        llm.model,
        {"recipe": settings.extraction.recipe, "timeout": llm.timeout},
    )


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


def in_band(entry: dict, window_gen_tok_s: float, sigma: float = BAND_SIGMA) -> bool:
    """Warm-start verification: the first real window's GENERATION tok/s
    against the entry's own measured variance band (gen tok/s is the band
    metric - ~4% relative spread across repeat windows vs ~23% for
    chunks/min, which gave a band that could not fail). In band -> the run
    itself is the verification; out of band -> recalibrate."""
    mean = entry.get("tok_s_generation")
    spread = entry.get("tok_s_generation_std")
    # no measured variance -> cannot verify (H351 rule: bands priced off
    # measured variance, never a magic fallback tolerance)
    if mean is None or spread is None:
        return False
    return abs(window_gen_tok_s - mean) <= sigma * spread


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

"""Event system: named blinker signals plus an optional JSONL event log.

Every pipeline stage emits through `emit(signal_name, **payload)`. The JSONL
log (enabled via Settings.event_log) captures every emission with a
timestamp - this is what makes benchmark forensics possible.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Optional

from blinker import signal

SIGNALS = [
    # ingestion
    "document.started",
    "document.completed",
    "document.skipped",
    "chunk.extracted",
    # extraction
    "extraction.completed",
    "extraction.warning",
    # resolution
    "resolution.merge",
    "resolution.defer",
    "resolution.block",
    "resolution.synonym_cluster",
    # ontology lifecycle
    "ontology.type_emerged",
    "ontology.type_confirmed",
    "ontology.evolved",
    "curing.metrics",
    "curing.cured",
    "curing.forced",
    # graph
    "load.batch",
    "load.completed",
    "graphrag.communities",
    "graphrag.scorecard",
    # drift
    "drift.warning",
    "drift.decision",
    # lifecycle
    "fsm.transition",
    "pipeline.error",
]


class EventLog:
    """JSONL sink subscribed to every signal."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a")

    def write(self, name: str, payload: dict[str, Any]) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": name,
            **payload,
        }
        self._fh.write(json.dumps(record, default=str) + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


_event_log: Optional[EventLog] = None


def enable_event_log(path: Path | str) -> None:
    global _event_log
    _event_log = EventLog(Path(path))


def disable_event_log() -> None:
    global _event_log
    if _event_log is not None:
        _event_log.close()
    _event_log = None


def emit(name: str, **payload: Any) -> None:
    """Emit a named signal to subscribers and the JSONL log."""
    signal(name).send("kgf", **payload)
    if _event_log is not None:
        _event_log.write(name, payload)


def subscribe(name: str, receiver: Any) -> None:
    signal(name).connect(receiver, weak=False)


def unsubscribe(name: str, receiver: Any) -> None:
    signal(name).disconnect(receiver)

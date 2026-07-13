"""R26-H274 external answer cache: query->answer kept OUTSIDE the graph, keyed
to graph state (corpus fingerprint).

CONFIRMED and PREFERRED over the in-graph derived layer (R26-H273): equal
answer-staleness safety at zero graph-contamination surface - content lives in
a file, never in the source-of-truth graph. Invalidation is automatic and
coarse (the shipped gate-calibration grade, R38-H384): a cache entry carries
the corpus fingerprint it was produced under, so when the graph mutates (a new
ingest changes the fingerprint) every prior-generation entry stops matching and
is pruned on the next store. Repairs that change answers WITHOUT adding
documents do not change the fingerprint - the same limitation the gate
calibration carries; a full graph-state hash would close it at a per-query cost.
"""

import hashlib
import json
from pathlib import Path
from typing import Optional, Union


def cache_key(question: str, fingerprint: str) -> str:
    """Normalized (case- and whitespace-insensitive) question joined to the
    graph fingerprint; two graph generations never collide on a key."""
    norm = " ".join((question or "").lower().split())
    return hashlib.sha1(f"{fingerprint}|{norm}".encode()).hexdigest()[:16]


class AnswerCache:
    """File-backed query->answer store: one JSON object on disk mapping key ->
    {fingerprint, result}. Reloaded on construction so a concurrent writer is
    observed; pruned to the current graph generation on every store."""

    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        self._data: dict = {}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text())
            except (ValueError, OSError):
                self._data = {}

    def lookup(self, question: str, fingerprint: str) -> Optional[dict]:
        entry = self._data.get(cache_key(question, fingerprint))
        if entry and entry.get("fingerprint") == fingerprint:
            return entry.get("result")
        return None

    def store(self, question: str, fingerprint: str, result: dict) -> None:
        # Drop superseded-generation entries: automatic invalidation + bound.
        self._data = {
            k: v for k, v in self._data.items() if v.get("fingerprint") == fingerprint
        }
        self._data[cache_key(question, fingerprint)] = {
            "fingerprint": fingerprint,
            "result": result,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data))

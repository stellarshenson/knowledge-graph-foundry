"""Post-cure drift detection and the rebuild decision engine.

Two independent signals, both windowed so a single outlier document never
fires: the per-document remap rate (entities whose extracted types had to be
remapped onto the cured ontology) and the JSD between the cured type
distribution and a rolling post-cure window. The decision engine classifies
evidence into none / warn / recure / rebuild; recure drives the FSM, rebuild
is only ever a recommendation with the evidence attached.
"""

from __future__ import annotations

import math
from typing import NamedTuple

from knowledge_graph_foundry.events import emit
from knowledge_graph_foundry.settings import DriftSettings


class DriftVerdict(NamedTuple):
    action: str  # none | warn | recure | rebuild
    evidence: dict


def _jsd(p: dict[str, int], q: dict[str, int]) -> float:
    """Jensen-Shannon divergence between two frequency dicts."""
    keys = set(p) | set(q)
    if not keys:
        return 0.0
    total_p = sum(p.values()) or 1
    total_q = sum(q.values()) or 1
    pp = [p.get(k, 0) / total_p for k in keys]
    qq = [q.get(k, 0) / total_q for k in keys]
    mm = [(a + b) / 2 for a, b in zip(pp, qq)]

    def _kl(x: list[float], m: list[float]) -> float:
        return sum(xi * math.log2(xi / mi) for xi, mi in zip(x, m) if xi > 0 and mi > 0)

    return 0.5 * _kl(pp, mm) + 0.5 * _kl(qq, mm)


class DriftDetector:
    """Tracks post-cure documents and renders a windowed drift verdict."""

    def __init__(self, cfg: DriftSettings, cured_frequencies: dict[str, int]):
        self.cfg = cfg
        self.cured_frequencies = dict(cured_frequencies)
        self._remap_rates: list[float] = []
        self._window_frequencies: list[dict[str, int]] = []
        self._recuring = False

    def record_document(self, remap_rate: float, type_frequencies: dict[str, int]) -> DriftVerdict:
        """Record one post-cure document and return the current verdict."""
        self._remap_rates.append(remap_rate)
        self._window_frequencies.append(dict(type_frequencies))

        verdict = self._evaluate()
        if verdict.action != "none":
            emit(
                "drift.warning" if verdict.action == "warn" else "drift.decision",
                **verdict.evidence,
                action=verdict.action,
            )
        return verdict

    def _evaluate(self) -> DriftVerdict:
        window = self.cfg.window
        if len(self._remap_rates) < window:
            return DriftVerdict("none", {})

        recent_rates = self._remap_rates[-window:]
        sustained_remap = all(r > self.cfg.remap_rate_threshold for r in recent_rates)

        merged: dict[str, int] = {}
        for freqs in self._window_frequencies[-window:]:
            for k, v in freqs.items():
                merged[k] = merged.get(k, 0) + v
        divergence = _jsd(self.cured_frequencies, merged)

        evidence = {
            "remap_rates": recent_rates,
            "jsd": divergence,
            "window": window,
        }

        if divergence > self.cfg.rebuild_jsd_threshold and sustained_remap:
            return DriftVerdict("rebuild", evidence)
        if sustained_remap:
            if self._recuring:
                return DriftVerdict("none", evidence)  # coalesce during RECURING
            return DriftVerdict("recure", evidence)
        if any(r > self.cfg.remap_rate_threshold for r in recent_rates):
            return DriftVerdict("warn", evidence)
        return DriftVerdict("none", evidence)

    def begin_recure(self) -> None:
        self._recuring = True

    def end_recure(self, cured_frequencies: dict[str, int]) -> None:
        self._recuring = False
        self.cured_frequencies = dict(cured_frequencies)
        self._remap_rates.clear()
        self._window_frequencies.clear()

    def to_dict(self) -> dict:
        return {
            "cured_frequencies": self.cured_frequencies,
            "remap_rates": self._remap_rates,
            "window_frequencies": self._window_frequencies,
            "recuring": self._recuring,
        }

    @classmethod
    def from_dict(cls, data: dict, cfg: DriftSettings) -> "DriftDetector":
        detector = cls(cfg, data.get("cured_frequencies", {}))
        detector._remap_rates = list(data.get("remap_rates", []))
        detector._window_frequencies = [dict(f) for f in data.get("window_frequencies", [])]
        detector._recuring = bool(data.get("recuring", False))
        return detector

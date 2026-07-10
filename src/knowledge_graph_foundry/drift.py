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
from typing import NamedTuple, Optional

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
        self._contradictions: list[int] = []  # R8: per-document invalidation counts
        self._recuring = False
        # R36-H378: CUSUM recure trigger (H317) - one-sided accumulator over the
        # dense per-document JSD series; mu0 arms from the first window's median
        self._cusum_s = 0.0
        self._cusum_mu0: Optional[float] = None
        self._jsd_series: list[float] = []
        self._recure_frequencies: list[dict[str, int]] = []  # docs seen while RECURING

    def record_contradictions(self, invalidated: int, entities: int) -> Optional[DriftVerdict]:
        """R8 fact-drift alarm: track the rate of edges invalidated per document
        (superseding facts). Sustained high contradiction-rate is the real
        signal that the world is moving under the graph - distinct from schema
        drift (remap + JSD). Returns a fact_drift verdict when the windowed rate
        crosses the threshold, else None."""
        rate = invalidated / entities if entities else 0.0
        self._contradictions.append(rate)
        window = self.cfg.window
        if len(self._contradictions) < window:
            return None
        recent = self._contradictions[-window:]
        mean_rate = sum(recent) / window
        if mean_rate > self.cfg.contradiction_rate_threshold:
            evidence = {"contradiction_rate": mean_rate, "window": window}
            emit("drift.warning", action="fact_drift", **evidence)
            return DriftVerdict("fact_drift", evidence)
        return None

    def record_document(self, remap_rate: float, type_frequencies: dict[str, int]) -> DriftVerdict:
        """Record one post-cure document and return the current verdict."""
        self._remap_rates.append(remap_rate)
        self._window_frequencies.append(dict(type_frequencies))
        if self._recuring:
            self._recure_frequencies.append(dict(type_frequencies))

        verdict = self._cusum_evaluate() if self.cfg.cusum_enabled else self._evaluate()
        if verdict.action != "none":
            emit(
                "drift.warning" if verdict.action == "warn" else "drift.decision",
                **verdict.evidence,
                action=verdict.action,
            )
        return verdict

    def _cusum_evaluate(self) -> DriftVerdict:
        """R36-H378/DEF-9: the H317 CUSUM trigger. The boolean conjunction
        (jsd > threshold AND all-window remap breaches) is anti-phase and
        structurally never fires (R28 verdict); the one-sided CUSUM
        S = max(0, S + (x - (mu0 + k))) accumulates sub-threshold excess and
        fires on both the step change and the slow ramp the boolean is blind
        to. Deterministic left-fold - state survives to_dict/from_dict."""
        x = _jsd(self.cured_frequencies, self._window_frequencies[-1])
        self._jsd_series.append(x)
        if self._cusum_mu0 is None:
            if len(self._jsd_series) < self.cfg.window:
                return DriftVerdict("none", {})
            head = sorted(self._jsd_series[: self.cfg.window])
            self._cusum_mu0 = head[len(head) // 2]
        self._cusum_s = max(0.0, self._cusum_s + (x - (self._cusum_mu0 + self.cfg.cusum_k)))
        evidence = {
            "cusum_s": round(self._cusum_s, 4),
            "jsd": round(x, 4),
            "mu0": round(self._cusum_mu0, 4),
        }
        if self._cusum_s > self.cfg.cusum_h:
            self._cusum_s = 0.0  # reset on fire (H317 form)
            if self._recuring:
                return DriftVerdict("none", evidence)  # coalesce during RECURING
            return DriftVerdict("recure", evidence)
        return DriftVerdict("none", evidence)

    def recure_ready(self) -> bool:
        """RECURING exit gate: enough post-recure documents accumulated."""
        return self._recuring and len(self._recure_frequencies) >= self.cfg.window

    def recure_window_frequencies(self) -> dict[str, int]:
        """Merged type frequencies observed while RECURING - the new register."""
        merged: dict[str, int] = {}
        for freqs in self._recure_frequencies:
            for k, v in freqs.items():
                merged[k] = merged.get(k, 0) + v
        return merged

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
        self._recure_frequencies.clear()
        self._cusum_s = 0.0
        self._cusum_mu0 = None  # re-arm against the new baseline
        self._jsd_series.clear()

    def to_dict(self) -> dict:
        return {
            "cured_frequencies": self.cured_frequencies,
            "remap_rates": self._remap_rates,
            "window_frequencies": self._window_frequencies,
            "contradictions": self._contradictions,
            "recuring": self._recuring,
            "cusum_s": self._cusum_s,
            "cusum_mu0": self._cusum_mu0,
            "jsd_series": self._jsd_series,
            "recure_frequencies": self._recure_frequencies,
        }

    @classmethod
    def from_dict(cls, data: dict, cfg: DriftSettings) -> "DriftDetector":
        detector = cls(cfg, data.get("cured_frequencies", {}))
        detector._remap_rates = list(data.get("remap_rates", []))
        detector._window_frequencies = [dict(f) for f in data.get("window_frequencies", [])]
        detector._contradictions = list(data.get("contradictions", []))
        detector._recuring = bool(data.get("recuring", False))
        detector._cusum_s = float(data.get("cusum_s", 0.0))
        detector._cusum_mu0 = data.get("cusum_mu0")
        detector._jsd_series = list(data.get("jsd_series", []))
        detector._recure_frequencies = [dict(f) for f in data.get("recure_frequencies", [])]
        return detector


def adopt_drifted_types(
    ontology, window_frequencies: dict[str, int], min_share: float
) -> list[str]:
    """RECURING exit, patch tier: adopt into the cured ontology the types that
    carried sustained mass in the recure window - stops the same register from
    re-alarming immediately after the exit (livelock guard). Returns adopted
    type names."""
    from knowledge_graph_foundry.models import TypeDef

    total = sum(window_frequencies.values()) or 1
    adopted = []
    for name, count in sorted(window_frequencies.items(), key=lambda kv: -kv[1]):
        if name in ontology.types or count / total < min_share:
            continue
        ontology.types[name] = TypeDef(name=name, status="cured", encounters=count)
        adopted.append(name)
    if adopted:
        emit("drift.types_adopted", types=adopted)
    return adopted

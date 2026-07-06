"""Curing detector - decides when the fluid type system has stabilized.

Consumes StabilityMetrics records and applies the v1-validated composite
criterion: JSD < 0.02 AND Chao1 coverage > 0.95 AND entropy delta < 0.01
(all configurable), after a minimum number of documents. A plateau check
(flat entropy with no new types over the variance window) catches corpora
that stabilize without full coverage; max_fluid_documents force-cures.
"""

from __future__ import annotations

from knowledge_graph_foundry.settings import CuringSettings


class CuringDetector:
    def __init__(self, cfg: CuringSettings):
        self.cfg = cfg
        self._records: list[dict[str, float]] = []

    @property
    def docs_processed(self) -> int:
        return len(self._records)

    def record(self, metrics: dict[str, float]) -> None:
        self._records.append(dict(metrics))

    def missing_mass_ucb(self) -> float | None:
        """DEF-3: Good-Turing missing mass with a one-sided upper confidence bound.

        The missing mass n1/N estimates the probability that the NEXT type
        observation is an unseen type; its UCB adds z*sqrt(n1+1)/N. The
        confidence term replaces any hardcoded count floor: at small N the
        bound is wide and blocks curing by itself, so the minimum evidence
        mass EMERGES from the statistics (~z/threshold observations) instead
        of being decreed. No corpus-size input anywhere - stream-native.
        Returns None when the counters are absent (older state, unit fixtures).
        """
        latest = self._records[-1] if self._records else {}
        total = latest.get("total_occurrences")
        singletons = latest.get("singletons")
        if not total or singletons is None:
            return None
        n1 = float(singletons)
        return n1 / total + self.cfg.missing_mass_z * ((n1 + 1.0) ** 0.5) / total

    def has_sufficient_evidence(self) -> bool:
        ucb = self.missing_mass_ucb()
        return ucb is None or ucb <= self.cfg.missing_mass_threshold

    def is_converged(self) -> bool:
        """Composite criterion on the latest record.

        R7: the Chao1 coverage estimator fluctuates wildly on tiny samples,
        so the gate is blocked until min_samples_before_cure documents have
        been recorded - a minimum-observation floor, not just min_documents.
        DEF-3: additionally blocked until the evidence-mass and Good-Turing
        missing-mass gate passes.
        """
        floor = max(self.cfg.min_documents, self.cfg.min_samples_before_cure)
        if len(self._records) < floor:
            return False
        if not self.has_sufficient_evidence():
            return False
        latest = self._records[-1]
        return (
            latest.get("js_divergence", 1.0) < self.cfg.jsd_threshold
            and latest.get("chao1_coverage", 0.0) > self.cfg.chao1_threshold
            and abs(latest.get("entropy_shannon_delta", 1.0)) < self.cfg.entropy_delta_threshold
        )

    def is_plateau(self, window: int = 3) -> bool:
        """No new types and near-flat entropy over the last `window` records.

        DEF-3: gated on the same evidence-mass check as convergence - a flat
        window over a handful of observations is small-sample noise, not a
        plateau (wave 1 cured at document 4 of 481 through this hole).
        """
        if len(self._records) < max(window, self.cfg.min_documents):
            return False
        if not self.has_sufficient_evidence():
            return False
        tail = self._records[-window:]
        type_counts = [r.get("unique_types", 0.0) for r in tail]
        entropy_deltas = [abs(r.get("entropy_shannon_delta", 1.0)) for r in tail]
        return len(set(type_counts)) == 1 and all(d < 0.1 for d in entropy_deltas)

    def is_force_required(self) -> bool:
        return len(self._records) >= self.cfg.max_fluid_documents

    def should_cure(self) -> tuple[bool, str]:
        """Check order: converged -> plateau -> force. Returns (cure, reason)."""
        if self.is_converged():
            return True, "converged"
        if self.is_plateau():
            return True, "plateau"
        if self.is_force_required():
            return True, "forced"
        return False, "fluid"

    def to_dict(self) -> dict:
        return {"records": self._records}

    @classmethod
    def from_dict(cls, data: dict, cfg: CuringSettings) -> "CuringDetector":
        detector = cls(cfg)
        detector._records = [dict(r) for r in data.get("records", [])]
        return detector

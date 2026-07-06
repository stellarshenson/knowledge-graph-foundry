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

    def is_converged(self) -> bool:
        """Composite criterion on the latest record."""
        if len(self._records) < self.cfg.min_documents:
            return False
        latest = self._records[-1]
        return (
            latest.get("js_divergence", 1.0) < self.cfg.jsd_threshold
            and latest.get("chao1_coverage", 0.0) > self.cfg.chao1_threshold
            and abs(latest.get("entropy_shannon_delta", 1.0)) < self.cfg.entropy_delta_threshold
        )

    def is_plateau(self, window: int = 3) -> bool:
        """No new types and near-flat entropy over the last `window` records."""
        if len(self._records) < max(window, self.cfg.min_documents):
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

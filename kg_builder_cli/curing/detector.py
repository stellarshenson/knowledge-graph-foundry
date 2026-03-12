"""Curing detection for fluid-to-stable ontology evolution."""

from __future__ import annotations

from loguru import logger

from kg_builder_cli.types.config import CuringConfig


class CuringDetector:
    """Detects when the ontology schema has stabilized (cured).

    Three conditions must ALL be true for curing:
    1. Minimum documents processed >= min_documents
    2. Coverage delta < coverage_delta_threshold for last N documents
    3. No new entity types for stability_window consecutive documents

    Failsafe: force-cure at max_fluid_documents.
    """

    def __init__(self, config: CuringConfig):
        self._config = config
        self._coverage_history: list[float] = []
        self._new_types_history: list[set[str]] = []
        self._docs_processed: int = 0
        self._metrics_history: list[dict[str, float]] = []
        self._remap_history: list[float] = []
        self._consecutive_cure_votes: int = 0

    @property
    def docs_processed(self) -> int:
        return self._docs_processed

    def record(
        self,
        coverage: float,
        new_types: set[str],
        metrics: dict[str, float] | None = None,
    ) -> None:
        """Record metrics after processing a document."""
        self._docs_processed += 1
        self._coverage_history.append(coverage)
        self._new_types_history.append(new_types)
        if metrics is not None:
            self._metrics_history.append(metrics)
        logger.debug(
            "Curing detector: doc={}, coverage={:.3f}, new_types={}",
            self._docs_processed,
            coverage,
            len(new_types),
        )

    def is_cured(self) -> bool:
        """Check if all three curing conditions are met."""
        from kg_builder_cli.events import signals as evt_signals
        from kg_builder_cli.events import types as etypes

        def _blocked(condition: str, actual: float, threshold: float):
            evt_signals.curing_condition_blocked.send(
                evt_signals.curing_condition_blocked,
                event=etypes.CuringConditionBlocked(
                    method="is_cured", condition=condition,
                    actual_value=actual, threshold=threshold,
                    doc_index=self._docs_processed,
                ),
            )

        if self._docs_processed < self._config.min_documents:
            _blocked("docs < min_documents", self._docs_processed, self._config.min_documents)
            return False

        # Coverage convergence: delta < threshold for last stability_window docs
        window = self._config.stability_window
        if len(self._coverage_history) < window + 1:
            _blocked("coverage_history < window", len(self._coverage_history), window + 1)
            return False

        recent = self._coverage_history[-window:]
        deltas = [abs(recent[i] - recent[i - 1]) for i in range(1, len(recent))]
        if any(d >= self._config.coverage_delta_threshold for d in deltas):
            _blocked("coverage_delta >= threshold", max(deltas), self._config.coverage_delta_threshold)
            return False

        # Type stability: no new types for stability_window consecutive docs
        recent_types = self._new_types_history[-window:]
        if any(len(types) > 0 for types in recent_types):
            new_count = sum(len(t) for t in recent_types)
            _blocked("new_types_in_window > 0", new_count, 0)
            return False

        # Chao1 coverage floor: do not cure if species richness indicates
        # significant undiscovered types (backward compatible: skip if None)
        if self._metrics_history:
            latest = self._metrics_history[-1]
            chao1 = latest.get("chao1_coverage")
            if chao1 is not None and chao1 < self._config.min_chao1_coverage:
                _blocked("chao1_coverage < min", chao1, self._config.min_chao1_coverage)
                logger.debug(
                    "Curing blocked: chao1_coverage={:.3f} < min_chao1_coverage={:.3f}",
                    chao1,
                    self._config.min_chao1_coverage,
                )
                return False

        evt_signals.curing_check_performed.send(
            evt_signals.curing_check_performed,
            event=etypes.CuringCheckPerformed(
                method="is_cured", result=True,
                doc_index=self._docs_processed, details={},
            ),
        )
        return True

    def is_converged(self) -> bool:
        """Check if schema has converged using metric progression.

        Three conditions must ALL be true:
        1. Minimum documents processed >= min_documents
        2. Last stability_window JSD values all < jsd_convergence_threshold
        3. Last stability_window entropy deltas all < entropy_delta_threshold
        """
        import math

        if self._docs_processed < self._config.min_documents:
            return False

        window = self._config.stability_window
        if len(self._metrics_history) < window:
            return False

        recent = self._metrics_history[-window:]

        # JSD convergence
        jsd_values = [m.get("js_divergence", float("nan")) for m in recent]
        if any(math.isnan(v) for v in jsd_values):
            return False
        if any(v >= self._config.jsd_convergence_threshold for v in jsd_values):
            return False

        # Entropy delta convergence
        ent_deltas = [m.get("entropy_shannon_delta", float("nan")) for m in recent]
        if any(math.isnan(v) for v in ent_deltas):
            return False
        if any(v >= self._config.entropy_delta_threshold for v in ent_deltas):
            return False

        # Type accumulation stalled
        tar_values = [m.get("type_accumulation_rate", 1.0) for m in recent]
        if any(v != 0.0 for v in tar_values):
            return False

        return True

    def is_plateau(self) -> bool:
        """Check if metrics show a plateau (distribution shape stable).

        Unlike is_converged(), allows low-rate type accumulation.
        Requires: JSD < threshold, entropy delta < plateau_entropy_delta,
        coverage delta < coverage_delta_threshold for stability_window docs.
        """
        import math

        if self._docs_processed < self._config.min_documents:
            return False

        window = self._config.stability_window
        if len(self._metrics_history) < window:
            return False
        if len(self._coverage_history) < window + 1:
            return False

        recent = self._metrics_history[-window:]

        # JSD convergence
        jsd_values = [m.get("js_divergence", float("nan")) for m in recent]
        if any(math.isnan(v) for v in jsd_values):
            return False
        if any(v >= self._config.jsd_convergence_threshold for v in jsd_values):
            return False

        # Entropy delta (plateau uses looser threshold)
        ent_deltas = [m.get("entropy_shannon_delta", float("nan")) for m in recent]
        if any(math.isnan(v) for v in ent_deltas):
            return False
        if any(v >= self._config.plateau_entropy_delta for v in ent_deltas):
            return False

        # Coverage delta convergence
        recent_cov = self._coverage_history[-window:]
        cov_deltas = [abs(recent_cov[i] - recent_cov[i - 1]) for i in range(1, len(recent_cov))]
        if any(d >= self._config.coverage_delta_threshold for d in cov_deltas):
            return False

        return True

    def record_llm_vote(self, should_cure: bool) -> None:
        """Track consecutive LLM cure votes for early stopping."""
        if should_cure:
            self._consecutive_cure_votes += 1
        else:
            self._consecutive_cure_votes = 0

    def patience_exceeded(self, patience_fraction: float) -> bool:
        """Return True when consecutive cure votes >= patience threshold.

        Patience is a fraction of max_fluid_documents. E.g. 0.4 with
        max_fluid_documents=20 means 8 consecutive cure votes required.
        Minimum effective patience is 3 regardless of fraction.
        """
        threshold = max(3, int(self._config.max_fluid_documents * patience_fraction))
        return self._consecutive_cure_votes >= threshold

    def check_drift(self, remap_rate: float) -> bool:
        """Returns True if remap rate signals schema drift."""
        from kg_builder_cli.events import signals as evt_signals
        from kg_builder_cli.events import types as etypes

        self._remap_history.append(remap_rate)
        if len(self._remap_history) < self._config.drift_window:
            return False
        recent = self._remap_history[-self._config.drift_window :]
        drifting = all(r >= self._config.drift_remap_threshold for r in recent)
        if drifting:
            evt_signals.drift_detected.send(
                evt_signals.drift_detected,
                event=etypes.DriftDetected(
                    remap_rate=remap_rate,
                    consecutive_docs=self._config.drift_window,
                    action="re_enter_fluid",
                ),
            )
        else:
            evt_signals.drift_check_passed.send(
                evt_signals.drift_check_passed,
                event=etypes.DriftCheckPassed(
                    remap_rate=remap_rate,
                    threshold=self._config.drift_remap_threshold,
                    doc_index=self._docs_processed,
                ),
            )
        return drifting

    def is_force_required(self) -> bool:
        """Check if max_fluid_documents reached (failsafe)."""
        return self._docs_processed >= self._config.max_fluid_documents

    def status(self) -> str:
        """Return a logging-friendly status summary."""
        window = self._config.stability_window

        # Coverage delta info
        if len(self._coverage_history) >= 2:
            last_delta = abs(self._coverage_history[-1] - self._coverage_history[-2])
            cov_str = f"delta={last_delta:.3f}"
        else:
            cov_str = "insufficient data"

        # Type stability info
        if self._new_types_history:
            recent_new = sum(len(t) for t in self._new_types_history[-window:])
            type_str = f"new_types_in_window={recent_new}"
        else:
            type_str = "no data"

        cov_val = self._coverage_history[-1] if self._coverage_history else 0.0
        parts = [
            f"docs={self._docs_processed}/{self._config.max_fluid_documents}",
            f"coverage={cov_val:.3f}",
            cov_str,
            type_str,
        ]

        # Append key stability metrics if available
        if self._metrics_history:
            m = self._metrics_history[-1]
            import math

            for key, fmt in [
                ("js_divergence", ".4f"),
                ("chao1_coverage", ".3f"),
                ("heaps_beta", ".3f"),
            ]:
                val = m.get(key)
                if val is not None and not math.isnan(val):
                    parts.append(f"{key}={val:{fmt}}")

        return ", ".join(parts)

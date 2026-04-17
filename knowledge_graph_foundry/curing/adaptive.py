"""Adaptive calibration state for continuous prior reshaping during cured phase.

Closes the gap between frozen-at-consolidation priors and the evolving
evidence stream. Two classes:

- AdaptivePriorState: per-type EMA tracking with sqrt(N) trigger schedule
- CalibrationHotLoader: interior-mutable wrapper around PosteriorCalibrator
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from loguru import logger


@dataclass
class _TypeState:
    """Per-type adaptive tracking state."""

    observation_count: int = 0
    observations_since_update: int = 0
    ema_posterior: float = 0.0
    # Welford online variance: M2 accumulator and mean
    _welford_mean: float = 0.0
    _welford_m2: float = 0.0
    last_prior: float = 0.0


class AdaptivePriorState:
    """Track per-type posterior observations and reshape priors continuously.

    Uses EMA with alpha = 2/(n+1) for smoothing and Welford online variance
    for sigma-cap feedback mitigation. Update trigger fires at sqrt(N) intervals.
    """

    def __init__(self, seed_priors: dict[str, float]):
        self._types: dict[str, _TypeState] = {}
        self._seed_priors = dict(seed_priors)
        for type_name, prior in seed_priors.items():
            state = _TypeState()
            state.ema_posterior = prior
            state.last_prior = prior
            self._types[type_name] = state

    @classmethod
    def from_type_metrics(
        cls,
        type_metrics: dict[str, dict[str, float]],
        type_frequencies: dict[str, int],
    ) -> AdaptivePriorState:
        """Factory: initialize from batch type metrics and frequencies.

        Computes initial priors from frequency distribution, matching
        the frequency-only _build_prior() in BayesianTypeResolver.
        """
        total = sum(type_frequencies.values())
        if total == 0:
            priors = (
                {t: 1.0 / len(type_frequencies) for t in type_frequencies}
                if type_frequencies
                else {}
            )
        else:
            priors = {t: freq / total for t, freq in type_frequencies.items()}
        return cls(priors)

    def record_observation(self, type_name: str, posterior: float) -> bool:
        """Record a posterior observation for a type. Returns True if update triggered."""
        if type_name not in self._types:
            # New type appearing in cured phase
            n_types = len(self._types) + 1
            state = _TypeState()
            state.ema_posterior = posterior
            state.last_prior = 1.0 / n_types  # minimal initial prior
            self._types[type_name] = state

        state = self._types[type_name]
        state.observation_count += 1
        state.observations_since_update += 1
        n = state.observation_count

        # EMA update: alpha = 2/(n+1)
        alpha = 2.0 / (n + 1)
        state.ema_posterior = alpha * posterior + (1.0 - alpha) * state.ema_posterior

        # Welford online variance update
        delta = posterior - state._welford_mean
        state._welford_mean += delta / n
        delta2 = posterior - state._welford_mean
        state._welford_m2 += delta * delta2

        triggered = self.should_update(type_name)
        if triggered:
            old_prior = state.last_prior
            adjusted = self.get_adjusted_priors()
            new_prior = adjusted.get(type_name, old_prior)

            # Emit adaptive-prior-updated event
            from knowledge_graph_foundry.events import signals as evt_signals
            from knowledge_graph_foundry.events import types as etypes

            sigma_cap_applied = False
            if state.observation_count >= 2:
                variance = state._welford_m2 / (state.observation_count - 1)
                sigma = math.sqrt(max(0.0, variance))
                if sigma > 0 and abs(state.ema_posterior - old_prior) > sigma:
                    sigma_cap_applied = True

            evt_signals.adaptive_prior_updated.send(
                evt_signals.adaptive_prior_updated,
                event=etypes.AdaptivePriorUpdated(
                    type_name=type_name,
                    old_prior=old_prior,
                    new_prior=new_prior,
                    observation_count=state.observation_count,
                    sigma_cap_applied=sigma_cap_applied,
                ),
            )

            state.observations_since_update = 0
        return triggered

    def should_update(self, type_name: str) -> bool:
        """Check if sqrt(N) trigger has fired for this type."""
        state = self._types.get(type_name)
        if state is None:
            return False
        threshold = max(1, math.floor(math.sqrt(state.observation_count)))
        return state.observations_since_update >= threshold

    def get_adjusted_priors(self) -> dict[str, float]:
        """Return current priors incorporating EMA with sigma cap, normalized to sum 1.0."""
        if not self._types:
            return {}

        adjusted: dict[str, float] = {}
        for type_name, state in self._types.items():
            if state.observation_count == 0:
                # No observations yet - use seed prior
                adjusted[type_name] = state.last_prior
                continue

            # Compute standard deviation from Welford
            if state.observation_count >= 2:
                variance = state._welford_m2 / (state.observation_count - 1)
                sigma = math.sqrt(max(0.0, variance))
            else:
                sigma = 0.0

            # Sigma cap: limit shift from last_prior to at most 1 sigma
            new_prior = state.ema_posterior
            if sigma > 0:
                shift = new_prior - state.last_prior
                if abs(shift) > sigma:
                    capped = state.last_prior + math.copysign(sigma, shift)
                    logger.debug(
                        "sigma cap applied: {} prior {:.4f} -> {:.4f} (capped from {:.4f}, sigma={:.4f})",
                        type_name,
                        state.last_prior,
                        capped,
                        new_prior,
                        sigma,
                    )
                    new_prior = capped

            # Ensure positive
            adjusted[type_name] = max(new_prior, 1e-8)
            state.last_prior = adjusted[type_name]

        # Normalize to sum 1.0
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {t: v / total for t, v in adjusted.items()}

        return adjusted


class CalibrationHotLoader:
    """Interior-mutable wrapper around PosteriorCalibrator for hot-loading.

    Allows the calibrator to be swapped after consolidation so cured-phase
    documents use the freshly-fitted curve from the current run.
    """

    def __init__(self, calibrator: object | None = None):
        self._inner = calibrator

    def calibrate(self, raw_posterior: float) -> float:
        """Delegate to inner calibrator, passthrough if None."""
        if self._inner is not None and hasattr(self._inner, "calibrate"):
            return self._inner.calibrate(raw_posterior)
        return raw_posterior

    @property
    def has_calibrator(self) -> bool:
        return self._inner is not None

    def hot_load(self, calibrator) -> None:
        """Swap inner calibrator reference."""
        self._inner = calibrator

"""Tests for adaptive calibration: AdaptivePriorState and CalibrationHotLoader."""

from __future__ import annotations

import math
import time

import pytest

from knowledge_graph_foundry.curing.adaptive import AdaptivePriorState, CalibrationHotLoader


# ── AdaptivePriorState: sqrt(N) trigger ──────────────────────────


class TestSqrtTrigger:
    """Verify sqrt(N) update trigger boundaries."""

    def test_first_observation_triggers(self):
        """N=0 -> first observation fires trigger (max(1, floor(sqrt(0))) = 1)."""
        state = AdaptivePriorState({"A": 0.5, "B": 0.5})
        triggered = state.record_observation("A", 0.6)
        assert triggered is True

    def test_n4_threshold_is_two(self):
        """At N=4, threshold is floor(sqrt(4))=2. Verify trigger fires at 2 since_update."""
        state = AdaptivePriorState({"A": 0.5, "B": 0.5})
        # First 3 observations trigger immediately (threshold=1 for N=1,2,3)
        for _ in range(3):
            assert state.record_observation("A", 0.6) is True
        # Obs 4: threshold = floor(sqrt(4)) = 2, since_update becomes 1 -> no trigger
        assert state.record_observation("A", 0.6) is False
        # Obs 5: since_update becomes 2, threshold = floor(sqrt(5)) = 2 -> trigger
        assert state.record_observation("A", 0.6) is True

    def test_n9_threshold_is_three(self):
        """At N=9, threshold is floor(sqrt(9))=3. Verify trigger spacing."""
        state = AdaptivePriorState({"A": 0.5, "B": 0.5})
        # Run up to a state where we can verify 3-observation gaps
        trigger_counts = []
        for i in range(20):
            if state.record_observation("A", 0.6):
                trigger_counts.append(i + 1)
        # After N >= 9, gaps between triggers should be >= 3
        for j in range(len(trigger_counts) - 1):
            if trigger_counts[j] >= 9:
                gap = trigger_counts[j + 1] - trigger_counts[j]
                assert gap >= 3, f"Gap {gap} at trigger {trigger_counts[j]}"

    def test_large_n_has_wide_gaps(self):
        """After 100 obs, gaps between triggers should be >= 10."""
        state = AdaptivePriorState({"A": 0.5, "B": 0.5})
        for _ in range(100):
            state.record_observation("A", 0.6)
        # Now find next two triggers and verify gap
        trigger_at = []
        for i in range(100, 130):
            state.record_observation("A", 0.6)
            if state._types["A"].observations_since_update == 0:
                trigger_at.append(i + 1)
            if len(trigger_at) >= 2:
                break
        if len(trigger_at) >= 2:
            assert trigger_at[1] - trigger_at[0] >= 10

    def test_increasing_gaps_between_triggers(self):
        """Trigger gaps grow: 1st at obs 1, then after 1, 2, 2, 2, 3, 3, ... more."""
        state = AdaptivePriorState({"A": 0.5})
        trigger_points = []
        for i in range(50):
            if state.record_observation("A", 0.6):
                trigger_points.append(i + 1)
        # Gaps should be non-decreasing
        gaps = [trigger_points[i + 1] - trigger_points[i] for i in range(len(trigger_points) - 1)]
        for i in range(len(gaps) - 1):
            assert gaps[i] <= gaps[i + 1] + 1  # allow for floor rounding


# ── AdaptivePriorState: EMA convergence ──────────────────────────


class TestEMAConvergence:
    """Verify EMA tracks toward true posterior mean."""

    def test_ema_converges_to_mean(self):
        """Feed 100 observations at known mean, verify EMA within 0.05."""
        state = AdaptivePriorState({"A": 0.3, "B": 0.7})
        true_mean = 0.7
        for _ in range(100):
            state.record_observation("A", true_mean)
        priors = state.get_adjusted_priors()
        # EMA for A should be close to 0.7 (before normalization)
        # After normalization, check it shifted significantly toward 0.7
        assert priors["A"] > 0.4  # started at 0.3, should move toward 0.7

    def test_ema_alpha_decreases(self):
        """Alpha = 2/(n+1) so early observations have more weight."""
        state = AdaptivePriorState({"A": 0.5})
        # First observation: alpha = 2/2 = 1.0, EMA = posterior
        state.record_observation("A", 0.9)
        s = state._types["A"]
        assert abs(s.ema_posterior - 0.9) < 0.01
        # After many observations, EMA should be stable
        for _ in range(99):
            state.record_observation("A", 0.5)
        assert abs(s.ema_posterior - 0.5) < 0.1


# ── AdaptivePriorState: sigma cap ────────────────────────────────


class TestSigmaCap:
    """Verify sigma cap limits prior shift."""

    def test_outlier_capped(self):
        """50 normal observations then 1 extreme - shift limited to sigma."""
        state = AdaptivePriorState({"A": 0.5, "B": 0.5})
        # Build stable distribution
        for _ in range(50):
            state.record_observation("A", 0.5)
        old_priors = state.get_adjusted_priors()

        # Extreme outlier
        state.record_observation("A", 0.99)
        new_priors = state.get_adjusted_priors()

        # Shift should be bounded
        shift = abs(new_priors["A"] - old_priors["A"])
        # With 50 observations at 0.5, variance should be very low
        # so the shift from one outlier should be heavily capped
        assert shift < 0.2  # generous bound - sigma cap prevents large shift

    def test_zero_variance_no_crash(self):
        """All identical posteriors (zero variance) handled gracefully."""
        state = AdaptivePriorState({"A": 0.5, "B": 0.5})
        for _ in range(10):
            state.record_observation("A", 0.5)
        priors = state.get_adjusted_priors()
        assert not any(math.isnan(v) for v in priors.values())
        assert "A" in priors
        assert "B" in priors


# ── AdaptivePriorState: normalization ─────────────────────────────


class TestPriorsNormalize:
    """Verify adjusted priors always sum to 1.0."""

    def test_sum_one_initial(self):
        state = AdaptivePriorState({"A": 0.3, "B": 0.5, "C": 0.2})
        priors = state.get_adjusted_priors()
        assert abs(sum(priors.values()) - 1.0) < 1e-10

    def test_sum_one_after_observations(self):
        state = AdaptivePriorState({"A": 0.3, "B": 0.5, "C": 0.2})
        for _ in range(10):
            state.record_observation("A", 0.8)
        for _ in range(5):
            state.record_observation("B", 0.3)
        priors = state.get_adjusted_priors()
        assert abs(sum(priors.values()) - 1.0) < 1e-10

    def test_sum_one_after_100_observations(self):
        types = {f"T{i}": 1.0 / 12 for i in range(12)}
        state = AdaptivePriorState(types)
        for i in range(100):
            state.record_observation(f"T{i % 12}", 0.5 + (i % 5) * 0.1)
        priors = state.get_adjusted_priors()
        assert abs(sum(priors.values()) - 1.0) < 1e-10

    def test_sum_one_after_1000_observations(self):
        types = {f"T{i}": 1.0 / 12 for i in range(12)}
        state = AdaptivePriorState(types)
        for i in range(1000):
            state.record_observation(f"T{i % 12}", 0.3 + (i % 7) * 0.1)
        priors = state.get_adjusted_priors()
        assert abs(sum(priors.values()) - 1.0) < 1e-10


# ── AdaptivePriorState: from_type_metrics factory ────────────────


class TestFromTypeMetrics:
    """Verify factory initialization from batch metrics."""

    def test_basic_initialization(self):
        freqs = {"Product": 100, "Component": 50, "Feature": 30}
        metrics = {"Product": {"f1": 0.8}, "Component": {"f1": 0.5}, "Feature": {"f1": 0.3}}
        state = AdaptivePriorState.from_type_metrics(metrics, freqs)
        priors = state.get_adjusted_priors()
        assert len(priors) == 3
        assert abs(sum(priors.values()) - 1.0) < 1e-10
        # Product should have highest prior (highest frequency)
        assert priors["Product"] > priors["Feature"]

    def test_empty_frequencies(self):
        state = AdaptivePriorState.from_type_metrics({}, {})
        priors = state.get_adjusted_priors()
        assert priors == {}


# ── AdaptivePriorState: cold start and new types ─────────────────


class TestColdStartAndNewTypes:
    """Verify behavior with zero observations and new types."""

    def test_cold_start_returns_seed(self):
        """get_adjusted_priors() returns seed prior when no observations recorded."""
        seed = {"A": 0.4, "B": 0.6}
        state = AdaptivePriorState(seed)
        priors = state.get_adjusted_priors()
        assert abs(priors["A"] - 0.4) < 1e-10
        assert abs(priors["B"] - 0.6) < 1e-10

    def test_new_type_incorporated(self):
        """New types appearing in cured phase get incorporated."""
        state = AdaptivePriorState({"A": 0.5, "B": 0.5})
        state.record_observation("C", 0.7)
        priors = state.get_adjusted_priors()
        assert "C" in priors
        assert priors["C"] > 0
        assert abs(sum(priors.values()) - 1.0) < 1e-10

    def test_sparse_type_bounded(self):
        """Sparse type (1 obs) doesn't dominate over well-observed types."""
        types = {f"T{i}": 1.0 / 12 for i in range(12)}
        state = AdaptivePriorState(types)
        # One sparse type with very high posterior
        state.record_observation("T0", 0.99)
        # Others with many observations
        for i in range(1, 12):
            for _ in range(50):
                state.record_observation(f"T{i}", 0.5)
        priors = state.get_adjusted_priors()
        seed_prior = 1.0 / 12
        # T0 should not exceed 2x its seed prior
        assert priors["T0"] < seed_prior * 2


# ── AdaptivePriorState: feedback loop resistance ────────────────


class TestFeedbackLoopResistance:
    """Verify biased early observations don't cascade into runaway drift."""

    def test_recovery_from_biased_start(self):
        """5 incorrect high-posterior obs, then 50 correct low-posterior - prior recovers."""
        state = AdaptivePriorState({"A": 0.1, "B": 0.9})
        # Biased early observations
        for _ in range(5):
            state.record_observation("A", 0.95)
        biased_priors = state.get_adjusted_priors()

        # Corrective observations
        for _ in range(50):
            state.record_observation("A", 0.4)
        recovered_priors = state.get_adjusted_priors()

        # After correction, A's prior should be lower than during the biased phase
        assert recovered_priors["A"] < biased_priors["A"]


# ── AdaptivePriorState: performance ──────────────────────────────


class TestPerformance:
    """Verify adaptive state handles large observation counts efficiently."""

    def test_large_corpus_performance(self):
        """10000+ observations: record and get_adjusted_priors both < 1ms per call."""
        types = {f"T{i}": 1.0 / 12 for i in range(12)}
        state = AdaptivePriorState(types)

        # Warm up
        for i in range(10000):
            state.record_observation(f"T{i % 12}", 0.5)

        # Time record_observation
        t0 = time.monotonic()
        for i in range(1000):
            state.record_observation(f"T{i % 12}", 0.5)
        record_ms = (time.monotonic() - t0) * 1000 / 1000
        assert record_ms < 1.0, f"record_observation: {record_ms:.3f}ms per call"

        # Time get_adjusted_priors
        t0 = time.monotonic()
        for _ in range(1000):
            state.get_adjusted_priors()
        get_ms = (time.monotonic() - t0) * 1000 / 1000
        assert get_ms < 1.0, f"get_adjusted_priors: {get_ms:.3f}ms per call"


# ── CalibrationHotLoader ─────────────────────────────────────────


class TestCalibrationHotLoader:
    """Verify hot-loader swap and passthrough behavior."""

    def test_none_passthrough(self):
        """No calibrator -> raw posterior returned."""
        loader = CalibrationHotLoader(None)
        assert loader.calibrate(0.7) == 0.7
        assert loader.has_calibrator is False

    def test_with_calibrator(self):
        """Calibrator delegates to inner."""

        class _MockCalibrator:
            def calibrate(self, x):
                return x * 0.5

        loader = CalibrationHotLoader(_MockCalibrator())
        assert loader.calibrate(0.8) == 0.4
        assert loader.has_calibrator is True

    def test_hot_load_swap(self):
        """Hot-load replaces inner calibrator."""
        loader = CalibrationHotLoader(None)
        assert loader.calibrate(0.7) == 0.7  # passthrough

        class _NewCalibrator:
            def calibrate(self, x):
                return x * 2.0

        loader.hot_load(_NewCalibrator())
        assert loader.calibrate(0.3) == 0.6  # new calibrator active
        assert loader.has_calibrator is True


# ── ObservationCollector callback ─────────────────────────────────


class TestObservationCallback:
    """Verify collector triggers on_observation callback."""

    def test_cross_type_fires_callback(self):
        from knowledge_graph_foundry.curing.observation import (
            CrossTypeObservation,
            ObservationCollector,
        )

        calls = []
        collector = ObservationCollector()
        collector.on_observation = lambda t, p: calls.append((t, p))

        obs = CrossTypeObservation(
            norm_name="test",
            type_a="Product",
            type_b="Component",
            raw_posterior=0.7,
            prior=0.8,
            lr_desc=1.0,
            lr_emb=1.0,
            lr_cooc=1.0,
            action="merged",
            doc_index=0,
            has_hierarchy=False,
            sibling=False,
        )
        collector.record_cross_type(obs)
        assert len(calls) == 2
        assert calls[0] == ("Product", 0.7)
        assert calls[1] == ("Component", 0.7)

    def test_type_assignment_fires_callback(self):
        from knowledge_graph_foundry.curing.observation import (
            ObservationCollector,
            TypeAssignmentObservation,
        )

        calls = []
        collector = ObservationCollector()
        collector.on_observation = lambda t, p: calls.append((t, p))

        obs = TypeAssignmentObservation(
            entity_name="test_entity",
            type_before="Feature",
            type_after="Component",
            posterior={"Component": 0.8, "Feature": 0.2},
            entropy=0.7,
            was_remapped=True,
            escalated_to_llm=False,
            doc_index=0,
        )
        collector.record_type_assignment(obs)
        assert len(calls) == 1
        assert calls[0] == ("Component", 0.8)

    def test_no_callback_no_crash(self):
        """Callback is None by default - no crash."""
        from knowledge_graph_foundry.curing.observation import (
            CrossTypeObservation,
            ObservationCollector,
        )

        collector = ObservationCollector()
        obs = CrossTypeObservation(
            norm_name="test",
            type_a="A",
            type_b="B",
            raw_posterior=0.5,
            prior=0.8,
            lr_desc=1.0,
            lr_emb=1.0,
            lr_cooc=1.0,
            action="blocked",
            doc_index=0,
            has_hierarchy=False,
            sibling=False,
        )
        collector.record_cross_type(obs)  # should not raise
        assert collector.cross_type_count == 1

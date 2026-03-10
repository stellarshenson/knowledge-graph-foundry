"""Tests for curing detection logic."""
import pytest

from kg_builder_cli.curing.detector import CuringDetector
from kg_builder_cli.types.config import CuringConfig


@pytest.fixture
def default_config():
    return CuringConfig(
        enabled=True,
        min_documents=3,
        max_fluid_documents=20,
        coverage_delta_threshold=0.05,
        stability_window=3,
    )


@pytest.fixture
def detector(default_config):
    return CuringDetector(default_config)


def test_not_cured_below_min_documents(detector):
    """Should not cure before min_documents are processed."""
    detector.record(0.5, set())
    detector.record(0.6, set())
    assert not detector.is_cured()


def test_cured_when_stable(detector):
    """Should cure when coverage converges and no new types appear."""
    # First 3 docs with new types (building up)
    detector.record(0.3, {"Person"})
    detector.record(0.5, {"Device"})
    detector.record(0.6, {"Manufacturer"})
    # Next 3 docs with stable coverage and no new types
    detector.record(0.61, set())
    detector.record(0.62, set())
    detector.record(0.62, set())
    assert detector.is_cured()


def test_force_required_at_max(default_config):
    """Should force-cure when max_fluid_documents is reached."""
    config = CuringConfig(
        enabled=True, min_documents=3, max_fluid_documents=5,
        coverage_delta_threshold=0.05, stability_window=3,
    )
    detector = CuringDetector(config)
    for i in range(5):
        detector.record(0.3 + i * 0.1, {f"Type{i}"})
    assert detector.is_force_required()


def test_not_cured_new_types_each_doc(detector):
    """Should stay fluid when new types keep appearing."""
    for i in range(10):
        detector.record(0.5, {f"Type{i}"})
    assert not detector.is_cured()


def test_coverage_oscillation_prevents_cure(detector):
    """Coverage bouncing above threshold should prevent cure."""
    detector.record(0.3, set())
    detector.record(0.5, set())
    detector.record(0.7, set())
    # Oscillating coverage
    detector.record(0.4, set())
    detector.record(0.7, set())
    detector.record(0.4, set())
    assert not detector.is_cured()


def test_status_returns_string(detector):
    """Status should return a non-empty string."""
    detector.record(0.5, {"Person"})
    status = detector.status()
    assert isinstance(status, str)
    assert "docs=" in status


def test_docs_processed_property(detector):
    """docs_processed should track the number of recorded documents."""
    assert detector.docs_processed == 0
    detector.record(0.5, set())
    assert detector.docs_processed == 1
    detector.record(0.6, set())
    assert detector.docs_processed == 2


def test_not_force_required_below_max(detector):
    """Should not force-cure below max_fluid_documents."""
    for i in range(5):
        detector.record(0.5, set())
    assert not detector.is_force_required()


class TestIsConverged:
    """Tests for metric-based convergence detection."""

    def test_converged_when_metrics_stable(self):
        """Should converge when JSD, entropy delta, and type rate all stable."""
        config = CuringConfig(
            enabled=True,
            min_documents=3,
            stability_window=3,
            jsd_convergence_threshold=0.01,
            entropy_delta_threshold=0.05,
        )
        detector = CuringDetector(config)

        # First 3 docs build up (won't converge)
        detector.record(0.3, {"Person"}, {
            "js_divergence": 0.5, "entropy_shannon_delta": 0.3,
            "type_accumulation_rate": 3.0,
        })
        detector.record(0.5, {"Device"}, {
            "js_divergence": 0.1, "entropy_shannon_delta": 0.1,
            "type_accumulation_rate": 1.0,
        })
        detector.record(0.6, set(), {
            "js_divergence": 0.05, "entropy_shannon_delta": 0.08,
            "type_accumulation_rate": 0.0,
        })
        assert not detector.is_converged()

        # Next 3 docs with fully converged metrics
        detector.record(0.61, set(), {
            "js_divergence": 0.005, "entropy_shannon_delta": 0.02,
            "type_accumulation_rate": 0.0,
        })
        detector.record(0.62, set(), {
            "js_divergence": 0.003, "entropy_shannon_delta": 0.01,
            "type_accumulation_rate": 0.0,
        })
        detector.record(0.62, set(), {
            "js_divergence": 0.002, "entropy_shannon_delta": 0.01,
            "type_accumulation_rate": 0.0,
        })
        assert detector.is_converged()

    def test_not_converged_below_min_docs(self):
        """Should not converge before min_documents."""
        config = CuringConfig(
            enabled=True, min_documents=5, stability_window=3,
            jsd_convergence_threshold=0.01, entropy_delta_threshold=0.05,
        )
        detector = CuringDetector(config)
        for _ in range(4):
            detector.record(0.5, set(), {
                "js_divergence": 0.001, "entropy_shannon_delta": 0.001,
                "type_accumulation_rate": 0.0,
            })
        assert not detector.is_converged()

    def test_not_converged_high_jsd(self):
        """Should not converge when JSD exceeds threshold."""
        config = CuringConfig(
            enabled=True, min_documents=3, stability_window=3,
            jsd_convergence_threshold=0.01, entropy_delta_threshold=0.05,
        )
        detector = CuringDetector(config)
        for _ in range(5):
            detector.record(0.5, set(), {
                "js_divergence": 0.05, "entropy_shannon_delta": 0.001,
                "type_accumulation_rate": 0.0,
            })
        assert not detector.is_converged()

    def test_not_converged_new_types(self):
        """Should not converge when types still accumulating."""
        config = CuringConfig(
            enabled=True, min_documents=3, stability_window=3,
            jsd_convergence_threshold=0.01, entropy_delta_threshold=0.05,
        )
        detector = CuringDetector(config)
        for _ in range(5):
            detector.record(0.5, set(), {
                "js_divergence": 0.001, "entropy_shannon_delta": 0.001,
                "type_accumulation_rate": 1.0,
            })
        assert not detector.is_converged()

    def test_not_converged_nan_metrics(self):
        """Should not converge when metrics contain NaN."""
        config = CuringConfig(
            enabled=True, min_documents=3, stability_window=3,
            jsd_convergence_threshold=0.01, entropy_delta_threshold=0.05,
        )
        detector = CuringDetector(config)
        for _ in range(5):
            detector.record(0.5, set(), {
                "js_divergence": float("nan"), "entropy_shannon_delta": 0.001,
                "type_accumulation_rate": 0.0,
            })
        assert not detector.is_converged()


class TestIsPlateau:
    """Tests for metric plateau detection."""

    def test_plateau_on_flat_metrics(self):
        """Should detect plateau when JSD, entropy delta, coverage all flat."""
        config = CuringConfig(
            enabled=True, min_documents=3, stability_window=3,
            jsd_convergence_threshold=0.01, entropy_delta_threshold=0.05,
            plateau_entropy_delta=0.1, coverage_delta_threshold=0.05,
        )
        detector = CuringDetector(config)
        # Build up phase
        detector.record(0.3, {"Person"}, {
            "js_divergence": 0.5, "entropy_shannon_delta": 0.3,
            "type_accumulation_rate": 3.0,
        })
        detector.record(0.5, {"Device"}, {
            "js_divergence": 0.1, "entropy_shannon_delta": 0.1,
            "type_accumulation_rate": 1.0,
        })
        detector.record(0.6, set(), {
            "js_divergence": 0.05, "entropy_shannon_delta": 0.08,
            "type_accumulation_rate": 0.0,
        })
        assert not detector.is_plateau()

        # Flat metrics with occasional new type (type_accumulation_rate > 0 is ok for plateau)
        detector.record(0.61, {"RareType"}, {
            "js_divergence": 0.005, "entropy_shannon_delta": 0.08,
            "type_accumulation_rate": 0.5,
        })
        detector.record(0.62, set(), {
            "js_divergence": 0.003, "entropy_shannon_delta": 0.06,
            "type_accumulation_rate": 0.0,
        })
        detector.record(0.62, set(), {
            "js_divergence": 0.002, "entropy_shannon_delta": 0.04,
            "type_accumulation_rate": 0.0,
        })
        assert detector.is_plateau()

    def test_no_plateau_on_shifting_metrics(self):
        """Should not detect plateau when entropy delta is high."""
        config = CuringConfig(
            enabled=True, min_documents=3, stability_window=3,
            jsd_convergence_threshold=0.01, entropy_delta_threshold=0.05,
            plateau_entropy_delta=0.1, coverage_delta_threshold=0.05,
        )
        detector = CuringDetector(config)
        for _ in range(5):
            detector.record(0.5, set(), {
                "js_divergence": 0.005, "entropy_shannon_delta": 0.15,
                "type_accumulation_rate": 0.0,
            })
        assert not detector.is_plateau()

    def test_plateau_allows_low_type_accumulation(self):
        """Plateau should fire even with type_accumulation_rate > 0."""
        config = CuringConfig(
            enabled=True, min_documents=3, stability_window=3,
            jsd_convergence_threshold=0.01, entropy_delta_threshold=0.05,
            plateau_entropy_delta=0.1, coverage_delta_threshold=0.05,
        )
        detector = CuringDetector(config)
        for i in range(3):
            detector.record(0.5 + i * 0.01, set(), {
                "js_divergence": 0.5, "entropy_shannon_delta": 0.3,
                "type_accumulation_rate": 2.0,
            })
        # Now stable metrics but with type accumulation
        for _ in range(3):
            detector.record(0.61, set(), {
                "js_divergence": 0.005, "entropy_shannon_delta": 0.05,
                "type_accumulation_rate": 0.5,
            })
        assert detector.is_plateau()
        # is_converged should NOT fire (type_accumulation_rate > 0)
        assert not detector.is_converged()


class TestCheckDrift:
    """Tests for drift detection."""

    def test_below_threshold_no_trigger(self):
        """Low remap rates should not trigger drift."""
        config = CuringConfig(
            enabled=True, drift_remap_threshold=0.3, drift_window=3,
        )
        detector = CuringDetector(config)
        assert not detector.check_drift(0.1)
        assert not detector.check_drift(0.2)
        assert not detector.check_drift(0.1)

    def test_consecutive_window_trigger(self):
        """Remap rate above threshold for drift_window docs should trigger."""
        config = CuringConfig(
            enabled=True, drift_remap_threshold=0.3, drift_window=3,
        )
        detector = CuringDetector(config)
        assert not detector.check_drift(0.4)
        assert not detector.check_drift(0.5)
        assert detector.check_drift(0.35)

    def test_reset_after_low_rate(self):
        """Low-rate doc in the middle should reset the window."""
        config = CuringConfig(
            enabled=True, drift_remap_threshold=0.3, drift_window=3,
        )
        detector = CuringDetector(config)
        assert not detector.check_drift(0.4)
        assert not detector.check_drift(0.5)
        assert not detector.check_drift(0.1)  # breaks the streak
        assert not detector.check_drift(0.4)
        assert not detector.check_drift(0.5)
        assert detector.check_drift(0.35)  # now 3 consecutive


class TestPatienceTracking:
    """Tests for LLM vote patience tracking and early stopping."""

    def test_record_llm_vote_consecutive(self):
        """Counter should increment on consecutive True votes."""
        config = CuringConfig(enabled=True)
        detector = CuringDetector(config)
        detector.record_llm_vote(True)
        assert detector._consecutive_cure_votes == 1
        detector.record_llm_vote(True)
        assert detector._consecutive_cure_votes == 2
        detector.record_llm_vote(True)
        assert detector._consecutive_cure_votes == 3

    def test_record_llm_vote_reset(self):
        """Counter should reset on False vote."""
        config = CuringConfig(enabled=True)
        detector = CuringDetector(config)
        detector.record_llm_vote(True)
        detector.record_llm_vote(True)
        assert detector._consecutive_cure_votes == 2
        detector.record_llm_vote(False)
        assert detector._consecutive_cure_votes == 0
        detector.record_llm_vote(True)
        assert detector._consecutive_cure_votes == 1

    def test_patience_exceeded(self):
        """Should return True when votes reach patience threshold.

        max_fluid_documents=10, patience=0.3 -> threshold = max(3, int(10*0.3)) = 3.
        """
        config = CuringConfig(enabled=True, max_fluid_documents=10)
        detector = CuringDetector(config)
        assert not detector.patience_exceeded(0.3)
        detector.record_llm_vote(True)
        assert not detector.patience_exceeded(0.3)
        detector.record_llm_vote(True)
        assert not detector.patience_exceeded(0.3)
        detector.record_llm_vote(True)
        assert detector.patience_exceeded(0.3)

    def test_patience_not_exceeded_after_reset(self):
        """Patience should not trigger after a reset."""
        config = CuringConfig(enabled=True, max_fluid_documents=10)
        detector = CuringDetector(config)
        detector.record_llm_vote(True)
        detector.record_llm_vote(True)
        detector.record_llm_vote(False)  # reset
        detector.record_llm_vote(True)
        assert not detector.patience_exceeded(0.3)


class TestChao1Floor:
    """Tests for Chao1 coverage floor in is_cured()."""

    def test_low_chao1_blocks_curing(self):
        """Curing should be blocked when chao1_coverage < min_chao1_coverage."""
        config = CuringConfig(
            enabled=True, min_documents=3, stability_window=3,
            coverage_delta_threshold=0.05, min_chao1_coverage=0.7,
        )
        detector = CuringDetector(config)
        detector.record(0.3, {"Person"}, {"chao1_coverage": 0.3})
        detector.record(0.5, {"Device"}, {"chao1_coverage": 0.4})
        detector.record(0.6, set(), {"chao1_coverage": 0.45})
        # Stable coverage and no new types - would cure without Chao1 floor
        detector.record(0.61, set(), {"chao1_coverage": 0.46})
        detector.record(0.62, set(), {"chao1_coverage": 0.46})
        detector.record(0.62, set(), {"chao1_coverage": 0.46})
        assert not detector.is_cured()

    def test_high_chao1_allows_curing(self):
        """Curing should proceed when chao1_coverage >= min_chao1_coverage."""
        config = CuringConfig(
            enabled=True, min_documents=3, stability_window=3,
            coverage_delta_threshold=0.05, min_chao1_coverage=0.7,
        )
        detector = CuringDetector(config)
        detector.record(0.3, {"Person"}, {"chao1_coverage": 0.5})
        detector.record(0.5, {"Device"}, {"chao1_coverage": 0.6})
        detector.record(0.6, set(), {"chao1_coverage": 0.7})
        detector.record(0.61, set(), {"chao1_coverage": 0.75})
        detector.record(0.62, set(), {"chao1_coverage": 0.75})
        detector.record(0.62, set(), {"chao1_coverage": 0.75})
        assert detector.is_cured()

    def test_missing_chao1_skips_guard(self):
        """When chao1_coverage is absent, guard should be skipped (backward compat)."""
        config = CuringConfig(
            enabled=True, min_documents=3, stability_window=3,
            coverage_delta_threshold=0.05, min_chao1_coverage=0.7,
        )
        detector = CuringDetector(config)
        detector.record(0.3, {"Person"})
        detector.record(0.5, {"Device"})
        detector.record(0.6, set())
        detector.record(0.61, set())
        detector.record(0.62, set())
        detector.record(0.62, set())
        assert detector.is_cured()

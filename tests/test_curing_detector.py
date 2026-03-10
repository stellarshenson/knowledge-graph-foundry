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

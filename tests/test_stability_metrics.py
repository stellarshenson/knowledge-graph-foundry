"""Tests for information-theoretic stability metrics."""
import math

import pytest

from knowledge_graph_foundry.curing.metrics import StabilityMetrics


@pytest.fixture
def tracker():
    return StabilityMetrics(variance_window=5)


def test_shannon_entropy_uniform(tracker):
    """Uniform distribution has maximum entropy log2(N)."""
    freqs = {"A": 10, "B": 10, "C": 10, "D": 10}
    result = tracker.record(freqs)
    assert abs(result["entropy_shannon"] - math.log2(4)) < 1e-9


def test_shannon_entropy_single_type(tracker):
    """Single type has entropy 0."""
    result = tracker.record({"A": 100})
    assert result["entropy_shannon"] == 0.0


def test_kl_divergence_identical(tracker):
    """Identical consecutive distributions give KL near 0."""
    freqs = {"A": 10, "B": 20, "C": 30}
    tracker.record(freqs)
    result = tracker.record(freqs)
    assert result["kl_divergence"] < 1e-6


def test_kl_divergence_shift(tracker):
    """A distributional shift produces positive KL divergence."""
    tracker.record({"A": 100, "B": 1})
    result = tracker.record({"A": 1, "B": 100})
    assert result["kl_divergence"] > 0.1


def test_js_divergence_bounded(tracker):
    """JSD is always in [0, 1] when using log2."""
    tracker.record({"A": 100, "B": 1, "C": 1})
    result = tracker.record({"A": 1, "B": 1, "C": 100})
    assert 0.0 <= result["js_divergence"] <= 1.0


def test_js_divergence_symmetric(tracker):
    """JSD(P||Q) == JSD(Q||P) - test via two separate trackers."""
    t1 = StabilityMetrics()
    t2 = StabilityMetrics()

    p = {"A": 10, "B": 30, "C": 60}
    q = {"A": 50, "B": 25, "C": 25}

    # t1: P then Q
    t1.record(p)
    r1 = t1.record(q)

    # t2: Q then P
    t2.record(q)
    r2 = t2.record(p)

    assert abs(r1["js_divergence"] - r2["js_divergence"]) < 1e-9


def test_gini_uniform(tracker):
    """Uniform frequencies give Gini near 0."""
    freqs = {f"T{i}": 10 for i in range(20)}
    result = tracker.record(freqs)
    assert result["gini_coefficient"] < 0.01


def test_gini_dominated(tracker):
    """One dominant type gives high Gini."""
    freqs = {"Dominant": 1000}
    freqs.update({f"Rare{i}": 1 for i in range(50)})
    result = tracker.record(freqs)
    assert result["gini_coefficient"] > 0.5


def test_zipf_perfect_powerlaw(tracker):
    """Frequencies following 1/rank^alpha give R^2 near 1."""
    alpha = 1.0
    freqs = {f"T{i}": max(1, int(1000 / ((i + 1) ** alpha))) for i in range(20)}
    result = tracker.record(freqs)
    assert result["zipf_r_squared"] > 0.95


def test_heaps_beta_saturating(tracker):
    """When vocabulary stops growing, Heaps beta drops toward 0."""
    # Simulate growing then saturating vocabulary
    for i in range(10):
        n_types = min(i + 1, 6)  # Saturates at 6 types
        freqs = {f"T{j}": (i + 1) * 10 for j in range(n_types)}
        result = tracker.record(freqs)

    # After saturation, beta should be low (vocabulary growth slowed)
    assert result["heaps_beta"] < 0.5


def test_chao1_no_singletons(tracker):
    """When all types seen >= 2 times, Chao1 equals observed."""
    freqs = {"A": 5, "B": 3, "C": 10, "D": 2}
    result = tracker.record(freqs)
    assert result["chao1_estimate"] == result["unique_types"]
    assert result["chao1_coverage"] == 1.0


def test_chao1_many_singletons(tracker):
    """Singletons inflate Chao1 above observed count."""
    freqs = {"Confirmed": 50, "Rare1": 1, "Rare2": 1, "Rare3": 1, "Seen2": 2}
    result = tracker.record(freqs)
    assert result["chao1_estimate"] > result["unique_types"]
    assert result["chao1_coverage"] < 1.0


def test_ace_estimate(tracker):
    """ACE estimate >= observed types."""
    freqs = {"A": 50, "B": 30, "C": 1, "D": 1, "E": 1, "F": 2}
    result = tracker.record(freqs)
    assert result["ace_estimate"] >= result["unique_types"]


def test_rolling_variance_stable(tracker):
    """Constant metric values give 0 variance."""
    freqs = {"A": 10, "B": 20, "C": 30}
    for _ in range(6):
        result = tracker.record(freqs)
    assert result["entropy_shannon_var"] < 1e-9


def test_first_document_nan(tracker):
    """Divergence metrics return nan on first document."""
    result = tracker.record({"A": 10, "B": 5})
    assert math.isnan(result["kl_divergence"])
    assert math.isnan(result["js_divergence"])
    assert math.isnan(result["entropy_shannon_delta"])


def test_record_returns_all_keys(tracker):
    """Output dict has all expected metric keys."""
    tracker.record({"A": 5, "B": 3})
    result = tracker.record({"A": 10, "B": 5, "C": 2})

    expected_keys = {
        "unique_types", "total_occurrences", "singletons", "doubletons",
        "entropy_shannon", "entropy_shannon_delta",
        "kl_divergence", "js_divergence",
        "type_accumulation_rate",
        "gini_coefficient",
        "zipf_r_squared",
        "heaps_beta",
        "chao1_estimate", "chao1_coverage",
        "ace_estimate",
        "entropy_shannon_var", "js_divergence_var",
        "gini_coefficient_var", "chao1_coverage_var",
    }
    assert expected_keys.issubset(result.keys())


def test_empty_frequencies_returns_empty(tracker):
    """Empty frequencies dict returns empty result."""
    assert tracker.record({}) == {}


def test_history_and_latest(tracker):
    """History grows with each record, latest returns most recent."""
    assert tracker.latest() is None
    assert tracker.history() == []

    tracker.record({"A": 5})
    assert len(tracker.history()) == 1
    assert tracker.latest() is not None

    tracker.record({"A": 10, "B": 3})
    assert len(tracker.history()) == 2


def test_type_accumulation_rate_first_doc(tracker):
    """First document rate equals the number of types seen."""
    result = tracker.record({"A": 5, "B": 3, "C": 1})
    assert result["type_accumulation_rate"] == 3.0


def test_type_accumulation_rate_no_new(tracker):
    """Same types across docs gives rate 0."""
    tracker.record({"A": 5, "B": 3})
    result = tracker.record({"A": 10, "B": 8})
    assert result["type_accumulation_rate"] == 0.0

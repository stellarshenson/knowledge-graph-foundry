"""Tests for drift detection and the rebuild decision engine."""

from knowledge_graph_foundry.drift import DriftDetector, _jsd
from knowledge_graph_foundry.settings import DriftSettings

CFG = DriftSettings()  # remap 0.3, window 3, rebuild jsd 0.15
CURED = {"Product": 50, "Component": 30, "Specification": 20}


class TestJsd:
    def test_identical_zero(self):
        assert _jsd(CURED, CURED) == 0.0

    def test_disjoint_is_one(self):
        assert abs(_jsd({"A": 10}, {"B": 10}) - 1.0) < 1e-9

    def test_empty_zero(self):
        assert _jsd({}, {}) == 0.0


class TestDriftDetector:
    def test_no_verdict_below_window(self):
        d = DriftDetector(CFG, CURED)
        verdict = d.record_document(0.9, {"Alien": 10})
        assert verdict.action == "none"

    def test_stable_documents_no_drift(self):
        d = DriftDetector(CFG, CURED)
        for _ in range(5):
            verdict = d.record_document(0.05, CURED)
        assert verdict.action == "none"

    def test_single_outlier_smoothed(self):
        d = DriftDetector(CFG, CURED)
        d.record_document(0.05, CURED)
        d.record_document(0.9, {"Alien": 10})  # one bad document
        verdict = d.record_document(0.05, CURED)
        assert verdict.action == "warn"  # noticed, but not recure

    def test_sustained_remap_triggers_recure(self):
        d = DriftDetector(CFG, CURED)
        for _ in range(3):
            verdict = d.record_document(0.5, CURED)
        assert verdict.action == "recure"

    def test_sustained_remap_and_divergence_recommends_rebuild(self):
        d = DriftDetector(CFG, CURED)
        for _ in range(3):
            verdict = d.record_document(0.6, {"Alien": 40, "Foreign": 30})
        assert verdict.action == "rebuild"
        assert verdict.evidence["jsd"] > CFG.rebuild_jsd_threshold

    def test_drift_coalesces_during_recuring(self):
        d = DriftDetector(CFG, CURED)
        d.begin_recure()
        for _ in range(3):
            verdict = d.record_document(0.6, CURED)
        assert verdict.action == "none"

    def test_end_recure_resets_baseline(self):
        d = DriftDetector(CFG, CURED)
        for _ in range(3):
            d.record_document(0.5, CURED)
        new_freqs = {"Product": 10, "Sensor": 5}
        d.end_recure(new_freqs)
        assert d.cured_frequencies == new_freqs
        assert d.record_document(0.05, new_freqs).action == "none"

    def test_serialization_roundtrip(self):
        d = DriftDetector(CFG, CURED)
        d.record_document(0.5, CURED)
        d.record_contradictions(2, 10)
        restored = DriftDetector.from_dict(d.to_dict(), CFG)
        assert restored.cured_frequencies == CURED
        assert restored._remap_rates == [0.5]
        assert restored._contradictions == [0.2]


class TestFactDriftAlarm:
    def test_no_alarm_below_window(self):
        d = DriftDetector(CFG, CURED)
        assert d.record_contradictions(5, 10) is None

    def test_sustained_contradictions_raise_fact_drift(self):
        d = DriftDetector(CFG, CURED)  # window 3, threshold 0.2
        verdicts = [d.record_contradictions(5, 10) for _ in range(3)]  # rate 0.5
        assert verdicts[-1] is not None
        assert verdicts[-1].action == "fact_drift"
        assert verdicts[-1].evidence["contradiction_rate"] > CFG.contradiction_rate_threshold

    def test_low_contradiction_rate_no_alarm(self):
        d = DriftDetector(CFG, CURED)
        for _ in range(5):
            v = d.record_contradictions(0, 10)  # no invalidations
        assert v is None

    def test_fact_drift_distinct_from_schema_drift(self):
        """Fact drift fires on invalidations while the type distribution (schema)
        stays put - the two signals are independent."""
        d = DriftDetector(CFG, CURED)
        schema_verdicts = [d.record_document(0.05, CURED) for _ in range(3)]  # stable schema
        fact_verdicts = [d.record_contradictions(4, 10) for _ in range(3)]  # facts churning
        assert all(v.action == "none" for v in schema_verdicts)
        assert fact_verdicts[-1] is not None and fact_verdicts[-1].action == "fact_drift"

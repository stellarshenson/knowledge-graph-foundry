"""Tests for drift detection and the rebuild decision engine."""

from knowledge_graph_foundry.drift import DriftDetector, _jsd
from knowledge_graph_foundry.settings import DriftSettings

CFG = DriftSettings(cusum_enabled=False)  # boolean-path config (cusum default-on since 2026-07-12): remap 0.3, window 3, rebuild jsd 0.15
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


class TestCusumTrigger:
    """R36-H378/DEF-9: the H317 CUSUM recure trigger and the RECURING exit."""

    def cfg(self):
        return DriftSettings(cusum_enabled=True)

    def test_step_change_fires_where_boolean_is_blind(self):
        # remap rates stay BELOW the boolean threshold - the anti-phase case
        # (DEF-9): the boolean conjunction can never fire, CUSUM must
        d = DriftDetector(self.cfg(), CURED)
        for _ in range(3):
            assert d.record_document(0.05, CURED).action == "none"  # arm mu0
        drifted = {"Alien": 40, "Product": 10}
        actions = [d.record_document(0.1, drifted).action for _ in range(5)]
        assert "recure" in actions

    def test_slow_ramp_fires(self):
        d = DriftDetector(self.cfg(), CURED)
        for _ in range(3):
            d.record_document(0.05, CURED)
        actions = []
        for i in range(1, 20):
            mix = {
                "Product": max(50 - 3 * i, 1),
                "Alien": 3 * i,
                "Component": 30,
                "Specification": 20,
            }
            actions.append(d.record_document(0.05, mix).action)
        assert "recure" in actions

    def test_stationary_never_fires(self):
        d = DriftDetector(self.cfg(), CURED)
        actions = [d.record_document(0.05, CURED).action for _ in range(30)]
        assert all(a == "none" for a in actions)

    def test_flag_off_keeps_boolean_path(self):
        d = DriftDetector(DriftSettings(cusum_enabled=False), CURED)
        for _ in range(3):
            d.record_document(0.05, CURED)
        drifted = {"Alien": 40, "Product": 10}
        # sub-threshold remap: boolean conjunction stays silent by design
        actions = [d.record_document(0.1, drifted).action for _ in range(5)]
        assert "recure" not in actions

    def test_recure_flow_exits_and_rebaselines(self):
        d = DriftDetector(self.cfg(), CURED)
        for _ in range(3):
            d.record_document(0.05, CURED)
        drifted = {"Alien": 40, "Product": 10}
        fired = False
        for _ in range(10):
            if d.record_document(0.1, drifted).action == "recure":
                fired = True
                break
        assert fired
        d.begin_recure()
        while not d.recure_ready():
            assert d.record_document(0.1, drifted).action == "none"  # coalesced
        window = d.recure_window_frequencies()
        assert window["Alien"] > 0
        d.end_recure(window)
        # livelock guard: the SAME register no longer alarms post-rebaseline
        actions = [d.record_document(0.1, drifted).action for _ in range(10)]
        assert all(a == "none" for a in actions)

    def test_cusum_state_roundtrip(self):
        d = DriftDetector(self.cfg(), CURED)
        for _ in range(3):
            d.record_document(0.05, CURED)
        d.record_document(0.1, {"Alien": 40, "Product": 10})
        restored = DriftDetector.from_dict(d.to_dict(), self.cfg())
        assert restored._cusum_s == d._cusum_s
        assert restored._cusum_mu0 == d._cusum_mu0
        assert restored._jsd_series == d._jsd_series


class TestAdoptDriftedTypes:
    def test_sustained_type_adopted_cured(self):
        from knowledge_graph_foundry.drift import adopt_drifted_types
        from knowledge_graph_foundry.models import Ontology, TypeDef

        ont = Ontology(types={"Product": TypeDef(name="Product", status="cured")}, cured=True)
        adopted = adopt_drifted_types(ont, {"Alien": 40, "Product": 60}, min_share=0.05)
        assert adopted == ["Alien"]
        assert ont.types["Alien"].status == "cured"
        assert ont.types["Alien"].encounters == 40

    def test_below_share_floor_not_adopted(self):
        from knowledge_graph_foundry.drift import adopt_drifted_types
        from knowledge_graph_foundry.models import Ontology

        ont = Ontology()
        adopted = adopt_drifted_types(ont, {"Rare": 1, "Common": 99}, min_share=0.05)
        assert "Rare" not in adopted
        assert "Common" in adopted

    def test_existing_type_untouched(self):
        from knowledge_graph_foundry.drift import adopt_drifted_types
        from knowledge_graph_foundry.models import Ontology, TypeDef

        ont = Ontology(types={"Product": TypeDef(name="Product", encounters=7)})
        adopt_drifted_types(ont, {"Product": 100}, min_share=0.05)
        assert ont.types["Product"].encounters == 7  # never overwritten

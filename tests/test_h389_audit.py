"""R39-H389 coverage-audit instrument: the deterministic gates."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "h389", Path(__file__).parent.parent / "scripts" / "r39_h389_coverage_audit.py"
)
h389 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h389)


class TestGroundednessGate:
    CHUNK = "The AirSense 11 covers a pressure range of 4 to 20 cmH2O and weighs 1.2 kg."

    def test_verbatim_probe_passes(self):
        assert h389.grounded("AirSense 11 pressure range 4 20 cmH2O", self.CHUNK)

    def test_hallucinated_term_fails(self):
        # 'altitude' does not appear in the chunk - the gate must reject
        assert not h389.grounded("AirSense 11 operates at high altitude", self.CHUNK)

    def test_empty_probe_fails(self):
        assert not h389.grounded("", self.CHUNK)
        assert not h389.grounded("the of and", self.CHUNK)  # stopwords only


class TestSupportTest:
    GRAPH = 'AirSense 11 CPAP device {"pressure_range": "4-20 cmH2O"} weighs 1.2 kg'

    def test_supported_fact(self):
        assert h389.supported("AirSense 11 pressure range cmH2O", self.GRAPH)

    def test_missed_fact(self):
        # sound level never made it into the graph - a coverage miss
        assert not h389.supported("AirSense 11 sound pressure level 27 dBA", self.GRAPH)

    def test_threshold_is_share_based(self):
        # 3 of 4 content terms present at threshold 0.8 -> not supported; at 0.7 -> supported
        probe = "AirSense pressure range quiet"
        assert not h389.supported(probe, self.GRAPH, threshold=0.8)
        assert h389.supported(probe, self.GRAPH, threshold=0.7)


class TestProbeParsing:
    class FakeEngine:
        def complete_text(self, system, user):
            return "AirSense 11 covers 4 to 20 cmH2O\n- weighs 1.2 kg\nInvented altitude claim\n"

    def test_generate_filters_ungrounded(self):
        chunk = "The AirSense 11 covers a pressure range of 4 to 20 cmH2O and weighs 1.2 kg."
        probes = h389.generate_probes(self.FakeEngine(), chunk)
        assert "AirSense 11 covers 4 to 20 cmH2O" in probes
        assert "weighs 1.2 kg" in probes
        assert all("altitude" not in p for p in probes)

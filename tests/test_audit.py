"""R39-H389/H548 coverage certificate + R49-H573 seed-hop reachability.

Synthetic fixtures - no live graph or LLM.
"""

from knowledge_graph_foundry.graph.audit import (
    content_terms,
    corpus_summary,
    document_certificate,
    grounded,
    seed_hop_distance,
    supported,
)


class TestGates:
    CHUNK = "The AirSense 11 covers a pressure range of 4 to 20 cmH2O and weighs 1.2 kg."

    def test_grounded_verbatim_passes(self):
        assert grounded("AirSense 11 pressure range 4 20 cmH2O", self.CHUNK)

    def test_grounded_hallucination_fails(self):
        assert not grounded("AirSense 11 operates at high altitude", self.CHUNK)

    def test_supported_share_threshold(self):
        graph = 'AirSense 11 CPAP device {"pressure_range": "4-20 cmH2O"}'
        assert supported("AirSense 11 pressure range cmH2O", graph)
        assert not supported("AirSense 11 sound level 27 dBA", graph)

    def test_content_terms_keeps_short_numerics(self):
        assert "9" in content_terms("rated 9 w")  # short numeric kept
        assert "of" not in content_terms("power of device")  # stopword dropped


class TestDocumentCertificate:
    GRAPH = 'AirSense 11 CPAP device {"pressure_range": "4-20 cmH2O"} weighs 1.2 kg'

    def test_full_coverage(self):
        probes = ["AirSense 11 pressure range cmH2O", "AirSense 11 weighs 1.2 kg"]
        cert = document_certificate(probes, self.GRAPH)
        assert cert == {"probes": 2, "coverage": 1.0, "missing_spans": []}

    def test_partial_coverage_lists_misses(self):
        probes = ["AirSense 11 pressure range cmH2O", "AirSense 11 sound level 27 dBA"]
        cert = document_certificate(probes, self.GRAPH)
        assert cert["probes"] == 2
        assert cert["coverage"] == 0.5
        assert cert["missing_spans"] == ["AirSense 11 sound level 27 dBA"]

    def test_no_probes_is_none_coverage(self):
        assert document_certificate([], self.GRAPH) == {
            "probes": 0,
            "coverage": None,
            "missing_spans": [],
        }


class TestCorpusSummary:
    def test_rolls_up_probes_and_coverage(self):
        certs = [
            {"probes": 2, "coverage": 1.0, "missing_spans": []},
            {"probes": 2, "coverage": 0.5, "missing_spans": ["m"]},
        ]
        summary = corpus_summary(certs)
        assert summary["documents"] == 2
        assert summary["probes"] == 4
        assert summary["supported"] == 3
        assert summary["coverage"] == 0.75

    def test_empty_corpus_is_none(self):
        assert corpus_summary([])["coverage"] is None


class TestSeedHopDistance:
    #  a - b - c - d ;  x is isolated
    ADJ = {"a": {"b"}, "b": {"a", "c"}, "c": {"b", "d"}, "d": {"c"}, "x": set()}

    def test_target_is_seed_zero_hops(self):
        assert seed_hop_distance(self.ADJ, {"a"}, "a") == 0

    def test_one_hop(self):
        assert seed_hop_distance(self.ADJ, {"a"}, "b") == 1

    def test_multi_hop(self):
        assert seed_hop_distance(self.ADJ, {"a"}, "d") == 3

    def test_nearest_seed_wins(self):
        assert seed_hop_distance(self.ADJ, {"a", "c"}, "d") == 1

    def test_unreachable_returns_none(self):
        assert seed_hop_distance(self.ADJ, {"a"}, "x") is None

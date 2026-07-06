"""Tests for proposition rendering (R02-H11) - deterministic fact sentences."""

from knowledge_graph_foundry.graph.propositions import (
    proposition_id,
    render_property_sentence,
    render_relation_sentence,
)


class TestRendering:
    def test_relation_sentence_humanizes_predicate(self):
        s = render_relation_sentence("AirSense 11", "HAS_PRESSURE_RANGE", "4-20 cmH2O")
        assert s == "AirSense 11 has pressure range 4-20 cmH2O."

    def test_property_sentence_sorts_and_humanizes_keys(self):
        s = render_property_sentence(
            "AirSense 11", {"weight": "1130 g", "pressure_range": "4-20 cmH2O"}
        )
        assert s == "AirSense 11 - pressure range: 4-20 cmH2O; weight: 1130 g."

    def test_proposition_id_deterministic_and_content_keyed(self):
        a = proposition_id("AirSense 11 has pressure range 4-20 cmH2O.")
        b = proposition_id("AirSense 11 has pressure range 4-20 cmH2O.")
        c = proposition_id("AirSense 11 weighs 1130 g.")
        assert a == b
        assert a != c
        assert a.startswith("p_")

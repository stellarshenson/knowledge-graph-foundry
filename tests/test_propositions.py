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


class TestQuoteSelection:
    """R04-H22: deterministic verbatim sentence selection."""

    TEXT = (
        "The device has several comfort features. SmartRamp maintains a constant "
        "lower pressure until the device detects that you require more pressure. "
        "SmartRamp. Standard ramp increases pressure on a fixed schedule regardless "
        "of breathing. It can be disabled in the clinical menu."
    )

    def test_selects_sentences_containing_the_name(self):
        from knowledge_graph_foundry.graph.propositions import select_quote_sentences

        quotes = select_quote_sentences(self.TEXT, "SmartRamp")
        assert quotes == [
            "SmartRamp maintains a constant lower pressure until the device "
            "detects that you require more pressure."
        ]  # the bare "SmartRamp." mention fails the min-length bound

    def test_case_insensitive_and_capped(self):
        from knowledge_graph_foundry.graph.propositions import select_quote_sentences

        text = " ".join(
            f"The smartramp feature does deterministic thing number {i} here." for i in range(9)
        )
        quotes = select_quote_sentences(text, "SmartRamp", max_quotes=3)
        assert len(quotes) == 3

    def test_no_match_returns_empty(self):
        from knowledge_graph_foundry.graph.propositions import select_quote_sentences

        assert select_quote_sentences(self.TEXT, "AutoRamp") == []


class TestDiversify:
    """R04-H22 iteration 3: alias-clone hits must not consume the whole window."""

    def _hit(self, text, score):
        return {"text": text, "score": score, "entity_ids": []}

    def test_near_duplicates_collapse_to_one_slot(self):
        from knowledge_graph_foundry.graph.propositions import diversify_hits

        hits = [
            self._hit("DreamStation has comfort feature SmartRamp.", 0.84),
            self._hit("Philips DreamStation has feature SmartRamp.", 0.83),
            self._hit("DreamStation CPAP Pro has feature Smart Ramp.", 0.81),
            self._hit(
                "Alternately, the SmartRamp mode maintains a constant lower pressure "
                "until the device detects that you require more pressure.",
                0.77,
            ),
        ]
        out = diversify_hits(hits, top_k=2)
        assert len(out) == 2
        assert out[0]["text"].startswith("DreamStation has")
        assert "constant lower pressure" in out[1]["text"]  # clone skipped, quote promoted

    def test_distinct_hits_kept_in_score_order(self):
        from knowledge_graph_foundry.graph.propositions import diversify_hits

        hits = [
            self._hit("AirSense 11 weighs 1130 g.", 0.9),
            self._hit("SleepStyle 200 dimensions are 275 x 170 x 140 mm.", 0.8),
        ]
        assert [h["score"] for h in diversify_hits(hits, top_k=8)] == [0.9, 0.8]

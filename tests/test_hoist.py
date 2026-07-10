"""R33-H365 spec-reachability repair: stem detection and unanimity semantics."""

from knowledge_graph_foundry.graph.hoist import series_stem, unanimous_props


class TestSeriesStem:
    def test_fragments_share_stem(self):
        assert series_stem("HC230-Series") == "HC230"
        assert series_stem("HC230 Product Range") == "HC230"

    def test_no_series_marker_is_not_a_fragment(self):
        assert series_stem("HC231") is None  # a model, never a merge target

    def test_no_model_code_is_not_a_fragment(self):
        assert series_stem("SleepStyle Series") is None

    def test_spaced_stem_normalizes(self):
        assert series_stem("HC 230 Series") == "HC230"

    def test_marker_case_insensitive(self):
        assert series_stem("hc230 FAMILY") == "HC230"


class TestUnanimousProps:
    def test_unanimous_key_hoists(self):
        kids = [{"prop_voltage": "230V"}, {"prop_voltage": "230V"}]
        assert unanimous_props(kids) == {"prop_voltage": "230V"}

    def test_conflicting_key_stays(self):
        kids = [{"prop_weight": "1kg"}, {"prop_weight": "2kg"}]
        assert unanimous_props(kids) == {}

    def test_missing_on_one_child_stays(self):
        kids = [{"prop_voltage": "230V"}, {}]
        assert unanimous_props(kids) == {}

    def test_single_child_never_hoists(self):
        assert unanimous_props([{"prop_voltage": "230V"}]) == {}

    def test_non_prop_keys_ignored(self):
        kids = [{"name": "a", "prop_x": "1"}, {"name": "b", "prop_x": "1"}]
        assert unanimous_props(kids) == {"prop_x": "1"}

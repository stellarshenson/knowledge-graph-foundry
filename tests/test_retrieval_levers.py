"""Tests for the H198 tranche-3a retrieval/render levers (R19 trio, H195a
generous-fetch, H205 foreign-device exclusion, H211 prop-val linkage). Pure
helpers - no live Neo4j or LLM."""

from knowledge_graph_foundry.graph.graphrag import (
    cap_fanout,
    detect_miss,
    exclude_foreign_devices,
    link_prop_values,
    overfetch_seeds,
    truncate_to_budget,
)
from knowledge_graph_foundry.settings import Settings


class TestOverfetch:
    """R15-H195a: query the index at top_k*factor then truncate to top_k."""

    def test_fetches_factor_multiple_then_truncates(self):
        calls = []

        def query_fn(k):
            calls.append(k)
            return [{"id": f"e{i}"} for i in range(k)]

        out = overfetch_seeds(query_fn, top_k=16, factor=4)
        assert calls == [64]  # fetched top_k * factor
        assert len(out) == 16  # truncated back to top_k

    def test_factor_one_is_plain_fetch(self):
        calls = []

        def query_fn(k):
            calls.append(k)
            return [{"id": f"e{i}"} for i in range(k)]

        out = overfetch_seeds(query_fn, top_k=8, factor=1)
        assert calls == [8]
        assert len(out) == 8


class TestFanoutCap:
    """R19-H180: rank 1-hop neighbors by query similarity, keep top k."""

    def test_ranks_by_similarity_and_truncates(self):
        qv = [1.0, 0.0]
        rows = [
            {"rel": "A", "name": "far", "emb": [0.0, 1.0]},  # sim 0.0
            {"rel": "B", "name": "near", "emb": [1.0, 0.0]},  # sim 1.0
            {"rel": "C", "name": "mid", "emb": [0.5, 0.5]},  # sim 0.5
        ]
        out = cap_fanout(rows, qv, k=2)
        assert [r["name"] for r in out] == ["near", "mid"]

    def test_missing_embedding_sorts_last(self):
        qv = [1.0, 0.0]
        rows = [
            {"rel": "A", "name": "noemb", "emb": None},
            {"rel": "B", "name": "hit", "emb": [1.0, 0.0]},
        ]
        out = cap_fanout(rows, qv, k=1)
        assert out[0]["name"] == "hit"

    def test_zero_cap_leaves_rows_unbounded(self):
        rows = [{"name": "x", "emb": None}, {"name": "y", "emb": None}]
        assert cap_fanout(rows, [1.0], k=0) == rows


class TestMissDetector:
    """R19-H181: fire when best seed similarity is below threshold (0.668)."""

    def test_fires_below_threshold(self):
        seeds = [{"score": 0.5}, {"score": 0.6}]
        assert detect_miss(seeds, 0.668) is True

    def test_does_not_fire_above_threshold(self):
        seeds = [{"score": 0.5}, {"score": 0.8}]
        assert detect_miss(seeds, 0.668) is False

    def test_empty_seeds_is_a_miss(self):
        assert detect_miss([], 0.668) is True


class TestRenderBudget:
    """R19-H182: keep the top-similarity 60% of render mass."""

    def test_keeps_top_similarity_share(self):
        # five equal-size units; budget 0.6 keeps the three highest-similarity
        units = [(f"u{i}", sim, 10.0) for i, sim in enumerate([0.1, 0.9, 0.5, 0.7, 0.3])]
        out = truncate_to_budget(units, 0.6)
        assert out == ["u1", "u3", "u2"]  # 0.9, 0.7, 0.5 - ranked, 30 of 50 mass

    def test_budget_one_keeps_everything_in_order(self):
        units = [("a", 0.1, 5.0), ("b", 0.9, 5.0)]
        assert truncate_to_budget(units, 1.0) == ["a", "b"]


class TestForeignDeviceExclusion:
    """R19-H205: optional layer - drop foreign-device render sections."""

    def test_off_by_default(self):
        assert Settings().graphrag.foreign_device_exclusion is False

    def test_drops_foreign_devices_keeps_queried_and_nondevice(self):
        nodes = [
            {"id": "q", "types": ["CPAPDevice"]},  # queried product - kept
            {"id": "foreign", "types": ["ProductModel"]},  # foreign device - dropped
            {"id": "feat", "types": ["Feature"]},  # non-device - kept
        ]
        out = exclude_foreign_devices(nodes, {"q"})
        assert [n["id"] for n in out] == ["q", "feat"]


class TestPropValLinkage:
    """R19-H211: link property values equal to an entity name (224-target map)."""

    def test_links_value_to_same_name_entity(self):
        value_index = {"bi-level": ["AirCurve 10 S"], "auto": ["DreamStation Auto"]}
        assert link_prop_values("Bi-level", value_index) == ["AirCurve 10 S"]

    def test_short_names_do_not_link(self):
        value_index = {"n95": ["Mask"]}
        assert link_prop_values("N95", value_index) == []

    def test_absent_value_returns_empty(self):
        assert link_prop_values("Nonexistent", {}) == []


class TestLeverDefaults:
    """The shipped default config is the promoted composition."""

    def test_r19_trio_defaults(self):
        g = Settings().graphrag
        assert g.fanout_cap == 5  # H180
        assert g.miss_detector is True and g.miss_threshold == 0.668  # H181
        assert g.render_budget == 0.6  # H182

    def test_overfetch_default(self):
        assert Settings().graphrag.overfetch_factor == 4  # H195a (GEN_K=64/16)

    def test_prop_val_linkage_on_by_default(self):
        assert Settings().graphrag.prop_val_linkage is True  # H211

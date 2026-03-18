"""Tests for ObservationCollector ground truth derivation and aggregation."""

import pytest

from kg_builder_cli.curing.observation import (
    CrossTypeObservation,
    ObservationCollector,
    TypeAssignmentObservation,
)


def _cross_obs(
    norm_name="widget",
    type_a="Component",
    type_b="Product",
    raw_posterior=0.7,
    prior=0.8,
    action="merged",
    doc_index=0,
) -> CrossTypeObservation:
    return CrossTypeObservation(
        norm_name=norm_name,
        type_a=type_a,
        type_b=type_b,
        raw_posterior=raw_posterior,
        prior=prior,
        lr_desc=1.0,
        lr_emb=1.0,
        lr_cooc=1.0,
        action=action,
        doc_index=doc_index,
        has_hierarchy=False,
        sibling=False,
    )


def _assign_obs(
    entity_name="Widget",
    type_before="Unknown",
    type_after="Component",
    posterior=None,
    entropy=0.5,
    was_remapped=True,
    doc_index=0,
) -> TypeAssignmentObservation:
    return TypeAssignmentObservation(
        entity_name=entity_name,
        type_before=type_before,
        type_after=type_after,
        posterior=posterior or {"Component": 0.8, "Product": 0.2},
        entropy=entropy,
        was_remapped=was_remapped,
        escalated_to_llm=False,
        doc_index=doc_index,
    )


class TestObservationCollector:
    def test_record_and_count(self):
        collector = ObservationCollector()
        collector.record_cross_type(_cross_obs())
        collector.record_type_assignment(_assign_obs())
        assert collector.cross_type_count == 1
        assert collector.type_assignment_count == 1

    def test_empty_collector(self):
        collector = ObservationCollector()
        assert collector.cross_type_count == 0
        assert collector.type_assignment_count == 0
        assert collector.derive_ground_truth({}) == []
        assert collector.aggregate_calibration() == {}


class TestGroundTruth:
    def test_correct_merge_same_cluster(self):
        """Merged pair where both types map to same cluster -> correct."""
        collector = ObservationCollector()
        collector.record_cross_type(_cross_obs(action="merged", raw_posterior=0.7))
        mapping = {"Component": "Component", "Product": "Component"}
        pairs = collector.derive_ground_truth(mapping)
        assert len(pairs) == 1
        assert pairs[0] == (0.7, True)

    def test_incorrect_merge_different_cluster(self):
        """Merged pair where types map to different clusters -> incorrect."""
        collector = ObservationCollector()
        collector.record_cross_type(_cross_obs(action="merged", raw_posterior=0.7))
        mapping = {"Component": "Component", "Product": "Product"}
        pairs = collector.derive_ground_truth(mapping)
        assert len(pairs) == 1
        assert pairs[0] == (0.7, False)

    def test_correct_block_different_cluster(self):
        """Blocked pair where types map to different clusters -> correct."""
        collector = ObservationCollector()
        collector.record_cross_type(_cross_obs(action="blocked", raw_posterior=0.3))
        mapping = {"Component": "Component", "Product": "Product"}
        pairs = collector.derive_ground_truth(mapping)
        assert len(pairs) == 1
        assert pairs[0] == (0.3, True)

    def test_incorrect_block_same_cluster(self):
        """Blocked pair where types map to same cluster -> incorrect."""
        collector = ObservationCollector()
        collector.record_cross_type(_cross_obs(action="blocked", raw_posterior=0.3))
        mapping = {"Component": "Component", "Product": "Component"}
        pairs = collector.derive_ground_truth(mapping)
        assert len(pairs) == 1
        assert pairs[0] == (0.3, False)

    def test_deferred_excluded(self):
        """Deferred actions should not produce ground truth pairs."""
        collector = ObservationCollector()
        collector.record_cross_type(_cross_obs(action="deferred"))
        pairs = collector.derive_ground_truth({"Component": "Component", "Product": "Product"})
        assert len(pairs) == 0

    def test_hierarchy_merge_correct(self):
        """hierarchy_merge treated same as merged."""
        collector = ObservationCollector()
        collector.record_cross_type(_cross_obs(action="hierarchy_merge", raw_posterior=0.9))
        mapping = {"Component": "Component", "Product": "Component"}
        pairs = collector.derive_ground_truth(mapping)
        assert len(pairs) == 1
        assert pairs[0] == (0.9, True)

    def test_multi_facet_correct(self):
        """multi_facet treated same as merged."""
        collector = ObservationCollector()
        collector.record_cross_type(_cross_obs(action="multi_facet", raw_posterior=0.6))
        mapping = {"Component": "Component", "Product": "Component"}
        pairs = collector.derive_ground_truth(mapping)
        assert len(pairs) == 1
        assert pairs[0] == (0.6, True)

    def test_identity_mapping(self):
        """Identity mapping: merged is incorrect (types stay separate)."""
        collector = ObservationCollector()
        collector.record_cross_type(
            _cross_obs(type_a="A", type_b="B", action="merged", raw_posterior=0.8)
        )
        mapping = {"A": "A", "B": "B"}
        pairs = collector.derive_ground_truth(mapping)
        assert pairs[0] == (0.8, False)

    def test_multiple_observations(self):
        collector = ObservationCollector()
        collector.record_cross_type(_cross_obs(action="merged", raw_posterior=0.7))
        collector.record_cross_type(_cross_obs(action="blocked", raw_posterior=0.3))
        collector.record_cross_type(_cross_obs(action="deferred", raw_posterior=0.5))
        mapping = {"Component": "Component", "Product": "Component"}
        pairs = collector.derive_ground_truth(mapping)
        # merged correct (same cluster), blocked incorrect (same cluster), deferred excluded
        assert len(pairs) == 2


class TestAggregation:
    def test_cross_type_aggregation(self):
        collector = ObservationCollector()
        collector.record_cross_type(_cross_obs(type_a="A", type_b="B", raw_posterior=0.7))
        collector.record_cross_type(_cross_obs(type_a="A", type_b="C", raw_posterior=0.3))

        result = collector.aggregate_calibration()
        assert "A" in result
        assert result["A"]["observation_count"] == 2
        assert abs(result["A"]["mean_posterior"] - 0.5) < 0.01
        assert "B" in result
        assert result["B"]["observation_count"] == 1

    def test_type_assignment_aggregation(self):
        collector = ObservationCollector()
        collector.record_type_assignment(
            _assign_obs(type_after="Component", was_remapped=True)
        )
        collector.record_type_assignment(
            _assign_obs(type_after="Component", was_remapped=False)
        )

        result = collector.aggregate_calibration()
        assert "Component" in result
        assert result["Component"]["observation_count"] == 2
        assert result["Component"]["remap_count"] == 1

    def test_mixed_aggregation(self):
        collector = ObservationCollector()
        collector.record_cross_type(_cross_obs(type_a="A", type_b="B"))
        collector.record_type_assignment(_assign_obs(type_after="A"))

        result = collector.aggregate_calibration()
        assert "A" in result
        assert result["A"]["observation_count"] == 2  # one from each source

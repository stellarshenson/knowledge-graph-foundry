"""Tests for TypeMetricsCollector - 19 per-type metrics."""

import math

import pytest

from kg_builder_cli.curing.type_metrics import TypeMetricsCollector
from kg_builder_cli.types.extraction import (
    Entity,
    ExtractionMetadata,
    ExtractionResult,
    Relationship,
)


def _entity(name, etype, description="", embedding=None, source_chunks=None):
    return Entity(
        id=f"{etype.lower()}_{name.lower().replace(' ', '_')}",
        name=name,
        type=etype,
        description=description,
        embedding=embedding,
        source_chunks=source_chunks or [],
    )


def _rel(source, target, rtype="RELATES_TO"):
    return Relationship(source=source, target=target, type=rtype, description="")


def _result(entities, relationships=None):
    return ExtractionResult(
        metadata=ExtractionMetadata(source="test.pdf", model="test"),
        entities=entities,
        relationships=relationships or [],
    )


def _make_embedding(seed, dim=16):
    """Deterministic pseudo-embedding for testing."""
    import numpy as np

    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(float)
    return (vec / max(np.linalg.norm(vec), 1e-8)).tolist()


class TestFrequencyMetrics:
    def test_freq_log_smooth(self):
        results = [_result([_entity("A", "Comp"), _entity("B", "Comp"), _entity("C", "Spec")])]
        freqs = {"Comp": 2, "Spec": 1}
        collector = TypeMetricsCollector(results, freqs)
        metrics = collector.compute()
        # F1: log(freq+1) / log(total+K)
        assert metrics["Comp"]["freq_log_smooth"] > metrics["Spec"]["freq_log_smooth"]

    def test_freq_rank_pct(self):
        results = [_result([_entity("A", "Comp"), _entity("B", "Spec")])]
        freqs = {"Comp": 10, "Spec": 5}
        collector = TypeMetricsCollector(results, freqs)
        metrics = collector.compute()
        # Comp is rank 0 (most frequent), Spec is rank 1
        assert metrics["Comp"]["freq_rank_pct"] == 0.0
        assert metrics["Spec"]["freq_rank_pct"] == 1.0

    def test_freq_cv_single_doc(self):
        results = [_result([_entity("A", "Comp")])]
        freqs = {"Comp": 1}
        collector = TypeMetricsCollector(results, freqs)
        metrics = collector.compute()
        # Single doc -> CV = 0
        assert metrics["Comp"]["freq_cv"] == 0.0

    def test_freq_cv_multi_doc(self):
        r1 = _result([_entity("A", "Comp"), _entity("B", "Comp")])
        r2 = _result([_entity("C", "Comp")])
        freqs = {"Comp": 3}
        collector = TypeMetricsCollector([r1, r2], freqs)
        metrics = collector.compute()
        # 2 docs with [2, 1] -> mean=1.5, std=0.5, CV=0.33
        assert metrics["Comp"]["freq_cv"] > 0


class TestDistributionMetrics:
    def test_name_diversity(self):
        results = [
            _result([
                _entity("Motor", "Comp"),
                _entity("Motor", "Comp"),
                _entity("Pump", "Comp"),
            ])
        ]
        freqs = {"Comp": 3}
        collector = TypeMetricsCollector(results, freqs)
        metrics = collector.compute()
        # 2 unique names / 3 entities = 0.67
        assert abs(metrics["Comp"]["name_diversity"] - 2 / 3) < 0.01

    def test_top3_concentration(self):
        results = [
            _result([
                _entity("A", "Comp"),
                _entity("A", "Comp"),
                _entity("A", "Comp"),
                _entity("B", "Comp"),
            ])
        ]
        freqs = {"Comp": 4}
        collector = TypeMetricsCollector(results, freqs)
        metrics = collector.compute()
        # Top-3 concentration: A(3) + B(1) = 4/4 = 1.0 (only 2 unique names)
        assert metrics["Comp"]["top3_concentration"] == 1.0

    def test_desc_entropy_zero_no_descriptions(self):
        results = [_result([_entity("A", "Comp", description="")])]
        freqs = {"Comp": 1}
        collector = TypeMetricsCollector(results, freqs)
        metrics = collector.compute()
        assert metrics["Comp"]["desc_entropy"] == 0.0


class TestEmbeddingMetrics:
    def test_nan_without_embeddings(self):
        results = [_result([_entity("A", "Comp"), _entity("B", "Comp")])]
        freqs = {"Comp": 2}
        collector = TypeMetricsCollector(results, freqs)
        metrics = collector.compute()
        assert math.isnan(metrics["Comp"]["emb_cohesion"])
        assert math.isnan(metrics["Comp"]["emb_separation"])
        assert math.isnan(metrics["Comp"]["emb_silhouette"])
        assert math.isnan(metrics["Comp"]["emb_centroid_dist"])

    def test_with_embeddings(self):
        e1 = _entity("A", "Comp", embedding=_make_embedding(1))
        e2 = _entity("B", "Comp", embedding=_make_embedding(2))
        e3 = _entity("C", "Spec", embedding=_make_embedding(10))
        e4 = _entity("D", "Spec", embedding=_make_embedding(11))
        results = [_result([e1, e2, e3, e4])]
        freqs = {"Comp": 2, "Spec": 2}
        collector = TypeMetricsCollector(results, freqs)
        metrics = collector.compute()
        # With embeddings, metrics should be real numbers
        assert not math.isnan(metrics["Comp"]["emb_cohesion"])
        assert not math.isnan(metrics["Comp"]["emb_separation"])
        assert not math.isnan(metrics["Comp"]["emb_centroid_dist"])

    def test_single_entity_nan(self):
        """Single entity per type -> nan (need pairs)."""
        e1 = _entity("A", "Comp", embedding=_make_embedding(1))
        results = [_result([e1])]
        freqs = {"Comp": 1}
        collector = TypeMetricsCollector(results, freqs)
        metrics = collector.compute()
        assert math.isnan(metrics["Comp"]["emb_cohesion"])


class TestTopologyMetrics:
    def test_rel_type_diversity(self):
        e1 = _entity("A", "Comp")
        e2 = _entity("B", "Spec")
        rels = [
            _rel(e1.id, e2.id, "HAS_SPEC"),
            _rel(e1.id, e2.id, "REQUIRES"),
        ]
        results = [_result([e1, e2], rels)]
        freqs = {"Comp": 1, "Spec": 1}
        collector = TypeMetricsCollector(results, freqs)
        metrics = collector.compute()
        assert metrics["Comp"]["rel_type_diversity"] == 2.0

    def test_type_cooccurrence(self):
        r1 = _result([_entity("A", "Comp"), _entity("B", "Spec")])
        r2 = _result([_entity("C", "Comp")])
        freqs = {"Comp": 2, "Spec": 1}
        collector = TypeMetricsCollector([r1, r2], freqs)
        metrics = collector.compute()
        # Comp and Spec co-occur in doc 0 but not doc 1
        # Jaccard = 1/2 = 0.5
        assert abs(metrics["Comp"]["type_cooccurrence"] - 0.5) < 0.01

    def test_reciprocity_no_reverse(self):
        e1 = _entity("A", "Comp")
        e2 = _entity("B", "Spec")
        rels = [_rel(e1.id, e2.id, "HAS")]
        results = [_result([e1, e2], rels)]
        freqs = {"Comp": 1, "Spec": 1}
        collector = TypeMetricsCollector(results, freqs)
        metrics = collector.compute()
        assert metrics["Comp"]["rel_reciprocity"] == 0.0


class TestTemporalMetrics:
    def test_discovery_order(self):
        r1 = _result([_entity("A", "Comp")])
        r2 = _result([_entity("B", "Spec")])
        freqs = {"Comp": 1, "Spec": 1}
        collector = TypeMetricsCollector([r1, r2], freqs)
        metrics = collector.compute()
        # Comp discovered in doc 0, Spec in doc 1
        assert metrics["Comp"]["discovery_order"] == 0.0
        assert metrics["Spec"]["discovery_order"] == 1.0

    def test_tar_at_discovery(self):
        r1 = _result([_entity("A", "Comp")])
        r2 = _result([_entity("B", "Spec")])
        freqs = {"Comp": 1, "Spec": 1}
        collector = TypeMetricsCollector([r1, r2], freqs)
        metrics = collector.compute()
        assert metrics["Comp"]["tar_at_discovery"] == 1.0

    def test_cross_type_rate_zero(self):
        results = [_result([_entity("A", "Comp")])]
        freqs = {"Comp": 1}
        collector = TypeMetricsCollector(results, freqs)
        metrics = collector.compute()
        assert metrics["Comp"]["cross_type_rate"] == 0.0


class TestCalibrationMetrics:
    def test_nan_without_calibration_data(self):
        results = [_result([_entity("A", "Comp")])]
        freqs = {"Comp": 1}
        collector = TypeMetricsCollector(results, freqs)
        metrics = collector.compute()
        assert math.isnan(metrics["Comp"]["hist_mean_posterior"])
        assert math.isnan(metrics["Comp"]["hist_remap_rate"])
        assert math.isnan(metrics["Comp"]["cross_run_freq_delta"])

    def test_with_calibration_data(self):
        cal_data = {
            "Comp": {"mean_posterior": 0.75, "observation_count": 10, "remap_count": 2}
        }
        results = [_result([_entity("A", "Comp")])]
        freqs = {"Comp": 1}
        collector = TypeMetricsCollector(results, freqs, calibration_data=cal_data)
        metrics = collector.compute()
        assert metrics["Comp"]["hist_mean_posterior"] == 0.75
        assert abs(metrics["Comp"]["hist_remap_rate"] - 0.2) < 0.01

    def test_cross_run_freq_delta(self):
        results = [_result([_entity("A", "Comp")])]
        freqs = {"Comp": 15}
        prev = {"Comp": 10}
        collector = TypeMetricsCollector(results, freqs, prev_frequencies=prev)
        metrics = collector.compute()
        # abs(15-10)/10 = 0.5
        assert abs(metrics["Comp"]["cross_run_freq_delta"] - 0.5) < 0.01


class TestAllMetrics:
    def test_19_metrics_per_type(self):
        """Every type should have exactly 19 metrics."""
        e1 = _entity("Motor", "Component", "electric motor", _make_embedding(1))
        e2 = _entity("Pump", "Component", "water pump", _make_embedding(2))
        e3 = _entity("Voltage", "Spec", "voltage rating", _make_embedding(10))
        e4 = _entity("Current", "Spec", "current draw", _make_embedding(11))
        rels = [_rel(e1.id, e3.id, "HAS_SPEC")]
        r1 = _result([e1, e2, e3, e4], rels)

        freqs = {"Component": 2, "Spec": 2}
        collector = TypeMetricsCollector([r1], freqs)
        metrics = collector.compute()

        for t, m in metrics.items():
            assert len(m) == 19, f"Type {t} has {len(m)} metrics, expected 19"

    def test_empty_input(self):
        collector = TypeMetricsCollector([], {})
        metrics = collector.compute()
        assert metrics == {}

"""Tests for entity resolution via multi-signal matching."""
from __future__ import annotations

import pytest

from knowledge_graph_foundry.extraction.resolution import (
    resolve_entities,
    _cosine_similarity,
    _description_similarity,
)
from knowledge_graph_foundry.types.extraction import Entity


class TestResolution:
    def test_resolve_near_duplicates(self):
        """'RESmart CPAP' and 'RESmart CPAP Machine' above threshold are merged."""
        entities = [
            Entity(id="e1", name="RESmart CPAP", type="Product",
                   description="CPAP device", source_chunks=["c1"], confidence=0.9),
            Entity(id="e2", name="RESmart CPAP Machine", type="Product",
                   description="A CPAP machine by RESmart", source_chunks=["c2"],
                   confidence=0.85),
        ]
        # These names have high similarity
        result = resolve_entities(entities, threshold=0.75)
        assert len(result.entities) == 1
        assert "c1" in result.entities[0].source_chunks
        assert "c2" in result.entities[0].source_chunks

    def test_resolve_below_threshold(self):
        """'RESmart CPAP' and 'Sleep Apnea' are too different to merge."""
        entities = [
            Entity(id="e1", name="RESmart CPAP", type="Product",
                   source_chunks=["c1"], confidence=0.9),
            Entity(id="e2", name="Sleep Apnea", type="Product",
                   source_chunks=["c2"], confidence=0.85),
        ]
        result = resolve_entities(entities, threshold=0.85)
        assert len(result.entities) == 2

    def test_resolve_blocks_by_type_within_type(self):
        """Different names within same type stay separate."""
        entities = [
            Entity(id="e1", name="Mercury", type="Planet",
                   source_chunks=["c1"], confidence=0.9),
            Entity(id="e2", name="Venus", type="Planet",
                   source_chunks=["c2"], confidence=0.85),
        ]
        result = resolve_entities(entities, threshold=0.85)
        assert len(result.entities) == 2

    def test_resolve_transitive_chain(self):
        """A~B and B~C merges all three via union-find."""
        entities = [
            Entity(id="e1", name="BMC Medical", type="Organization",
                   source_chunks=["c1"], confidence=0.9),
            Entity(id="e2", name="BMC Medical Co", type="Organization",
                   source_chunks=["c2"], confidence=0.85),
            Entity(id="e3", name="BMC Medical Co Ltd", type="Organization",
                   source_chunks=["c3"], confidence=0.88),
        ]
        result = resolve_entities(entities, threshold=0.75)
        assert len(result.entities) == 1
        assert len(result.entities[0].source_chunks) == 3

    def test_resolve_canonical_longest_name(self):
        """Longest name in cluster becomes canonical."""
        entities = [
            Entity(id="e1", name="BMC Medical", type="Organization",
                   source_chunks=["c1"], confidence=0.9),
            Entity(id="e2", name="BMC Medical Co., Ltd.", type="Organization",
                   source_chunks=["c2"], confidence=0.85),
        ]
        # ratio("bmc medical", "bmc medical co., ltd.") ≈ 0.69
        result = resolve_entities(entities, threshold=0.6)
        assert len(result.entities) == 1
        assert result.entities[0].name == "BMC Medical Co., Ltd."

    def test_resolve_source_chunks_union(self):
        """All source_chunks collected from cluster members."""
        entities = [
            Entity(id="e1", name="CPAP Device", type="Product",
                   source_chunks=["c1", "c2"], confidence=0.9),
            Entity(id="e2", name="CPAP Machine", type="Product",
                   source_chunks=["c2", "c3"], confidence=0.85),
        ]
        # Both normalize to "cpap", ratio=1.0
        result = resolve_entities(entities, threshold=0.85)
        assert len(result.entities) == 1
        assert set(result.entities[0].source_chunks) == {"c1", "c2", "c3"}

    def test_resolve_empty_input(self):
        """Empty returns empty."""
        assert resolve_entities([]).entities == []

    def test_resolve_single_entity(self):
        """Single entity unchanged."""
        entity = Entity(id="e1", name="Test", type="Product",
                        source_chunks=["c1"], confidence=0.9)
        result = resolve_entities([entity])
        assert len(result.entities) == 1
        assert result.entities[0].name == "Test"

    def test_resolve_normalized_names_merge(self):
        """'humidifier' and 'humidifier system' merge because normalization strips 'system'."""
        entities = [
            Entity(id="e1", name="humidifier", type="Component",
                   source_chunks=["c1"], confidence=0.9),
            Entity(id="e2", name="humidifier system", type="Component",
                   source_chunks=["c2"], confidence=0.85),
        ]
        # After normalization both become "humidifier", ratio=1.0
        result = resolve_entities(entities, threshold=0.85)
        assert len(result.entities) == 1

    def test_resolve_with_embeddings(self):
        """Multi-signal matching: both name and embedding thresholds must pass."""
        # Same-ish embeddings, similar names
        emb_a = [1.0, 0.0, 0.0] * 10
        emb_b = [0.99, 0.1, 0.0] * 10
        entities = [
            Entity(id="e1", name="CPAP therapy", type="Feature",
                   source_chunks=["c1"], confidence=0.9, embedding=emb_a),
            Entity(id="e2", name="CPAP therapy device", type="Feature",
                   source_chunks=["c2"], confidence=0.85, embedding=emb_b),
        ]
        result = resolve_entities(
            entities, use_embeddings=True,
            name_threshold=0.5, embedding_threshold=0.8,
        )
        assert len(result.entities) == 1

    def test_resolve_with_embeddings_below_cosine(self):
        """Dissimilar embeddings prevent merge even if names match."""
        emb_a = [1.0, 0.0, 0.0] * 10
        emb_b = [0.0, 1.0, 0.0] * 10  # orthogonal
        entities = [
            Entity(id="e1", name="CPAP", type="Feature",
                   source_chunks=["c1"], confidence=0.9, embedding=emb_a),
            Entity(id="e2", name="CPAP mode", type="Feature",
                   source_chunks=["c2"], confidence=0.85, embedding=emb_b),
        ]
        result = resolve_entities(
            entities, use_embeddings=True,
            name_threshold=0.5, embedding_threshold=0.8,
        )
        assert len(result.entities) == 2


    def test_resolve_cross_type_merges(self):
        """Entities with same normalized name but different types are merged when descriptions overlap."""
        entities = [
            Entity(id="e1", name="ramp", type="Feature",
                   source_chunks=["c1"], confidence=0.9,
                   description="gradual pressure ramp for CPAP therapy"),
            Entity(id="e2", name="ramp", type="WorkMode",
                   source_chunks=["c2"], confidence=0.85,
                   description="ramp pressure mode for CPAP device"),
        ]
        result = resolve_entities(entities, threshold=0.85)
        assert len(result.entities) == 1
        # WorkMode has higher priority than Feature? No - Feature=6, WorkMode=5
        # So Feature wins
        assert result.entities[0].type == "Feature"
        assert set(result.entities[0].source_chunks) == {"c1", "c2"}

    def test_resolve_cross_type_keeps_specific(self):
        """Specification (priority 8) beats Component (priority 7)."""
        entities = [
            Entity(id="e1", name="power supply", type="Component",
                   source_chunks=["c1"], confidence=0.9,
                   description="power supply unit for electrical delivery"),
            Entity(id="e2", name="power supply", type="Specification",
                   source_chunks=["c2"], confidence=0.85,
                   description="power supply electrical specification"),
        ]
        result = resolve_entities(entities, threshold=0.85)
        assert len(result.entities) == 1
        assert result.entities[0].type == "Specification"


class TestDescriptionSimilarity:
    def test_basic_similarity(self):
        """Word overlap produces non-zero similarity."""
        assert _description_similarity("physical air filter component", "data smoothing algorithm") < 0.3

    def test_high_similarity(self):
        """Overlapping descriptions have high similarity."""
        sim = _description_similarity("gradual pressure ramp mode", "ramp pressure mode for CPAP")
        assert sim > 0.3

    def test_empty_descriptions(self):
        """Empty descriptions return 0.0."""
        assert _description_similarity("", "") == 0.0
        assert _description_similarity("hello world", "") == 0.0
        assert _description_similarity("", "hello world") == 0.0

    def test_identical_descriptions(self):
        """Identical descriptions return 1.0."""
        assert _description_similarity("pressure control system", "pressure control system") == 1.0


class TestCrossTypeBayesianMerge:
    def test_cross_type_blocks_divergent_descriptions(self):
        """'Filter' (Component) vs 'Filter' (Feature) with different descriptions stay separate.

        Prior=0.8, desc_sim~0.0 (no shared words), lr_desc=0.3, lr_cooc=0.9.
        posterior_odds = 4.0 * 0.3 * 0.9 = 1.08 -> posterior = 0.519 < 0.6.
        """
        entities = [
            Entity(id="e1", name="Filter", type="Component",
                   source_chunks=["c1"], confidence=0.9,
                   description="physical air filter for removing particulates"),
            Entity(id="e2", name="Filter", type="Feature",
                   source_chunks=["c2"], confidence=0.85,
                   description="data smoothing algorithm for signal processing"),
        ]
        result = resolve_entities(entities, threshold=0.85, cross_type_merge_threshold=0.6)
        assert len(result.entities) == 2

    def test_cross_type_merges_similar_descriptions(self):
        """'Ramp' with overlapping descriptions should merge.

        Prior=0.8, desc_sim>0.3 (shared: pressure, ramp, cpap), lr_desc>0.6.
        posterior_odds > 4.0 * 0.6 * 0.9 = 2.16 -> posterior > 0.68.
        """
        entities = [
            Entity(id="e1", name="Ramp", type="Feature",
                   source_chunks=["c1"], confidence=0.9,
                   description="gradual pressure ramp for CPAP therapy"),
            Entity(id="e2", name="Ramp", type="WorkMode",
                   source_chunks=["c2"], confidence=0.85,
                   description="ramp pressure mode for CPAP device"),
        ]
        result = resolve_entities(entities, threshold=0.85, cross_type_merge_threshold=0.6)
        assert len(result.entities) == 1

    def test_cross_type_empty_descriptions_no_merge(self):
        """Empty descriptions: prior=0.8, lr_desc=0.3, posterior=0.519 < 0.6."""
        entities = [
            Entity(id="e1", name="Filter", type="Component",
                   source_chunks=["c1"], confidence=0.9, description=""),
            Entity(id="e2", name="Filter", type="Feature",
                   source_chunks=["c2"], confidence=0.85, description=""),
        ]
        result = resolve_entities(entities, threshold=0.85, cross_type_merge_threshold=0.6)
        assert len(result.entities) == 2

    def test_cross_type_shared_chunks_boosts_merge(self):
        """Shared source chunks (co-occurrence) boost posterior above threshold.

        Prior=0.8, lr_desc=0.3, lr_cooc=1.5 (shared chunks).
        posterior_odds = 4.0 * 0.3 * 1.5 = 1.8 -> posterior = 0.643 >= 0.6.
        """
        entities = [
            Entity(id="e1", name="Filter", type="Component",
                   source_chunks=["c1", "c2"], confidence=0.9,
                   description="physical air filter"),
            Entity(id="e2", name="Filter", type="Feature",
                   source_chunks=["c2", "c3"], confidence=0.85,
                   description="data algorithm"),
        ]
        result = resolve_entities(entities, threshold=0.85, cross_type_merge_threshold=0.6)
        assert len(result.entities) == 1

    def test_cross_type_threshold_zero_always_merges(self):
        """cross_type_merge_threshold=0.0 reproduces old behavior (always merge)."""
        entities = [
            Entity(id="e1", name="Filter", type="Component",
                   source_chunks=["c1"], confidence=0.9,
                   description="physical air filter"),
            Entity(id="e2", name="Filter", type="Feature",
                   source_chunks=["c2"], confidence=0.85,
                   description="data algorithm"),
        ]
        result = resolve_entities(entities, threshold=0.85, cross_type_merge_threshold=0.0)
        assert len(result.entities) == 1


class TestCosine:
    def test_identical_vectors(self):
        assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_zero_vector(self):
        assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == pytest.approx(0.0)

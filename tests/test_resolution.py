"""Tests for entity resolution via multi-signal matching."""
from __future__ import annotations

import pytest

from kg_builder_cli.extraction.resolution import resolve_entities, _cosine_similarity
from kg_builder_cli.types.extraction import Entity


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
        resolved = resolve_entities(entities, threshold=0.75)
        assert len(resolved) == 1
        assert "c1" in resolved[0].source_chunks
        assert "c2" in resolved[0].source_chunks

    def test_resolve_below_threshold(self):
        """'RESmart CPAP' and 'Sleep Apnea' are too different to merge."""
        entities = [
            Entity(id="e1", name="RESmart CPAP", type="Product",
                   source_chunks=["c1"], confidence=0.9),
            Entity(id="e2", name="Sleep Apnea", type="Product",
                   source_chunks=["c2"], confidence=0.85),
        ]
        resolved = resolve_entities(entities, threshold=0.85)
        assert len(resolved) == 2

    def test_resolve_blocks_by_type_within_type(self):
        """Different names within same type stay separate."""
        entities = [
            Entity(id="e1", name="Mercury", type="Planet",
                   source_chunks=["c1"], confidence=0.9),
            Entity(id="e2", name="Venus", type="Planet",
                   source_chunks=["c2"], confidence=0.85),
        ]
        resolved = resolve_entities(entities, threshold=0.85)
        assert len(resolved) == 2

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
        resolved = resolve_entities(entities, threshold=0.75)
        assert len(resolved) == 1
        assert len(resolved[0].source_chunks) == 3

    def test_resolve_canonical_longest_name(self):
        """Longest name in cluster becomes canonical."""
        entities = [
            Entity(id="e1", name="BMC Medical", type="Organization",
                   source_chunks=["c1"], confidence=0.9),
            Entity(id="e2", name="BMC Medical Co., Ltd.", type="Organization",
                   source_chunks=["c2"], confidence=0.85),
        ]
        # ratio("bmc medical", "bmc medical co., ltd.") ≈ 0.69
        resolved = resolve_entities(entities, threshold=0.6)
        assert len(resolved) == 1
        assert resolved[0].name == "BMC Medical Co., Ltd."

    def test_resolve_source_chunks_union(self):
        """All source_chunks collected from cluster members."""
        entities = [
            Entity(id="e1", name="CPAP Device", type="Product",
                   source_chunks=["c1", "c2"], confidence=0.9),
            Entity(id="e2", name="CPAP Machine", type="Product",
                   source_chunks=["c2", "c3"], confidence=0.85),
        ]
        # Both normalize to "cpap", ratio=1.0
        resolved = resolve_entities(entities, threshold=0.85)
        assert len(resolved) == 1
        assert set(resolved[0].source_chunks) == {"c1", "c2", "c3"}

    def test_resolve_empty_input(self):
        """Empty returns empty."""
        assert resolve_entities([]) == []

    def test_resolve_single_entity(self):
        """Single entity unchanged."""
        entity = Entity(id="e1", name="Test", type="Product",
                        source_chunks=["c1"], confidence=0.9)
        resolved = resolve_entities([entity])
        assert len(resolved) == 1
        assert resolved[0].name == "Test"

    def test_resolve_normalized_names_merge(self):
        """'humidifier' and 'humidifier system' merge because normalization strips 'system'."""
        entities = [
            Entity(id="e1", name="humidifier", type="Component",
                   source_chunks=["c1"], confidence=0.9),
            Entity(id="e2", name="humidifier system", type="Component",
                   source_chunks=["c2"], confidence=0.85),
        ]
        # After normalization both become "humidifier", ratio=1.0
        resolved = resolve_entities(entities, threshold=0.85)
        assert len(resolved) == 1

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
        resolved = resolve_entities(
            entities, use_embeddings=True,
            name_threshold=0.5, embedding_threshold=0.8,
        )
        assert len(resolved) == 1

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
        resolved = resolve_entities(
            entities, use_embeddings=True,
            name_threshold=0.5, embedding_threshold=0.8,
        )
        assert len(resolved) == 2


    def test_resolve_cross_type_merges(self):
        """Entities with same normalized name but different types are merged."""
        entities = [
            Entity(id="e1", name="ramp", type="Feature",
                   source_chunks=["c1"], confidence=0.9,
                   description="Ramp feature for pressure adjustment"),
            Entity(id="e2", name="ramp", type="WorkMode",
                   source_chunks=["c2"], confidence=0.85,
                   description="Ramp mode"),
        ]
        resolved = resolve_entities(entities, threshold=0.85)
        assert len(resolved) == 1
        # WorkMode has higher priority than Feature? No - Feature=6, WorkMode=5
        # So Feature wins
        assert resolved[0].type == "Feature"
        assert set(resolved[0].source_chunks) == {"c1", "c2"}

    def test_resolve_cross_type_keeps_specific(self):
        """Specification (priority 8) beats Component (priority 7)."""
        entities = [
            Entity(id="e1", name="power supply", type="Component",
                   source_chunks=["c1"], confidence=0.9),
            Entity(id="e2", name="power supply", type="Specification",
                   source_chunks=["c2"], confidence=0.85),
        ]
        resolved = resolve_entities(entities, threshold=0.85)
        assert len(resolved) == 1
        assert resolved[0].type == "Specification"


class TestCosine:
    def test_identical_vectors(self):
        assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_zero_vector(self):
        assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == pytest.approx(0.0)

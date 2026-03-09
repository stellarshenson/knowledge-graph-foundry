"""Tests for entity resolution via fuzzy name matching."""
from __future__ import annotations

import pytest

from kg_builder_cli.extraction.resolution import resolve_entities
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

    def test_resolve_blocks_by_type(self):
        """Same name but different type are not merged."""
        entities = [
            Entity(id="e1", name="Mercury", type="Planet",
                   source_chunks=["c1"], confidence=0.9),
            Entity(id="e2", name="Mercury", type="Element",
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
            Entity(id="e2", name="CPAP Devices", type="Product",
                   source_chunks=["c2", "c3"], confidence=0.85),
        ]
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

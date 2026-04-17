"""Tests for entity and relationship deduplication."""
from __future__ import annotations

import pytest

from kgf.extraction.dedup import deduplicate
from kgf.types.extraction import Entity, Relationship


class TestEntityDedup:
    def test_dedup_no_duplicates(self, sample_entities):
        """Unique entities pass through unchanged."""
        deduped, _ = deduplicate(sample_entities, [])
        assert len(deduped) == len(sample_entities)

    def test_dedup_entity_merge(self):
        """Same (type, id) merges: longest desc, merged chunks, averaged confidence."""
        entities = [
            Entity(id="e1", name="A", type="Product", description="short",
                   source_chunks=["c1"], confidence=0.8),
            Entity(id="e1", name="A Longer", type="Product",
                   description="a longer description here",
                   source_chunks=["c2"], confidence=0.9),
        ]
        deduped, _ = deduplicate(entities, [])
        assert len(deduped) == 1
        merged = deduped[0]
        assert merged.description == "a longer description here"
        assert set(merged.source_chunks) == {"c1", "c2"}
        assert merged.confidence == pytest.approx(0.85)
        assert merged.name == "A Longer"

    def test_dedup_relationship_merge(self):
        """Same (source, target, type) relationships merged."""
        rels = [
            Relationship(source="a", target="b", type="REL", description="short",
                        source_chunks=["c1"], confidence=0.8),
            Relationship(source="a", target="b", type="REL",
                        description="a longer description",
                        source_chunks=["c2"], confidence=0.9),
        ]
        _, deduped = deduplicate([], rels)
        assert len(deduped) == 1
        assert deduped[0].description == "a longer description"

    def test_dedup_confidence_averaging(self):
        """Progressive averaging with 3 copies."""
        entities = [
            Entity(id="e1", name="A", type="T", confidence=1.0, source_chunks=["c1"]),
            Entity(id="e1", name="A", type="T", confidence=0.5, source_chunks=["c2"]),
            Entity(id="e1", name="A", type="T", confidence=0.8, source_chunks=["c3"]),
        ]
        deduped, _ = deduplicate(entities, [])
        assert len(deduped) == 1
        # Progressive: (1.0+0.5)/2 = 0.75, then (0.75+0.8)/2 = 0.775
        assert deduped[0].confidence == pytest.approx(0.775)

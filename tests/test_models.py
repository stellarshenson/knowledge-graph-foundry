"""Tests for core domain models - identity decoupled from type."""

from knowledge_graph_foundry.models import (
    Entity,
    chunk_id,
    entity_id,
    normalize_name,
)


class TestNormalizeName:
    def test_lowercase_and_whitespace(self):
        assert normalize_name("  AirSense   11 ") == "airsense 11"

    def test_idempotent(self):
        assert normalize_name(normalize_name("A  B")) == normalize_name("A  B")


class TestEntityIdentity:
    def test_id_independent_of_type(self):
        """Same name under different types is the SAME identity - v1's core failure."""
        a = Entity.create("Humidifier", types=["Component"])
        b = Entity.create("Humidifier", types=["Accessory"])
        assert a.id == b.id

    def test_id_case_insensitive(self):
        assert entity_id("DreamStation") == entity_id("dreamstation")

    def test_different_names_differ(self):
        assert entity_id("AirSense 10") != entity_id("AirSense 11")

    def test_multi_label(self):
        e = Entity.create("Humidifier", types=["Component", "Accessory"])
        assert set(e.types) == {"Component", "Accessory"}


class TestChunkId:
    def test_deterministic(self):
        assert chunk_id("doc1", 0, "text") == chunk_id("doc1", 0, "text")

    def test_varies_by_document_index_text(self):
        base = chunk_id("doc1", 0, "text")
        assert chunk_id("doc2", 0, "text") != base
        assert chunk_id("doc1", 1, "text") != base
        assert chunk_id("doc1", 0, "other") != base

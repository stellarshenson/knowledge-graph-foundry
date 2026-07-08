"""Tests for core domain models - identity decoupled from type."""

from knowledge_graph_foundry.models import (
    Entity,
    chunk_id,
    entity_id,
    glyph_clean_text,
    glyph_norm,
    glyph_nospace,
    normalize_name,
)


class TestGlyphNormalization:
    """R15-H190 glyph operator: recover trademark/unicode name variants."""

    def test_strips_trademark_glyphs(self):
        assert glyph_norm("SleepStyle™ Auto") == "sleepstyle auto"

    def test_nfkc_before_tm_expansion(self):
        # NFKC maps U+2122 to "TM"; the operator strips it FIRST so no "tm" leaks.
        assert "tm" not in glyph_norm("Brand™")

    def test_dash_family_folds_to_hyphen(self):
        assert glyph_norm("Ultra‑Fine") == glyph_norm("Ultra-Fine") == "ultra-fine"

    def test_nospace_variant(self):
        assert glyph_nospace("Air Filter™") == "airfilter"

    def test_clean_text_preserves_case_and_newlines(self):
        cleaned = glyph_clean_text("Row A™\n| x | y |\n")
        assert cleaned == "Row A\n| x | y |\n"

    def test_identity_of_glyph_variants(self):
        assert glyph_norm("DreamStation™") == glyph_norm("dreamstation")

    def test_distinct_names_stay_distinct(self):
        assert glyph_norm("AirSense 10") != glyph_norm("AirSense 11")


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

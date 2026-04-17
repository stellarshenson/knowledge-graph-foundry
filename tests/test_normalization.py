"""Tests for entity name normalization."""
from __future__ import annotations

from knowledge_graph_foundry.extraction.normalization import normalize_entity_name


class TestNormalization:
    def test_lowercase_and_strip(self):
        assert normalize_entity_name("  CPAP Device  ") == "cpap"

    def test_remove_generic_suffixes(self):
        assert normalize_entity_name("humidifier system") == "humidifier"
        assert normalize_entity_name("CPAP Device") == "cpap"
        assert normalize_entity_name("Pressure Unit") == "pressure"
        assert normalize_entity_name("cpap equipment") == "cpap"

    def test_remove_articles(self):
        assert normalize_entity_name("the humidifier") == "humidifier"
        assert normalize_entity_name("a CPAP machine") == "cpap"
        assert normalize_entity_name("an OSA condition") == "osa condition"

    def test_single_word_preserved(self):
        """Single word that is a suffix should not be removed."""
        assert normalize_entity_name("device") == "device"
        assert normalize_entity_name("system") == "system"

    def test_collapse_whitespace(self):
        assert normalize_entity_name("CPAP   Device") == "cpap"

    def test_empty_guard(self):
        """If all words removed, return lowered original."""
        assert normalize_entity_name("the") == "the"

    def test_multi_word_suffix_strip(self):
        assert normalize_entity_name("heated humidifier unit") == "heated humidifier"

    def test_no_suffix(self):
        assert normalize_entity_name("obstructive sleep apnea") == "obstructive sleep apnea"

    def test_complex_name(self):
        assert normalize_entity_name("DreamStation CPAP Machine") == "dreamstation cpap"

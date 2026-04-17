"""Tests for type normalization and canonical tracking."""
from __future__ import annotations

import pytest

from kgf.extraction.dedup import normalize_type_name
from kgf.ontology.buffer import OntologyBuffer
from kgf.types.config import OntologyBufferConfig
from kgf.types.ontology import TypeSignal


class TestNormalizeTypeName:
    """Tests for the normalize_type_name() utility."""

    def test_pascalcase_passthrough(self):
        assert normalize_type_name("WorkMode") == "WorkMode"

    def test_space_separated(self):
        assert normalize_type_name("Operating Mode") == "OperatingMode"

    def test_underscore_separated(self):
        assert normalize_type_name("operating_mode") == "OperatingMode"

    def test_hyphen_separated(self):
        assert normalize_type_name("OPERATING-MODE") == "OperatingMode"

    def test_mixed_separators(self):
        assert normalize_type_name("work_mode-test case") == "WorkModeTestCase"

    def test_all_caps(self):
        assert normalize_type_name("WORK_MODE") == "WorkMode"

    def test_whitespace_strip(self):
        assert normalize_type_name("  Work Mode  ") == "WorkMode"

    def test_single_word(self):
        assert normalize_type_name("product") == "Product"

    def test_empty_string(self):
        assert normalize_type_name("") == ""

    def test_surface_variants_collapse(self):
        """All surface variants of the same concept should normalize identically."""
        variants = ["Work Mode", "work_mode", "WORK_MODE", "work-mode", "WorkMode"]
        normalized = {normalize_type_name(v) for v in variants}
        assert len(normalized) == 1, f"Expected 1 canonical form, got {normalized}"


class TestCanonicalTracking:
    """Tests for OntologyBuffer canonical type tracking."""

    @pytest.fixture
    def buffer(self):
        config = OntologyBufferConfig(min_frequency_to_confirm=2)
        return OntologyBuffer(config)

    def test_first_seen_wins(self, buffer):
        buffer.accumulate([TypeSignal(type_name="Work Mode", frequency=1)])
        buffer.accumulate([TypeSignal(type_name="work_mode", frequency=1)])
        # First-seen raw form is "Work Mode"
        assert buffer.canonical_type("work_mode") == "Work Mode"
        assert buffer.canonical_type("WORK_MODE") == "Work Mode"

    def test_canonical_collapses_frequencies(self, buffer):
        buffer.accumulate([TypeSignal(type_name="Work Mode", frequency=3)])
        buffer.accumulate([TypeSignal(type_name="work_mode", frequency=2)])
        # Frequencies should be merged under canonical name
        freqs = buffer.frequencies()
        assert freqs.get("Work Mode", 0) == 5

    def test_unknown_type_returns_raw(self, buffer):
        assert buffer.canonical_type("Unknown") == "Unknown"

    def test_seed_types_registered(self, tmp_path):
        """Seed types loaded from YAML should be registered in canonical map."""
        import yaml

        seed_file = tmp_path / "ontology.yml"
        seed_file.write_text(yaml.dump({
            "entity_types": [
                {"name": "WorkMode", "description": "Work mode type"},
                {"name": "Product", "description": "Product type"},
            ],
            "relationship_types": [],
        }))

        config = OntologyBufferConfig(min_frequency_to_confirm=2)
        buffer = OntologyBuffer.from_yaml(seed_file, config)

        # "work_mode" should resolve to seeded "WorkMode"
        assert buffer.canonical_type("work_mode") == "WorkMode"

    def test_entity_types_not_duplicated(self, buffer):
        """Surface variants should not create duplicate entity type entries."""
        buffer.accumulate([TypeSignal(type_name="Safety Standard", frequency=2)])
        buffer.accumulate([TypeSignal(type_name="safety_standard", frequency=3)])
        buffer.accumulate([TypeSignal(type_name="SafetyStandard", frequency=1)])
        # All three are the same canonical type
        names = buffer.type_names()
        assert len(names) == 1


class TestPruneLowFrequency:
    """Tests for enforcement threshold pruning."""

    def test_prune_removes_rare_types(self):
        config = OntologyBufferConfig(min_frequency_to_confirm=1)
        buffer = OntologyBuffer(config)
        buffer.accumulate([
            TypeSignal(type_name="Product", frequency=100),
            TypeSignal(type_name="RareType", frequency=1),
        ])
        # 1/101 = 0.99%, threshold at 2% means RareType is pruned
        pruned = buffer.prune_low_frequency_types(2.0)
        assert "RareType" in pruned
        assert "Product" not in pruned

    def test_seed_types_not_pruned(self, tmp_path):
        import yaml

        seed_file = tmp_path / "ontology.yml"
        seed_file.write_text(yaml.dump({
            "entity_types": [{"name": "SeedType", "description": ""}],
            "relationship_types": [],
        }))

        config = OntologyBufferConfig(min_frequency_to_confirm=2)
        buffer = OntologyBuffer.from_yaml(seed_file, config)
        # SeedType has freq=2 from pre-confirm, add a dominant type
        buffer.accumulate([TypeSignal(type_name="Dominant", frequency=1000)])

        pruned = buffer.prune_low_frequency_types(1.0)
        assert "SeedType" not in pruned

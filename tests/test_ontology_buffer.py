"""Tests for the ontology buffer."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kgf.ontology.buffer import OntologyBuffer
from kgf.types.config import OntologyBufferConfig
from kgf.types.extraction import Entity, Relationship
from kgf.types.ontology import TypeSignal


@pytest.fixture
def buffer_config():
    return OntologyBufferConfig(min_frequency_to_confirm=2)


@pytest.fixture
def empty_buffer(buffer_config):
    return OntologyBuffer(buffer_config)


class TestOntologyBuffer:
    def test_buffer_empty_init(self, empty_buffer):
        """Empty buffer has zero types and 0.0 coverage."""
        snapshot = empty_buffer.snapshot()
        assert len(snapshot.entity_types) == 0
        assert empty_buffer.coverage() == 0.0

    def test_buffer_from_yaml(self, tmp_path, buffer_config):
        """Load sample ontology YAML, verify types."""
        ontology_file = tmp_path / "ontology.yml"
        ontology_file.write_text(yaml.dump({
            "entity_types": [
                {"name": "Product", "description": "A product"},
                {"name": "Feature", "description": "A feature"},
            ],
            "relationship_types": [
                {"name": "HAS_FEATURE", "source_type": "Product",
                 "target_type": "Feature", "description": "Product has feature"},
            ],
        }))
        buffer = OntologyBuffer.from_yaml(ontology_file, buffer_config)
        snapshot = buffer.snapshot()
        assert len(snapshot.entity_types) == 2
        assert len(snapshot.relationship_types) == 1
        # Seed types are pre-confirmed
        assert "Product" in snapshot.confirmed_types
        assert "Feature" in snapshot.confirmed_types

    def test_buffer_snapshot_frozen(self, empty_buffer):
        """Snapshot returns frozen OntologyState."""
        snapshot = empty_buffer.snapshot()
        assert snapshot.model_config.get("frozen") is True

    def test_buffer_accumulate_new_type(self, empty_buffer):
        """New type added as candidate (below confirmation threshold).

        With emerge threshold=1, frequency 1 types appear as emerging in
        snapshot entity_types but remain in candidate_types (not confirmed).
        """
        empty_buffer.accumulate([TypeSignal(type_name="NewType", frequency=1)])
        snapshot = empty_buffer.snapshot()
        assert "NewType" in snapshot.candidate_types
        assert "NewType" not in snapshot.confirmed_types
        # Emerge tier: included in entity_types as emerging suggestion
        assert "NewType" in {t.name for t in snapshot.entity_types}
        assert "NewType" in snapshot.emerging_types

    def test_buffer_accumulate_frequency(self, empty_buffer):
        """Type becomes confirmed at threshold."""
        empty_buffer.accumulate([TypeSignal(type_name="Product", frequency=1)])
        assert "Product" in empty_buffer.snapshot().candidate_types
        empty_buffer.accumulate([TypeSignal(type_name="Product", frequency=1)])
        assert "Product" in empty_buffer.snapshot().confirmed_types

    def test_buffer_coverage_calculation(self, empty_buffer):
        """2 confirmed / 4 total = 0.5."""
        # Add 4 types, confirm 2
        for name in ["A", "B", "C", "D"]:
            empty_buffer.accumulate([TypeSignal(type_name=name, frequency=1)])
        # Confirm A and B by adding more frequency
        empty_buffer.accumulate([TypeSignal(type_name="A", frequency=1)])
        empty_buffer.accumulate([TypeSignal(type_name="B", frequency=1)])
        assert empty_buffer.coverage() == pytest.approx(0.5)

    def test_buffer_flush_writes_yaml(self, empty_buffer, tmp_path):
        """Flush writes YAML, read back, verify."""
        empty_buffer.accumulate([TypeSignal(type_name="Product", frequency=2)])
        output_path = tmp_path / "ontology_out.yml"
        empty_buffer.flush(output_path)
        assert output_path.exists()
        data = yaml.safe_load(output_path.read_text())
        assert len(data["entity_types"]) == 1
        assert data["entity_types"][0]["name"] == "Product"

    def test_buffer_flush_only_confirmed(self, empty_buffer, tmp_path):
        """Candidates excluded from flush."""
        empty_buffer.accumulate([TypeSignal(type_name="Confirmed", frequency=2)])
        empty_buffer.accumulate([TypeSignal(type_name="Candidate", frequency=1)])
        output_path = tmp_path / "ontology_out.yml"
        empty_buffer.flush(output_path)
        data = yaml.safe_load(output_path.read_text())
        type_names = [t["name"] for t in data["entity_types"]]
        assert "Confirmed" in type_names
        assert "Candidate" not in type_names

    def test_buffer_accumulate_from_result(self, empty_buffer):
        """Entity/Relationship lists produce correct signals.

        Product has frequency 2 (confirmed), Feature has frequency 1 (emerging).
        With emerge threshold=1, all discovered types appear in snapshot
        entity_types. Relationship types with freq>=1 appear in snapshot too.
        """
        entities = [
            Entity(id="e1", name="A", type="Product", source_chunks=["c1"]),
            Entity(id="e2", name="B", type="Product", source_chunks=["c2"]),
            Entity(id="e3", name="C", type="Feature", source_chunks=["c3"]),
        ]
        relationships = [
            Relationship(source="e1", target="e3", type="HAS_FEATURE",
                        source_chunks=["c1"]),
        ]
        empty_buffer.accumulate_from_result(entities, relationships)
        snapshot = empty_buffer.snapshot()
        type_names = {t.name for t in snapshot.entity_types}
        # Product: freq=2, confirmed, included
        assert "Product" in type_names
        # Feature: freq=1, emerging tier, included in entity_types
        assert "Feature" in type_names
        assert "Feature" in snapshot.emerging_types
        assert "Feature" in snapshot.candidate_types
        # Frequencies tracked
        assert snapshot.type_frequencies["Product"] == 2
        assert snapshot.type_frequencies["Feature"] == 1

    def test_buffer_emerging_type(self, empty_buffer):
        """Type with frequency 2+ but below threshold appears as emerging."""
        config = OntologyBufferConfig(min_frequency_to_confirm=3)
        buffer = OntologyBuffer(config)
        buffer.accumulate([TypeSignal(type_name="Emerging", frequency=2)])
        snapshot = buffer.snapshot()
        assert "Emerging" in snapshot.emerging_types
        assert "Emerging" not in snapshot.confirmed_types
        # Emerging types are included in entity_types (shown in prompt)
        assert "Emerging" in {t.name for t in snapshot.entity_types}

    def test_buffer_seed_vs_discovered(self, tmp_path, buffer_config):
        """Seed types are distinct from generatively discovered types."""
        ontology_file = tmp_path / "ontology.yml"
        ontology_file.write_text(yaml.dump({
            "entity_types": [
                {"name": "Product", "description": "A product"},
            ],
            "relationship_types": [
                {"name": "HAS_FEATURE", "source_type": "Product",
                 "target_type": "Feature", "description": "Product has feature"},
            ],
        }))
        buffer = OntologyBuffer.from_yaml(ontology_file, buffer_config)
        # Discover a new type generatively
        buffer.accumulate([TypeSignal(type_name="NewType", frequency=2)])
        snapshot = buffer.snapshot()
        # Both in entity_types (Product confirmed, NewType confirmed)
        type_names = {t.name for t in snapshot.entity_types}
        assert "Product" in type_names
        assert "NewType" in type_names
        # Both confirmed but seed has description
        product_td = next(t for t in snapshot.entity_types if t.name == "Product")
        newtype_td = next(t for t in snapshot.entity_types if t.name == "NewType")
        assert product_td.description == "A product"
        assert newtype_td.description == ""

    def test_compute_hash_deterministic(self, empty_buffer):
        """Hash is deterministic and changes when confirmed types change."""
        empty_buffer.accumulate([TypeSignal(type_name="Alpha", frequency=2)])
        empty_buffer.accumulate([TypeSignal(type_name="Beta", frequency=2)])
        hash1 = empty_buffer.compute_hash()
        hash2 = empty_buffer.compute_hash()
        assert hash1 == hash2
        assert len(hash1) == 16  # 16 hex chars

        # Adding a new confirmed type changes the hash
        empty_buffer.accumulate([TypeSignal(type_name="Gamma", frequency=2)])
        hash3 = empty_buffer.compute_hash()
        assert hash3 != hash1

    def test_compute_hash_ignores_unconfirmed(self, empty_buffer):
        """Unconfirmed types (freq < threshold) do not affect hash."""
        empty_buffer.accumulate([TypeSignal(type_name="Confirmed", frequency=2)])
        hash1 = empty_buffer.compute_hash()

        empty_buffer.accumulate([TypeSignal(type_name="Candidate", frequency=1)])
        hash2 = empty_buffer.compute_hash()
        assert hash1 == hash2

    def test_compute_hash_order_independent(self, buffer_config):
        """Hash is the same regardless of accumulation order."""
        buf_a = OntologyBuffer(buffer_config)
        buf_a.accumulate([TypeSignal(type_name="Zebra", frequency=2)])
        buf_a.accumulate([TypeSignal(type_name="Apple", frequency=2)])

        buf_b = OntologyBuffer(buffer_config)
        buf_b.accumulate([TypeSignal(type_name="Apple", frequency=2)])
        buf_b.accumulate([TypeSignal(type_name="Zebra", frequency=2)])

        assert buf_a.compute_hash() == buf_b.compute_hash()

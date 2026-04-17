"""Tests for fluid accumulator."""
import pytest

from kgf.curing.accumulator import FluidAccumulator
from kgf.types.config import ExtractConfig
from kgf.types.document import Chunk
from kgf.types.extraction import (
    Entity,
    ExtractionResult,
    Relationship,
)
from kgf.types.ontology import OntologyState, TypeDef


def _make_entity(id: str, name: str, type: str = "Device") -> Entity:
    return Entity(id=id, name=name, type=type)


def _make_relationship(source: str, target: str, type: str = "RELATES_TO") -> Relationship:
    return Relationship(source=source, target=target, type=type)


def _make_chunk(id: str, text: str = "test") -> Chunk:
    return Chunk(id=id, text=text, source="test.pdf", index=0, token_count=10)


def _make_result(entities=None, relationships=None, chunks=None) -> ExtractionResult:
    return ExtractionResult(
        entities=entities or [],
        relationships=relationships or [],
        chunks=chunks or [],
    )


def test_add_result_accumulates():
    """Entities from multiple results should be accessible."""
    acc = FluidAccumulator()
    r1 = _make_result(entities=[_make_entity("e1", "Device A")])
    r2 = _make_result(entities=[_make_entity("e2", "Device B")])
    acc.add_result(r1)
    acc.add_result(r2)
    assert len(acc.all_entities()) == 2
    assert acc.doc_count == 2


def test_all_relationships():
    """Relationships from multiple results should be flattened."""
    acc = FluidAccumulator()
    acc.add_result(_make_result(relationships=[_make_relationship("a", "b")]))
    acc.add_result(_make_result(relationships=[_make_relationship("c", "d")]))
    assert len(acc.all_relationships()) == 2


def test_all_chunks():
    """Chunks from multiple results should be flattened."""
    acc = FluidAccumulator()
    acc.add_result(_make_result(chunks=[_make_chunk("c1")]))
    acc.add_result(_make_result(chunks=[_make_chunk("c2"), _make_chunk("c3")]))
    assert len(acc.all_chunks()) == 3


def test_consolidate_enforces_types():
    """Type enforcement should remap entities to cured ontology types."""
    acc = FluidAccumulator()
    acc.add_result(_make_result(
        entities=[
            _make_entity("e1", "CPAP Device", "CPAPDevice"),
            _make_entity("e2", "ResMed", "Manufacturer"),
        ]
    ))

    ontology = OntologyState(
        entity_types=(TypeDef(name="Device"), TypeDef(name="Manufacturer")),
        relationship_types=(),
        coverage=0.8,
    )
    config = ExtractConfig()
    result = acc.consolidate(ontology, config)

    # CPAPDevice should be remapped to closest: Device
    types = {e.type for e in result.entities}
    assert "Device" in types
    assert "Manufacturer" in types
    assert "CPAPDevice" not in types


def test_consolidate_merges_entities():
    """Dedup and resolution should be applied across corpus."""
    acc = FluidAccumulator()
    # Same entity in two documents
    acc.add_result(_make_result(
        entities=[_make_entity("device_cpap_device", "CPAP Device", "Device")]
    ))
    acc.add_result(_make_result(
        entities=[_make_entity("device_cpap_device", "CPAP Device", "Device")]
    ))

    ontology = OntologyState(
        entity_types=(TypeDef(name="Device"),),
        relationship_types=(),
        coverage=1.0,
    )
    config = ExtractConfig()
    result = acc.consolidate(ontology, config)
    # Dedup should merge identical entities
    assert len(result.entities) == 1


def test_empty_accumulator():
    """Empty accumulator should handle gracefully."""
    acc = FluidAccumulator()
    assert acc.all_entities() == []
    assert acc.all_relationships() == []
    assert acc.all_chunks() == []
    assert acc.doc_count == 0

    ontology = OntologyState(
        entity_types=(),
        relationship_types=(),
        coverage=0.0,
    )
    config = ExtractConfig()
    result = acc.consolidate(ontology, config)
    assert len(result.entities) == 0
    assert len(result.relationships) == 0

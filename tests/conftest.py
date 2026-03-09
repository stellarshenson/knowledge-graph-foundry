"""Shared test fixtures for kg-builder-cli."""
from __future__ import annotations

import pytest

from kg_builder_cli.types.config import (
    AppConfig, Neo4jConfig, LLMConfig, ExtractConfig, OntologyBufferConfig, LoadConfig
)
from kg_builder_cli.types.document import TextSegment, Chunk, ChunkMetadata
from kg_builder_cli.types.extraction import Entity, Relationship
from kg_builder_cli.types.ontology import OntologyState, TypeDef, RelationshipDef


@pytest.fixture
def sample_config() -> AppConfig:
    """Test config with small chunk size."""
    return AppConfig(
        neo4j=Neo4jConfig(uri="bolt://localhost:7687", user="neo4j", password="test"),
        llm=LLMConfig(model="bedrock/test-model", temperature=0.0),
        extract=ExtractConfig(chunk_size=500, chunk_overlap=50, concurrency=1),
        ontology_buffer=OntologyBufferConfig(intent="CPAP device specifications"),
        load=LoadConfig(batch_size=100, create_indexes=False, validate_graph=False),
    )


@pytest.fixture
def sample_segments() -> list[TextSegment]:
    """Three CPAP domain text segments."""
    return [
        TextSegment(
            text="The RESmart CPAP machine operates at pressure ranges of 4-20 cmH2O. "
                 "It features an integrated humidifier and advanced EPR technology. "
                 "The device weighs 3.5 lbs without the humidifier attachment.",
            page=1,
            source_path="cpap_manual.pdf",
        ),
        TextSegment(
            text="BMC Medical manufactures the RESmart Auto CPAP series. "
                 "The Auto-CPAP model automatically adjusts pressure based on detected events. "
                 "It includes a heated tube option and SmartFlex pressure relief.",
            page=2,
            source_path="cpap_manual.pdf",
        ),
        TextSegment(
            text="Operating temperature range is 41-95 degrees F (5-35 C). "
                 "Sound level is less than 30 dB at 10 cmH2O. "
                 "Power supply accepts 100-240V AC, 50/60Hz.",
            page=3,
            source_path="cpap_manual.pdf",
        ),
    ]


@pytest.fixture
def sample_chunks() -> list[Chunk]:
    """Four chunks with deterministic IDs."""
    return [
        Chunk(id="a1b2c3d4e5f6", text="RESmart CPAP operates at 4-20 cmH2O.", index=0,
              metadata=ChunkMetadata(document_source="cpap.pdf", page=1), token_count=12),
        Chunk(id="b2c3d4e5f6a1", text="BMC Medical manufactures the RESmart.", index=1,
              metadata=ChunkMetadata(document_source="cpap.pdf", page=1), token_count=10),
        Chunk(id="c3d4e5f6a1b2", text="Auto-CPAP adjusts pressure automatically.", index=2,
              metadata=ChunkMetadata(document_source="cpap.pdf", page=2), token_count=8),
        Chunk(id="d4e5f6a1b2c3", text="Sound level less than 30 dB.", index=3,
              metadata=ChunkMetadata(document_source="cpap.pdf", page=3), token_count=9),
    ]


@pytest.fixture
def sample_entities() -> list[Entity]:
    """Six entities across Person/Organization/Product types."""
    return [
        Entity(id="product_resmart_cpap", name="RESmart CPAP", type="Product",
               description="CPAP device by BMC Medical", source_chunks=["a1b2c3d4e5f6"],
               confidence=0.95),
        Entity(id="org_bmc_medical", name="BMC Medical", type="Organization",
               description="Medical device manufacturer", source_chunks=["b2c3d4e5f6a1"],
               confidence=0.9),
        Entity(id="spec_pressure_range", name="Pressure Range", type="Specification",
               description="4-20 cmH2O", properties={"min": 4, "max": 20, "unit": "cmH2O"},
               source_chunks=["a1b2c3d4e5f6"], confidence=0.92),
        Entity(id="feature_epr", name="EPR Technology", type="Feature",
               description="Expiratory Pressure Relief", source_chunks=["a1b2c3d4e5f6"],
               confidence=0.88),
        Entity(id="product_auto_cpap", name="RESmart Auto CPAP", type="Product",
               description="Auto-titrating CPAP", source_chunks=["c3d4e5f6a1b2"],
               confidence=0.93),
        Entity(id="feature_smartflex", name="SmartFlex", type="Feature",
               description="Pressure relief technology", source_chunks=["c3d4e5f6a1b2"],
               confidence=0.85),
    ]


@pytest.fixture
def sample_relationships() -> list[Relationship]:
    """Four relationships."""
    return [
        Relationship(source="org_bmc_medical", target="product_resmart_cpap",
                     type="MANUFACTURES", description="BMC makes RESmart",
                     source_chunks=["b2c3d4e5f6a1"], confidence=0.9),
        Relationship(source="product_resmart_cpap", target="spec_pressure_range",
                     type="HAS_SPECIFICATION", description="Pressure range spec",
                     source_chunks=["a1b2c3d4e5f6"], confidence=0.88),
        Relationship(source="product_resmart_cpap", target="feature_epr",
                     type="HAS_FEATURE", description="EPR feature",
                     source_chunks=["a1b2c3d4e5f6"], confidence=0.85),
        Relationship(source="org_bmc_medical", target="product_auto_cpap",
                     type="MANUFACTURES", description="BMC makes Auto CPAP",
                     source_chunks=["c3d4e5f6a1b2"], confidence=0.9),
    ]


@pytest.fixture
def sample_ontology() -> OntologyState:
    """Ontology with 3 entity types and 2 relationship defs."""
    return OntologyState(
        entity_types=(
            TypeDef(name="Product", description="Medical device or product"),
            TypeDef(name="Specification", description="Technical specification"),
            TypeDef(name="Feature", description="Product feature or capability"),
        ),
        relationship_types=(
            RelationshipDef(name="HAS_SPECIFICATION", source_type="Product",
                          target_type="Specification", description="Product has spec"),
            RelationshipDef(name="HAS_FEATURE", source_type="Product",
                          target_type="Feature", description="Product has feature"),
        ),
        confirmed_types=frozenset({"Product", "Specification", "Feature"}),
    )


@pytest.fixture
def near_duplicate_entities() -> list[Entity]:
    """Near-duplicate entity pairs for resolution testing."""
    return [
        Entity(id="product_resmart_cpap", name="RESmart CPAP", type="Product",
               description="CPAP device", source_chunks=["chunk1"], confidence=0.9),
        Entity(id="product_resmart_auto_cpap", name="RESmart Auto CPAP", type="Product",
               description="Auto-titrating CPAP device by BMC",
               source_chunks=["chunk2"], confidence=0.85),
        Entity(id="org_3b_products", name="3B Products", type="Organization",
               description="Medical products company", source_chunks=["chunk3"],
               confidence=0.88),
        Entity(id="org_3b_medical", name="3B Medical", type="Organization",
               description="Medical device manufacturer",
               source_chunks=["chunk4"], confidence=0.92),
    ]

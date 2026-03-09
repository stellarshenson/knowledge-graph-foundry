"""Tests for graph quality improvements - embeddings, indexes, PropertyDef."""

from __future__ import annotations

import pytest

from kg_builder_cli.types.extraction import Entity, ExtractionResult
from kg_builder_cli.types.ontology import PropertyDef, TypeDef


class TestGraphQuality:
    def test_entity_embedding_field(self):
        """Entity accepts list[float] embedding."""
        entity = Entity(
            id="e1",
            name="Test",
            type="Product",
            embedding=[0.1, 0.2, 0.3, 0.4],
        )
        assert entity.embedding == [0.1, 0.2, 0.3, 0.4]

    def test_entity_embedding_none_default(self):
        """Entity embedding defaults to None."""
        entity = Entity(id="e1", name="Test", type="Product")
        assert entity.embedding is None

    def test_property_def_validation(self):
        """PropertyDef with allowed_values and min/max."""
        prop = PropertyDef(
            name="pressure",
            type="number",
            description="Operating pressure",
            min_value=4.0,
            max_value=20.0,
            allowed_values=[],
        )
        assert prop.min_value == 4.0
        assert prop.max_value == 20.0

    def test_property_def_with_pattern(self):
        """PropertyDef with regex pattern."""
        prop = PropertyDef(
            name="serial_number",
            type="string",
            pattern=r"^[A-Z]{2}\d{6}$",
        )
        assert prop.pattern == r"^[A-Z]{2}\d{6}$"

    def test_typedef_with_aliases(self):
        """TypeDef with aliases list."""
        typedef = TypeDef(
            name="Organization",
            description="Company or manufacturer",
            aliases=["Company", "Manufacturer", "Corp"],
        )
        assert len(typedef.aliases) == 3
        assert "Company" in typedef.aliases

    def test_typedef_with_property_defs(self):
        """TypeDef with property_defs."""
        typedef = TypeDef(
            name="Specification",
            property_defs=[
                PropertyDef(name="value", type="string"),
                PropertyDef(name="unit", type="string", required=True),
            ],
        )
        assert len(typedef.property_defs) == 2
        assert typedef.property_defs[1].required is True

    def test_extraction_result_has_chunks(self):
        """ExtractionResult has chunks field."""
        from kg_builder_cli.types.document import Chunk, ChunkMetadata

        result = ExtractionResult(
            chunks=[
                Chunk(
                    id="c1",
                    text="test",
                    index=0,
                    metadata=ChunkMetadata(),
                    token_count=5,
                ),
            ],
        )
        assert len(result.chunks) == 1
        assert result.chunks[0].text == "test"

    def test_index_definitions_count(self):
        """4 indexes defined (id, name, vector, fulltext)."""
        from kg_builder_cli.loading.indexes import _INDEXES

        assert len(_INDEXES) == 4
        names = [name for name, _ in _INDEXES]
        assert "entity_id_idx" in names
        assert "entity_name_idx" in names
        assert "entity_embeddings" in names
        assert "entity_names" in names

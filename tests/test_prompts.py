"""Tests for extraction prompt construction."""
from __future__ import annotations

from kg_builder_cli.extraction.prompts import build_extraction_prompt
from kg_builder_cli.types.document import Chunk, ChunkMetadata
from kg_builder_cli.types.ontology import OntologyState, RelationshipDef, TypeDef


def _make_chunk(text: str = "Test text.") -> Chunk:
    return Chunk(id="test123", text=text, index=0,
                metadata=ChunkMetadata(), token_count=5)


class TestPrompts:
    def test_free_prompt_no_ontology(self):
        """Free prompt with text substituted when no ontology."""
        chunk = _make_chunk("Sample text here.")
        prompt = build_extraction_prompt(chunk)
        assert "Sample text here." in prompt
        assert "Allowed entity types" not in prompt

    def test_constrained_prompt_with_types(self):
        """Constrained prompt lists entity types (fallback flat format)."""
        chunk = _make_chunk()
        ontology = OntologyState(
            entity_types=(
                TypeDef(name="Product"),
                TypeDef(name="Feature"),
            ),
        )
        prompt = build_extraction_prompt(chunk, ontology)
        assert "Product" in prompt
        assert "Feature" in prompt
        assert "Allowed entity types" in prompt

    def test_intent_prefix_prepended(self):
        """Intent prefix appears before main prompt."""
        chunk = _make_chunk()
        prompt = build_extraction_prompt(chunk, intent="CPAP medical devices")
        assert prompt.startswith("**Use case context**: CPAP medical devices")

    def test_intent_plus_constrained(self):
        """Both intent and ontology work together."""
        chunk = _make_chunk()
        ontology = OntologyState(
            entity_types=(TypeDef(name="Product"),),
        )
        prompt = build_extraction_prompt(chunk, ontology, intent="Medical devices")
        assert "Medical devices" in prompt
        assert "Product" in prompt
        assert "Allowed entity types" in prompt

    def test_enriched_prompt_with_descriptions(self):
        """Confirmed types show descriptions and frequencies."""
        chunk = _make_chunk()
        ontology = OntologyState(
            entity_types=(
                TypeDef(name="Product", description="A physical device"),
                TypeDef(name="Feature", description="A device capability"),
            ),
            confirmed_types=frozenset({"Product", "Feature"}),
            type_frequencies={"Product": 10, "Feature": 5},
        )
        prompt = build_extraction_prompt(chunk, ontology)
        assert "Established entity types" in prompt
        assert "A physical device" in prompt
        assert "seen 10x" in prompt
        assert "A device capability" in prompt

    def test_enriched_prompt_seed_vs_discovered(self):
        """Established and discovered types shown in separate blocks."""
        chunk = _make_chunk()
        ontology = OntologyState(
            entity_types=(
                TypeDef(name="Product", description="A product"),
                TypeDef(name="ErrorCode"),
            ),
            confirmed_types=frozenset({"Product"}),
            emerging_types=frozenset({"ErrorCode"}),
            type_frequencies={"Product": 20, "ErrorCode": 3},
        )
        prompt = build_extraction_prompt(chunk, ontology)
        assert "Established entity types" in prompt
        assert "Discovered entity types" in prompt
        assert "strongly prefer" in prompt
        assert "ErrorCode" in prompt
        assert "seen 3x" in prompt

    def test_enriched_prompt_relationship_types(self):
        """Relationship types with source/target constraints in prompt."""
        chunk = _make_chunk()
        ontology = OntologyState(
            entity_types=(TypeDef(name="Product"),),
            relationship_types=(
                RelationshipDef(
                    name="HAS_FEATURE",
                    source_type="Product",
                    target_type="Feature",
                    description="Product has feature",
                ),
            ),
            confirmed_types=frozenset({"Product"}),
            type_frequencies={"Product": 5},
        )
        prompt = build_extraction_prompt(chunk, ontology)
        assert "Allowed relationship types" in prompt
        assert "HAS_FEATURE" in prompt
        assert "Product -> Feature" in prompt
        assert "Product has feature" in prompt

"""Tests for extraction prompt construction."""
from __future__ import annotations

from kg_builder_cli.extraction.prompts import build_extraction_prompt
from kg_builder_cli.types.document import Chunk, ChunkMetadata
from kg_builder_cli.types.ontology import OntologyState, TypeDef


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
        """Constrained prompt lists entity types."""
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

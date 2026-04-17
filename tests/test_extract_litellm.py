"""Tests for litellm + instructor based extraction."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from kgf.extraction.extract import extract_chunk
from kgf.extraction.response_models import (
    EntityResponse,
    ExtractionResponse,
    RelationshipResponse,
    build_response_model,
)
from kgf.types.document import Chunk, ChunkMetadata
from kgf.types.ontology import OntologyState, TypeDef


@pytest.fixture
def test_chunk():
    return Chunk(id="test123", text="BMC Medical makes CPAP devices.", index=0,
                 metadata=ChunkMetadata(), token_count=8)


class TestResponseModels:
    def test_extraction_response_validation(self):
        """Rejects confidence > 1.0."""
        with pytest.raises(ValidationError):
            EntityResponse(id="e1", name="Test", type="Product", confidence=1.5)

    def test_extraction_response_valid(self):
        """Valid response accepted."""
        resp = ExtractionResponse(
            entities=[EntityResponse(id="e1", name="Test", type="Product", confidence=0.9)],
            relationships=[],
        )
        assert len(resp.entities) == 1
        assert resp.entities[0].confidence == 0.9

    def test_build_response_model_no_ontology(self):
        """No ontology returns static ExtractionResponse."""
        model = build_response_model(None)
        assert model is ExtractionResponse

    def test_build_response_model_with_ontology(self):
        """Ontology with types returns constrained model."""
        ontology = OntologyState(
            entity_types=(TypeDef(name="Product"), TypeDef(name="Feature")),
        )
        model = build_response_model(ontology)
        assert model is not ExtractionResponse
        schema = model.model_json_schema()
        assert "allowed_entity_types" in str(schema)


class TestExtractChunk:
    def test_extract_chunk_structured_response(self, test_chunk):
        """Mock litellm.completion, verify Entity/Relationship objects."""
        mock_response = ExtractionResponse(
            entities=[EntityResponse(id="e1", name="BMC", type="Organization", confidence=0.9)],
            relationships=[],
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        entities, rels = extract_chunk(
            test_chunk, "Extract entities.", "bedrock/test-model",
            mock_client, response_model=ExtractionResponse,
        )
        assert len(entities) == 1
        assert entities[0].name == "BMC"
        assert entities[0].type == "Organization"

    def test_extract_chunk_empty_response(self, test_chunk):
        """Empty extraction returns empty lists."""
        mock_response = ExtractionResponse(entities=[], relationships=[])
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        entities, rels = extract_chunk(
            test_chunk, "Extract.", "bedrock/test", mock_client,
            response_model=ExtractionResponse,
        )
        assert entities == []
        assert rels == []

    def test_extract_chunk_exception_returns_empty(self, test_chunk):
        """Exception during extraction returns empty lists."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")

        entities, rels = extract_chunk(
            test_chunk, "Extract.", "bedrock/test", mock_client,
            response_model=ExtractionResponse,
        )
        assert entities == []
        assert rels == []

    def test_litellm_model_string_bedrock(self):
        """Bedrock model string format."""
        from kgf.extraction.unstructured import _litellm_model_id
        from kgf.types.config import LLMConfig

        config = LLMConfig(provider="bedrock", model="eu.anthropic.claude-sonnet-4-20250514-v1:0")
        assert _litellm_model_id(config) == "bedrock/eu.anthropic.claude-sonnet-4-20250514-v1:0"

    def test_litellm_model_string_openai(self):
        """OpenAI model string is plain."""
        from kgf.extraction.unstructured import _litellm_model_id
        from kgf.types.config import LLMConfig

        config = LLMConfig(provider="openai", model="gpt-4o")
        assert _litellm_model_id(config) == "gpt-4o"

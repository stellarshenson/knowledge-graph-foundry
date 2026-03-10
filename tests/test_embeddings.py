"""Tests for embedding generation with mocked boto3."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from kg_builder_cli.extraction.embeddings import generate_embeddings
from kg_builder_cli.types.extraction import Entity


class TestEmbeddings:
    def _mock_entity(self, name: str = "Test", entity_type: str = "Product") -> Entity:
        return Entity(id="e1", name=name, type=entity_type, description="A test entity")

    @patch("kg_builder_cli.extraction.embeddings.boto3")
    def test_generate_embeddings_populates_field(self, mock_boto3):
        """Embedding vectors are populated on entities."""
        fake_embedding = [0.1] * 1024
        mock_client = MagicMock()
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps(
            {"embedding": fake_embedding}
        ).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}
        mock_boto3.Session.return_value.client.return_value = mock_client

        entities = [self._mock_entity("CPAP"), self._mock_entity("Humidifier")]
        result = generate_embeddings(entities)

        assert len(result) == 2
        assert result[0].embedding == fake_embedding
        assert result[1].embedding == fake_embedding
        assert mock_client.invoke_model.call_count == 2

    @patch("kg_builder_cli.extraction.embeddings.boto3")
    def test_generate_embeddings_empty_list(self, mock_boto3):
        """Empty input returns empty output without API calls."""
        result = generate_embeddings([])
        assert result == []
        mock_boto3.Session.assert_not_called()

    @patch("kg_builder_cli.extraction.embeddings.boto3")
    def test_generate_embeddings_handles_failure(self, mock_boto3):
        """Failed API call leaves embedding as None."""
        mock_client = MagicMock()
        mock_client.invoke_model.side_effect = Exception("API error")
        mock_boto3.Session.return_value.client.return_value = mock_client

        entities = [self._mock_entity()]
        result = generate_embeddings(entities)

        assert len(result) == 1
        assert result[0].embedding is None

    @patch("kg_builder_cli.extraction.embeddings.boto3")
    def test_input_text_format(self, mock_boto3):
        """Input text follows format: '{type}: {name} - {description[:200]}'."""
        fake_embedding = [0.1] * 1024
        mock_client = MagicMock()
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps(
            {"embedding": fake_embedding}
        ).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}
        mock_boto3.Session.return_value.client.return_value = mock_client

        entity = Entity(
            id="e1", name="DreamStation", type="Product",
            description="A CPAP device by Philips"
        )
        generate_embeddings([entity])

        call_args = mock_client.invoke_model.call_args
        body = json.loads(call_args[1]["body"] if "body" in call_args[1] else call_args.kwargs["body"])
        assert body["inputText"] == "Product: DreamStation - A CPAP device by Philips"

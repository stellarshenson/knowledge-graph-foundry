"""Tests for embedding generation with Bedrock + local fallback."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from knowledge_graph_foundry.extraction import embeddings as emb_mod
from knowledge_graph_foundry.extraction.embeddings import (
    generate_embeddings,
    reset_provider_state,
)
from knowledge_graph_foundry.models import Entity
from knowledge_graph_foundry.settings import EmbeddingSettings


@pytest.fixture(autouse=True)
def _reset_provider():
    """Reset the module-level provider lock before every test."""
    reset_provider_state()
    yield
    reset_provider_state()


def _entity(name: str = "Test", entity_type: str = "Product") -> Entity:
    return Entity(id=f"e_{name}", name=name, types=[entity_type], description="A test entity")


def _cfg(**kwargs) -> EmbeddingSettings:
    return EmbeddingSettings(**kwargs)


def _mock_bedrock_client(mock_boto3, embedding: list[float]) -> MagicMock:
    mock_client = MagicMock()
    mock_body = MagicMock()
    mock_body.read.return_value = json.dumps({"embedding": embedding}).encode()
    mock_client.invoke_model.return_value = {"body": mock_body}
    mock_boto3.Session.return_value.client.return_value = mock_client
    return mock_client


class TestBedrockProvider:
    @patch("knowledge_graph_foundry.extraction.embeddings.boto3")
    def test_populates_embedding_field(self, mock_boto3):
        fake = [0.1] * 1024
        mock_client = _mock_bedrock_client(mock_boto3, fake)

        result = generate_embeddings([_entity("CPAP"), _entity("Humidifier")], _cfg())

        assert len(result) == 2
        assert result[0].embedding == fake
        assert result[1].embedding == fake
        assert mock_client.invoke_model.call_count == 2

    @patch("knowledge_graph_foundry.extraction.embeddings.boto3")
    def test_input_text_format(self, mock_boto3):
        mock_client = _mock_bedrock_client(mock_boto3, [0.1] * 1024)

        entity = Entity(
            id="e1",
            name="DreamStation",
            types=["Product"],
            description="A CPAP device by Philips",
        )
        generate_embeddings([entity], _cfg(fallback=None))

        body = json.loads(mock_client.invoke_model.call_args.kwargs["body"])
        assert body["inputText"] == "Product: DreamStation - A CPAP device by Philips"

    @patch("knowledge_graph_foundry.extraction.embeddings.boto3")
    def test_typeless_entity_uses_entity_placeholder(self, mock_boto3):
        mock_client = _mock_bedrock_client(mock_boto3, [0.1] * 1024)

        entity = Entity(id="e1", name="Widget", types=[], description="Untyped")
        generate_embeddings([entity], _cfg(fallback=None))

        body = json.loads(mock_client.invoke_model.call_args.kwargs["body"])
        assert body["inputText"] == "Entity: Widget - Untyped"

    @patch("knowledge_graph_foundry.extraction.embeddings.boto3")
    def test_per_entity_failure_after_first_success_continues(self, mock_boto3):
        """If first call succeeds then later fails, continue with warnings."""
        fake = [0.1] * 1024
        mock_client = MagicMock()
        good_body = MagicMock()
        good_body.read.return_value = json.dumps({"embedding": fake}).encode()
        mock_client.invoke_model.side_effect = [
            {"body": good_body},
            Exception("transient"),
        ]
        mock_boto3.Session.return_value.client.return_value = mock_client

        result = generate_embeddings([_entity("A"), _entity("B")], _cfg(fallback=None))
        assert result[0].embedding == fake
        assert result[1].embedding is None


class TestLocalProvider:
    def test_local_provider_uses_sentence_transformers(self):
        fake_model = MagicMock()
        fake_model.encode.return_value = [[0.1] * 384, [0.2] * 384]
        fake_module = SimpleNamespace(SentenceTransformer=MagicMock(return_value=fake_model))

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            result = generate_embeddings(
                [_entity("A"), _entity("B")],
                _cfg(provider="sentence-transformers", model="all-MiniLM-L6-v2"),
            )

        assert len(result[0].embedding) == 384
        assert len(result[1].embedding) == 384
        assert result[0].embedding[0] == pytest.approx(0.1)
        assert result[1].embedding[0] == pytest.approx(0.2)
        fake_module.SentenceTransformer.assert_called_once_with("all-MiniLM-L6-v2")

    def test_local_provider_input_text_format(self):
        fake_model = MagicMock()
        fake_model.encode.return_value = [[0.1] * 384]
        fake_module = SimpleNamespace(SentenceTransformer=MagicMock(return_value=fake_model))

        entity = Entity(
            id="e1",
            name="DreamStation",
            types=["Product"],
            description="A CPAP device by Philips",
        )
        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            generate_embeddings(
                [entity], _cfg(provider="sentence-transformers", model="all-MiniLM-L6-v2")
            )

        texts_arg = fake_model.encode.call_args.args[0]
        assert texts_arg == ["Product: DreamStation - A CPAP device by Philips"]

    def test_local_provider_missing_dependency_raises(self):
        """When sentence_transformers is not installed and no fallback, raise."""
        with patch.dict(sys.modules, {"sentence_transformers": None}):
            with pytest.raises(RuntimeError, match="sentence-transformers not installed"):
                generate_embeddings(
                    [_entity("A")],
                    _cfg(
                        provider="sentence-transformers", model="all-MiniLM-L6-v2", fallback=None
                    ),
                )


class TestProviderFallback:
    @patch("knowledge_graph_foundry.extraction.embeddings.boto3")
    def test_bedrock_failure_falls_back_to_local(self, mock_boto3):
        mock_boto3.Session.side_effect = Exception("AWS auth failed")
        fake_model = MagicMock()
        fake_model.encode.return_value = [[0.7] * 384, [0.8] * 384]
        fake_module = SimpleNamespace(SentenceTransformer=MagicMock(return_value=fake_model))

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            result = generate_embeddings([_entity("A"), _entity("B")], _cfg())

        assert len(result[0].embedding) == 384
        assert len(result[1].embedding) == 384
        assert emb_mod._active_provider == "sentence-transformers"
        fake_module.SentenceTransformer.assert_called_once_with("all-MiniLM-L6-v2")

    @patch("knowledge_graph_foundry.extraction.embeddings.boto3")
    def test_no_fallback_when_fallback_is_none(self, mock_boto3):
        mock_boto3.Session.side_effect = Exception("AWS auth failed")

        with pytest.raises(Exception, match="AWS auth failed"):
            generate_embeddings([_entity("A")], _cfg(fallback=None))

    @patch("knowledge_graph_foundry.extraction.embeddings.boto3")
    def test_fallback_partial_embeddings_cleared_before_retry(self, mock_boto3):
        """When primary fails at first call, partial embeddings are cleared before fallback."""
        mock_client = MagicMock()
        mock_client.invoke_model.side_effect = Exception("auth failed at first call")
        mock_boto3.Session.return_value.client.return_value = mock_client

        # Pre-set an embedding to verify it gets cleared on fallback
        entity = _entity("A")
        entity.embedding = [999.0]

        fake_local = MagicMock()
        fake_local.encode.return_value = [[0.5] * 384]
        fake_module = SimpleNamespace(SentenceTransformer=MagicMock(return_value=fake_local))

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            result = generate_embeddings([entity], _cfg())

        assert len(result[0].embedding) == 384
        assert result[0].embedding[0] == pytest.approx(0.5)


class TestRunProviderLock:
    def test_second_call_uses_locked_provider(self):
        """Once a provider succeeds, the same provider is reused."""
        fake_model = MagicMock()
        fake_model.encode.return_value = [[0.1] * 384]
        fake_st_class = MagicMock(return_value=fake_model)
        fake_module = SimpleNamespace(SentenceTransformer=fake_st_class)

        with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
            generate_embeddings(
                [_entity("A")], _cfg(provider="sentence-transformers", model="all-MiniLM-L6-v2")
            )
            assert emb_mod._active_provider == "sentence-transformers"

            # Request bedrock - should still use locked sentence-transformers
            generate_embeddings([_entity("B")], _cfg(provider="bedrock"))
            assert emb_mod._active_provider == "sentence-transformers"

    @patch("knowledge_graph_foundry.extraction.embeddings.boto3")
    def test_locked_provider_does_not_fall_back(self, mock_boto3):
        """After lock-in, provider failures do not trigger fallback."""
        mock_client = _mock_bedrock_client(mock_boto3, [0.1] * 1024)

        generate_embeddings([_entity("A")], _cfg())
        assert emb_mod._active_provider == "bedrock"

        # Now all calls fail - should raise instead of falling back
        mock_client.invoke_model.side_effect = Exception("network down")
        with pytest.raises(Exception, match="network down"):
            generate_embeddings([_entity("B")], _cfg())

    def test_empty_list_does_not_lock_provider(self):
        """Empty input short-circuits without locking a provider."""
        result = generate_embeddings([], _cfg(provider="sentence-transformers"))
        assert result == []
        assert emb_mod._active_provider is None


class TestEmbeddingCache:
    """DEF-1: identical mention texts embed once per run."""

    @patch("knowledge_graph_foundry.extraction.embeddings.boto3")
    def test_repeat_text_served_from_cache(self, mock_boto3):
        fake = [0.5] * 1024
        mock_client = _mock_bedrock_client(mock_boto3, fake)

        generate_embeddings([_entity("ResMed"), _entity("CPAP")], _cfg())
        assert mock_client.invoke_model.call_count == 2

        # same texts again (new Entity objects) - zero new API calls
        again = generate_embeddings([_entity("ResMed"), _entity("CPAP")], _cfg())
        assert mock_client.invoke_model.call_count == 2
        assert again[0].embedding == fake
        assert again[1].embedding == fake

    @patch("knowledge_graph_foundry.extraction.embeddings.boto3")
    def test_duplicates_within_one_call_still_dispatch_once_each(self, mock_boto3):
        fake = [0.5] * 1024
        mock_client = _mock_bedrock_client(mock_boto3, fake)

        # two distinct texts + one repeat of an already-cached text
        generate_embeddings([_entity("ResMed")], _cfg())
        generate_embeddings([_entity("ResMed"), _entity("AirSense 11")], _cfg())
        assert mock_client.invoke_model.call_count == 2  # ResMed once, AirSense once

    @patch("knowledge_graph_foundry.extraction.embeddings.boto3")
    def test_changed_description_is_a_cache_miss(self, mock_boto3):
        fake = [0.5] * 1024
        mock_client = _mock_bedrock_client(mock_boto3, fake)

        generate_embeddings([_entity("ResMed")], _cfg())
        grown = _entity("ResMed")
        grown.description = "A manufacturer of CPAP devices headquartered in San Diego"
        generate_embeddings([grown], _cfg())
        assert mock_client.invoke_model.call_count == 2  # different text, re-embedded

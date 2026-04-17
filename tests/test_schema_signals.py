"""Tests for schema signal extraction."""

from unittest.mock import MagicMock, patch

import pytest

from kgf.extraction.schema_signals import SchemaSignals, compute_coverage, extract_schema_signals


class TestComputeCoverage:
    def test_full_coverage(self):
        signals = SchemaSignals(entity_types=["Component", "Product"])
        known = {"Component", "Product", "Specification"}
        assert compute_coverage(signals, known) == 1.0

    def test_partial_coverage(self):
        signals = SchemaSignals(entity_types=["Component", "Product", "NewType", "AnotherNew"])
        known = {"Component", "Product"}
        assert compute_coverage(signals, known) == 0.5

    def test_empty_signals(self):
        signals = SchemaSignals(entity_types=[])
        known = {"Component"}
        assert compute_coverage(signals, known) == 1.0

    def test_no_known_types(self):
        signals = SchemaSignals(entity_types=["Component", "Product"])
        known: set[str] = set()
        assert compute_coverage(signals, known) == 0.0

    def test_case_insensitive(self):
        signals = SchemaSignals(entity_types=["component", "PRODUCT"])
        known = {"Component", "Product"}
        assert compute_coverage(signals, known) == 1.0


class TestExtractSchemaSignals:
    @patch("kgf.extraction.schema_signals.instructor")
    @patch("kgf.extraction.schema_signals.litellm")
    def test_mock_extraction(self, mock_litellm, mock_instructor):
        mock_client = MagicMock()
        mock_instructor.from_litellm.return_value = mock_client
        mock_client.chat.completions.create.return_value = SchemaSignals(
            entity_types=["Person", "Organization"],
            relationship_types=["WORKS_AT"],
        )

        result = extract_schema_signals("Some text about people and companies", model="test-model")
        assert len(result.entity_types) == 2
        assert "Person" in result.entity_types

    @patch("kgf.extraction.schema_signals.instructor")
    @patch("kgf.extraction.schema_signals.litellm")
    def test_exception_returns_empty(self, mock_litellm, mock_instructor):
        mock_client = MagicMock()
        mock_instructor.from_litellm.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("LLM error")

        result = extract_schema_signals("Some text", model="test-model")
        assert result.entity_types == []
        assert result.relationship_types == []

"""Tests for generative curing LLM advisory layer."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from kg_builder_cli.curing.generative import (
    CureDecision,
    CureProbe,
    RecureDecision,
    _is_ambiguous_for_query,
    llm_should_cure,
    llm_should_recure,
)
from kg_builder_cli.types.config import CuringConfig, LLMConfig


@pytest.fixture
def llm_config():
    return LLMConfig(provider="bedrock", model="test-model", region="us-east-1")


@pytest.fixture
def sample_metrics_history():
    return [
        {"js_divergence": 0.45, "entropy_shannon_delta": 0.31, "type_accumulation_rate": 3.0, "chao1_coverage": 0.6, "heaps_beta": 0.89},
        {"js_divergence": 0.12, "entropy_shannon_delta": 0.08, "type_accumulation_rate": 1.0, "chao1_coverage": 0.75, "heaps_beta": 0.45},
        {"js_divergence": 0.005, "entropy_shannon_delta": 0.02, "type_accumulation_rate": 0.0, "chao1_coverage": 0.95, "heaps_beta": 0.12},
    ]


@pytest.fixture
def sample_new_types_history():
    return [
        {"Person", "Device", "Org"},
        {"Standard"},
        set(),
    ]


@pytest.fixture
def mock_instructor_litellm():
    """Mock instructor and litellm for generative curing tests."""
    mock_client = MagicMock()
    mock_instructor = MagicMock()
    mock_instructor.from_litellm.return_value = mock_client
    mock_litellm = MagicMock()

    with patch.dict(sys.modules, {"instructor": mock_instructor, "litellm": mock_litellm}):
        yield mock_client, mock_instructor, mock_litellm


class TestCureDecisionModel:
    def test_valid_cure(self):
        d = CureDecision(should_cure=True, reasoning="Types cover intent")
        assert d.should_cure is True
        assert d.reasoning == "Types cover intent"

    def test_valid_block(self):
        d = CureDecision(should_cure=False, reasoning="Missing categories")
        assert d.should_cure is False


class TestCureProbeModel:
    def test_probe_without_query(self):
        p = CureProbe(should_cure=True, reasoning="Clear metrics")
        assert p.needs_query is False
        assert p.query_type is None

    def test_probe_with_query(self):
        p = CureProbe(
            should_cure=False,
            reasoning="Need to check",
            needs_query=True,
            query_type="entity_counts",
            query_filter_type="Person",
        )
        assert p.needs_query is True
        assert p.query_type == "entity_counts"


class TestRecureDecisionModel:
    def test_valid_recure(self):
        d = RecureDecision(should_recure=True, reasoning="New types missing")
        assert d.should_recure is True

    def test_valid_dismiss(self):
        d = RecureDecision(should_recure=False, reasoning="Synonyms only")
        assert d.should_recure is False


class TestIsAmbiguousForQuery:
    def test_ambiguous_jsd(self):
        assert _is_ambiguous_for_query({"js_divergence": 0.05}, 0.9)

    def test_ambiguous_coverage(self):
        assert _is_ambiguous_for_query({"js_divergence": 0.001}, 0.6)

    def test_not_ambiguous_clear_converge(self):
        assert not _is_ambiguous_for_query({"js_divergence": 0.001}, 0.9)

    def test_not_ambiguous_clear_diverge(self):
        assert not _is_ambiguous_for_query({"js_divergence": 0.15}, 0.9)


class TestLlmShouldCure:
    def test_returns_cure_decision(
        self, mock_instructor_litellm, llm_config, sample_metrics_history, sample_new_types_history
    ):
        mock_client, _, _ = mock_instructor_litellm
        mock_client.create.return_value = CureProbe(
            should_cure=True, reasoning="All conditions met"
        )

        result = llm_should_cure(
            type_names={"Person", "Device", "Org", "Standard"},
            frequencies={"Person": 10, "Device": 8, "Org": 5, "Standard": 3},
            coverage=0.95,
            intent="medical device catalog",
            stability={"js_divergence": 0.005},
            metrics_history=sample_metrics_history,
            new_types_history=sample_new_types_history,
            docs_processed=3,
            total_entities=100,
            llm_config=llm_config,
        )

        assert result is not None
        assert result.should_cure is True
        assert result.reasoning == "All conditions met"
        mock_client.create.assert_called_once()

    def test_returns_none_on_failure(
        self, mock_instructor_litellm, llm_config, sample_metrics_history, sample_new_types_history
    ):
        mock_client, _, _ = mock_instructor_litellm
        mock_client.create.side_effect = Exception("API error")

        result = llm_should_cure(
            type_names={"Person"},
            frequencies={"Person": 5},
            coverage=0.5,
            intent=None,
            stability={},
            metrics_history=sample_metrics_history,
            new_types_history=sample_new_types_history,
            docs_processed=3,
            total_entities=50,
            llm_config=llm_config,
        )

        assert result is None

    def test_two_phase_cure_with_query(
        self, mock_instructor_litellm, llm_config, sample_metrics_history, sample_new_types_history
    ):
        """When probe requests query and metrics are ambiguous, second call is made."""
        mock_client, _, _ = mock_instructor_litellm

        # First call returns probe wanting a query
        probe = CureProbe(
            should_cure=False,
            reasoning="Need to verify entity distribution",
            needs_query=True,
            query_type="entity_counts",
        )
        # Second call returns final decision
        final = CureDecision(should_cure=True, reasoning="Graph confirms coverage")
        mock_client.create.side_effect = [probe, final]

        mock_accumulator = MagicMock()
        mock_accumulator.all_entities.return_value = []
        mock_accumulator.all_relationships.return_value = []

        result = llm_should_cure(
            type_names={"Person", "Device"},
            frequencies={"Person": 10, "Device": 5},
            coverage=0.6,  # in ambiguous range
            intent="medical devices",
            stability={"js_divergence": 0.05},  # in ambiguous range
            metrics_history=sample_metrics_history,
            new_types_history=sample_new_types_history,
            docs_processed=3,
            total_entities=50,
            llm_config=llm_config,
            accumulator=mock_accumulator,
            max_tool_calls=2,
        )

        assert result is not None
        assert result.should_cure is True
        assert result.reasoning == "Graph confirms coverage"
        assert mock_client.create.call_count == 2

    def test_query_not_honoured_when_metrics_clear(
        self, mock_instructor_litellm, llm_config, sample_metrics_history, sample_new_types_history
    ):
        """When metrics are clearly converged, query request is ignored."""
        mock_client, _, _ = mock_instructor_litellm
        mock_client.create.return_value = CureProbe(
            should_cure=True,
            reasoning="Converged",
            needs_query=True,  # LLM requests query but metrics are clear
            query_type="entity_counts",
        )

        mock_accumulator = MagicMock()

        result = llm_should_cure(
            type_names={"Person"},
            frequencies={"Person": 10},
            coverage=0.95,  # NOT ambiguous
            intent="test",
            stability={"js_divergence": 0.001},  # NOT ambiguous
            metrics_history=sample_metrics_history,
            new_types_history=sample_new_types_history,
            docs_processed=3,
            total_entities=50,
            llm_config=llm_config,
            accumulator=mock_accumulator,
            max_tool_calls=2,
        )

        # Should use probe decision directly, no second call
        assert result is not None
        assert result.should_cure is True
        mock_client.create.assert_called_once()


class TestLlmShouldRecure:
    def test_returns_recure_decision(self, mock_instructor_litellm, llm_config):
        mock_client, _, _ = mock_instructor_litellm
        mock_client.create.return_value = RecureDecision(
            should_recure=True, reasoning="Missing type categories"
        )

        result = llm_should_recure(
            cured_ontology_types=["Person", "Device"],
            remap_history=[0.35, 0.40, 0.38],
            recent_remap_rate=0.38,
            remap_count=12,
            intent="medical device catalog",
            stability={"js_divergence": 0.15},
            llm_config=llm_config,
        )

        assert result is not None
        assert result.should_recure is True
        mock_client.create.assert_called_once()

    def test_returns_none_on_failure(self, mock_instructor_litellm, llm_config):
        mock_client, _, _ = mock_instructor_litellm
        mock_client.create.side_effect = RuntimeError("timeout")

        result = llm_should_recure(
            cured_ontology_types=["Person"],
            remap_history=[0.5],
            recent_remap_rate=0.5,
            remap_count=5,
            intent=None,
            stability={},
            llm_config=llm_config,
        )

        assert result is None


class TestGenerativeCuringConfig:
    def test_default_false(self):
        cfg = CuringConfig()
        assert cfg.generative_curing is False

    def test_enable(self):
        cfg = CuringConfig(generative_curing=True)
        assert cfg.generative_curing is True

    def test_patience_default(self):
        cfg = CuringConfig()
        assert cfg.generative_patience == 0.4

    def test_max_tool_calls_default(self):
        cfg = CuringConfig()
        assert cfg.generative_max_tool_calls == 2


class TestEarlyStopPatience:
    """Integration test: patience-based early stopping via detector."""

    def test_early_stop_triggers(self):
        """Consecutive cure votes exceeding threshold triggers early stop.

        With max_fluid_documents=10 and patience=0.3, threshold = max(3, int(10*0.3)) = 3.
        """
        from kg_builder_cli.curing.detector import CuringDetector

        config = CuringConfig(enabled=True, max_fluid_documents=10, generative_patience=0.3)
        detector = CuringDetector(config)

        detector.record_llm_vote(True)
        detector.record_llm_vote(True)
        assert not detector.patience_exceeded(config.generative_patience)
        detector.record_llm_vote(True)
        assert detector.patience_exceeded(config.generative_patience)

    def test_early_stop_scales_with_corpus(self):
        """With max_fluid_documents=20 and patience=0.4, need 8 consecutive votes."""
        from kg_builder_cli.curing.detector import CuringDetector

        config = CuringConfig(enabled=True, max_fluid_documents=20, generative_patience=0.4)
        detector = CuringDetector(config)

        for _ in range(7):
            detector.record_llm_vote(True)
        assert not detector.patience_exceeded(config.generative_patience)
        detector.record_llm_vote(True)
        assert detector.patience_exceeded(config.generative_patience)

    def test_early_stop_reset_on_continue(self):
        """A 'continue' vote resets the patience counter."""
        from kg_builder_cli.curing.detector import CuringDetector

        config = CuringConfig(enabled=True, max_fluid_documents=10, generative_patience=0.3)
        detector = CuringDetector(config)

        detector.record_llm_vote(True)
        detector.record_llm_vote(True)
        detector.record_llm_vote(False)  # reset
        detector.record_llm_vote(True)
        detector.record_llm_vote(True)
        assert not detector.patience_exceeded(config.generative_patience)

"""Tests using pre-recorded LLM cassettes for deterministic replay.

These tests exercise the actual extraction and curing functions with
pre-recorded LLM responses instead of MagicMock, ensuring response
deserialization and downstream logic work end-to-end.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.llm_cassette import Cassette, CassetteCall, RecordingClient, ReplayClient

CASSETTES = Path(__file__).parent / "fixtures" / "llm_cassettes"


def load_cassette(name: str) -> ReplayClient:
    """Load a cassette by name and return a ReplayClient."""
    path = CASSETTES / f"{name}.json"
    return ReplayClient.from_cassette_file(path)


# ---------------------------------------------------------------------------
# Cassette infrastructure tests
# ---------------------------------------------------------------------------


class TestCassetteInfrastructure:
    def test_load_and_replay(self):
        """Load a cassette file and replay responses."""
        client = load_cassette("extraction_cpap_product")
        assert client.calls_remaining == 1

        from kgf.extraction.response_models import ExtractionResponse

        resp = client.chat.completions.create(
            model="bedrock/test-model",
            response_model=ExtractionResponse,
            messages=[{"role": "user", "content": "test"}],
            temperature=0.0,
        )
        assert isinstance(resp, ExtractionResponse)
        assert len(resp.entities) == 3
        assert client.calls_made == 1
        assert client.calls_remaining == 0

    def test_cassette_exhaustion_raises(self):
        """Accessing beyond cassette length raises IndexError."""
        client = load_cassette("curing_should_cure")
        client.create(model="x", response_model=None, messages=[])
        with pytest.raises(IndexError, match="exhausted"):
            client.create(model="x", response_model=None, messages=[])

    def test_method_mismatch_raises(self):
        """Wrong call method raises ValueError."""
        client = load_cassette("extraction_cpap_product")
        with pytest.raises(ValueError, match="expected method"):
            client.create(model="x")

    def test_save_and_reload(self, tmp_path):
        """Round-trip: build cassette, save, reload, replay."""
        from tests.llm_cassette import Cassette, CassetteCall, ReplayClient

        cassette = Cassette(
            description="round-trip test",
            calls=[
                CassetteCall(
                    method="create",
                    response_model_name="CureDecision",
                    response_data={"should_cure": True, "reasoning": "test"},
                ),
            ],
        )
        path = tmp_path / "test_cassette.json"
        cassette.save(path)

        client = ReplayClient.from_cassette_file(path)
        resp = client.create(model="test")
        assert resp.should_cure is True
        assert resp.reasoning == "test"

    def test_multi_call_cassette(self):
        """Cassette with multiple calls replays in order."""
        client = load_cassette("extraction_multi_chunk")
        assert client.calls_remaining == 2

        from kgf.extraction.response_models import ExtractionResponse

        r1 = client.chat.completions.create(model="x", response_model=ExtractionResponse, messages=[])
        assert len(r1.entities) == 2  # first chunk: AirSense + ResMed

        r2 = client.chat.completions.create(model="x", response_model=ExtractionResponse, messages=[])
        assert len(r2.entities) == 3  # second chunk: Feature + Spec + Product
        assert client.calls_remaining == 0


# ---------------------------------------------------------------------------
# Extraction tests with cassettes
# ---------------------------------------------------------------------------


class TestExtractionWithCassettes:
    def test_extract_chunk_cpap_product(self):
        """Full extract_chunk with cassette-replayed LLM response."""
        from kgf.extraction.extract import extract_chunk
        from kgf.extraction.response_models import ExtractionResponse
        from kgf.types.document import Chunk, ChunkMetadata

        client = load_cassette("extraction_cpap_product")
        chunk = Chunk(
            id="chunk_001", text="BMC Medical manufactures the RESmart CPAP...",
            index=0, metadata=ChunkMetadata(), token_count=50,
        )

        entities, rels = extract_chunk(
            chunk, "Extract entities.", "bedrock/test-model",
            client, response_model=ExtractionResponse,
        )

        assert len(entities) == 3
        assert {e.type for e in entities} == {"Product", "Organization", "Specification"}
        assert entities[0].name == "RESmart CPAP"
        assert entities[0].source_chunks == ["chunk_001"]
        assert entities[0].extraction_model == "bedrock/test-model"

        assert len(rels) == 2
        assert {r.type for r in rels} == {"MANUFACTURES", "HAS_SPECIFICATION"}
        assert rels[0].source_chunks == ["chunk_001"]

    def test_extract_multi_chunk_session(self):
        """Two sequential chunk extractions from one cassette."""
        from kgf.extraction.extract import extract_chunk
        from kgf.extraction.response_models import ExtractionResponse
        from kgf.types.document import Chunk, ChunkMetadata

        client = load_cassette("extraction_multi_chunk")

        chunk1 = Chunk(id="c1", text="ResMed AirSense 10...", index=0,
                       metadata=ChunkMetadata(), token_count=40)
        chunk2 = Chunk(id="c2", text="AutoSet algorithm adjusts...", index=1,
                       metadata=ChunkMetadata(), token_count=35)

        e1, r1 = extract_chunk(chunk1, "Extract.", "bedrock/test-model",
                               client, response_model=ExtractionResponse)
        e2, r2 = extract_chunk(chunk2, "Extract.", "bedrock/test-model",
                               client, response_model=ExtractionResponse)

        assert len(e1) == 2  # Product + Organization
        assert len(e2) == 3  # Feature + Specification + Product (cross-ref)
        assert e1[0].source_chunks == ["c1"]
        assert e2[0].source_chunks == ["c2"]

        # Cross-chunk entity appears in both
        product_names = {e.name for e in e1 + e2 if e.type == "Product"}
        assert "AirSense 10" in product_names

    def test_schema_signals_with_cassette(self):
        """Schema signal extraction replayed from cassette."""
        from kgf.extraction.schema_signals import SchemaSignals

        client = load_cassette("schema_signals_cpap")
        resp = client.chat.completions.create(
            model="bedrock/test-model",
            response_model=SchemaSignals,
            messages=[{"role": "user", "content": "test"}],
        )

        assert isinstance(resp, SchemaSignals)
        assert "Product" in resp.entity_types
        assert "MANUFACTURES" in resp.relationship_types
        assert len(resp.entity_types) == 6


# ---------------------------------------------------------------------------
# Curing decision tests with cassettes
# ---------------------------------------------------------------------------


class TestCuringWithCassettes:
    @pytest.fixture
    def llm_config(self):
        from kgf.types.config import LLMConfig
        return LLMConfig(provider="bedrock", model="test-model", region="us-east-1")

    @pytest.fixture
    def metrics_history(self):
        return [
            {"js_divergence": 0.45, "entropy_shannon_delta": 0.31,
             "type_accumulation_rate": 3.0, "chao1_coverage": 0.6, "heaps_beta": 0.89},
            {"js_divergence": 0.12, "entropy_shannon_delta": 0.08,
             "type_accumulation_rate": 1.0, "chao1_coverage": 0.75, "heaps_beta": 0.45},
            {"js_divergence": 0.03, "entropy_shannon_delta": 0.01,
             "type_accumulation_rate": 0.0, "chao1_coverage": 0.92, "heaps_beta": 0.12},
        ]

    @pytest.fixture
    def new_types_history(self):
        return [
            {"Product", "Organization", "Specification"},
            {"Feature"},
            set(),
        ]

    def _patch_instructor(self, cassette_name):
        """Create a patch context that injects a cassette replay client."""
        client = load_cassette(cassette_name)
        mock_instructor = type(sys)("instructor")
        mock_instructor.from_litellm = lambda _: client
        mock_litellm = type(sys)("litellm")
        mock_litellm.completion = None
        return patch.dict(sys.modules, {"instructor": mock_instructor, "litellm": mock_litellm}), client

    def test_cure_approved(self, llm_config, metrics_history, new_types_history):
        """Cassette: probe approves curing without graph query."""
        from kgf.curing.generative import llm_should_cure

        ctx, client = self._patch_instructor("curing_should_cure")
        with ctx:
            result = llm_should_cure(
                type_names={"Product", "Organization", "Specification", "Feature", "Component"},
                frequencies={"Product": 45, "Organization": 12, "Specification": 89,
                             "Feature": 34, "Component": 67},
                coverage=0.92,
                intent="CPAP medical device catalog with product specifications and component architecture",
                stability={"js_divergence": 0.003},
                metrics_history=metrics_history,
                new_types_history=new_types_history,
                docs_processed=5,
                total_entities=247,
                llm_config=llm_config,
            )

        assert result is not None
        assert result.should_cure is True
        assert "Chao1" in result.reasoning
        assert client.calls_made == 1

    def test_cure_blocked(self, llm_config, metrics_history, new_types_history):
        """Cassette: probe blocks curing - missing entity categories."""
        from kgf.curing.generative import llm_should_cure

        ctx, client = self._patch_instructor("curing_block_cure")
        with ctx:
            result = llm_should_cure(
                type_names={"Product", "Organization"},
                frequencies={"Product": 15, "Organization": 8},
                coverage=0.4,
                intent="CPAP devices with component architecture and regulatory standards",
                stability={"js_divergence": 0.15},
                metrics_history=metrics_history[:2],
                new_types_history=new_types_history[:2],
                docs_processed=2,
                total_entities=23,
                llm_config=llm_config,
            )

        assert result is not None
        assert result.should_cure is False
        assert "Standard" in result.reasoning or "Component" in result.reasoning
        assert client.calls_made == 1

    def test_cure_two_phase_with_query(self, llm_config, metrics_history, new_types_history):
        """Cassette: probe requests graph query, second call decides."""
        from unittest.mock import MagicMock

        from kgf.curing.generative import llm_should_cure

        ctx, client = self._patch_instructor("curing_two_phase")
        mock_accumulator = MagicMock()
        mock_accumulator.all_entities.return_value = []
        mock_accumulator.all_relationships.return_value = []

        with ctx:
            result = llm_should_cure(
                type_names={"Product", "Organization", "Specification"},
                frequencies={"Product": 30, "Organization": 10, "Specification": 55},
                coverage=0.65,  # ambiguous range
                intent="medical device catalog",
                stability={"js_divergence": 0.04},  # ambiguous range
                metrics_history=metrics_history,
                new_types_history=new_types_history,
                docs_processed=4,
                total_entities=95,
                llm_config=llm_config,
                accumulator=mock_accumulator,
                max_tool_calls=2,
            )

        assert result is not None
        assert result.should_cure is True
        assert "confirms" in result.reasoning.lower()
        assert client.calls_made == 2

    def test_recure_dismissed(self, llm_config):
        """Cassette: drift dismissed as synonym variants."""
        from kgf.curing.generative import llm_should_recure

        ctx, client = self._patch_instructor("recure_dismiss_drift")
        with ctx:
            result = llm_should_recure(
                cured_ontology_types=["Product", "Organization", "Specification", "Feature"],
                remap_history=[0.25, 0.22, 0.18],
                recent_remap_rate=0.18,
                remap_count=8,
                intent="CPAP medical device catalog",
                stability={"js_divergence": 0.02},
                llm_config=llm_config,
            )

        assert result is not None
        assert result.should_recure is False
        assert "variant" in result.reasoning.lower()

    def test_recure_triggered(self, llm_config):
        """Cassette: re-cure triggered due to genuinely missing categories."""
        from kgf.curing.generative import llm_should_recure

        ctx, client = self._patch_instructor("recure_trigger")
        with ctx:
            result = llm_should_recure(
                cured_ontology_types=["Product", "Organization", "Specification", "Feature"],
                remap_history=[0.38, 0.42, 0.35, 0.40],
                recent_remap_rate=0.40,
                remap_count=24,
                intent="medical device catalog with regulatory compliance",
                stability={"js_divergence": 0.12},
                llm_config=llm_config,
            )

        assert result is not None
        assert result.should_recure is True
        assert "Standard" in result.reasoning or "Certification" in result.reasoning


# ---------------------------------------------------------------------------
# Type clustering with cassette
# ---------------------------------------------------------------------------


class TestTypeClusteringWithCassette:
    def test_clustering_merges_synonyms(self):
        """Cassette: type clustering merges synonym variants."""
        client = load_cassette("type_clustering")

        from kgf.curing.type_clustering import TypeClusteringResult

        resp = client.create(model="bedrock/test-model", response_model=TypeClusteringResult, messages=[])

        assert isinstance(resp, TypeClusteringResult)
        assert resp.mapping["CPAPDevice"] == "Product"
        assert resp.mapping["Manufacturer"] == "Organization"
        assert resp.mapping["RegulatoryStandard"] == "Standard"
        assert resp.mapping["Product"] == "Product"  # canonical maps to itself


# ---------------------------------------------------------------------------
# Inline response model tests (type_resolver, deferred_dedup)
# ---------------------------------------------------------------------------


class TestInlineModelCassettes:
    def test_type_resolver_escalation(self):
        """Cassette: _TypeChoice inline model replays correctly."""
        from tests.llm_cassette import _TypeChoice

        client = load_cassette("type_resolver_escalation")
        resp = client.chat.completions.create(
            model="bedrock/test-model",
            response_model=_TypeChoice,
            messages=[{"role": "user", "content": "test"}],
            temperature=0.0,
        )

        assert isinstance(resp, _TypeChoice)
        assert resp.chosen_type == "Component"
        assert "physical part" in resp.reasoning.lower()
        assert client.calls_made == 1
        assert client.calls_remaining == 0

    def test_deferred_dedup_escalation(self):
        """Cassette: _CrossTypeMergeDecision inline model replays correctly."""
        from tests.llm_cassette import _CrossTypeMergeDecision

        client = load_cassette("deferred_dedup_escalation")
        resp = client.chat.completions.create(
            model="bedrock/test-model",
            response_model=_CrossTypeMergeDecision,
            messages=[{"role": "user", "content": "test"}],
            temperature=0.0,
        )

        assert isinstance(resp, _CrossTypeMergeDecision)
        assert resp.should_merge is True
        assert resp.chosen_type == "Product"
        assert "standalone" in resp.reasoning.lower()
        assert client.calls_made == 1

    def test_inline_models_in_registry(self):
        """Both inline models are registered and resolvable."""
        from tests.llm_cassette import _resolve_model

        tc = _resolve_model("_TypeChoice")
        assert tc.__name__ == "_TypeChoice"

        ctmd = _resolve_model("_CrossTypeMergeDecision")
        assert ctmd.__name__ == "_CrossTypeMergeDecision"


# ---------------------------------------------------------------------------
# Recording client tests
# ---------------------------------------------------------------------------


class TestRecordingClient:
    def test_record_and_replay_round_trip(self, tmp_path):
        """Record calls to a mock client, save, reload, replay."""
        from unittest.mock import MagicMock

        from kgf.curing.generative import CureDecision

        from tests.llm_cassette import RecordingClient, ReplayClient

        # Simulate a real client
        mock_real = MagicMock()
        mock_real.create.return_value = CureDecision(
            should_cure=True, reasoning="recorded response"
        )

        recorder = RecordingClient(mock_real, description="recording test")
        result = recorder.create(model="test-model", temperature=0.0)
        assert result.should_cure is True

        path = tmp_path / "recorded.json"
        recorder.save(path)

        # Replay
        replayer = ReplayClient.from_cassette_file(path)
        replayed = replayer.create(model="test-model")
        assert replayed.should_cure is True
        assert replayed.reasoning == "recorded response"

    def test_record_chat_completions(self, tmp_path):
        """Record chat.completions.create calls."""
        from unittest.mock import MagicMock

        from kgf.extraction.response_models import (
            EntityResponse,
            ExtractionResponse,
        )

        from tests.llm_cassette import RecordingClient, ReplayClient

        mock_real = MagicMock()
        mock_real.chat.completions.create.return_value = ExtractionResponse(
            entities=[EntityResponse(id="e1", name="Test", type="Product")],
            relationships=[],
        )

        recorder = RecordingClient(mock_real, description="chat test")
        result = recorder.chat.completions.create(
            model="test", response_model=ExtractionResponse, messages=[]
        )
        assert len(result.entities) == 1

        path = tmp_path / "chat_recorded.json"
        recorder.save(path)

        replayer = ReplayClient.from_cassette_file(path)
        replayed = replayer.chat.completions.create(model="test")
        assert len(replayed.entities) == 1
        assert replayed.entities[0].name == "Test"

"""R34-H366 passage channel unit tests: span construction (offline-cache
keying parity), channel embedding dispatch edges, and settings defaults."""

import pytest

from knowledge_graph_foundry.extraction.embeddings import embed_channel_texts
from knowledge_graph_foundry.graph.passages import build_spans
from knowledge_graph_foundry.settings import ChannelEmbedding, Settings


class TestBuildSpans:
    """Spans must reproduce the R34 offline construction exactly: 900-char
    windows at half-span stride, keyed {chunk_id}:{span}:{start}."""

    def test_keying_matches_offline_cache(self):
        spans = build_spans("c1", "x" * 1000, span_chars=900)
        assert [s["id"] for s in spans] == ["c1:900:0", "c1:900:450"]
        assert spans[0]["text"] == "x" * 900
        assert spans[1]["text"] == "x" * 550  # tail window

    def test_short_text_yields_single_span(self):
        spans = build_spans("c2", "short text", span_chars=900)
        assert [s["id"] for s in spans] == ["c2:900:0"]

    def test_whitespace_pieces_skipped(self):
        spans = build_spans("c3", "a" * 450 + " " * 600, span_chars=900)
        ids = [s["id"] for s in spans]
        assert "c3:900:0" in ids
        assert "c3:900:450" not in ids  # pure-whitespace window dropped


class TestChannelDispatch:
    def test_empty_input_short_circuits(self):
        assert embed_channel_texts([], ChannelEmbedding()) == []

    def test_unknown_provider_rejected(self):
        cfg = ChannelEmbedding.model_construct(provider="carrier-pigeon", model="m", device="cpu")
        with pytest.raises(ValueError, match="Unknown channel embedding provider"):
            embed_channel_texts(["t"], cfg)

    def test_openai_requires_endpoint(self):
        cfg = ChannelEmbedding(provider="openai", model="m", endpoint=None)
        with pytest.raises(ValueError, match="endpoint"):
            embed_channel_texts(["t"], cfg)


class TestChannelSettings:
    def test_passage_channel_defaults_local_gpu(self):
        s = Settings()
        ch = s.embedding_channels.passages
        assert ch.provider == "local-gpu"  # bulk embedding never defaults to cloud
        assert ch.model == "BAAI/bge-m3"
        assert s.graphrag.passages_enabled is False  # rides the escalation gate
        assert s.graphrag.passage_span_chars == 900  # H366 s900k1
        assert s.graphrag.passage_top_k == 1

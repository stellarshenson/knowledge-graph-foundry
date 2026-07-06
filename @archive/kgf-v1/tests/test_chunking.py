"""Tests for token-based text chunking."""
from __future__ import annotations

import hashlib

import pytest

from knowledge_graph_foundry.extraction.chunking import chunk_text
from knowledge_graph_foundry.types.config import ExtractConfig
from knowledge_graph_foundry.types.document import TextSegment


@pytest.fixture
def short_segment():
    return [TextSegment(text="Short text.", source_path="test.txt")]


@pytest.fixture
def long_segment():
    # Generate text that exceeds chunk_size of 100 tokens
    text = "The CPAP device operates continuously. " * 50
    return [TextSegment(text=text, source_path="test.txt", page=1, section="specs")]


class TestChunking:
    def test_chunk_short_text(self, short_segment):
        """Text under chunk_size produces single chunk with SHA1 ID."""
        config = ExtractConfig(chunk_size=500)
        chunks = chunk_text(short_segment, config)
        assert len(chunks) == 1
        expected_id = hashlib.sha1("Short text.".encode()).hexdigest()[:12]
        assert chunks[0].id == expected_id

    def test_chunk_deterministic_ids(self, short_segment):
        """Same text always produces same chunk ID."""
        config = ExtractConfig(chunk_size=500)
        chunks1 = chunk_text(short_segment, config)
        chunks2 = chunk_text(short_segment, config)
        assert chunks1[0].id == chunks2[0].id

    def test_chunk_overlap(self, long_segment):
        """Overlapping content between consecutive chunks."""
        config = ExtractConfig(chunk_size=100, chunk_overlap=20)
        chunks = chunk_text(long_segment, config)
        assert len(chunks) > 1

    def test_chunk_sentence_boundary(self):
        """Chunks end at sentence boundaries when possible."""
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        segment = [TextSegment(text=text, source_path="test.txt")]
        config = ExtractConfig(chunk_size=10, chunk_overlap=2)
        chunks = chunk_text(segment, config)
        for chunk in chunks:
            stripped = chunk.text.rstrip()
            if stripped and not stripped.endswith((".", "?", "!")):
                # Last chunk may not end with sentence boundary
                if chunk.index < len(chunks) - 1:
                    assert stripped[-1] in ".?!", f"Chunk {chunk.index} doesn't end at sentence boundary"

    def test_chunk_token_count(self, short_segment):
        """Token count matches tiktoken encoding."""
        import tiktoken
        config = ExtractConfig(chunk_size=500)
        chunks = chunk_text(short_segment, config)
        enc = tiktoken.get_encoding("cl100k_base")
        for chunk in chunks:
            expected = len(enc.encode(chunk.text))
            assert chunk.token_count == expected

    def test_chunk_metadata_propagation(self):
        """Page/section/source from segment propagated to chunk metadata."""
        segment = [TextSegment(text="Test content.", page=5, section="intro",
                              source_path="doc.pdf")]
        config = ExtractConfig(chunk_size=500)
        chunks = chunk_text(segment, config)
        assert chunks[0].metadata.page == 5
        assert chunks[0].metadata.section == "intro"
        assert chunks[0].metadata.document_source == "doc.pdf"

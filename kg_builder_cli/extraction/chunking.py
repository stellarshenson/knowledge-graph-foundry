"""Token-based text chunking with sentence boundary awareness."""

from __future__ import annotations

import hashlib

from loguru import logger

from kg_builder_cli.types.config import ExtractConfig
from kg_builder_cli.types.document import Chunk, ChunkMetadata, TextSegment

_SENTENCE_BOUNDARIES = (". ", "? ", "! ", "\n")


def chunk_text(segments: list[TextSegment], config: ExtractConfig) -> list[Chunk]:
    """Split text segments into token-sized chunks with overlap.

    Uses tiktoken cl100k_base encoding for token counting.
    Splits on sentence boundaries when possible.
    Generates deterministic chunk IDs from content hash.
    """
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    chunks: list[Chunk] = []
    chunk_index = 0

    for segment in segments:
        text = segment.text
        if not text.strip():
            continue

        tokens = enc.encode(text)
        total_tokens = len(tokens)

        if total_tokens <= config.chunk_size:
            chunk_id = _make_chunk_id(text)
            chunks.append(
                Chunk(
                    id=chunk_id,
                    text=text,
                    index=chunk_index,
                    metadata=ChunkMetadata(
                        document_source=segment.source_path,
                        page=segment.page,
                        section=segment.section,
                        chunk_index=chunk_index,
                    ),
                    token_count=total_tokens,
                )
            )
            chunk_index += 1
            continue

        # Split into overlapping chunks on sentence boundaries
        start = 0
        while start < total_tokens:
            end = min(start + config.chunk_size, total_tokens)
            chunk_tokens = tokens[start:end]
            chunk_text_raw = enc.decode(chunk_tokens)

            # Try to break on sentence boundary if not at end of text
            if end < total_tokens:
                chunk_text_raw = _snap_to_sentence_boundary(
                    chunk_text_raw, enc, config.chunk_size
                )

            if not chunk_text_raw.strip():
                start = end
                continue

            chunk_id = _make_chunk_id(chunk_text_raw)
            actual_tokens = len(enc.encode(chunk_text_raw))
            chunks.append(
                Chunk(
                    id=chunk_id,
                    text=chunk_text_raw,
                    index=chunk_index,
                    metadata=ChunkMetadata(
                        document_source=segment.source_path,
                        page=segment.page,
                        section=segment.section,
                        chunk_index=chunk_index,
                    ),
                    token_count=actual_tokens,
                )
            )
            chunk_index += 1

            # Advance by chunk_size minus overlap
            advance = max(actual_tokens - config.chunk_overlap, 1)
            start += advance

    logger.info("Created {} chunks from {} segments", len(chunks), len(segments))
    return chunks


def _snap_to_sentence_boundary(text: str, enc, max_tokens: int) -> str:
    """Try to break text at the last sentence boundary within token limit."""
    best_pos = -1
    for boundary in _SENTENCE_BOUNDARIES:
        pos = text.rfind(boundary)
        if pos > 0:
            candidate = text[: pos + len(boundary)]
            if len(enc.encode(candidate)) <= max_tokens and pos > best_pos:
                best_pos = pos + len(boundary)

    if best_pos > 0:
        return text[:best_pos]
    return text


def _make_chunk_id(text: str) -> str:
    """Generate deterministic chunk ID from content hash."""
    return hashlib.sha1(text.encode()).hexdigest()[:12]

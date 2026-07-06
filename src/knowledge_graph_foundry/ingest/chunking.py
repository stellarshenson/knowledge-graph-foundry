"""Token-based chunking with sentence-boundary snapping.

Uses tiktoken cl100k_base counts and deterministic chunk ids from
models.chunk_id, so identical input yields identical ids across runs.
"""

from __future__ import annotations

from loguru import logger

from knowledge_graph_foundry.models import Chunk, Document, chunk_id

_SENTENCE_BOUNDARIES = (". ", "\n\n", "\n")


def chunk_document(doc: Document, chunk_size: int = 2000, chunk_overlap: int = 200) -> list[Chunk]:
    """Split a document into overlapping token-sized chunks."""
    import tiktoken

    text = doc.text
    if not text.strip():
        return []

    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    total = len(tokens)

    if total <= chunk_size:
        return [
            Chunk(
                id=chunk_id(doc.id, 0, text),
                document_id=doc.id,
                index=0,
                text=text,
                token_count=total,
            )
        ]

    chunks: list[Chunk] = []
    start = 0
    index = 0
    while start < total:
        end = min(start + chunk_size, total)
        piece = enc.decode(tokens[start:end])
        if end < total:
            piece = _snap_to_boundary(piece, enc, chunk_size)
        if not piece.strip():
            start = end
            continue
        token_count = len(enc.encode(piece))
        chunks.append(
            Chunk(
                id=chunk_id(doc.id, index, piece),
                document_id=doc.id,
                index=index,
                text=piece,
                token_count=token_count,
            )
        )
        index += 1
        if end >= total:
            break
        start += max(token_count - chunk_overlap, 1)

    logger.debug("chunked {} into {} chunks", doc.id, len(chunks))
    return chunks


def _snap_to_boundary(text: str, enc, max_tokens: int) -> str:
    """Cut at the last sentence boundary that stays within the token limit."""
    best = -1
    for boundary in _SENTENCE_BOUNDARIES:
        pos = text.rfind(boundary)
        if pos > 0:
            candidate_end = pos + len(boundary)
            if candidate_end > best and len(enc.encode(text[:candidate_end])) <= max_tokens:
                best = candidate_end
    return text[:best] if best > 0 else text

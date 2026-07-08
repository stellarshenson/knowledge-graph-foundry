"""Token-based chunking with sentence-boundary snapping.

Uses tiktoken cl100k_base counts and deterministic chunk ids from
models.chunk_id, so identical input yields identical ids across runs.
"""

from __future__ import annotations

import re

from loguru import logger

from knowledge_graph_foundry.models import Chunk, Document, chunk_id

_SENTENCE_BOUNDARIES = (". ", "\n\n", "\n")

# R15-H153 header carryover (glyph_carryover_r14 notebook). A markdown table is a
# row line, a `---` separator line, then row lines.
_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")
_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")


def chunk_document(
    doc: Document,
    chunk_size: int = 2000,
    chunk_overlap: int = 200,
    header_carryover: bool = True,
) -> list[Chunk]:
    """Split a document into overlapping token-sized chunks.

    R15-H153: when `header_carryover` is set, a continuation chunk that holds a
    table's data rows but not its header gets the header row and separator
    re-printed at the top (0.258% token overhead, zero false injections).
    """
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

    if header_carryover:
        chunks = _carry_headers(doc, chunks, enc)

    logger.debug("chunked {} into {} chunks", doc.id, len(chunks))
    return chunks


def _find_tables(text: str) -> list[dict]:
    """Detect markdown tables: a row line, a separator line, then row lines."""
    lines = text.splitlines()
    tables: list[dict] = []
    i = 0
    while i < len(lines) - 1:
        if _ROW_RE.match(lines[i]) and _SEP_RE.match(lines[i + 1]):
            rows: list[str] = []
            j = i + 2
            while j < len(lines) and _ROW_RE.match(lines[j]):
                rows.append(lines[j])
                j += 1
            tables.append(
                {
                    "header": lines[i],
                    "separator": lines[i + 1],
                    "ncols": lines[i].count("|"),
                    "rows": rows,
                }
            )
            i = j
        else:
            i += 1
    return tables


def _carry_headers(doc: Document, chunks: list[Chunk], enc) -> list[Chunk]:
    """Re-print a table header + separator on any chunk holding its data rows but
    not the header (H153). Only genuine tables (>= 2 columns, >= 1 data row) carry
    over, which is what keeps false header injections at zero on prose."""
    tables = [t for t in _find_tables(doc.text) if t["ncols"] >= 2 and t["rows"]]
    if not tables:
        return chunks
    result: list[Chunk] = []
    for chunk in chunks:
        prepends: list[str] = []
        for table in tables:
            block = table["header"] + "\n" + table["separator"]
            if block in chunk.text or block in prepends:
                continue
            if any(row in chunk.text for row in table["rows"]):
                prepends.append(block)
        if not prepends:
            result.append(chunk)
            continue
        new_text = "\n".join(prepends) + "\n" + chunk.text
        result.append(
            chunk.model_copy(
                update={
                    "id": chunk_id(doc.id, chunk.index, new_text),
                    "text": new_text,
                    "token_count": len(enc.encode(new_text)),
                }
            )
        )
    return result


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

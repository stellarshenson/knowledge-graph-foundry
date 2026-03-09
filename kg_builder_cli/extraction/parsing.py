"""Document parsers for PDF, TXT, MD, and DOCX formats."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from kg_builder_cli.types.document import TextSegment


def parse_document(file_path: Path) -> list[TextSegment]:
    """Parse a document into text segments based on file extension.

    Supported formats:
    - .pdf  -> pymupdf4llm (markdown with page chunks)
    - .txt, .md -> plain text read
    - .docx -> python-docx paragraph extraction
    """
    suffix = file_path.suffix.lower()
    source = str(file_path)

    if suffix == ".pdf":
        return _parse_pdf(file_path, source)
    elif suffix in (".txt", ".md"):
        return _parse_text(file_path, source)
    elif suffix == ".docx":
        return _parse_docx(file_path, source)
    else:
        msg = f"Unsupported file format: {suffix}"
        raise ValueError(msg)


def _parse_pdf(file_path: Path, source: str) -> list[TextSegment]:
    """Parse PDF using pymupdf4llm with page chunking."""
    import pymupdf4llm

    logger.info("Parsing PDF: {}", file_path.name)
    page_chunks = pymupdf4llm.to_markdown(str(file_path), page_chunks=True)

    segments: list[TextSegment] = []
    for chunk in page_chunks:
        text = chunk.get("text", "")
        if not text.strip():
            continue
        metadata = chunk.get("metadata", {})
        page = metadata.get("page", 0)
        segments.append(
            TextSegment(
                text=text,
                page=page,
                source_path=source,
            )
        )

    logger.info("Parsed {} page segments from {}", len(segments), file_path.name)
    return segments


def _parse_text(file_path: Path, source: str) -> list[TextSegment]:
    """Parse plain text or markdown file as a single segment."""
    logger.info("Parsing text file: {}", file_path.name)
    text = file_path.read_text(encoding="utf-8")
    return [
        TextSegment(
            text=text,
            page=0,
            source_path=source,
        )
    ]


def _parse_docx(file_path: Path, source: str) -> list[TextSegment]:
    """Parse DOCX using python-docx to extract paragraph text."""
    from docx import Document

    logger.info("Parsing DOCX: {}", file_path.name)
    doc = Document(str(file_path))
    text = "\n".join(para.text for para in doc.paragraphs if para.text.strip())
    return [
        TextSegment(
            text=text,
            page=0,
            source_path=source,
        )
    ]

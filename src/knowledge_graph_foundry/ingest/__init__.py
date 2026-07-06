"""Ingestion: file readers and chunking."""

from knowledge_graph_foundry.ingest.chunking import chunk_document
from knowledge_graph_foundry.ingest.readers import (
    STRUCTURED_EXTENSIONS,
    UNSTRUCTURED_EXTENSIONS,
    UnsupportedFormatError,
    is_structured,
    is_supported,
    iter_source_files,
    read_document,
    read_structured,
)

__all__ = [
    "STRUCTURED_EXTENSIONS",
    "UNSTRUCTURED_EXTENSIONS",
    "UnsupportedFormatError",
    "chunk_document",
    "is_structured",
    "is_supported",
    "iter_source_files",
    "read_document",
    "read_structured",
]

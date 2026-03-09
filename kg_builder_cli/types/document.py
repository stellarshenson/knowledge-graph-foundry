"""Document and chunk models for kg-builder-cli."""

from typing import Optional

from pydantic import BaseModel


class DocumentMetadata(BaseModel):
    source_path: str
    format: str = "unknown"
    page_count: int = 0
    size_bytes: int = 0


class TextSegment(BaseModel):
    text: str
    page: Optional[int] = None
    section: Optional[str] = None
    source_path: str = ""
    byte_offset: int = 0


class ChunkMetadata(BaseModel):
    document_source: str = ""
    page: Optional[int] = None
    section: Optional[str] = None
    chunk_index: int = 0


class Chunk(BaseModel):
    id: str
    text: str
    index: int = 0
    metadata: ChunkMetadata = ChunkMetadata()
    token_count: int = 0

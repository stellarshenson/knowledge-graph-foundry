"""Extraction result models for kg-builder-cli."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from knowledge_graph_foundry.types.document import Chunk


class Entity(BaseModel):
    id: str
    name: str
    type: str
    description: str = ""
    properties: dict = Field(default_factory=dict)
    source_chunks: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    extraction_model: str = ""
    embedding: list[float] | None = None
    labels: list[str] = Field(default_factory=list)


class Relationship(BaseModel):
    source: str
    target: str
    type: str
    description: str = ""
    properties: dict = Field(default_factory=dict)
    source_chunks: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    extraction_model: str = ""


class Fact(BaseModel):
    statement: str
    source_chunks: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    extraction_model: str = ""
    triplet: Optional[dict] = None


class ExtractionMetadata(BaseModel):
    source: str = ""
    model: str = ""
    ontology: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)
    chunk_count: int = 0
    remap_count: int = 0


class ExtractionResult(BaseModel):
    metadata: ExtractionMetadata = ExtractionMetadata()
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    chunks: list[Chunk] = Field(default_factory=list)
    validation: dict = Field(default_factory=dict)

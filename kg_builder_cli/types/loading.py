"""Loading models for kg-builder-cli."""

from pydantic import BaseModel, Field

from .extraction import Entity, Relationship


class LoadBatch(BaseModel):
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    batch_index: int = 0


class LoadResult(BaseModel):
    nodes_created: int = 0
    nodes_merged: int = 0
    relationships_created: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_ms: int = 0


class ValidationReport(BaseModel):
    orphan_entities: list[str] = Field(default_factory=list)
    missing_relationships: list[str] = Field(default_factory=list)
    type_coverage: float = 0.0
    warnings: list[str] = Field(default_factory=list)

"""Core domain models for Knowledge Graph Foundry.

Design rule: entity identity derives from the normalized name (and later,
embedding evidence) - never from type. Types are mutable multi-label
attributes; a dual-role entity (Component and Accessory) is one node with
two labels, not two nodes.
"""

from __future__ import annotations

import hashlib
from typing import Any, Optional

from pydantic import BaseModel, Field


def normalize_name(name: str) -> str:
    """Canonical form of an entity name used for identity and lookup."""
    return " ".join(name.strip().lower().split())


def entity_id(name: str) -> str:
    """Deterministic entity id from the normalized name only (no type)."""
    return "e_" + hashlib.sha1(normalize_name(name).encode()).hexdigest()[:16]


def chunk_id(document_id: str, index: int, text: str) -> str:
    """Deterministic chunk id, stable across runs."""
    digest = hashlib.sha1(f"{document_id}:{index}:{text}".encode()).hexdigest()[:16]
    return f"c_{digest}"


class Chunk(BaseModel):
    id: str
    document_id: str
    index: int
    text: str
    token_count: int


class Document(BaseModel):
    id: str
    path: str
    format: str
    text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class Entity(BaseModel):
    id: str
    name: str
    types: list[str] = Field(default_factory=list)
    description: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[list[float]] = None
    source_documents: list[str] = Field(default_factory=list)
    source_chunks: list[str] = Field(default_factory=list)

    @classmethod
    def create(cls, name: str, types: list[str], **kwargs: Any) -> "Entity":
        return cls(id=entity_id(name), name=name, types=types, **kwargs)


class Relationship(BaseModel):
    source_id: str
    target_id: str
    type: str
    description: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)
    source_documents: list[str] = Field(default_factory=list)
    source_chunks: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """Validated output of one chunk extraction."""

    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)


class TypeDef(BaseModel):
    """One ontology type with evidence counters."""

    name: str
    description: str = ""
    properties: list[str] = Field(default_factory=list)
    encounters: int = 0
    status: str = "emerging"  # emerging | confirmed | cured


class RelationshipTypeDef(BaseModel):
    name: str
    description: str = ""
    encounters: int = 0


class Ontology(BaseModel):
    """The evolving (fluid) or cured type system."""

    purpose: str = ""
    types: dict[str, TypeDef] = Field(default_factory=dict)
    relationship_types: dict[str, RelationshipTypeDef] = Field(default_factory=dict)
    cured: bool = False


class StabilityMetrics(BaseModel):
    """Decision-free stability signals computed after each document."""

    document_index: int
    type_count: int
    entity_count: int
    shannon_entropy: float
    entropy_delta: float
    jsd: float
    chao1_coverage: float
    heaps_beta: Optional[float] = None


class ResolutionDecision(BaseModel):
    """One pairwise merge decision with full evidence for forensics."""

    left_id: str
    right_id: str
    prior: float
    lr_description: float
    lr_embedding: float
    lr_cooccurrence: float
    posterior: float
    decision: str  # merge | defer | block

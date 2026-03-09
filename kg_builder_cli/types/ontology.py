"""Ontology models for kg-builder-cli."""

from typing import Optional

from pydantic import BaseModel, Field


class PropertyDef(BaseModel):
    """Property definition with validation rules."""

    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    allowed_values: list[str] = Field(default_factory=list)
    pattern: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class TypeDef(BaseModel):
    name: str
    description: str = ""
    properties: dict = Field(default_factory=dict)
    property_defs: list[PropertyDef] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    parent: Optional[str] = None


class RelationshipDef(BaseModel):
    name: str
    source_type: str
    target_type: str
    description: str = ""


class OntologyState(BaseModel, frozen=True):
    entity_types: tuple[TypeDef, ...] = ()
    relationship_types: tuple[RelationshipDef, ...] = ()
    coverage: float = 0.0
    variants: dict[str, str] = Field(default_factory=dict)
    confirmed_types: frozenset[str] = frozenset()
    candidate_types: frozenset[str] = frozenset()


class TypeSignal(BaseModel):
    type_name: str
    frequency: int = 1
    source_chunk: str = ""
    is_relationship: bool = False


class NormDiagnostic(BaseModel):
    tier_used: int = 1
    types_count: int = 0
    rels_count: int = 0
    depth: int = 0
    issues_resolved: int = 0

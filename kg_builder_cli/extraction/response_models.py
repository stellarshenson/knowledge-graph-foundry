"""Pydantic response models for structured LLM extraction via instructor."""
from __future__ import annotations

from pydantic import BaseModel, Field


class EntityResponse(BaseModel):
    """Single extracted entity from LLM response."""
    id: str = Field(description="Lowercase ID with underscores, prefixed by type")
    name: str = Field(description="Canonical name as it appears in text")
    type: str = Field(description="Entity type category")
    description: str = Field(default="", description="Brief description from context")
    properties: dict = Field(default_factory=dict, description="Additional attributes")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence")


class RelationshipResponse(BaseModel):
    """Single extracted relationship from LLM response."""
    source: str = Field(description="Source entity ID")
    target: str = Field(description="Target entity ID")
    type: str = Field(description="UPPER_SNAKE_CASE relationship type")
    description: str = Field(default="", description="Brief description")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence")


class ExtractionResponse(BaseModel):
    """Complete extraction response with entities and relationships."""
    entities: list[EntityResponse] = Field(default_factory=list)
    relationships: list[RelationshipResponse] = Field(default_factory=list)


def build_response_model(ontology=None) -> type[BaseModel]:
    """Return the response model, optionally with ontology constraints in json_schema_extra.

    When ontology has entity types, adds them as json_schema_extra hint
    for the LLM. Otherwise returns the static ExtractionResponse.
    """
    if ontology and ontology.entity_types:
        type_names = [t.name for t in ontology.entity_types]

        class ConstrainedExtractionResponse(ExtractionResponse):
            """Extraction response constrained to specific entity types."""
            model_config = {
                "json_schema_extra": {
                    "allowed_entity_types": type_names,
                    "instructions": f"Entity type field must be one of: {', '.join(type_names)}",
                }
            }

        return ConstrainedExtractionResponse

    return ExtractionResponse

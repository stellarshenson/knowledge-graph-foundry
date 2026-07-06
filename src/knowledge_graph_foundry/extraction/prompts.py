"""Extraction prompts: purpose as guiding principle, current ontology state injected."""

from __future__ import annotations

from knowledge_graph_foundry.models import Ontology

_SYSTEM_TEMPLATE = """You extract entities and relationships for a knowledge graph.

Graph purpose (guiding principle): {purpose}
Extract what serves this purpose; skip what does not.

Current entity types:
{types}

Current relationship types:
{relationship_types}

Rules:
- Prefer existing types; introduce a genuinely new type only when nothing existing fits
- Entity type names are PascalCase (e.g. OperatingMode)
- Relationship type names are UPPER_SNAKE_CASE (e.g. SUPPORTS_MODE)
- Use specific entity names, never generic references like "the device" or "it"
- Capture specifications as key-value properties; split numeric specs into value
  and unit (e.g. "pressure": "20", "pressure_unit": "cmH2O")
- A measured value, range, dimension, weight, duration, warranty period or rating
  is NEVER an entity and NEVER a type - record it as a property on the entity it
  describes (the device carries "pressure_range": "4-20 cmH2O"); do not create
  types like PressureRange, Weight, Warranty or Dimension"""


def _format_types(ontology: Ontology) -> str:
    if not ontology.types:
        return "(none yet - discover types that serve the purpose)"
    return "\n".join(
        f"- {t.name} ({t.status}): {t.description}".rstrip(": ") for t in ontology.types.values()
    )


def _format_relationship_types(ontology: Ontology) -> str:
    if not ontology.relationship_types:
        return "(none yet - discover relationship types that serve the purpose)"
    return "\n".join(f"- {r.name}" for r in ontology.relationship_types.values())


def _format_names(names: list[str]) -> str:
    if not names:
        return "(none)"
    return "\n".join(f"- {n}" for n in names)


def extraction_messages(chunk_text: str, purpose: str, ontology: Ontology) -> list[dict]:
    """Build the system+user messages for one chunk extraction."""
    system = _SYSTEM_TEMPLATE.format(
        purpose=purpose,
        types=_format_types(ontology),
        relationship_types=_format_relationship_types(ontology),
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": chunk_text},
    ]


_ENTITY_TEMPLATE = """You extract ENTITIES ONLY for a knowledge graph. Do not extract relationships.

Graph purpose (guiding principle): {purpose}
Extract entities that serve this purpose; skip what does not.

Current entity types:
{types}

Current relationship types:
{relationship_types}

Rules:
- Prefer existing types; introduce a genuinely new type only when nothing existing fits
- Entity type names are PascalCase (e.g. OperatingMode)
- Use specific entity names, never generic references like "the device" or "it"
- Capture specifications as key-value properties; split numeric specs into value
  and unit (e.g. "pressure": "20", "pressure_unit": "cmH2O")
- A measured value, range, dimension, weight, duration, warranty period or rating
  is NEVER an entity and NEVER a type - record it as a property on the entity it
  describes (the device carries "pressure_range": "4-20 cmH2O"); do not create
  types like PressureRange, Weight, Warranty or Dimension
- Return an empty relationships list"""


_RELATION_TEMPLATE = """You extract RELATIONSHIPS ONLY for a knowledge graph, connecting the given entities.

Graph purpose (guiding principle): {purpose}
Extract relationships that serve this purpose; skip what does not.

Current entity types:
{types}

Current relationship types:
{relationship_types}

Entities already extracted from this text (use these exact names as source/target):
{entity_names}

Rules:
- Only create relationships between the entities listed above
- Relationship type names are UPPER_SNAKE_CASE (e.g. SUPPORTS_MODE)
- Prefer existing relationship types; introduce a new one only when nothing fits
- Return an empty entities list"""


_GLEANING_TEMPLATE = """You review an extraction for a knowledge graph and find what was MISSED.

Graph purpose (guiding principle): {purpose}
Extract only items that serve this purpose.

Current entity types:
{types}

Current relationship types:
{relationship_types}

Already extracted (do NOT repeat these):
{existing_names}

List entities and relationships that are present in the text but NOT in the list above.
Follow the same naming rules: entity types PascalCase, relationship types UPPER_SNAKE_CASE,
specific entity names only. A measured value, range or rating is never an entity or a
type - it belongs as a property on the entity it describes. If nothing was missed,
return empty lists."""


def entity_only_messages(chunk_text: str, purpose: str, ontology: Ontology) -> list[dict]:
    """Build messages for the entity-only pass of split extraction."""
    system = _ENTITY_TEMPLATE.format(
        purpose=purpose,
        types=_format_types(ontology),
        relationship_types=_format_relationship_types(ontology),
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": chunk_text},
    ]


def relation_only_messages(
    chunk_text: str, entity_names: list[str], purpose: str, ontology: Ontology
) -> list[dict]:
    """Build messages for the relation-only pass, given the extracted entity names."""
    system = _RELATION_TEMPLATE.format(
        purpose=purpose,
        types=_format_types(ontology),
        relationship_types=_format_relationship_types(ontology),
        entity_names=_format_names(entity_names),
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": chunk_text},
    ]


def gleaning_messages(
    chunk_text: str, existing_names: list[str], purpose: str, ontology: Ontology
) -> list[dict]:
    """Build messages for a gleaning round listing items missed so far."""
    system = _GLEANING_TEMPLATE.format(
        purpose=purpose,
        types=_format_types(ontology),
        relationship_types=_format_relationship_types(ontology),
        existing_names=_format_names(existing_names),
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": chunk_text},
    ]

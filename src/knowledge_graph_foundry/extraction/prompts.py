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
  and unit (e.g. "pressure": "20", "pressure_unit": "cmH2O")"""


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

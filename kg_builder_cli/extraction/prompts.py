"""Extraction prompt construction for LLM-based entity and relationship extraction."""

from __future__ import annotations

from kg_builder_cli.types.document import Chunk
from kg_builder_cli.types.ontology import OntologyState

_CONSTRAINED_PROMPT = """\
Extract entities and relationships from the following text.

**Allowed entity types**: {entity_types}

IMPORTANT: You MUST only use entity types from the list above. Do NOT invent new types.

For each entity, provide:
- id: lowercase with underscores, prefixed by type (e.g., person_john_smith)
- name: the canonical name as it appears in the text
- type: MUST be exactly one of the allowed entity types listed above - no exceptions
- description: MUST include specific numeric values, measurements, ranges, and units from the text. Never use generic descriptions like "a specification" - always include the actual values (e.g., "Weight: 1.6 kg (3.5 lbs) without humidifier" not "weight specification")
- properties: dict of any additional attributes mentioned, including numeric values as separate keys
- confidence: 0.0 to 1.0

For each relationship, provide:
- source: entity id of the source
- target: entity id of the target
- type: UPPER_SNAKE_CASE relationship name
- description: brief description of the relationship
- confidence: 0.0 to 1.0

Return ONLY valid JSON in this exact format:
{{
  "entities": [
    {{"id": "type_name", "name": "Name", "type": "Type", "description": "...", "properties": {{}}, "confidence": 0.9}}
  ],
  "relationships": [
    {{"source": "type_name1", "target": "type_name2", "type": "RELATIONSHIP_TYPE", "description": "...", "confidence": 0.9}}
  ]
}}

Text:
{text}"""

_FREE_PROMPT = """\
Extract all entities and relationships from the following text.

For each entity, provide:
- id: lowercase with underscores, prefixed by type (e.g., person_john_smith)
- name: the canonical name as it appears in the text
- type: a concise category label (e.g., Person, Organization, Location, Product)
- description: MUST include specific numeric values, measurements, ranges, and units from the text. Never use generic descriptions - always include the actual values mentioned in context
- properties: dict of any additional attributes mentioned, including numeric values as separate keys
- confidence: 0.0 to 1.0

For each relationship, provide:
- source: entity id of the source
- target: entity id of the target
- type: UPPER_SNAKE_CASE relationship name
- description: brief description of the relationship
- confidence: 0.0 to 1.0

Return ONLY valid JSON in this exact format:
{{
  "entities": [
    {{"id": "type_name", "name": "Name", "type": "Type", "description": "...", "properties": {{}}, "confidence": 0.9}}
  ],
  "relationships": [
    {{"source": "type_name1", "target": "type_name2", "type": "RELATIONSHIP_TYPE", "description": "...", "confidence": 0.9}}
  ]
}}

Text:
{text}"""


_INTENT_PREFIX = """\
**Use case context**: {intent}

Focus extraction on entities and relationships relevant to this use case.

"""


def build_extraction_prompt(
    chunk: Chunk,
    ontology: OntologyState | None = None,
    intent: str | None = None,
) -> str:
    """Build an extraction prompt for a chunk.

    If ontology is provided and has entity types, uses a constrained prompt
    listing the allowed types. Otherwise uses a free extraction prompt.
    If intent is provided, prepends use case context to guide extraction.
    """
    prefix = _INTENT_PREFIX.format(intent=intent) if intent else ""

    if ontology and ontology.entity_types:
        type_names = ", ".join(t.name for t in ontology.entity_types)
        return prefix + _CONSTRAINED_PROMPT.format(
            entity_types=type_names,
            text=chunk.text,
        )

    return prefix + _FREE_PROMPT.format(text=chunk.text)

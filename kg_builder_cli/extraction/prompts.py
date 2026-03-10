"""Extraction prompt construction for LLM-based entity and relationship extraction."""

from __future__ import annotations

from kg_builder_cli.types.document import Chunk
from kg_builder_cli.types.ontology import OntologyState

_CONSTRAINED_PROMPT = """\
Extract entities and relationships from the following text.

{entity_types_block}
{relationship_types_block}
{property_defs_block}
IMPORTANT: You MUST only use entity types from the lists above. Do NOT invent new types.
Strongly prefer established types over discovered types.

For each entity, provide:
- id: lowercase with underscores, prefixed by type (e.g., person_john_smith)
- name: the canonical name as it appears in the text
- type: MUST be exactly one of the allowed entity types listed above - no exceptions
- description: MUST include specific numeric values, measurements, ranges, and units from the text. Never use generic descriptions like "a specification" - always include the actual values (e.g., "Weight: 1.6 kg (3.5 lbs) without humidifier" not "weight specification"). For specifications, always state the value, unit, and any conditions or ranges
- properties: dict of structured attributes using the EXACT property names listed above per type. For example Product must include {{"model_name": "AirSense 10"}}, Specification must include {{"value": "4-20", "unit": "hPa"}}, Standard must include {{"standard_id": "IEC 60601-1"}}, Organization must include {{"role": "manufacturer"}}. Always populate these type-specific properties when the information is available in the text
- confidence: 0.0 to 1.0

For each relationship, provide:
- source: entity id of the source
- target: entity id of the target
- type: UPPER_SNAKE_CASE relationship name from the allowed relationship types above
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


def _build_entity_types_block(ontology: OntologyState) -> str:
    """Build entity types block with descriptions and seed vs discovered distinction."""
    confirmed = ontology.confirmed_types
    emerging = ontology.emerging_types
    frequencies = ontology.type_frequencies

    established_lines = []
    discovered_lines = []

    for type_def in ontology.entity_types:
        freq = frequencies.get(type_def.name, 0)
        desc_suffix = f": {type_def.description}" if type_def.description else ""

        # Exemplar hint
        exemplars = ontology.type_exemplars.get(type_def.name, ())
        if exemplars:
            examples = ", ".join(e.name for e in exemplars[:5])
            exemplar_hint = f" (e.g., {examples})"
        else:
            exemplar_hint = ""

        if type_def.name in confirmed:
            freq_label = f" (seen {freq}x)" if freq > 0 else ""
            established_lines.append(f"- {type_def.name}{desc_suffix}{exemplar_hint}{freq_label}")
        elif type_def.name in emerging:
            discovered_lines.append(
                f"- {type_def.name}{desc_suffix}{exemplar_hint} (seen {freq}x)"
            )

    parts = []
    if established_lines:
        parts.append(
            "**Established entity types** (from ontology, strongly prefer these):\n"
            + "\n".join(established_lines)
        )
    if discovered_lines:
        parts.append(
            "**Discovered entity types** (use only when no established type fits):\n"
            + "\n".join(discovered_lines)
        )

    if not parts:
        type_names = ", ".join(t.name for t in ontology.entity_types)
        return f"**Allowed entity types**: {type_names}"

    return "\n\n".join(parts)


def _build_relationship_types_block(ontology: OntologyState) -> str:
    """Build relationship types block with descriptions and source/target constraints."""
    if not ontology.relationship_types:
        return ""

    lines = []
    for rel_def in ontology.relationship_types:
        parts = [f"- {rel_def.name}"]
        if rel_def.source_type and rel_def.target_type:
            parts.append(f": {rel_def.source_type} -> {rel_def.target_type}")
        if rel_def.description:
            parts.append(f" ({rel_def.description})")
        lines.append("".join(parts))

    return "**Allowed relationship types** (use these exact names):\n" + "\n".join(lines)


def _build_property_defs_block(ontology: OntologyState) -> str:
    """Build a property definitions block from ontology type definitions."""
    lines = []
    for type_def in ontology.entity_types:
        if not type_def.property_defs:
            continue
        props = ", ".join(f"{p.name} ({p.type})" for p in type_def.property_defs)
        lines.append(f"- **{type_def.name}**: {props}")

    if not lines:
        return ""
    return "**Required properties per type**:\n" + "\n".join(lines)


def build_extraction_prompt(
    chunk: Chunk,
    ontology: OntologyState | None = None,
    intent: str | None = None,
) -> str:
    """Build an extraction prompt for a chunk.

    If ontology is provided and has entity types, uses a constrained prompt
    listing the allowed types with descriptions and relationship definitions.
    Otherwise uses a free extraction prompt.
    If intent is provided, prepends use case context to guide extraction.
    """
    prefix = _INTENT_PREFIX.format(intent=intent) if intent else ""

    if ontology and ontology.entity_types:
        entity_types_block = _build_entity_types_block(ontology)
        relationship_types_block = _build_relationship_types_block(ontology)
        property_defs_block = _build_property_defs_block(ontology)
        return prefix + _CONSTRAINED_PROMPT.format(
            entity_types_block=entity_types_block,
            relationship_types_block=relationship_types_block,
            property_defs_block=property_defs_block,
            text=chunk.text,
        )

    return prefix + _FREE_PROMPT.format(text=chunk.text)

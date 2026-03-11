"""Extraction prompt construction for LLM-based entity and relationship extraction."""

from __future__ import annotations

from kg_builder_cli.types.document import Chunk
from kg_builder_cli.types.ontology import OntologyState

_CONSTRAINED_PROMPT = """\
Extract entities and relationships from the following text.

{entity_types_block}
{relationship_types_block}
{property_defs_block}
{resolution_guidance_block}
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
- id: lowercase with underscores, prefixed by type (e.g., product_dreamstation)
- name: the canonical name as it appears in the text
- type: a concise PascalCase category label. Prefer reusing these standard types when they fit: Product, Component, Specification, Feature, Organization, Standard, Accessory, Setting, Interface, Section, Location, MedicalCondition. Use other types only when none of these fit
- description: MUST include specific numeric values, measurements, ranges, and units from the text. Never use generic descriptions - always include the actual values mentioned in context
- properties: dict of structured attributes. For Product include {{"model_name": "..."}}, for Specification include {{"value": "...", "unit": "..."}}, for Organization include {{"role": "manufacturer"|"distributor"|...}}, for Standard include {{"standard_id": "..."}}
- confidence: 0.0 to 1.0

For each relationship, use these standard UPPER_SNAKE_CASE names when applicable:
- MANUFACTURES: Organization -> Product
- HAS_COMPONENT: Product -> Component
- HAS_FEATURE: Product -> Feature
- HAS_SPECIFICATION: Product -> Specification (link products to their technical specs)
- SUPPORTS_MODE: Product -> Feature/Setting (operating modes like CPAP, Auto, Bilevel)
- COMPLIES_WITH: Product -> Standard
- TREATS: Product -> MedicalCondition
- HAS_ACCESSORY: Product -> Accessory
- PART_OF: Component -> Product or Section -> Document
Use other relationship names only when none of these fit.

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


def _build_resolution_guidance_block(ontology: OntologyState) -> str:
    """Build resolution guidance from intent (immutable) + guide (evolved).

    Combined length is capped at MAX_RESOLUTION_PROMPT_TOKENS. The intent
    is always included in full; the guide is truncated from the end if
    the combined length exceeds the limit.
    """
    from kg_builder_cli.settings.defaults import MAX_RESOLUTION_PROMPT_TOKENS

    intent = ontology.resolution_intent.strip()
    guide = ontology.resolution_guide.strip()

    if not intent and not guide:
        return ""

    parts = []
    if intent:
        parts.append(
            f"**Use case context**: {intent}\n\n"
            "Focus extraction on entities and relationships relevant to this use case."
        )
    if guide:
        parts.append(f"**Learned disambiguation rules** (from previous runs):\n{guide}")

    combined = "\n\n".join(parts)

    # Approximate token count (words / 0.75)
    word_count = len(combined.split())
    approx_tokens = int(word_count / 0.75)

    if approx_tokens > MAX_RESOLUTION_PROMPT_TOKENS and guide:
        # Truncate guide, keep intent in full
        if intent:
            intent_words = len(intent.split())
            budget = int(MAX_RESOLUTION_PROMPT_TOKENS * 0.75) - intent_words
            if budget > 0:
                guide_words = guide.split()[:budget]
                guide = " ".join(guide_words) + " [truncated]"
            else:
                guide = ""
        else:
            guide_words = guide.split()[: int(MAX_RESOLUTION_PROMPT_TOKENS * 0.75)]
            guide = " ".join(guide_words) + " [truncated]"

        parts = []
        if intent:
            parts.append(
                f"**Use case context**: {intent}\n\n"
                "Focus extraction on entities and relationships relevant to this use case."
            )
        if guide:
            parts.append(f"**Learned disambiguation rules** (from previous runs):\n{guide}")
        combined = "\n\n".join(parts)

    return combined


def build_extraction_prompt(
    chunk: Chunk,
    ontology: OntologyState | None = None,
) -> str:
    """Build an extraction prompt for a chunk.

    If ontology is provided and has entity types, uses a constrained prompt
    listing the allowed types with descriptions and relationship definitions.
    Otherwise uses a free extraction prompt.

    The resolution_intent (use case context) and resolution_guide (learned rules)
    flow through ontology.resolution_intent and ontology.resolution_guide,
    rendered by _build_resolution_guidance_block().
    """
    if ontology and ontology.entity_types:
        entity_types_block = _build_entity_types_block(ontology)
        relationship_types_block = _build_relationship_types_block(ontology)
        property_defs_block = _build_property_defs_block(ontology)
        resolution_guidance_block = _build_resolution_guidance_block(ontology)
        return _CONSTRAINED_PROMPT.format(
            entity_types_block=entity_types_block,
            relationship_types_block=relationship_types_block,
            property_defs_block=property_defs_block,
            resolution_guidance_block=resolution_guidance_block,
            text=chunk.text,
        )

    # Free prompt: intent still flows through ontology if provided
    prefix = ""
    if ontology and ontology.resolution_intent:
        prefix = (
            f"**Use case context**: {ontology.resolution_intent}\n\n"
            "Focus extraction on entities and relationships relevant to this use case.\n\n"
        )
    return prefix + _FREE_PROMPT.format(text=chunk.text)

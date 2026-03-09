"""Entity and relationship deduplication."""

from __future__ import annotations

from loguru import logger

from kg_builder_cli.types.extraction import Entity, Relationship


def deduplicate(
    entities: list[Entity],
    relationships: list[Relationship],
) -> tuple[list[Entity], list[Relationship]]:
    """Deduplicate entities and relationships.

    Entities are merged by (type, id) tuple:
    - Keeps longest description
    - Merges source_chunks lists
    - Averages confidence
    - Merges properties (later overwrites earlier)

    Relationships are deduplicated by (source, target, type) tuple.
    """
    deduped_entities = _dedup_entities(entities)
    deduped_rels = _dedup_relationships(relationships)

    logger.info(
        "Dedup: {} -> {} entities, {} -> {} relationships",
        len(entities),
        len(deduped_entities),
        len(relationships),
        len(deduped_rels),
    )
    return deduped_entities, deduped_rels


def _dedup_entities(entities: list[Entity]) -> list[Entity]:
    """Merge entities sharing the same (type, id) key."""
    merged: dict[tuple[str, str], Entity] = {}

    for entity in entities:
        key = (entity.type.lower(), entity.id.lower())
        if key not in merged:
            copy = entity.model_copy()
            copy.id = entity.id.lower()
            merged[key] = copy
            continue

        existing = merged[key]

        # Keep longest description
        if len(entity.description) > len(existing.description):
            existing.description = entity.description

        # Merge source chunks
        seen_chunks = set(existing.source_chunks)
        for chunk_id in entity.source_chunks:
            if chunk_id not in seen_chunks:
                existing.source_chunks.append(chunk_id)
                seen_chunks.add(chunk_id)

        # Average confidence
        existing.confidence = (existing.confidence + entity.confidence) / 2.0

        # Merge properties (later overwrites)
        existing.properties.update(entity.properties)

        # Keep longer name if available
        if len(entity.name) > len(existing.name):
            existing.name = entity.name

    return list(merged.values())


def _dedup_relationships(relationships: list[Relationship]) -> list[Relationship]:
    """Deduplicate relationships by (source, target, type) key."""
    merged: dict[tuple[str, str, str], Relationship] = {}

    for rel in relationships:
        key = (rel.source.lower(), rel.target.lower(), rel.type.lower())
        if key not in merged:
            copy = rel.model_copy()
            copy.source = rel.source.lower()
            copy.target = rel.target.lower()
            merged[key] = copy
            continue

        existing = merged[key]

        # Keep longest description
        if len(rel.description) > len(existing.description):
            existing.description = rel.description

        # Merge source chunks
        seen_chunks = set(existing.source_chunks)
        for chunk_id in rel.source_chunks:
            if chunk_id not in seen_chunks:
                existing.source_chunks.append(chunk_id)
                seen_chunks.add(chunk_id)

        # Average confidence
        existing.confidence = (existing.confidence + rel.confidence) / 2.0

        # Merge properties
        existing.properties.update(rel.properties)

    return list(merged.values())

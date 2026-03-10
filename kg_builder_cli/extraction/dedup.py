"""Entity and relationship deduplication."""

from __future__ import annotations

import hashlib

from loguru import logger

from kg_builder_cli.extraction.normalization import normalize_entity_name
from kg_builder_cli.types.extraction import Entity, Relationship


def normalize_entity_ids(
    entities: list[Entity],
    relationships: list[Relationship],
) -> tuple[list[Entity], list[Relationship]]:
    """Normalize entity IDs to deterministic hashes for cross-document merging.

    Generates IDs as ``{type_lower}_{sha1_prefix}`` where the SHA-1 input is
    ``{type_lower}:{name_lower_stripped}``.  This ensures the same real-world
    entity receives the same ID regardless of which document it was extracted
    from, so that Neo4j MERGE consolidates them on load.

    Also rewrites ``relationship.source`` and ``relationship.target`` to match
    the new entity IDs.
    """
    old_to_new: dict[str, str] = {}

    for entity in entities:
        canon = f"{entity.type.lower()}:{normalize_entity_name(entity.name)}"
        hash_prefix = hashlib.sha1(canon.encode()).hexdigest()[:12]
        new_id = f"{entity.type.lower()}_{hash_prefix}"

        if entity.id != new_id:
            old_to_new[entity.id] = new_id
        entity.id = new_id

    # Rewrite relationship endpoints
    for rel in relationships:
        if rel.source in old_to_new:
            rel.source = old_to_new[rel.source]
        if rel.target in old_to_new:
            rel.target = old_to_new[rel.target]

    if old_to_new:
        logger.info("ID normalization: renormalized {} entity IDs", len(old_to_new))
    else:
        logger.debug("ID normalization: all IDs already canonical")

    return entities, relationships


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

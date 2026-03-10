"""Entity resolution via multi-signal matching and graph-based clustering."""

from __future__ import annotations

from loguru import logger
import numpy as np

from kg_builder_cli.extraction.normalization import normalize_entity_name
from kg_builder_cli.types.extraction import Entity


class _UnionFind:
    """Union-Find for transitive entity clustering."""

    def __init__(self, n: int):
        self._parent = list(range(n))
        self._rank = [0] * n

    def find(self, x: int) -> int:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1


def resolve_entities(
    entities: list[Entity],
    threshold: float = 0.85,
    use_embeddings: bool = False,
    embedding_threshold: float = 0.80,
    name_threshold: float = 0.65,
    type_frequencies: dict[str, int] | None = None,
) -> list[Entity]:
    """Merge near-duplicate entities within type blocks using multi-signal matching.

    Signals:
    1. Levenshtein ratio on normalized names (strips generic suffixes)
    2. Cosine similarity on embeddings (if available and use_embeddings=True)

    Matching logic:
    - If embeddings available: name_sim >= name_threshold AND cosine >= embedding_threshold
    - If no embeddings: name_sim >= threshold (backward-compatible)

    Connected components on the similarity graph determine merge clusters.
    """
    if len(entities) <= 1:
        return entities

    from Levenshtein import ratio as levenshtein_ratio

    # Group by type
    type_blocks: dict[str, list[Entity]] = {}
    for entity in entities:
        type_blocks.setdefault(entity.type, []).append(entity)

    resolved: list[Entity] = []
    for entity_type, block in type_blocks.items():
        has_embeddings = use_embeddings and any(e.embedding for e in block)
        merged_block = _resolve_block(
            block,
            threshold=threshold,
            ratio_fn=levenshtein_ratio,
            use_embeddings=has_embeddings,
            embedding_threshold=embedding_threshold,
            name_threshold=name_threshold,
        )
        resolved.extend(merged_block)

    # Cross-type resolution: merge entities with identical normalized names
    resolved, id_map = _resolve_cross_type(resolved, type_frequencies)

    merge_count = len(entities) - len(resolved)
    if merge_count > 0:
        logger.info(
            "Resolution: {} -> {} entities ({} merged)",
            len(entities),
            len(resolved),
            merge_count,
        )

    # Store ID map on module level for caller access
    resolve_entities._last_id_map = id_map

    return resolved


# Initialize the class attribute
resolve_entities._last_id_map = {}


# Static fallback: higher number = more specific, preferred when merging
_TYPE_PRIORITY_FALLBACK = {
    "Specification": 8,
    "Component": 7,
    "Feature": 6,
    "WorkMode": 5,
    "Product": 4,
    "MedicalCondition": 3,
    "Standard": 2,
    "Organization": 1,
}


def _build_type_priority(frequencies: dict[str, int] | None) -> dict[str, int]:
    """Build type priority from frequency counts.

    Higher frequency = higher priority. Falls back to static priority
    when no frequencies are provided.
    """
    if not frequencies:
        return _TYPE_PRIORITY_FALLBACK
    # Sort by frequency descending, assign priority (highest freq = highest rank)
    sorted_types = sorted(frequencies.items(), key=lambda x: x[1], reverse=True)
    dynamic = {t: i + 1 for i, (t, _) in enumerate(reversed(sorted_types))}
    # Merge: dynamic overrides fallback
    merged = dict(_TYPE_PRIORITY_FALLBACK)
    merged.update(dynamic)
    return merged


def _resolve_cross_type(
    entities: list[Entity],
    type_frequencies: dict[str, int] | None = None,
) -> tuple[list[Entity], dict[str, str]]:
    """Merge entities with identical normalized names across different types.

    When two entities share the same normalized name but have different types,
    keep the more specific type (higher priority) and merge the other into it.

    Returns (resolved_entities, id_mapping) where id_mapping maps merged entity
    IDs to their canonical entity IDs (for relationship rewiring).
    """
    from collections import defaultdict

    type_priority = _build_type_priority(type_frequencies)

    name_groups: dict[str, list[int]] = defaultdict(list)
    for idx, entity in enumerate(entities):
        norm = normalize_entity_name(entity.name)
        name_groups[norm].append(idx)

    merged_indices: set[int] = set()
    canonicals: dict[int, Entity] = {}
    id_map: dict[str, str] = {}

    for norm_name, indices in name_groups.items():
        if len(indices) <= 1:
            continue

        # Pick the one with highest type priority as canonical
        best_idx = max(
            indices,
            key=lambda i: type_priority.get(entities[i].type, 0),
        )

        canonical = entities[best_idx].model_copy()
        for idx in indices:
            if idx == best_idx:
                continue
            id_map[entities[idx].id] = canonical.id
            canonical = _merge_entities(canonical, entities[idx])
            merged_indices.add(idx)
        canonicals[best_idx] = canonical

    # Build result
    result: list[Entity] = []
    for idx, entity in enumerate(entities):
        if idx in merged_indices:
            continue
        if idx in canonicals:
            result.append(canonicals[idx])
        else:
            result.append(entity)

    cross_merged = len(entities) - len(result)
    if cross_merged > 0:
        logger.info("Cross-type resolution: merged {} entities", cross_merged)

    return result, id_map


def rewire_relationships(
    relationships: list,
    id_map: dict[str, str],
) -> list:
    """Rewire relationship endpoints after entity merges."""
    if not id_map:
        return relationships

    rewired = 0
    for rel in relationships:
        if rel.source in id_map:
            rel.source = id_map[rel.source]
            rewired += 1
        if rel.target in id_map:
            rel.target = id_map[rel.target]
            rewired += 1

    if rewired > 0:
        logger.info("Rewired {} relationship endpoints after cross-type merge", rewired)

    return relationships


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    va = np.array(a)
    vb = np.array(b)
    dot = np.dot(va, vb)
    norm = np.linalg.norm(va) * np.linalg.norm(vb)
    if norm == 0:
        return 0.0
    return float(dot / norm)


def _resolve_block(
    entities: list[Entity],
    threshold: float,
    ratio_fn,
    use_embeddings: bool = False,
    embedding_threshold: float = 0.80,
    name_threshold: float = 0.65,
) -> list[Entity]:
    """Resolve near-duplicates within a single type block."""
    n = len(entities)
    if n <= 1:
        return entities

    uf = _UnionFind(n)

    # Pre-compute normalized names
    norm_names = [normalize_entity_name(e.name) for e in entities]

    # Compare all pairs within block
    for i in range(n):
        for j in range(i + 1, n):
            name_sim = ratio_fn(norm_names[i], norm_names[j])

            if use_embeddings and entities[i].embedding and entities[j].embedding:
                cosine_sim = _cosine_similarity(entities[i].embedding, entities[j].embedding)
                # Multi-signal: both must pass their thresholds
                if name_sim >= name_threshold and cosine_sim >= embedding_threshold:
                    uf.union(i, j)
            else:
                # Fallback: name similarity only with normalized names
                if name_sim >= threshold:
                    uf.union(i, j)

    # Build clusters
    clusters: dict[int, list[int]] = {}
    for i in range(n):
        root = uf.find(i)
        clusters.setdefault(root, []).append(i)

    # Merge each cluster
    result: list[Entity] = []
    for indices in clusters.values():
        if len(indices) == 1:
            result.append(entities[indices[0]])
            continue

        # Start with first entity as base, merge others in
        canonical = entities[indices[0]].model_copy()
        for idx in indices[1:]:
            canonical = _merge_entities(canonical, entities[idx])
        result.append(canonical)

    return result


def _merge_entities(canonical: Entity, duplicate: Entity) -> Entity:
    """Merge duplicate into canonical entity.

    - Longest name becomes canonical name
    - Longest description kept
    - source_chunks unioned
    - Confidence averaged
    - Properties merged (later overwrites)
    - Embedding kept from canonical (first in cluster)
    """
    # Longest name
    if len(duplicate.name) > len(canonical.name):
        canonical.name = duplicate.name

    # Longest description
    if len(duplicate.description) > len(canonical.description):
        canonical.description = duplicate.description

    # Union source chunks
    seen = set(canonical.source_chunks)
    for chunk_id in duplicate.source_chunks:
        if chunk_id not in seen:
            canonical.source_chunks.append(chunk_id)
            seen.add(chunk_id)

    # Average confidence
    canonical.confidence = (canonical.confidence + duplicate.confidence) / 2.0

    # Merge properties
    canonical.properties.update(duplicate.properties)

    return canonical

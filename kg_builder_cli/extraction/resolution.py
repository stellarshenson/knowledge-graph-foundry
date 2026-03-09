"""Entity resolution via fuzzy name matching within type blocks."""
from __future__ import annotations

from loguru import logger

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
    entities: list[Entity], threshold: float = 0.85
) -> list[Entity]:
    """Merge near-duplicate entities within type blocks using fuzzy name matching.

    Entities are grouped by type, then within each group Levenshtein ratio
    is computed for all pairs. Pairs above threshold are merged transitively
    via union-find. The canonical entity in each cluster gets the longest
    name, longest description, union of source_chunks, and averaged confidence.
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
        merged_block = _resolve_block(block, threshold, levenshtein_ratio)
        resolved.extend(merged_block)

    merge_count = len(entities) - len(resolved)
    if merge_count > 0:
        logger.info(
            "Resolution: {} -> {} entities ({} merged)",
            len(entities),
            len(resolved),
            merge_count,
        )
    return resolved


def _resolve_block(
    entities: list[Entity], threshold: float, ratio_fn
) -> list[Entity]:
    """Resolve near-duplicates within a single type block."""
    n = len(entities)
    if n <= 1:
        return entities

    uf = _UnionFind(n)

    # Compare all pairs within block
    for i in range(n):
        for j in range(i + 1, n):
            name_i = entities[i].name.lower().strip()
            name_j = entities[j].name.lower().strip()
            sim = ratio_fn(name_i, name_j)
            if sim >= threshold:
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

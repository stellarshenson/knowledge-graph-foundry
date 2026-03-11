"""Entity resolution via multi-signal matching and graph-based clustering."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from loguru import logger
import numpy as np

from kg_builder_cli.extraction.normalization import normalize_entity_name
from kg_builder_cli.types.extraction import Entity

if TYPE_CHECKING:
    from kg_builder_cli.extraction.deferred_dedup import DeferredDedupBuffer
    from kg_builder_cli.types.ontology import OntologyState


class CrossTypeStat(NamedTuple):
    """Record of a cross-type pair encounter during resolution."""

    norm_name: str
    type_a: str
    type_b: str
    doc_index: int
    action: str  # "merged", "deferred", "blocked", "hierarchy_merge", "multi_facet"


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
    description_threshold: float = 0.3,
    cross_type_embedding_threshold: float = 0.75,
    cross_type_merge_threshold: float = 0.6,
    deferred_buffer: "DeferredDedupBuffer | None" = None,
    deferred_ambiguous_lower: float = 0.4,
    doc_index: int = 0,
    ontology_state: "OntologyState | None" = None,
    hierarchy_resolution: bool = True,
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
    resolved, id_map, cross_type_stats = _resolve_cross_type(
        resolved,
        type_frequencies,
        merge_threshold=cross_type_merge_threshold,
        deferred_buffer=deferred_buffer,
        ambiguous_lower=deferred_ambiguous_lower,
        doc_index=doc_index,
        ontology_state=ontology_state,
        hierarchy_resolution=hierarchy_resolution,
    )

    merge_count = len(entities) - len(resolved)
    if merge_count > 0:
        logger.info(
            "Resolution: {} -> {} entities ({} merged)",
            len(entities),
            len(resolved),
            merge_count,
        )

    # Store ID map and cross-type stats on module level for caller access
    resolve_entities._last_id_map = id_map
    resolve_entities._last_cross_type_stats = cross_type_stats

    return resolved


# Initialize the class attributes
resolve_entities._last_id_map = {}
resolve_entities._last_cross_type_stats = []


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


def _description_similarity(desc_a: str, desc_b: str) -> float:
    """Jaccard similarity on lowercased word sets, excluding stop words."""
    stop = {
        "a",
        "an",
        "the",
        "is",
        "are",
        "of",
        "for",
        "in",
        "to",
        "and",
        "or",
        "with",
        "that",
        "this",
    }
    words_a = {w for w in desc_a.lower().split() if w not in stop and len(w) > 2}
    words_b = {w for w in desc_b.lower().split() if w not in stop and len(w) > 2}
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def _cross_type_posterior(
    canonical: Entity,
    other: Entity,
    prior_override: float | None = None,
) -> float:
    """Bayesian posterior P(same_entity | evidence) for cross-type pairs.

    Combines name identity, description similarity, embedding cosine,
    and source chunk co-occurrence as independent evidence signals.
    """
    name_a = normalize_entity_name(canonical.name)
    name_b = normalize_entity_name(other.name)

    # Prior: use override if provided, otherwise compute from name identity
    if prior_override is not None:
        prior = prior_override
    else:
        prior = 0.8 if name_a == name_b else 0.2

    # Evidence 1: Description similarity (Jaccard)
    desc_sim = _description_similarity(canonical.description, other.description)
    lr_desc = max(0.3, desc_sim * 2.0)

    # Evidence 2: Embedding cosine (if available)
    lr_emb = 1.0  # neutral if no embeddings
    if canonical.embedding and other.embedding:
        emb_sim = _cosine_similarity(canonical.embedding, other.embedding)
        lr_emb = max(0.2, emb_sim * 2.0)

    # Evidence 3: Shared source chunks (co-occurrence in same document)
    shared_chunks = set(canonical.source_chunks) & set(other.source_chunks)
    lr_cooc = 1.5 if shared_chunks else 0.9

    # Posterior via odds form
    prior_odds = prior / (1.0 - prior)
    posterior_odds = prior_odds * lr_desc * lr_emb * lr_cooc
    posterior = posterior_odds / (1.0 + posterior_odds)

    return posterior


def _resolve_cross_type(
    entities: list[Entity],
    type_frequencies: dict[str, int] | None = None,
    merge_threshold: float = 0.6,
    deferred_buffer: "DeferredDedupBuffer | None" = None,
    ambiguous_lower: float = 0.4,
    doc_index: int = 0,
    ontology_state: "OntologyState | None" = None,
    hierarchy_resolution: bool = True,
) -> tuple[list[Entity], dict[str, str], list[CrossTypeStat]]:
    """Merge entities with identical normalized names across different types.

    Resolution order (when hierarchy is available):
    1. Sibling types (shared parent) -> auto-merge without Bayesian posterior
    2. Cross-parent types (both have parents, different) -> multi-facet labels
    3. No hierarchy relationship -> fall through to Bayesian posterior

    Bayesian three-zone logic (when deferred_buffer is provided):
    - posterior >= merge_threshold -> merge immediately
    - ambiguous_lower <= posterior < merge_threshold -> defer to buffer
    - posterior < ambiguous_lower -> block immediately

    When deferred_buffer is None, falls back to binary: merge at threshold, block below.

    Returns (resolved_entities, id_mapping, cross_type_stats).
    """
    from collections import defaultdict

    type_priority = _build_type_priority(type_frequencies)
    cross_type_stats: list[CrossTypeStat] = []

    # Build hierarchy lookup from ontology state
    has_hierarchy = (
        hierarchy_resolution
        and ontology_state is not None
        and len(ontology_state.type_hierarchy) > 0
    )
    child_to_parent: dict[str, str] = {}
    if has_hierarchy and ontology_state is not None:
        for entry in ontology_state.type_hierarchy:
            for child in entry.children:
                child_to_parent[child] = entry.name

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
            if entities[idx].type != canonical.type:
                other = entities[idx]

                # H5g: Hierarchy-boosted Bayesian resolution
                if has_hierarchy:
                    parent_canon = child_to_parent.get(canonical.type)
                    parent_other = child_to_parent.get(other.type)

                    # Compute hierarchy signals (read-only)
                    sibling_boost = bool(
                        parent_canon and parent_other and parent_canon == parent_other
                    )
                    multi_facet_signal = bool(
                        parent_canon and parent_other and parent_canon != parent_other
                    )

                    # Compute prior based on hierarchy and name identity
                    name_a = normalize_entity_name(canonical.name)
                    name_b = normalize_entity_name(other.name)
                    if sibling_boost:
                        prior = 0.95
                    elif name_a == name_b:
                        prior = 0.8
                    else:
                        prior = 0.2

                    # Always run Bayesian - hierarchy boosts prior, doesn't skip it
                    posterior = _cross_type_posterior(canonical, other, prior_override=prior)

                    if posterior >= merge_threshold:
                        # Merge. Determine action and labels
                        if multi_facet_signal:
                            # Cross-parent merge: preserve both type labels
                            if not canonical.labels:
                                canonical.labels = [canonical.type]
                            if other.type not in canonical.labels:
                                canonical.labels.append(other.type)
                            action = "multi_facet"
                            logger.info(
                                "[resolve] multi-facet merge: '{}' ({} + {}) - "
                                "prior={:.2f}, posterior={:.3f}",
                                other.name,
                                canonical.type,
                                other.type,
                                prior,
                                posterior,
                            )
                        elif sibling_boost:
                            action = "hierarchy_merge"
                            parent = parent_canon
                            logger.info(
                                "[resolve] hierarchy-boosted merge: '{}' ({}) -> ({}) - "
                                "prior={:.2f}, posterior={:.3f}, parent='{}'",
                                other.name,
                                other.type,
                                canonical.type,
                                prior,
                                posterior,
                                parent,
                            )
                        else:
                            action = "merged"
                            logger.info(
                                "[resolve] cross-type merge via Bayesian: '{}' ({}) -> ({}) - "
                                "prior={:.2f}, posterior={:.3f}",
                                other.name,
                                other.type,
                                canonical.type,
                                prior,
                                posterior,
                            )
                        cross_type_stats.append(
                            CrossTypeStat(
                                norm_name,
                                canonical.type,
                                other.type,
                                doc_index,
                                action,
                            )
                        )
                        id_map[other.id] = canonical.id
                        canonical = _merge_entities(canonical, other)
                        merged_indices.add(idx)
                        continue

                    # Multi-facet at moderate evidence (posterior >= 0.3)
                    if multi_facet_signal and posterior >= 0.3:
                        if not canonical.labels:
                            canonical.labels = [canonical.type]
                        if other.type not in canonical.labels:
                            canonical.labels.append(other.type)
                        logger.info(
                            "[resolve] multi-facet merge (moderate evidence): '{}' "
                            "({} + {}) - prior={:.2f}, posterior={:.3f}",
                            other.name,
                            canonical.type,
                            other.type,
                            prior,
                            posterior,
                        )
                        cross_type_stats.append(
                            CrossTypeStat(
                                norm_name,
                                canonical.type,
                                other.type,
                                doc_index,
                                "multi_facet",
                            )
                        )
                        id_map[other.id] = canonical.id
                        canonical = _merge_entities(canonical, other)
                        merged_indices.add(idx)
                        continue

                    # Deferred or blocked
                    if deferred_buffer is not None and posterior >= ambiguous_lower:
                        deferred_buffer.defer(canonical, other, posterior, doc_index)
                        logger.info(
                            "[resolve] cross-type DEFERRED (hierarchy): '{}' ({}) vs ({}) - "
                            "prior={:.2f}, posterior={:.3f} (ambiguous zone {}-{})",
                            other.name,
                            other.type,
                            canonical.type,
                            prior,
                            posterior,
                            ambiguous_lower,
                            merge_threshold,
                        )
                        cross_type_stats.append(
                            CrossTypeStat(
                                norm_name,
                                canonical.type,
                                other.type,
                                doc_index,
                                "deferred",
                            )
                        )
                        continue

                    # Block - log if hierarchy was present but evidence insufficient
                    if sibling_boost:
                        logger.info(
                            "[resolve] cross-type BLOCKED despite hierarchy: '{}' "
                            "({}) vs ({}) - prior={:.2f}, posterior={:.3f} < {}",
                            other.name,
                            other.type,
                            canonical.type,
                            prior,
                            posterior,
                            merge_threshold,
                        )
                    else:
                        logger.info(
                            "[resolve] cross-type merge blocked: '{}' ({}) vs ({}) - "
                            "prior={:.2f}, posterior={:.3f} < {}",
                            other.name,
                            other.type,
                            canonical.type,
                            prior,
                            posterior,
                            ambiguous_lower if deferred_buffer else merge_threshold,
                        )
                    cross_type_stats.append(
                        CrossTypeStat(
                            norm_name,
                            canonical.type,
                            other.type,
                            doc_index,
                            "blocked",
                        )
                    )
                    continue

                # No hierarchy -> standard Bayesian
                posterior = _cross_type_posterior(canonical, other)
                if posterior >= merge_threshold:
                    logger.info(
                        "[resolve] cross-type merge via Bayesian: '{}' ({}) -> ({}) - "
                        "posterior={:.3f}",
                        other.name,
                        other.type,
                        canonical.type,
                        posterior,
                    )
                    cross_type_stats.append(
                        CrossTypeStat(
                            norm_name,
                            canonical.type,
                            other.type,
                            doc_index,
                            "merged",
                        )
                    )
                elif deferred_buffer is not None and posterior >= ambiguous_lower:
                    # Ambiguous zone: defer for evidence accumulation
                    deferred_buffer.defer(canonical, other, posterior, doc_index)
                    logger.info(
                        "[resolve] cross-type DEFERRED: '{}' ({}) vs ({}) - "
                        "posterior={:.3f} (ambiguous zone {}-{})",
                        other.name,
                        other.type,
                        canonical.type,
                        posterior,
                        ambiguous_lower,
                        merge_threshold,
                    )
                    cross_type_stats.append(
                        CrossTypeStat(
                            norm_name,
                            canonical.type,
                            other.type,
                            doc_index,
                            "deferred",
                        )
                    )
                    continue
                else:
                    logger.info(
                        "[resolve] cross-type merge blocked: '{}' ({}) vs ({}) - "
                        "posterior={:.3f} < {}",
                        other.name,
                        other.type,
                        canonical.type,
                        posterior,
                        ambiguous_lower if deferred_buffer else merge_threshold,
                    )
                    cross_type_stats.append(
                        CrossTypeStat(
                            norm_name,
                            canonical.type,
                            other.type,
                            doc_index,
                            "blocked",
                        )
                    )
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
    if deferred_buffer and deferred_buffer.pair_count > 0:
        logger.info(
            "Cross-type resolution: {} pairs deferred for evidence accumulation",
            deferred_buffer.pair_count,
        )
    if cross_type_stats:
        actions = {}
        for stat in cross_type_stats:
            actions[stat.action] = actions.get(stat.action, 0) + 1
        logger.info("Cross-type stats: {}", actions)

    return result, id_map, cross_type_stats


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

"""Entity resolver: exact identity collapse, then Bayesian candidate merging.

Phase 1 - exact: entities sharing an id (same normalized name) merge
structurally - types union as multi-labels, provenance unions. This is not
a decision; it is the identity model.

Phase 2 - candidates: fuzzy-name neighbours (sorted-neighbourhood over
normalized names) and within-type embedding synonyms. Every candidate pair
is scored by the Bayesian posterior; three-zone logic merges, defers or
blocks; merges resolve transitively through union-find.
"""

from __future__ import annotations

from collections import defaultdict
from typing import NamedTuple, Optional

from knowledge_graph_foundry.events import emit
from knowledge_graph_foundry.models import (
    Entity,
    Relationship,
    ResolutionDecision,
    normalize_name,
)
from knowledge_graph_foundry.resolution.bayesian import evidence
from knowledge_graph_foundry.resolution.calibration import PosteriorCalibrator
from knowledge_graph_foundry.resolution.similarity import (
    cosine_similarity,
    name_similarity,
)
from knowledge_graph_foundry.settings import ResolutionSettings

_NEIGHBOURHOOD = 4  # sorted-neighbourhood window for fuzzy-name candidates


class ResolutionResult(NamedTuple):
    entities: list[Entity]
    id_map: dict[str, str]
    decisions: list[ResolutionDecision]


class _UnionFind:
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


def merge_entities(canonical: Entity, other: Entity) -> Entity:
    """Merge `other` into `canonical`: union types, provenance and properties,
    keep the longest description."""
    types = list(canonical.types)
    for t in other.types:
        if t not in types:
            types.append(t)
    properties = {**other.properties, **canonical.properties}
    description = max(canonical.description, other.description, key=len)
    return canonical.model_copy(
        update={
            "types": types,
            "properties": properties,
            "description": description,
            "source_documents": _union(canonical.source_documents, other.source_documents),
            "source_chunks": _union(canonical.source_chunks, other.source_chunks),
        }
    )


def _union(a: list[str], b: list[str]) -> list[str]:
    seen = list(a)
    for item in b:
        if item not in seen:
            seen.append(item)
    return seen


def _exact_collapse(entities: list[Entity]) -> tuple[list[Entity], dict[str, str]]:
    by_id: dict[str, Entity] = {}
    order: list[str] = []
    for entity in entities:
        if entity.id in by_id:
            by_id[entity.id] = merge_entities(by_id[entity.id], entity)
        else:
            by_id[entity.id] = entity
            order.append(entity.id)
    return [by_id[i] for i in order], {}


def _fuzzy_candidates(entities: list[Entity], threshold: float) -> set[tuple[int, int]]:
    """Sorted-neighbourhood over normalized names - O(n * window)."""
    indexed = sorted(range(len(entities)), key=lambda i: normalize_name(entities[i].name))
    pairs: set[tuple[int, int]] = set()
    for pos, i in enumerate(indexed):
        for j in indexed[pos + 1 : pos + 1 + _NEIGHBOURHOOD]:
            a, b = entities[i], entities[j]
            if name_similarity(normalize_name(a.name), normalize_name(b.name)) >= threshold:
                pairs.add((min(i, j), max(i, j)))
    return pairs


def _synonym_candidates(entities: list[Entity], threshold: float) -> set[tuple[int, int]]:
    """Within-type embedding pairs above the synonym threshold."""
    blocks: dict[str, list[int]] = defaultdict(list)
    for idx, entity in enumerate(entities):
        if entity.embedding:
            for t in entity.types:
                blocks[t].append(idx)
    pairs: set[tuple[int, int]] = set()
    for members in blocks.values():
        for pos, i in enumerate(members):
            for j in members[pos + 1 :]:
                sim = cosine_similarity(entities[i].embedding, entities[j].embedding)
                if sim >= threshold:
                    pairs.add((min(i, j), max(i, j)))
    return pairs


def resolve_entities(
    entities: list[Entity],
    cfg: ResolutionSettings,
    calibrator: Optional[PosteriorCalibrator] = None,
    name_candidate_threshold: float = 0.82,
) -> ResolutionResult:
    """Resolve a batch of entities; returns merged entities, an id remap for
    relationship rewriting, and every pairwise decision for forensics."""
    collapsed, _ = _exact_collapse(entities)
    if len(collapsed) < 2:
        return ResolutionResult(collapsed, {}, [])

    candidates = _fuzzy_candidates(collapsed, name_candidate_threshold)
    candidates |= _synonym_candidates(collapsed, cfg.synonym_cluster_threshold)

    decisions: list[ResolutionDecision] = []
    uf = _UnionFind(len(collapsed))
    for i, j in sorted(candidates):
        decision = evidence(collapsed[i], collapsed[j], cfg)
        if calibrator is not None:
            calibrated = calibrator.calibrate(decision.posterior)
            if calibrated >= cfg.merge_threshold:
                verdict = "merge"
            elif calibrated >= cfg.defer_lower:
                verdict = "defer"
            else:
                verdict = "block"
            decision = decision.model_copy(update={"posterior": calibrated, "decision": verdict})
        decisions.append(decision)
        emit(f"resolution.{decision.decision}", **decision.model_dump())
        if decision.decision == "merge":
            uf.union(i, j)

    groups: dict[int, list[int]] = defaultdict(list)
    for idx in range(len(collapsed)):
        groups[uf.find(idx)].append(idx)

    resolved: list[Entity] = []
    id_map: dict[str, str] = {}
    for members in groups.values():
        members.sort()
        merged = collapsed[members[0]]
        for idx in members[1:]:
            merged = merge_entities(merged, collapsed[idx])
        resolved.append(merged)
        for idx in members:
            if collapsed[idx].id != merged.id:
                id_map[collapsed[idx].id] = merged.id

    return ResolutionResult(resolved, id_map, decisions)


def remap_relationships(
    relationships: list[Relationship], id_map: dict[str, str]
) -> list[Relationship]:
    """Rewrite relationship endpoints through the id map, dropping self-loops
    and exact duplicates that emerge from merging."""
    seen: set[tuple[str, str, str]] = set()
    result: list[Relationship] = []
    for rel in relationships:
        source = id_map.get(rel.source_id, rel.source_id)
        target = id_map.get(rel.target_id, rel.target_id)
        if source == target:
            continue
        key = (source, target, rel.type)
        if key in seen:
            continue
        seen.add(key)
        result.append(rel.model_copy(update={"source_id": source, "target_id": target}))
    return result

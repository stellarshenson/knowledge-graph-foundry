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

from knowledge_graph_foundry.engines.base import Engine
from knowledge_graph_foundry.events import emit
from knowledge_graph_foundry.models import (
    Entity,
    Relationship,
    ResolutionDecision,
    glyph_norm,
    normalize_name,
)
from knowledge_graph_foundry.resolution.bayesian import evidence
from knowledge_graph_foundry.resolution.blocking import ann_candidates
from knowledge_graph_foundry.resolution.calibration import PosteriorCalibrator
from knowledge_graph_foundry.resolution.identity_stack import V2IdentityStack
from knowledge_graph_foundry.resolution.judge import judge_pair
from knowledge_graph_foundry.resolution.similarity import (
    cosine_similarity,
    name_similarity,
)
from knowledge_graph_foundry.settings import ResolutionSettings

_NEIGHBOURHOOD = 4  # sorted-neighbourhood window for fuzzy-name candidates

_V2_STACK_CACHE: dict[tuple[str, float], V2IdentityStack] = {}


def _v2_stack(cfg: ResolutionSettings) -> V2IdentityStack:
    """Load (and cache) the baked v2 identity stack so the NLI model loads once."""
    key = (cfg.identity_stack_artifact, cfg.nli_veto_threshold)
    stack = _V2_STACK_CACHE.get(key)
    if stack is None:
        stack = V2IdentityStack.load(cfg.identity_stack_artifact, cfg.nli_veto_threshold)
        _V2_STACK_CACHE[key] = stack
    return stack


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


def _glyph_collapse(entities: list[Entity]) -> tuple[list[Entity], dict[str, str]]:
    """R15-H190 resolver name-identity detector: merge entities whose names are
    equal under glyph normalization (trademark/unicode variants of one name).
    Runs at comparison time only - `entity_id` (and thus `normalize_name`) is
    untouched, so ids stay backward-compatible; the first-seen entity's id is the
    canonical. Promoted at 0 false conflations on the 2797-name vocabulary."""
    by_key: dict[str, Entity] = {}
    order: list[str] = []
    id_map: dict[str, str] = {}
    for entity in entities:
        key = glyph_norm(entity.name)
        canonical = by_key.get(key)
        if canonical is None:
            by_key[key] = entity
            order.append(key)
        else:
            by_key[key] = merge_entities(canonical, entity)
            if entity.id != by_key[key].id:
                id_map[entity.id] = by_key[key].id
    return [by_key[k] for k in order], id_map


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


def _pair_similarity(a: Entity, b: Entity, cfg: ResolutionSettings) -> float:
    """Cohesion signal for the split guard: embedding cosine when both sides
    carry a vector, otherwise the Bayesian posterior over name and description."""
    if a.embedding and b.embedding:
        return cosine_similarity(a.embedding, b.embedding)
    return evidence(a, b, cfg).posterior


def _split_low_cohesion(
    components: list[list[int]], entities: list[Entity], cfg: ResolutionSettings
) -> list[list[int]]:
    """R8 split guard: break snowballed A~B~C over-merges. A component with
    more than two members whose average pairwise cohesion falls below
    `split_guard_min_avg_similarity` sheds any member whose mean similarity to
    the rest is below that threshold into a singleton."""
    result: list[list[int]] = []
    for members in components:
        if len(members) <= 2:
            result.append(members)
            continue
        sims: dict[tuple[int, int], float] = {}
        for pos, i in enumerate(members):
            for j in members[pos + 1 :]:
                sims[(i, j)] = _pair_similarity(entities[i], entities[j], cfg)
        mean = sum(sims.values()) / len(sims)
        if mean >= cfg.split_guard_min_avg_similarity:
            result.append(members)
            continue
        kept: list[int] = []
        for i in members:
            others = [m for m in members if m != i]
            member_mean = sum(sims[(min(i, m), max(i, m))] for m in others) / len(others)
            if member_mean < cfg.split_guard_min_avg_similarity:
                result.append([i])
            else:
                kept.append(i)
        if kept:
            result.append(kept)
    return result


def resolve_entities(
    entities: list[Entity],
    cfg: ResolutionSettings,
    calibrator: Optional[PosteriorCalibrator] = None,
    name_candidate_threshold: float = 0.82,
    engine: Optional[Engine] = None,
    glyph_normalization: bool = True,
) -> ResolutionResult:
    """Resolve a batch of entities; returns merged entities, an id remap for
    relationship rewriting, and every pairwise decision for forensics."""
    collapsed, _ = _exact_collapse(entities)
    glyph_map: dict[str, str] = {}
    if glyph_normalization:
        collapsed, glyph_map = _glyph_collapse(collapsed)
    if len(collapsed) < 2:
        return ResolutionResult(collapsed, dict(glyph_map), [])

    candidates = _fuzzy_candidates(collapsed, name_candidate_threshold)
    candidates |= ann_candidates(
        collapsed, cfg.ann_top_k, cfg.ann_min_entities, cfg.synonym_cluster_threshold
    )

    ordered = sorted(candidates)
    stack = _v2_stack(cfg) if cfg.identity_stack == "v2" else None
    nli_scores: dict[tuple[int, int], float] = {}
    if stack is not None:
        pairs = [(collapsed[i], collapsed[j]) for i, j in ordered]
        nli_scores = dict(zip(ordered, stack.nli_contra_batch(pairs)))

    decisions: list[ResolutionDecision] = []
    uf = _UnionFind(len(collapsed))
    for i, j in ordered:
        decision = evidence(collapsed[i], collapsed[j], cfg)
        if stack is not None:
            contra = nli_scores.get((i, j), 0.0)
            verdict, score, vetoed = stack.decide(
                collapsed[i], collapsed[j], decision.posterior, contra
            )
            decision = decision.model_copy(update={"posterior": score, "decision": verdict})
            if vetoed:
                emit(
                    "resolution.veto",
                    left_id=collapsed[i].id,
                    right_id=collapsed[j].id,
                    nli_contra=contra,
                )
        elif calibrator is not None:
            calibrated = calibrator.calibrate(decision.posterior)
            if calibrated >= cfg.merge_threshold:
                verdict = "merge"
            elif calibrated >= cfg.defer_lower:
                verdict = "defer"
            else:
                verdict = "block"
            decision = decision.model_copy(update={"posterior": calibrated, "decision": verdict})
        if decision.decision == "defer" and cfg.llm_defer_judge and engine is not None:
            same = judge_pair(collapsed[i], collapsed[j], engine)
            decision = decision.model_copy(update={"decision": "merge" if same else "block"})
        decisions.append(decision)
        emit(f"resolution.{decision.decision}", **decision.model_dump())
        if decision.decision == "merge":
            uf.union(i, j)

    groups: dict[int, list[int]] = defaultdict(list)
    for idx in range(len(collapsed)):
        groups[uf.find(idx)].append(idx)

    components = [sorted(members) for members in groups.values()]
    if cfg.split_guard:
        components = _split_low_cohesion(components, collapsed, cfg)

    resolved: list[Entity] = []
    id_map: dict[str, str] = {}
    for members in components:
        merged = collapsed[members[0]]
        for idx in members[1:]:
            merged = merge_entities(merged, collapsed[idx])
        resolved.append(merged)
        for idx in members:
            if collapsed[idx].id != merged.id:
                id_map[collapsed[idx].id] = merged.id

    # Chain the glyph-collapse remap through phase-2 merges so relationships on a
    # glyph-variant endpoint rewrite all the way to the final canonical id.
    for original, canonical in glyph_map.items():
        id_map[original] = id_map.get(canonical, canonical)

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

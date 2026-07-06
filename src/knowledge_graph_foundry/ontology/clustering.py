"""Cure-time type clustering - the single owner of type consolidation.

Consolidation merges semantic synonym types (Standard vs RegulatoryStandard)
that deterministic normalization cannot catch. v1 lesson: exactly one owner
per decision - nothing downstream may re-enforce or overwrite this pass.

R5 upgrades the one-shot flat LLM pass to an embed -> block -> LLM-verify
pass (EDC-style canonicalization). Types are embedded from their definition
text, candidate merge pairs are blocked by cosine similarity, and only blocked
pairs are LLM-verified. This is cheaper and more consistent than a single flat
pass and can be re-run after curing so late-appearing synonyms still merge.
When no ``embed_fn`` is supplied the legacy single-pass behaviour is used.
"""

from __future__ import annotations

from typing import Callable, Optional

from loguru import logger
from pydantic import BaseModel, Field

from knowledge_graph_foundry.engines.base import Engine
from knowledge_graph_foundry.events import emit
from knowledge_graph_foundry.models import Ontology, TypeDef
from knowledge_graph_foundry.resolution.similarity import cosine_similarity

# cosine threshold above which a type pair is a candidate merge worth verifying
MERGE_SIMILARITY_THRESHOLD = 0.6

EmbedFn = Callable[[list[str]], list[list[float]]]


class TypeMerge(BaseModel):
    source: str = Field(description="type name to merge away")
    target: str = Field(description="type name to keep")
    reason: str = ""


class TypeClustering(BaseModel):
    merges: list[TypeMerge] = Field(default_factory=list)


class VerifyMerge(BaseModel):
    """LLM verdict for one blocked candidate pair."""

    same: bool = Field(description="true if the two types are semantic synonyms")
    reason: str = ""


def _clustering_messages(ontology: Ontology, purpose: str) -> list[dict[str, str]]:
    lines = [
        f"- {t.name} ({t.encounters} encounters, {t.status}): {t.description or 'no description'}"
        for t in ontology.types.values()
    ]
    system = (
        "You consolidate an entity type system for a knowledge graph. "
        "Merge only types that are semantic synonyms or trivial variants of each other. "
        "Do NOT merge types that are genuinely distinct facets, even if related. "
        "Keep the more general, better-named type as the target."
    )
    user = (
        f"The knowledge graph purpose is: {purpose}\n\n"
        f"Current types:\n" + "\n".join(lines) + "\n\n"
        "Return the merges needed to consolidate synonym types. "
        "An empty list is a valid answer when the type system is already clean."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _type_text(t: TypeDef) -> str:
    """Definition text embedded to represent a type (name + description)."""
    return f"{t.name}: {t.description}" if t.description else t.name


def _verify_messages(source: TypeDef, target: TypeDef, purpose: str) -> list[dict[str, str]]:
    system = (
        "You decide whether two entity types in a knowledge graph are semantic "
        "synonyms that should be merged into one type. Answer same=true only when "
        "they denote the same kind of thing, not merely related facets."
    )
    user = (
        f"The knowledge graph purpose is: {purpose}\n\n"
        f"Type A: {source.name} - {source.description or 'no description'}\n"
        f"Type B: {target.name} - {target.description or 'no description'}\n\n"
        "Are A and B the same type?"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _order_pair(a: TypeDef, b: TypeDef) -> tuple[str, str]:
    """Decide merge direction; target is the more general type.

    More general = more encounters, then shorter name, then lexical order.
    Returns (source_name, target_name).
    """
    if a.encounters != b.encounters:
        target = a if a.encounters > b.encounters else b
    elif len(a.name) != len(b.name):
        target = a if len(a.name) < len(b.name) else b
    else:
        target = a if a.name < b.name else b
    source = b if target is a else a
    return source.name, target.name


def _legacy_remap(ontology: Ontology, purpose: str, engine: Engine) -> dict[str, str]:
    """One flat LLM pass over all types (original v1 behaviour)."""
    clustering = engine.complete(_clustering_messages(ontology, purpose), TypeClustering)
    remap: dict[str, str] = {}
    for merge in clustering.merges:
        if merge.source not in ontology.types or merge.target not in ontology.types:
            logger.warning(f"clustering proposed unknown type: {merge.source} -> {merge.target}")
            continue
        if merge.source == merge.target:
            continue
        remap[merge.source] = merge.target
    return remap


def _embed_verify_remap(
    ontology: Ontology, purpose: str, engine: Engine, embed_fn: EmbedFn
) -> dict[str, str]:
    """Embed types, block candidate pairs by cosine similarity, LLM-verify each."""
    names = list(ontology.types)
    vectors = embed_fn([_type_text(ontology.types[n]) for n in names])
    remap: dict[str, str] = {}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if cosine_similarity(vectors[i], vectors[j]) < MERGE_SIMILARITY_THRESHOLD:
                continue
            source, target = _order_pair(ontology.types[names[i]], ontology.types[names[j]])
            verdict = engine.complete(
                _verify_messages(ontology.types[source], ontology.types[target], purpose),
                VerifyMerge,
            )
            if verdict.same:
                remap[source] = target
    return remap


def _collapse_chains(remap: dict[str, str]) -> dict[str, str]:
    """Collapse chains (A->B, B->C becomes A->C) and drop cycles."""
    for source in list(remap):
        target = remap[source]
        seen = {source}
        while target in remap and target not in seen:
            seen.add(target)
            target = remap[target]
        if target in seen and remap.get(target) is not None and target in remap:
            del remap[source]  # cycle - keep both types
            continue
        remap[source] = target
    return remap


def _consolidate(ontology: Ontology, remap: dict[str, str]) -> Ontology:
    """Apply the remap to the ontology, folding source types into targets and
    recording each absorbed type as an ``alias:<name>`` marker on the survivor."""
    consolidated = ontology.model_copy(deep=True)
    for source, target in remap.items():
        source_def = consolidated.types.pop(source, None)
        if source_def is None:
            continue
        target_def = consolidated.types[target]
        target_def.encounters += source_def.encounters
        for prop in source_def.properties:
            if prop not in target_def.properties:
                target_def.properties.append(prop)
        alias = f"alias:{source}"
        if alias not in target_def.properties:
            target_def.properties.append(alias)
    return consolidated


def cluster_types(
    ontology: Ontology,
    purpose: str,
    engine: Engine,
    embed_fn: Optional[EmbedFn] = None,
) -> tuple[Ontology, dict[str, str]]:
    """Run the clustering pass; returns the consolidated ontology and a type
    remap (old name -> new name) for rewriting buffered entities.

    When ``embed_fn`` is provided, use the embed -> block -> verify path.
    When it is None, fall back to the legacy single flat LLM pass.
    """
    if len(ontology.types) < 2:
        return ontology, {}

    if embed_fn is None:
        remap = _legacy_remap(ontology, purpose, engine)
    else:
        remap = _embed_verify_remap(ontology, purpose, engine, embed_fn)

    remap = _collapse_chains(remap)
    if not remap:
        return ontology, {}

    consolidated = _consolidate(ontology, remap)
    emit("ontology.evolved", merges={k: v for k, v in remap.items()}, stage="cure_clustering")
    return consolidated, remap


def should_recure(cured_type_count: int, current_type_count: int, burst: int) -> bool:
    """True when enough new types have appeared since curing to reopen
    consolidation (a post-cure burst of >= ``burst`` new types)."""
    return current_type_count - cured_type_count >= burst


def apply_type_remap(types: list[str], remap: dict[str, str]) -> list[str]:
    """Rewrite an entity's type labels through the remap, deduplicated."""
    result: list[str] = []
    for t in types:
        mapped = remap.get(t, t)
        if mapped not in result:
            result.append(mapped)
    return result

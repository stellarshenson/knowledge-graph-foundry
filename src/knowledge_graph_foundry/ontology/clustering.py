"""Cure-time type clustering - the single owner of type consolidation.

One purpose-aware LLM pass at curing merges semantic synonym types
(Standard vs RegulatoryStandard) that deterministic normalization cannot
catch. v1 lesson: exactly one owner per decision - nothing downstream may
re-enforce or overwrite this pass.
"""

from __future__ import annotations

from loguru import logger
from pydantic import BaseModel, Field

from knowledge_graph_foundry.engines.base import Engine
from knowledge_graph_foundry.events import emit
from knowledge_graph_foundry.models import Ontology


class TypeMerge(BaseModel):
    source: str = Field(description="type name to merge away")
    target: str = Field(description="type name to keep")
    reason: str = ""


class TypeClustering(BaseModel):
    merges: list[TypeMerge] = Field(default_factory=list)


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


def cluster_types(
    ontology: Ontology, purpose: str, engine: Engine
) -> tuple[Ontology, dict[str, str]]:
    """Run the clustering pass; returns the consolidated ontology and a
    type remap (old name -> new name) for rewriting buffered entities."""
    if len(ontology.types) < 2:
        return ontology, {}

    clustering = engine.complete(_clustering_messages(ontology, purpose), TypeClustering)

    remap: dict[str, str] = {}
    for merge in clustering.merges:
        if merge.source not in ontology.types or merge.target not in ontology.types:
            logger.warning(f"clustering proposed unknown type: {merge.source} -> {merge.target}")
            continue
        if merge.source == merge.target:
            continue
        remap[merge.source] = merge.target

    # collapse chains (A->B, B->C becomes A->C) and drop cycles
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

    if not remap:
        return ontology, {}

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

    emit("ontology.evolved", merges={k: v for k, v in remap.items()}, stage="cure_clustering")
    return consolidated, remap


def apply_type_remap(types: list[str], remap: dict[str, str]) -> list[str]:
    """Rewrite an entity's type labels through the remap, deduplicated."""
    result: list[str] = []
    for t in types:
        mapped = remap.get(t, t)
        if mapped not in result:
            result.append(mapped)
    return result

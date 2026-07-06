"""LLM-assisted type clustering at curing time.

Makes a single LLM call to cluster discovered entity types into canonical
forms, catching semantic synonyms that deterministic normalization misses
(e.g. Standard vs RegulatoryStandard).
"""

from __future__ import annotations

import os

from loguru import logger
from pydantic import BaseModel, Field


class TypeClusteringResult(BaseModel):
    """Mapping of discovered types to canonical forms."""

    mapping: dict[str, str] = Field(description="Maps each discovered type to its canonical form")


_CLUSTERING_PROMPT = """You are a knowledge graph ontology expert. Given the following discovered entity types with their frequencies, cluster them into canonical types.

**Domain intent**: {intent}

**Discovered types** (type: frequency):
{type_list}

**Rules**:
1. Merge ONLY genuine synonyms or formatting variants (e.g. MedicalCondition and Medical_Condition)
2. The canonical form should be PascalCase (e.g. "MedicalDevice", "SafetyStandard")
3. Do NOT merge types that serve different semantic roles, even if they seem related
4. Prefer the highest-frequency variant as the canonical name
5. When in doubt, keep types separate - false merges are worse than redundant types

Return a mapping where each discovered type maps to its canonical form. Types that are already canonical map to themselves."""


async def cluster_types(
    discovered_types: list[str],
    frequencies: dict[str, int],
    intent: str | None = None,
    model: str = "eu.anthropic.claude-sonnet-4-20250514-v1:0",
    provider: str = "bedrock",
    region: str | None = None,
    profile: str | None = None,
) -> dict[str, str]:
    """Cluster discovered types into canonical forms via one LLM call.

    Returns mapping: discovered_type -> canonical_type.
    """
    if not discovered_types:
        return {}

    # Set AWS env if needed
    if region:
        os.environ["AWS_REGION_NAME"] = region
    if profile:
        os.environ["AWS_PROFILE"] = profile

    type_list = "\n".join(f"- {t}: {frequencies.get(t, 0)}" for t in sorted(discovered_types))

    prompt = _CLUSTERING_PROMPT.format(
        intent=intent or "general knowledge graph",
        type_list=type_list,
    )

    model_id = f"{provider}/{model}" if provider == "bedrock" else model

    import instructor
    import litellm

    client = instructor.from_litellm(litellm.acompletion)

    try:
        import time

        from knowledge_graph_foundry.events import signals as evt_signals
        from knowledge_graph_foundry.events import types as etypes
        from knowledge_graph_foundry.extraction.extract import extract_usage

        evt_signals.llm_call_started.send(
            evt_signals.llm_call_started,
            event=etypes.LLMCallStarted(call_type="type_clustering", model=model_id),
        )
        t0 = time.monotonic()

        result = await client.create(
            model=model_id,
            response_model=TypeClusteringResult,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_retries=2,
        )

        duration_ms = int((time.monotonic() - t0) * 1000)
        usage = extract_usage(result)
        evt_signals.llm_call_completed.send(
            evt_signals.llm_call_completed,
            event=etypes.LLMCallCompleted(
                call_type="type_clustering",
                model=model_id,
                duration_ms=duration_ms,
                token_count=usage["total_tokens"],
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            ),
        )

        mapping = result.mapping
        # Ensure all discovered types are in the mapping
        for t in discovered_types:
            if t not in mapping:
                mapping[t] = t

        canonical_count = len(set(mapping.values()))
        logger.info(
            "Type clustering: {} discovered -> {} canonical types",
            len(discovered_types),
            canonical_count,
        )
        return mapping

    except Exception:
        logger.exception("Type clustering LLM call failed, using identity mapping")
        return {t: t for t in discovered_types}


def apply_type_mapping(
    entities: list,
    mapping: dict[str, str],
) -> list:
    """Apply type mapping to a list of entities, remapping their types."""
    remapped = 0
    for entity in entities:
        new_type = mapping.get(entity.type)
        if new_type and new_type != entity.type:
            entity.type = new_type
            remapped += 1

    if remapped > 0:
        logger.info("Type mapping applied: remapped {} entities", remapped)

    return entities

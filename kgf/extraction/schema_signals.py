"""Lightweight schema signal extraction for pre-extraction type discovery."""

from __future__ import annotations

import os

import instructor
import litellm
from loguru import logger
from pydantic import BaseModel, Field


class SchemaSignals(BaseModel):
    """Schema signals discovered from a lightweight first-pass extraction."""

    entity_types: list[str] = Field(default_factory=list)
    relationship_types: list[str] = Field(default_factory=list)


def extract_schema_signals(
    text: str,
    model: str,
    provider: str = "bedrock",
    region: str | None = None,
    profile: str | None = None,
) -> SchemaSignals:
    """Run a lightweight LLM call to discover entity and relationship type signals.

    This is a cheaper pre-pass that identifies what categories of entities
    and relationships are likely present in the text, without extracting
    specific instances.
    """
    if region:
        os.environ["AWS_REGION_NAME"] = region
    if profile:
        os.environ["AWS_PROFILE"] = profile

    model_id = f"{provider}/{model}" if provider == "bedrock" else model
    client = instructor.from_litellm(litellm.completion)

    prompt = (
        "Scan the following text and list the categories of entities and "
        "relationships you would expect to find. Do not extract specific "
        "entities - only list the types.\n\n"
        f"Text:\n{text[:4000]}\n\n"
        "Return the entity types and relationship types you detect."
    )

    import time

    from kgf.events import signals as evt_signals
    from kgf.events import types as etypes
    from kgf.extraction.extract import extract_usage

    evt_signals.llm_call_started.send(
        evt_signals.llm_call_started,
        event=etypes.LLMCallStarted(
            call_type="schema_signals",
            model=model_id,
        ),
    )
    t0 = time.monotonic()

    try:
        result = client.chat.completions.create(
            model=model_id,
            response_model=SchemaSignals,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_retries=2,
        )
        duration_ms = int((time.monotonic() - t0) * 1000)
        usage = extract_usage(result)
        evt_signals.llm_call_completed.send(
            evt_signals.llm_call_completed,
            event=etypes.LLMCallCompleted(
                call_type="schema_signals",
                model=model_id,
                duration_ms=duration_ms,
                token_count=usage["total_tokens"],
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            ),
        )
        logger.debug(
            "Schema signals: {} entity types, {} relationship types",
            len(result.entity_types),
            len(result.relationship_types),
        )
        return result
    except Exception:
        duration_ms = int((time.monotonic() - t0) * 1000)
        evt_signals.llm_call_failed.send(
            evt_signals.llm_call_failed,
            event=etypes.LLMCallFailed(
                call_type="schema_signals",
                model=model_id,
                error_type="exception",
                error_message="Schema signal extraction failed",
            ),
        )
        logger.warning("Schema signal extraction failed, returning empty signals")
        return SchemaSignals()


def compute_coverage(signals: SchemaSignals, known_types: set[str]) -> float:
    """Compute coverage of detected signals against known types.

    Returns fraction of signal entity types that are already known.
    Range [0.0, 1.0].
    """
    if not signals.entity_types:
        return 1.0  # no signals = nothing unknown

    known_lower = {t.lower() for t in known_types}
    matched = sum(1 for t in signals.entity_types if t.lower() in known_lower)
    return matched / len(signals.entity_types)

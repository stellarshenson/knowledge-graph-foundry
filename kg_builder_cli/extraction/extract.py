"""LLM extraction per chunk using litellm + instructor for structured output."""

from __future__ import annotations

import instructor
import litellm
from loguru import logger

from kg_builder_cli.types.document import Chunk
from kg_builder_cli.types.extraction import Entity, Relationship

from .response_models import ExtractionResponse


class LLMAuthError(Exception):
    """Raised when the LLM provider returns an authentication/authorization error.

    This is a fatal error that should abort the pipeline immediately rather than
    silently returning empty results for every chunk.
    """


def create_extraction_client() -> instructor.Instructor:
    """Create an instructor client wrapping litellm.completion.

    Thread-safe, can be shared across extraction workers.
    """
    return instructor.from_litellm(litellm.completion)


def _is_auth_error(exc: Exception) -> bool:
    """Detect authentication/authorization errors from LLM providers."""
    msg = str(exc).lower()
    auth_indicators = [
        "accessdeniedexception",
        "not authorized to perform",
        "forbidden",
        "invalid api key",
        "authentication",
        "unauthorized",
        "403",
    ]
    return any(indicator in msg for indicator in auth_indicators)


def extract_chunk(
    chunk: Chunk,
    prompt: str,
    model_id: str,
    client: instructor.Instructor,
    temperature: float = 0.0,
    max_retries: int = 3,
    response_model: type = ExtractionResponse,
) -> tuple[list[Entity], list[Relationship]]:
    """Extract entities and relationships from a chunk using structured output.

    Uses instructor + litellm for automatic Pydantic validation and retry.
    Returns empty lists on transient errors. Raises LLMAuthError on auth failures.
    """
    import time

    from kg_builder_cli.events import signals as evt_signals
    from kg_builder_cli.events import types as etypes

    evt_signals.llm_call_started.send(
        evt_signals.llm_call_started,
        event=etypes.LLMCallStarted(
            call_type="chunk_extraction",
            model=model_id,
            doc_index=None,
            context={"chunk_id": chunk.id},
        ),
    )
    t0 = time.monotonic()

    try:
        response = client.chat.completions.create(
            model=model_id,
            response_model=response_model,
            messages=[
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_retries=max_retries,
        )

        entities = [
            Entity(
                id=e.id,
                name=e.name,
                type=e.type,
                description=e.description,
                properties=e.properties,
                source_chunks=[chunk.id],
                confidence=e.confidence,
                extraction_model=model_id,
            )
            for e in response.entities
        ]

        relationships = [
            Relationship(
                source=r.source,
                target=r.target,
                type=r.type,
                description=r.description,
                source_chunks=[chunk.id],
                confidence=r.confidence,
                extraction_model=model_id,
            )
            for r in response.relationships
        ]

        duration_ms = int((time.monotonic() - t0) * 1000)
        evt_signals.llm_call_completed.send(
            evt_signals.llm_call_completed,
            event=etypes.LLMCallCompleted(
                call_type="chunk_extraction",
                model=model_id,
                duration_ms=duration_ms,
                token_count=None,
                doc_index=None,
            ),
        )

        logger.debug(
            "Chunk {} -> {} entities, {} relationships",
            chunk.id,
            len(entities),
            len(relationships),
        )
        return entities, relationships

    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        if _is_auth_error(exc):
            evt_signals.llm_call_failed.send(
                evt_signals.llm_call_failed,
                event=etypes.LLMCallFailed(
                    call_type="chunk_extraction",
                    model=model_id,
                    error_type="auth",
                    error_message=str(exc),
                    doc_index=None,
                ),
            )
            raise LLMAuthError(
                f"LLM authentication failed: {exc}\n"
                f"Check your provider credentials and IAM permissions for model '{model_id}'."
            ) from exc
        evt_signals.llm_call_failed.send(
            evt_signals.llm_call_failed,
            event=etypes.LLMCallFailed(
                call_type="chunk_extraction",
                model=model_id,
                error_type=type(exc).__name__,
                error_message=str(exc),
                doc_index=None,
            ),
        )
        logger.exception("Extraction failed for chunk {}", chunk.id)
        return [], []

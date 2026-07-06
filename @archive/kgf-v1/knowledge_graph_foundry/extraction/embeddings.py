"""Embedding generation with provider fallback.

Supports cloud providers (Bedrock Titan v2) and a local CPU fallback
(sentence-transformers all-MiniLM-L6-v2) for deployment resilience.

Single-provider-per-run contract: once a provider is selected (either by
config or via fallback after primary failure), subsequent calls in the
same process use the same provider. This keeps the exemplar index
dimensionally consistent.
"""

from __future__ import annotations

import json
import os
from typing import Optional

import boto3
from loguru import logger

from knowledge_graph_foundry.types.extraction import Entity

# Module-level state: the provider locked in for the current run
_active_provider: Optional[str] = None
_local_model = None  # cached sentence-transformers model instance


def reset_provider_state() -> None:
    """Reset the locked provider state. Intended for tests."""
    global _active_provider, _local_model
    _active_provider = None
    _local_model = None


def _entity_text(entity: Entity) -> str:
    """Build the embedding input text for an entity."""
    return f"{entity.type}: {entity.name} - {entity.description[:200]}"


def _embed_bedrock(
    entities: list[Entity],
    model: str,
    batch_size: int,
) -> int:
    """Embed entities via Bedrock. Raises on provider-level failure.

    First invoke_model call failure is treated as provider failure and
    re-raised so the caller can trigger fallback. Subsequent failures
    are logged as per-entity warnings.
    """
    profile = os.environ.get("AWS_PROFILE", "kolomolo")
    region = os.environ.get(
        "AWS_REGION_NAME", os.environ.get("AWS_DEFAULT_REGION", "eu-central-1")
    )

    session = boto3.Session(profile_name=profile, region_name=region)
    client = session.client("bedrock-runtime")

    total = len(entities)
    embedded = 0
    first_call = True

    for offset in range(0, total, batch_size):
        batch = entities[offset : offset + batch_size]
        for entity in batch:
            text = _entity_text(entity)
            try:
                response = client.invoke_model(
                    modelId=model,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps({"inputText": text}),
                )
                body = json.loads(response["body"].read())
                entity.embedding = body["embedding"]
                embedded += 1
                first_call = False
            except Exception:
                if first_call:
                    raise
                logger.warning("Embedding failed for entity '{}'", entity.name)

        if embedded % 50 == 0 or offset + batch_size >= total:
            logger.info("Embeddings: {}/{}", embedded, total)

    return embedded


def _load_local_model(model_name: str):
    """Load and cache the sentence-transformers model."""
    global _local_model
    if _local_model is not None:
        return _local_model

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers not installed. "
            "Install with: pip install knowledge-graph-foundry[local-embeddings]"
        ) from exc

    logger.info("[embeddings] loading local model '{}' (first use may download ~22MB)", model_name)
    _local_model = SentenceTransformer(model_name)
    return _local_model


def _embed_local(
    entities: list[Entity],
    model_name: str,
    batch_size: int,
) -> int:
    """Embed entities via local sentence-transformers model."""
    model = _load_local_model(model_name)
    total = len(entities)
    embedded = 0

    for offset in range(0, total, batch_size):
        batch = entities[offset : offset + batch_size]
        texts = [_entity_text(e) for e in batch]
        try:
            vectors = model.encode(texts, show_progress_bar=False)
        except Exception as exc:
            logger.error("[embeddings] local model encode failed: {}", exc)
            continue

        for entity, vector in zip(batch, vectors):
            entity.embedding = vector.tolist() if hasattr(vector, "tolist") else list(vector)
            embedded += 1

        if embedded % 50 == 0 or offset + batch_size >= total:
            logger.info("Embeddings: {}/{}", embedded, total)

    return embedded


def _resolve_provider(provider: Optional[str], model: Optional[str]) -> tuple[str, str]:
    """Resolve (provider, model) tuple from inputs, respecting run lock."""
    global _active_provider

    if _active_provider is not None:
        resolved_provider = _active_provider
    elif provider:
        resolved_provider = provider
    elif model and model.startswith("amazon."):
        resolved_provider = "bedrock"
    elif model and model.startswith("all-") or model and "MiniLM" in (model or ""):
        resolved_provider = "sentence-transformers"
    else:
        resolved_provider = "bedrock"

    if resolved_provider == "bedrock":
        resolved_model = model or "amazon.titan-embed-text-v2:0"
    elif resolved_provider == "sentence-transformers":
        resolved_model = model or "all-MiniLM-L6-v2"
    else:
        raise ValueError(f"Unknown embedding provider: {resolved_provider}")

    return resolved_provider, resolved_model


def generate_embeddings(
    entities: list[Entity],
    model: Optional[str] = None,
    batch_size: int = 25,
    provider: Optional[str] = None,
    fallback: Optional[str] = "sentence-transformers",
    fallback_model: Optional[str] = None,
) -> list[Entity]:
    """Generate embeddings for entities with optional provider fallback.

    Providers: "bedrock" (Titan v2, 1024-dim), "sentence-transformers"
    (all-MiniLM-L6-v2, 384-dim).

    Fallback: if primary provider fails at the first API call, switch to
    the fallback provider for this run. Set fallback=None to disable.

    Single-provider-per-run: once a provider is locked (by first successful
    call or by fallback), subsequent calls reuse it to keep embedding
    dimensions consistent across the exemplar index.
    """
    global _active_provider

    if not entities:
        return entities

    resolved_provider, resolved_model = _resolve_provider(provider, model)

    try:
        if resolved_provider == "bedrock":
            embedded = _embed_bedrock(entities, resolved_model, batch_size)
        elif resolved_provider == "sentence-transformers":
            embedded = _embed_local(entities, resolved_model, batch_size)
        else:
            raise ValueError(f"Unknown embedding provider: {resolved_provider}")

        _active_provider = resolved_provider
        logger.info(
            "Generated embeddings for {}/{} entities via {}",
            embedded,
            len(entities),
            resolved_provider,
        )
        return entities

    except Exception as exc:
        if _active_provider is not None:
            # Already locked in - do not fall back mid-run
            raise
        if not fallback or fallback == resolved_provider:
            raise

        logger.warning(
            "[embeddings] primary provider '{}' failed ({}), falling back to '{}'",
            resolved_provider,
            type(exc).__name__,
            fallback,
        )
        # Reset any partial embeddings from failed attempt
        for entity in entities:
            entity.embedding = None

        _, fb_model = _resolve_provider(fallback, fallback_model)
        if fallback == "bedrock":
            embedded = _embed_bedrock(entities, fb_model, batch_size)
        elif fallback == "sentence-transformers":
            embedded = _embed_local(entities, fb_model, batch_size)
        else:
            raise ValueError(f"Unknown fallback provider: {fallback}") from exc

        _active_provider = fallback
        logger.info(
            "Generated embeddings for {}/{} entities via fallback {}",
            embedded,
            len(entities),
            fallback,
        )
        return entities

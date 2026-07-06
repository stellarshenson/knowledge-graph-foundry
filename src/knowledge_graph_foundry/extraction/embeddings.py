"""Embedding generation with provider fallback.

Supports cloud providers (Bedrock Titan v2) and a local CPU fallback
(sentence-transformers all-MiniLM-L6-v2) for deployment resilience.

Single-provider-per-run contract: once a provider is selected (either by
config or via fallback after primary failure), subsequent calls in the
same process use the same provider. This keeps embedding dimensions
consistent across the run.
"""

from __future__ import annotations

import json
import os
from typing import Optional

import boto3
from loguru import logger

from knowledge_graph_foundry.models import Entity
from knowledge_graph_foundry.settings import EmbeddingSettings

_BATCH_SIZE = 25

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
    entity_type = entity.types[0] if entity.types else "Entity"
    return f"{entity_type}: {entity.name} - {entity.description[:200]}"


def _embed_bedrock(entities: list[Entity], model: str) -> int:
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

    for offset in range(0, total, _BATCH_SIZE):
        batch = entities[offset : offset + _BATCH_SIZE]
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

        if embedded % 50 == 0 or offset + _BATCH_SIZE >= total:
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


def _embed_local(entities: list[Entity], model_name: str) -> int:
    """Embed entities via local sentence-transformers model."""
    model = _load_local_model(model_name)
    total = len(entities)
    embedded = 0

    for offset in range(0, total, _BATCH_SIZE):
        batch = entities[offset : offset + _BATCH_SIZE]
        texts = [_entity_text(e) for e in batch]
        try:
            vectors = model.encode(texts, show_progress_bar=False)
        except Exception as exc:
            logger.error("[embeddings] local model encode failed: {}", exc)
            continue

        for entity, vector in zip(batch, vectors):
            entity.embedding = vector.tolist() if hasattr(vector, "tolist") else list(vector)
            embedded += 1

        if embedded % 50 == 0 or offset + _BATCH_SIZE >= total:
            logger.info("Embeddings: {}/{}", embedded, total)

    return embedded


def _resolve_provider(cfg: EmbeddingSettings) -> tuple[str, str]:
    """Resolve (provider, model) from cfg, respecting the run lock."""
    if _active_provider is None or _active_provider == cfg.provider:
        return cfg.provider, cfg.model
    # Locked onto the other provider (via earlier fallback) - use its model
    return _active_provider, cfg.fallback_model


def _dispatch(provider: str, entities: list[Entity], model: str) -> int:
    if provider == "bedrock":
        return _embed_bedrock(entities, model)
    if provider == "sentence-transformers":
        return _embed_local(entities, model)
    raise ValueError(f"Unknown embedding provider: {provider}")


def generate_embeddings(entities: list[Entity], cfg: EmbeddingSettings) -> list[Entity]:
    """Generate embeddings for entities with optional provider fallback.

    Providers: "bedrock" (Titan v2, 1024-dim), "sentence-transformers"
    (all-MiniLM-L6-v2, 384-dim).

    Fallback: if the primary provider fails at the first API call, switch
    to cfg.fallback for this run. Set cfg.fallback=None to disable.

    Single-provider-per-run: once a provider is locked (by first successful
    call or by fallback), subsequent calls reuse it to keep embedding
    dimensions consistent.
    """
    global _active_provider

    if not entities:
        return entities

    resolved_provider, resolved_model = _resolve_provider(cfg)

    try:
        embedded = _dispatch(resolved_provider, entities, resolved_model)
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
        if not cfg.fallback or cfg.fallback == resolved_provider:
            raise

        logger.warning(
            "[embeddings] primary provider '{}' failed ({}), falling back to '{}'",
            resolved_provider,
            type(exc).__name__,
            cfg.fallback,
        )
        # Reset any partial embeddings from failed attempt
        for entity in entities:
            entity.embedding = None

        embedded = _dispatch(cfg.fallback, entities, cfg.fallback_model)
        _active_provider = cfg.fallback
        logger.info(
            "Generated embeddings for {}/{} entities via fallback {}",
            embedded,
            len(entities),
            cfg.fallback,
        )
        return entities

"""Embedding generation with provider fallback.

Supports cloud providers (Bedrock Titan v2), a local CPU fallback
(sentence-transformers all-MiniLM-L6-v2) for deployment resilience, and a
local e5 provider (R47-H582b: intfloat/e5-base-v2, 768-dim, statistical
parity with Titan) honoring the e5 conventions - "query: "/"passage: "
prefixes, mean pooling, bf16 on GPU.

NEW-GRAPHS-ONLY caveat for e5-local: an entity vector index is pinned to the
dimension of the provider/model that built it (Titan 1024-dim vs e5 768-dim),
so e5-local must not be swapped onto a live Titan graph - it is a silent
dimension mismatch. Titan stays the default for exactly this reason.

Single-provider-per-run contract: once a provider is selected (either by
config or via fallback after primary failure), subsequent calls in the
same process use the same provider. This keeps embedding dimensions
consistent across the run.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

import boto3
from loguru import logger

from knowledge_graph_foundry.models import Entity
from knowledge_graph_foundry.settings import ChannelEmbedding, EmbeddingSettings

_BATCH_SIZE = 25

# R47-H582b: e5 conventions. Passage-side text (entities/documents) is prefixed
# "passage: "; a query embedding must use E5_QUERY_PREFIX. Exposed for callers
# that embed queries against an e5-local entity index.
E5_QUERY_PREFIX = "query: "
E5_PASSAGE_PREFIX = "passage: "

# Module-level state: the provider locked in for the current run
_active_provider: Optional[str] = None
_local_model = None  # cached sentence-transformers model instance
_e5_model = None  # cached e5 (sentence-transformers) model instance

# DEF-1 embedding cache: (provider, model, text) -> vector. The same mention
# text recurs hundreds of times within one ingest run (per-chunk mentions,
# recurring entities across documents); embed each unique text once per run.
_CACHE_MAX = 16384
_cache: dict[tuple[str, str, str], list[float]] = {}


def reset_provider_state() -> None:
    """Reset the locked provider state and cache. Intended for tests."""
    global _active_provider, _local_model, _e5_model
    _active_provider = None
    _local_model = None
    _e5_model = None
    _cache.clear()


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


def _load_e5_model(model_name: str):
    """Load and cache a local e5 model (intfloat/e5-*). e5 does mean pooling by
    its own config; we add bf16 on GPU. Full precision on CPU / when torch is
    absent."""
    global _e5_model
    if _e5_model is not None:
        return _e5_model

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers not installed. "
            "Install with: pip install knowledge-graph-foundry[local-embeddings]"
        ) from exc

    logger.info("[embeddings] loading e5 model '{}' (mean pooling; bf16 on GPU)", model_name)
    model = SentenceTransformer(model_name)
    try:
        import torch

        if torch.cuda.is_available():
            model.to(torch.bfloat16)  # in-place for nn.Module; returns self
    except Exception:
        pass  # CPU or no torch - keep full precision
    _e5_model = model
    return _e5_model


def _embed_e5(entities: list[Entity], model_name: str) -> int:
    """Embed entities via a local e5 model: passage-side prefix, normalized
    vectors (R47-H582b)."""
    model = _load_e5_model(model_name)
    total = len(entities)
    embedded = 0

    for offset in range(0, total, _BATCH_SIZE):
        batch = entities[offset : offset + _BATCH_SIZE]
        texts = [E5_PASSAGE_PREFIX + _entity_text(e) for e in batch]
        try:
            vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        except Exception as exc:
            logger.error("[embeddings] e5 encode failed: {}", exc)
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
    if provider == "e5-local":
        return _embed_e5(entities, model)
    raise ValueError(f"Unknown embedding provider: {provider}")


def generate_embeddings(entities: list[Entity], cfg: EmbeddingSettings) -> list[Entity]:
    """Generate embeddings for entities with optional provider fallback.

    Providers: "bedrock" (Titan v2, 1024-dim), "sentence-transformers"
    (all-MiniLM-L6-v2, 384-dim), "e5-local" (intfloat/e5-base-v2, 768-dim,
    passage-prefixed; new graphs only - see the module docstring caveat).

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

    # DEF-1: serve cache hits, dispatch only unique unseen texts
    misses: list[Entity] = []
    hits = 0
    for entity in entities:
        cached = _cache.get((resolved_provider, resolved_model, _entity_text(entity)))
        if cached is not None:
            entity.embedding = cached
            hits += 1
        else:
            misses.append(entity)

    if not misses:
        logger.info("Embeddings: {}/{} from cache", hits, len(entities))
        return entities

    try:
        embedded = _dispatch(resolved_provider, misses, resolved_model)
        _active_provider = resolved_provider
        for entity in misses:
            if entity.embedding and len(_cache) < _CACHE_MAX:
                _cache[(resolved_provider, resolved_model, _entity_text(entity))] = (
                    entity.embedding
                )
        logger.info(
            "Generated embeddings for {}/{} entities via {} ({} cache hits)",
            embedded,
            len(misses),
            resolved_provider,
            hits,
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


# -- channel embeddings (acc-crit Embeddings: provider-abstracted, any model,
# -- GPU by default, per-channel spaces) --------------------------------------

_channel_models: dict[tuple[str, str], object] = {}  # (model, device) -> instance
_channel_dims: dict[tuple[str, str], int] = {}  # (provider, model) -> dimensions


def _load_channel_model(model_name: str, device: str):
    """Load a local HF/sentence-transformers model on the requested GPU.
    Device is the nvidia-smi index or UUID; env pinning must happen before
    the first torch import, so a mask conflict raises instead of silently
    embedding on the wrong card. "cpu" only by explicit config."""
    key = (model_name, device)
    if key in _channel_models:
        return _channel_models[key]

    if device != "cpu":
        if "torch" not in sys.modules:
            os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
            os.environ["CUDA_VISIBLE_DEVICES"] = device
        elif os.environ.get("CUDA_VISIBLE_DEVICES") != device:
            raise RuntimeError(
                f"torch already imported with CUDA_VISIBLE_DEVICES="
                f"{os.environ.get('CUDA_VISIBLE_DEVICES')!r}; cannot repin to "
                f"{device!r} - set the device before the first torch import"
            )
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers not installed - required by the local-gpu provider"
        ) from exc

    try:
        model = SentenceTransformer(model_name, device="cpu" if device == "cpu" else "cuda")
    except Exception as exc:
        cache = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
        raise RuntimeError(
            f"could not load embedding model {model_name!r} (HF cache: {cache}); "
            f"if offline, pre-download it or unset HF_HUB_OFFLINE: {exc}"
        ) from exc
    if device != "cpu":
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError(
                f"device {device!r} requested but CUDA is unavailable - "
                "set device='cpu' explicitly to run on CPU"
            )
        model.half()
    _channel_models[key] = model
    return model


def _embed_openai(texts: list[str], model: str, endpoint: str) -> list[list[float]]:
    """OpenAI-compatible /v1/embeddings endpoint (vLLM, TEI)."""
    import urllib.request

    req = urllib.request.Request(
        endpoint.rstrip("/") + "/v1/embeddings",
        data=json.dumps({"model": model, "input": texts}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        body = json.loads(resp.read())
    rows = sorted(body["data"], key=lambda d: d["index"])
    return [r["embedding"] for r in rows]


def _embed_bedrock_texts(texts: list[str], model: str) -> list[list[float]]:
    profile = os.environ.get("AWS_PROFILE", "kolomolo")
    region = os.environ.get(
        "AWS_REGION_NAME", os.environ.get("AWS_DEFAULT_REGION", "eu-central-1")
    )
    client = boto3.Session(profile_name=profile, region_name=region).client("bedrock-runtime")
    out = []
    for text in texts:
        response = client.invoke_model(
            modelId=model,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({"inputText": text}),
        )
        out.append(json.loads(response["body"].read())["embedding"])
    return out


def embed_channel_texts(texts: list[str], cfg: ChannelEmbedding) -> list[list[float]]:
    """Embed raw texts in a channel's pinned (provider, model) space."""
    if not texts:
        return []
    if cfg.provider == "local-gpu":
        model = _load_channel_model(cfg.model, cfg.device)
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]
    if cfg.provider == "openai":
        if not cfg.endpoint:
            raise ValueError("openai provider requires ChannelEmbedding.endpoint")
        return _embed_openai(texts, cfg.model, cfg.endpoint)
    if cfg.provider == "bedrock":
        return _embed_bedrock_texts(texts, cfg.model)
    raise ValueError(f"Unknown channel embedding provider: {cfg.provider}")


def channel_dimensions(cfg: ChannelEmbedding) -> int:
    """Vector dimensions of the channel's model, derived from the model itself
    (acc-crit dimension-index coupling) - one probe embed, cached."""
    key = (cfg.provider, cfg.model)
    if key not in _channel_dims:
        _channel_dims[key] = len(embed_channel_texts(["dimension probe"], cfg)[0])
    return _channel_dims[key]

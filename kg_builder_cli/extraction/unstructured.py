"""Unstructured document ingestion pipeline orchestrator."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kg_builder_cli.extraction.exemplar_index import ExemplarIndex
    from kg_builder_cli.extraction.type_resolver import BayesianTypeResolver

from loguru import logger

from kg_builder_cli.extraction.chunking import chunk_text
from kg_builder_cli.extraction.dedup import deduplicate, normalize_entity_ids
from kg_builder_cli.extraction.embeddings import generate_embeddings
from kg_builder_cli.extraction.extract import LLMAuthError, create_extraction_client, extract_chunk
from kg_builder_cli.extraction.rate_limiter import TokenBucketRateLimiter


class ExtractionFailedError(RuntimeError):
    """Raised when all chunks in a document fail extraction."""

    def __init__(self, document: str, total_chunks: int):
        self.document = document
        self.total_chunks = total_chunks
        super().__init__(
            f"All {total_chunks} chunks failed extraction for {document} "
            "- check LLM provider configuration and rate limits"
        )


from kg_builder_cli.extraction.parsing import parse_document  # noqa: E402
from kg_builder_cli.extraction.prompts import build_extraction_prompt  # noqa: E402
from kg_builder_cli.extraction.resolution import (  # noqa: E402
    resolve_entities,
    rewire_relationships,
)
from kg_builder_cli.extraction.response_models import build_response_model  # noqa: E402
from kg_builder_cli.ontology.buffer import OntologyBuffer  # noqa: E402
from kg_builder_cli.types.config import AppConfig, LLMConfig  # noqa: E402
from kg_builder_cli.types.document import Chunk  # noqa: E402
from kg_builder_cli.types.extraction import (  # noqa: E402
    Entity,
    ExtractionMetadata,
    ExtractionResult,
    Relationship,
)
from kg_builder_cli.types.ontology import OntologyState  # noqa: E402


def _litellm_model_id(config: LLMConfig) -> str:
    """Build litellm model string from provider config."""
    if not config.model:
        raise ValueError("LLM model not configured. Set llm.model in config.yml")
    if config.provider == "bedrock":
        return f"bedrock/{config.model}"
    return config.model


def _configure_aws_env(config: LLMConfig) -> None:
    """Set AWS environment variables from config for litellm."""
    if config.region:
        os.environ["AWS_REGION_NAME"] = config.region
    if config.profile:
        os.environ["AWS_PROFILE"] = config.profile


def ingest_document(
    file_path: Path,
    config: AppConfig,
    ontology: OntologyState | None = None,
    buffer: OntologyBuffer | None = None,
    exemplar_index: "ExemplarIndex | None" = None,
    doc_index: int = 0,
    total_docs: int = 1,
    phase: str = "direct",
    collector: object | None = None,
    calibrator: object | None = None,
    type_metrics: dict[str, dict[str, float]] | None = None,
    adaptive_state: object | None = None,
) -> ExtractionResult:
    """Run the full unstructured ingestion pipeline.

    Steps:
    1. Parse document into text segments
    2. Chunk segments by token count
    3. Build extraction prompts
    4. Extract entities/relationships per chunk (concurrent)
    5. Deduplicate results
    6. Build ExtractionResult
    """
    logger.info("Starting ingestion: {}", file_path.name)

    # Step 1: Parse
    segments = parse_document(file_path)
    if not segments:
        logger.warning("No text segments extracted from {}", file_path.name)
        return _empty_result(file_path, config)

    # Step 2: Chunk
    chunks = chunk_text(segments, config.extract)
    if not chunks:
        logger.warning("No chunks created from {}", file_path.name)
        return _empty_result(file_path, config)

    logger.info("{} chunks ready for extraction", len(chunks))

    # Step 2b: Schema signal extraction (optional pre-pass)
    if config.extract.schema_signal_extraction and buffer:
        from kg_builder_cli.extraction.schema_signals import (
            compute_coverage,
            extract_schema_signals,
        )

        signal_text = "\n".join(c.text for c in chunks[:3])
        signals = extract_schema_signals(
            signal_text,
            model=config.llm.model,
            provider=config.llm.provider,
            region=config.llm.region,
            profile=config.llm.profile,
        )
        known = buffer.type_names()
        cov = compute_coverage(signals, known)
        logger.info("Schema signal coverage: {:.1%} ({} known types)", cov, len(known))
        # Accumulate new type signals into buffer
        from kg_builder_cli.types.ontology import TypeSignal

        new_signals = []
        for t in signals.entity_types:
            if t.lower() not in {k.lower() for k in known}:
                new_signals.append(TypeSignal(type_name=t, frequency=1))
        for t in signals.relationship_types:
            if t.lower() not in {k.lower() for k in known}:
                new_signals.append(TypeSignal(type_name=t, frequency=1, is_relationship=True))
        if new_signals:
            buffer.accumulate(new_signals)
            logger.info("Added {} new type signals from schema extraction", len(new_signals))

    # Step 3 & 4: Build prompts and extract with concurrency
    all_entities: list[Entity] = []
    all_relationships: list[Relationship] = []

    model_id = _litellm_model_id(config.llm)
    temperature = config.llm.temperature
    max_retries = config.llm.max_retries
    concurrency = max(1, config.extract.concurrency)

    # Configure AWS env and create litellm+instructor client
    _configure_aws_env(config.llm)
    client = create_extraction_client()

    # Use buffer snapshot as ontology if buffer is available
    if buffer:
        ontology = buffer.snapshot(
            resolution_intent=config.ontology_buffer.resolution_intent or "",
        )

    # Build response model (constrained if ontology has types)
    response_model = build_response_model(ontology)

    prompts_and_chunks: list[tuple[Chunk, str]] = [
        (chunk, build_extraction_prompt(chunk, ontology)) for chunk in chunks
    ]

    # Rate limiter: no-op when rate_limit is not configured
    rate = config.llm.rate_limit.requests_per_second if config.llm.rate_limit else 0
    rate_limiter = TokenBucketRateLimiter(rate=rate)
    if config.llm.rate_limit:
        logger.info("Rate limiting enabled: {} req/s", rate)

    def _throttled_extract(chunk, prompt):
        rate_limiter.acquire()
        return extract_chunk(
            chunk,
            prompt,
            model_id,
            client,
            temperature,
            max_retries,
            response_model,
            doc_index=doc_index,
        )

    from kg_builder_cli.events import signals as evt_signals
    from kg_builder_cli.events import types as etypes

    evt_signals.document_extraction_started.send(
        evt_signals.document_extraction_started,
        event=etypes.DocumentExtractionStarted(
            document_source=str(file_path),
            doc_index=doc_index,
            total_docs=total_docs,
            chunk_count=len(chunks),
            phase=phase,
        ),
    )

    completed = 0
    total = len(prompts_and_chunks)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(_throttled_extract, chunk, prompt): chunk.id
            for chunk, prompt in prompts_and_chunks
        }

        failed_chunks = 0
        for future in as_completed(futures):
            chunk_id = futures[future]
            try:
                entities, relationships = future.result()
                all_entities.extend(entities)
                all_relationships.extend(relationships)
                if not entities:
                    failed_chunks += 1
            except LLMAuthError:
                # Cancel remaining futures and propagate immediately
                for f in futures:
                    f.cancel()
                raise
            except Exception:
                logger.exception("Extraction failed for chunk {}", chunk_id)
                failed_chunks += 1

            completed += 1
            if completed % 10 == 0 or completed == total:
                logger.info("Extraction progress: {}/{}", completed, total)

    if failed_chunks == total and total > 0:
        raise ExtractionFailedError(file_path.name, total)

    # Step 4b: Type resolution - Bayesian or Levenshtein fallback
    remap_count = 0
    if ontology and ontology.entity_types:
        allowed = [t.name for t in ontology.entity_types]
        if config.extract.bayesian_resolution and exemplar_index:
            from kg_builder_cli.extraction.type_resolver import (
                BayesianTypeResolver,
            )

            resolver = BayesianTypeResolver(
                config.ontology_buffer,
                ontology.type_frequencies,
                exemplar_index,
                type_exemplars=ontology.type_exemplars,
                llm_config=config.llm if config.extract.llm_escalation else None,
                llm_escalation=config.extract.llm_escalation,
                neo4j_config=config.neo4j if config.extract.llm_escalation else None,
                collector=collector,
                calibrator=calibrator,
                type_metrics=type_metrics,
                adaptive_state=adaptive_state,
            )
            all_entities, remap_count = _resolve_types_bayesian(
                all_entities,
                all_relationships,
                resolver,
                allowed,
            )
        else:
            all_entities, remap_count = _enforce_ontology_types(all_entities, allowed)
    else:
        logger.debug(
            "No ontology types to enforce (ontology={}, types={})",
            ontology is not None,
            len(ontology.entity_types) if ontology else 0,
        )

    # Step 4c: Normalize entity IDs AFTER type enforcement
    all_entities, all_relationships = normalize_entity_ids(all_entities, all_relationships)

    # Step 5: Deduplicate
    deduped_entities, deduped_relationships = deduplicate(all_entities, all_relationships)

    # Step 5c: Generate embeddings for semantic resolution
    use_embeddings = config.extract.use_embeddings
    if use_embeddings:
        logger.info("Generating embeddings for {} entities", len(deduped_entities))
        deduped_entities = generate_embeddings(
            deduped_entities,
            model=config.extract.embedding_model,
        )

    # Step 5d: Entity resolution (multi-signal merge near-duplicates)
    type_freqs = buffer.frequencies() if buffer else None
    resolution = resolve_entities(
        deduped_entities,
        threshold=config.extract.resolution_threshold,
        use_embeddings=use_embeddings,
        embedding_threshold=config.extract.embedding_threshold,
        name_threshold=config.extract.name_threshold,
        type_frequencies=type_freqs,
        cross_type_merge_threshold=config.extract.cross_type_merge_threshold,
        ontology_state=ontology,
        hierarchy_resolution=config.extract.hierarchy_resolution,
        collector=collector,
        calibrator=calibrator,
    )
    deduped_entities = resolution.entities

    # Step 5e: Rewire relationships after cross-type entity merges
    if resolution.id_map:
        deduped_relationships = rewire_relationships(deduped_relationships, resolution.id_map)

    # Step 5f: Record cross-type stats and feed back into ontology buffer
    if buffer:
        if resolution.cross_type_stats:
            buffer.record_cross_type_stats(
                [
                    (s.norm_name, s.type_a, s.type_b, s.doc_index, s.action)
                    for s in resolution.cross_type_stats
                ]
            )
        buffer.accumulate_from_result(deduped_entities, deduped_relationships)

    # Step 6: Build result
    result = ExtractionResult(
        metadata=ExtractionMetadata(
            source=str(file_path),
            model=model_id,
            ontology=_ontology_label(ontology),
            timestamp=datetime.now(),
            chunk_count=len(chunks),
            remap_count=remap_count,
        ),
        entities=deduped_entities,
        relationships=deduped_relationships,
        chunks=chunks,
    )

    evt_signals.document_extraction_completed.send(
        evt_signals.document_extraction_completed,
        event=etypes.DocumentExtractionCompleted(
            document_source=str(file_path.name),
            doc_index=doc_index,
            total_docs=total_docs,
            entity_count=len(deduped_entities),
            rel_count=len(deduped_relationships),
            remap_count=remap_count,
            phase=phase,
        ),
    )

    logger.info(
        "Ingestion complete: {} entities, {} relationships from {}",
        len(deduped_entities),
        len(deduped_relationships),
        file_path.name,
    )
    return result


def _empty_result(file_path: Path, config: AppConfig) -> ExtractionResult:
    """Return an empty extraction result."""
    return ExtractionResult(
        metadata=ExtractionMetadata(
            source=str(file_path),
            model=config.llm.model,
            timestamp=datetime.now(),
        ),
    )


def _enforce_ontology_types(
    entities: list[Entity], allowed_types: list[str]
) -> tuple[list[Entity], int]:
    """Remap entities with types outside the ontology to the closest allowed type.

    Uses Levenshtein ratio to find the best match. Types are only remapped
    when similarity >= min_score (default 0.7). Low-scoring matches are kept
    as-is to avoid semantic corruption (e.g. Mode->Role, Gas->Accessory).

    Returns (entities, remap_count).
    """
    from Levenshtein import ratio as levenshtein_ratio

    min_score = 0.7
    allowed_lower = {t.lower(): t for t in allowed_types}
    remapped = 0

    for entity in entities:
        if entity.type.lower() in allowed_lower:
            # Normalize casing to match ontology
            entity.type = allowed_lower[entity.type.lower()]
            continue

        # Find closest allowed type
        best_score = 0.0
        best_type = allowed_types[0]
        for allowed in allowed_types:
            score = levenshtein_ratio(entity.type.lower(), allowed.lower())
            if score > best_score:
                best_score = score
                best_type = allowed

        if best_score < min_score:
            logger.debug(
                "Type kept: '{}' for '{}' (best match '{}' score={:.2f} < {:.2f})",
                entity.type,
                entity.name,
                best_type,
                best_score,
                min_score,
            )
            continue

        old_type = entity.type
        entity.type = best_type
        remapped += 1
        logger.debug(
            "Type remap: '{}' -> '{}' (score={:.2f}) for '{}'",
            old_type,
            best_type,
            best_score,
            entity.name,
        )

    if remapped > 0:
        logger.info("Type enforcement: remapped {} entities to allowed types", remapped)

    return entities, remapped


def _resolve_types_bayesian(
    entities: list[Entity],
    relationships: list[Relationship],
    resolver: "BayesianTypeResolver",
    allowed_types: list[str],
) -> tuple[list[Entity], int]:
    """Resolve entity types using Bayesian inference.

    Returns (entities, resolved_count).
    """
    from kg_builder_cli.extraction.type_resolver import ResolverContext

    allowed_lower = {t.lower(): t for t in allowed_types}
    resolved = 0

    # Build chunk-entity index for co-occurrence signal
    chunk_entity_map: dict[str, list[Entity]] = {}
    for e in entities:
        for chunk_id in e.source_chunks:
            chunk_entity_map.setdefault(chunk_id, []).append(e)

    for entity in entities:
        # Skip entities already in allowed types
        if entity.type.lower() in allowed_lower:
            entity.type = allowed_lower[entity.type.lower()]
            continue

        # Build context for this entity
        entity_rels = [r for r in relationships if r.source == entity.id or r.target == entity.id]
        # Collect co-occurring entities from same chunks (excluding self)
        chunk_entities: list[Entity] = []
        for chunk_id in entity.source_chunks:
            for co_entity in chunk_entity_map.get(chunk_id, []):
                if co_entity.id != entity.id:
                    chunk_entities.append(co_entity)

        ctx = ResolverContext(
            relationships=entity_rels,
            chunk_entities=chunk_entities,
            entity_embedding=entity.embedding,
        )
        new_type = resolver.resolve(entity, ctx)
        if new_type != entity.type:
            logger.debug(
                "Bayesian type resolve: '{}' {} -> {}",
                entity.name,
                entity.type,
                new_type,
            )
            entity.type = new_type
            resolved += 1

    if resolved > 0:
        logger.info("Bayesian type resolution: resolved {} entities", resolved)

    return entities, resolved


def _ontology_label(ontology: OntologyState | None) -> str:
    """Generate a label for the ontology used."""
    if not ontology:
        return "free"
    if ontology.entity_types:
        return f"constrained ({len(ontology.entity_types)} types)"
    return "empty"

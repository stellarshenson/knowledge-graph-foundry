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
from kg_builder_cli.extraction.extract import create_extraction_client, extract_chunk
from kg_builder_cli.extraction.parsing import parse_document
from kg_builder_cli.extraction.prompts import build_extraction_prompt
from kg_builder_cli.extraction.resolution import resolve_entities, rewire_relationships
from kg_builder_cli.extraction.response_models import build_response_model
from kg_builder_cli.ontology.buffer import OntologyBuffer
from kg_builder_cli.types.config import AppConfig, LLMConfig
from kg_builder_cli.types.document import Chunk
from kg_builder_cli.types.extraction import (
    Entity,
    ExtractionMetadata,
    ExtractionResult,
    Relationship,
)
from kg_builder_cli.types.ontology import OntologyState


def _litellm_model_id(config: LLMConfig) -> str:
    """Build litellm model string from provider config."""
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
        ontology = buffer.snapshot()

    # Build response model (constrained if ontology has types)
    response_model = build_response_model(ontology)

    intent = config.ontology_buffer.intent
    prompts_and_chunks: list[tuple[Chunk, str]] = [
        (chunk, build_extraction_prompt(chunk, ontology, intent=intent)) for chunk in chunks
    ]

    completed = 0
    total = len(prompts_and_chunks)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(
                extract_chunk,
                chunk,
                prompt,
                model_id,
                client,
                temperature,
                max_retries,
                response_model,
            ): chunk.id
            for chunk, prompt in prompts_and_chunks
        }

        for future in as_completed(futures):
            chunk_id = futures[future]
            try:
                entities, relationships = future.result()
                all_entities.extend(entities)
                all_relationships.extend(relationships)
            except Exception:
                logger.exception("Extraction failed for chunk {}", chunk_id)

            completed += 1
            if completed % 10 == 0 or completed == total:
                logger.info("Extraction progress: {}/{}", completed, total)

    # Step 4b: Type resolution - Bayesian or Levenshtein fallback
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
            )
            all_entities = _resolve_types_bayesian(
                all_entities,
                all_relationships,
                resolver,
                allowed,
            )
        else:
            all_entities = _enforce_ontology_types(all_entities, allowed)
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
    deduped_entities = resolve_entities(
        deduped_entities,
        threshold=config.extract.resolution_threshold,
        use_embeddings=use_embeddings,
        embedding_threshold=config.extract.embedding_threshold,
        name_threshold=config.extract.name_threshold,
        type_frequencies=type_freqs,
    )

    # Step 5e: Rewire relationships after cross-type entity merges
    id_map = getattr(resolve_entities, "_last_id_map", {})
    if id_map:
        deduped_relationships = rewire_relationships(deduped_relationships, id_map)

    # Step 5f: Feed back into ontology buffer
    if buffer:
        buffer.accumulate_from_result(deduped_entities, deduped_relationships)

    # Step 6: Build result
    result = ExtractionResult(
        metadata=ExtractionMetadata(
            source=str(file_path),
            model=model_id,
            ontology=_ontology_label(ontology),
            timestamp=datetime.now(),
            chunk_count=len(chunks),
        ),
        entities=deduped_entities,
        relationships=deduped_relationships,
        chunks=chunks,
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


def _enforce_ontology_types(entities: list[Entity], allowed_types: list[str]) -> list[Entity]:
    """Remap entities with types outside the ontology to the closest allowed type.

    Uses Levenshtein ratio to find the best match. If no match exceeds 0.4,
    defaults to the most generic type (first in the allowed list).
    """
    from Levenshtein import ratio as levenshtein_ratio

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

    return entities


def _resolve_types_bayesian(
    entities: list[Entity],
    relationships: list[Relationship],
    resolver: "BayesianTypeResolver",
    allowed_types: list[str],
) -> list[Entity]:
    """Resolve entity types using Bayesian inference."""
    from kg_builder_cli.extraction.type_resolver import ResolverContext

    allowed_lower = {t.lower(): t for t in allowed_types}
    resolved = 0

    for entity in entities:
        # Skip entities already in allowed types
        if entity.type.lower() in allowed_lower:
            entity.type = allowed_lower[entity.type.lower()]
            continue

        # Build context for this entity
        entity_rels = [r for r in relationships if r.source == entity.id or r.target == entity.id]
        ctx = ResolverContext(
            relationships=entity_rels,
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

    return entities


def _ontology_label(ontology: OntologyState | None) -> str:
    """Generate a label for the ontology used."""
    if not ontology:
        return "free"
    if ontology.entity_types:
        return f"constrained ({len(ontology.entity_types)} types)"
    return "empty"

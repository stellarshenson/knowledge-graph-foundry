"""Unstructured document ingestion pipeline orchestrator."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from loguru import logger

from kg_builder_cli.extraction.chunking import chunk_text
from kg_builder_cli.extraction.dedup import deduplicate
from kg_builder_cli.extraction.extract import extract_chunk
from kg_builder_cli.extraction.parsing import parse_document
from kg_builder_cli.extraction.prompts import build_extraction_prompt
from kg_builder_cli.types.config import AppConfig
from kg_builder_cli.types.document import Chunk
from kg_builder_cli.types.extraction import (
    Entity,
    ExtractionMetadata,
    ExtractionResult,
    Relationship,
)
from kg_builder_cli.types.ontology import OntologyState


def ingest_document(
    file_path: Path,
    config: AppConfig,
    ontology: OntologyState | None = None,
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

    model_id = config.llm.model
    region = config.llm.region or "us-east-1"
    profile = config.llm.profile or ""
    concurrency = max(1, config.extract.concurrency)

    intent = config.ontology_buffer.intent
    prompts_and_chunks: list[tuple[Chunk, str]] = [
        (chunk, build_extraction_prompt(chunk, ontology, intent=intent)) for chunk in chunks
    ]

    completed = 0
    total = len(prompts_and_chunks)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(
                extract_chunk, chunk, prompt, model_id, region, profile
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

    # Step 5: Deduplicate
    deduped_entities, deduped_relationships = deduplicate(
        all_entities, all_relationships
    )

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


def _ontology_label(ontology: OntologyState | None) -> str:
    """Generate a label for the ontology used."""
    if not ontology:
        return "free"
    if ontology.entity_types:
        return f"constrained ({len(ontology.entity_types)} types)"
    return "empty"

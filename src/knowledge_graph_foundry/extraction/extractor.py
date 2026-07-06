"""Chunk extraction (LLM) and structured-source mapping (LLM once, then deterministic)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import re

from pydantic import BaseModel, Field

from knowledge_graph_foundry.engines.base import Engine
from knowledge_graph_foundry.events import emit
from knowledge_graph_foundry.extraction.prompts import extraction_messages
from knowledge_graph_foundry.models import (
    Chunk,
    Entity,
    ExtractionResult,
    Ontology,
    Relationship,
    entity_id,
)
from knowledge_graph_foundry.ontology.seed import normalize_type_name

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def normalize_relationship_type(name: str) -> str:
    """Deterministic UPPER_SNAKE_CASE: 'supports mode', 'supportsMode' -> SUPPORTS_MODE."""
    words: list[str] = []
    for token in re.split(r"[\s_\-]+", name.strip()):
        if token:
            words.extend(_CAMEL_BOUNDARY.split(token))
    return "_".join(w.upper() for w in words)


class WireEntity(BaseModel):
    """Entity as the LLM returns it - names, not ids."""

    name: str
    types: list[str] = Field(default_factory=list)
    description: str = ""
    properties: dict[str, str] = Field(default_factory=dict)


class WireRelationship(BaseModel):
    """Relationship as the LLM returns it - endpoint entity names."""

    source: str
    target: str
    type: str
    description: str = ""


class WireExtraction(BaseModel):
    entities: list[WireEntity] = Field(default_factory=list)
    relationships: list[WireRelationship] = Field(default_factory=list)


def extract_chunk(
    chunk: Chunk, purpose: str, ontology: Ontology, engine: Engine
) -> ExtractionResult:
    """Extract one chunk: LLM call, wire-to-domain conversion, relationship validation."""
    wire = engine.complete(extraction_messages(chunk.text, purpose, ontology), WireExtraction)

    entities = [
        Entity.create(
            name=we.name,
            types=[normalize_type_name(t) for t in we.types],
            description=we.description,
            properties=dict(we.properties),
            source_documents=[chunk.document_id],
            source_chunks=[chunk.id],
        )
        for we in wire.entities
    ]
    known_ids = {e.id for e in entities}

    relationships: list[Relationship] = []
    for wr in wire.relationships:
        source_id, target_id = entity_id(wr.source), entity_id(wr.target)
        if source_id not in known_ids or target_id not in known_ids:
            emit(
                "extraction.warning",
                reason=f"dangling relationship: {wr.source} -[{wr.type}]-> {wr.target}",
                chunk=chunk.id,
            )
            continue
        if source_id == target_id:
            emit(
                "extraction.warning",
                reason=f"self-referencing relationship on {wr.source}",
                chunk=chunk.id,
            )
            continue
        relationships.append(
            Relationship(
                source_id=source_id,
                target_id=target_id,
                type=normalize_relationship_type(wr.type),
                description=wr.description,
                source_documents=[chunk.document_id],
                source_chunks=[chunk.id],
            )
        )

    return ExtractionResult(entities=entities, relationships=relationships)


def extract_document(
    chunks: list[Chunk],
    purpose: str,
    ontology: Ontology,
    engine: Engine,
    concurrency: int = 4,
) -> ExtractionResult:
    """Extract all chunks in parallel; failing chunks are skipped, order preserved."""
    results: list[ExtractionResult | None] = [None] * len(chunks)

    def _run(index: int, chunk: Chunk) -> None:
        try:
            results[index] = extract_chunk(chunk, purpose, ontology, engine)
        except Exception as exc:
            emit("extraction.warning", reason=f"chunk extraction failed: {exc}", chunk=chunk.id)

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for index, chunk in enumerate(chunks):
            pool.submit(_run, index, chunk)

    combined = ExtractionResult()
    for result in results:
        if result is not None:
            combined.entities.extend(result.entities)
            combined.relationships.extend(result.relationships)

    emit(
        "extraction.completed",
        chunks=len(chunks),
        entities=len(combined.entities),
        relationships=len(combined.relationships),
    )
    return combined


class RelationshipColumn(BaseModel):
    column: str
    relationship_type: str
    target_type: str


class SourceMapping(BaseModel):
    """Column-to-entity mapping for a structured source, inferred once via LLM."""

    entity_column: str
    entity_type: str
    property_columns: list[str] = Field(default_factory=list)
    relationship_columns: list[RelationshipColumn] = Field(default_factory=list)


_MAPPING_PROMPT = """You map columns of a structured data source to a knowledge graph schema.

Graph purpose (guiding principle): {purpose}

Given the sample rows, decide: which column holds the entity name (entity_column),
the entity type (PascalCase), which columns are entity properties (property_columns),
and which columns reference other entities (relationship_columns with column,
relationship_type in UPPER_SNAKE_CASE, and target_type in PascalCase)."""


def structured_mapping(sample_rows: list[dict], purpose: str, engine: Engine) -> SourceMapping:
    """Infer the column-to-entity mapping once from sample rows via the engine."""
    messages = [
        {"role": "system", "content": _MAPPING_PROMPT.format(purpose=purpose)},
        {"role": "user", "content": json.dumps(sample_rows, default=str)},
    ]
    return engine.complete(messages, SourceMapping)


def apply_mapping(rows: list[dict], mapping: SourceMapping, document_id: str) -> ExtractionResult:
    """Apply an inferred mapping to rows deterministically - no LLM involved."""
    entity_type = normalize_type_name(mapping.entity_type)
    result = ExtractionResult()

    for row in rows:
        name = row.get(mapping.entity_column)
        if name is None or str(name).strip() == "":
            continue
        name = str(name)
        result.entities.append(
            Entity.create(
                name=name,
                types=[entity_type],
                properties={
                    column: row[column]
                    for column in mapping.property_columns
                    if row.get(column) is not None
                },
                source_documents=[document_id],
            )
        )
        for rel in mapping.relationship_columns:
            target = row.get(rel.column)
            if target is None or str(target).strip() == "":
                continue
            target = str(target)
            result.entities.append(
                Entity.create(
                    name=target,
                    types=[normalize_type_name(rel.target_type)],
                    source_documents=[document_id],
                )
            )
            result.relationships.append(
                Relationship(
                    source_id=entity_id(name),
                    target_id=entity_id(target),
                    type=normalize_relationship_type(rel.relationship_type),
                    source_documents=[document_id],
                )
            )

    return result

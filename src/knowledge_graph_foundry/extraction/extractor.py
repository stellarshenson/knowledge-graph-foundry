"""Chunk extraction (LLM) and structured-source mapping (LLM once, then deterministic)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import re

from pydantic import BaseModel, Field

from knowledge_graph_foundry.engines.base import Engine
from knowledge_graph_foundry.events import emit
from knowledge_graph_foundry.extraction.prompts import (
    entity_only_messages,
    enumeration_messages,
    extraction_messages,
    gleaning_messages,
    relation_only_messages,
)
from knowledge_graph_foundry.models import (
    Chunk,
    Entity,
    ExtractionResult,
    Ontology,
    Relationship,
    entity_id,
)
from knowledge_graph_foundry.ontology.seed import normalize_type_name
from knowledge_graph_foundry.settings import ExtractionSettings

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_ENUM_OBJECT = re.compile(r"\{.*\}", re.DOTALL)  # outermost JSON object
_ENUM_NAME = re.compile(r'"name"\s*:\s*"([^"]+)"')  # regex fallback on parse failure
_ENUM_CANDIDATE_CAP = 150  # H246: cap candidate names fed to stage 2


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


def _parse_enumeration(raw: str) -> list[str]:
    """Parse stage-1 names-only output: strip fences, regex outermost {...}, JSON-then-regex
    fallback (reproduces the measured harness tolerance). Order-preserving dedup, capped."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    match = _ENUM_OBJECT.search(text)
    blob = match.group(0) if match else text
    names: list[str] = []
    try:
        data = json.loads(blob)
        for entity in data.get("entities", []):
            name = entity.get("name")
            if name:
                names.append(name)
    except Exception:
        names = _ENUM_NAME.findall(blob)
    return list(dict.fromkeys(names))[:_ENUM_CANDIDATE_CAP]


def _enumerate_names(chunk_text: str, purpose: str, engine: Engine) -> list[str]:
    """H246 stage 1: names-only plain-chat completion, parsed to a candidate list."""
    raw = engine.complete_text(enumeration_messages(chunk_text, purpose)[0]["content"], chunk_text)
    return _parse_enumeration(raw)


def _first_pass(
    chunk_text: str, purpose: str, ontology: Ontology, engine: Engine, cfg: ExtractionSettings
) -> WireExtraction:
    """Run the initial extraction: recipe selects single/split, enumerate (H246), or mention (H258)."""
    if cfg.recipe == "enumerate":
        candidates = _enumerate_names(chunk_text, purpose, engine)
        return engine.complete(
            extraction_messages(chunk_text, purpose, ontology, candidate_names=candidates),
            WireExtraction,
        )
    if cfg.recipe == "mention":
        return engine.complete(
            extraction_messages(chunk_text, purpose, ontology, mention=True), WireExtraction
        )

    if not cfg.split_entity_relation:
        return engine.complete(extraction_messages(chunk_text, purpose, ontology), WireExtraction)

    ent = engine.complete(entity_only_messages(chunk_text, purpose, ontology), WireExtraction)
    names = [we.name for we in ent.entities]
    rel = engine.complete(
        relation_only_messages(chunk_text, names, purpose, ontology), WireExtraction
    )
    return WireExtraction(entities=ent.entities, relationships=rel.relationships)


def _gather_wire(
    chunk_text: str, purpose: str, ontology: Ontology, engine: Engine, cfg: ExtractionSettings
) -> WireExtraction:
    """First pass plus gleaning rounds; dedup entities by id and relationships by endpoints/type."""
    entities: list[WireEntity] = []
    relationships: list[WireRelationship] = []
    seen_entities: set[str] = set()
    seen_relationships: set[tuple[str, str, str]] = set()

    def _merge(wire: WireExtraction) -> int:
        added = 0
        for we in wire.entities:
            eid = entity_id(we.name)
            if eid in seen_entities:
                continue
            seen_entities.add(eid)
            entities.append(we)
            added += 1
        for wr in wire.relationships:
            key = (
                entity_id(wr.source),
                entity_id(wr.target),
                normalize_relationship_type(wr.type),
            )
            if key in seen_relationships:
                continue
            seen_relationships.add(key)
            relationships.append(wr)
            added += 1
        return added

    _merge(_first_pass(chunk_text, purpose, ontology, engine, cfg))

    for _ in range(cfg.gleaning_rounds):
        existing = [we.name for we in entities]
        glean = engine.complete(
            gleaning_messages(chunk_text, existing, purpose, ontology), WireExtraction
        )
        if _merge(glean) == 0:
            break

    return WireExtraction(entities=entities, relationships=relationships)


def extract_chunk(
    chunk: Chunk,
    purpose: str,
    ontology: Ontology,
    engine: Engine,
    extraction_cfg: ExtractionSettings | None = None,
) -> ExtractionResult:
    """Extract one chunk: LLM call(s), wire-to-domain conversion, relationship validation."""
    cfg = extraction_cfg or ExtractionSettings()
    wire = _gather_wire(chunk.text, purpose, ontology, engine, cfg)

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
    extraction_cfg: ExtractionSettings | None = None,
) -> ExtractionResult:
    """Extract all chunks in parallel; failing chunks are skipped, order preserved."""
    cfg = extraction_cfg or ExtractionSettings()
    results: list[ExtractionResult | None] = [None] * len(chunks)

    def _run(index: int, chunk: Chunk) -> None:
        try:
            results[index] = extract_chunk(chunk, purpose, ontology, engine, cfg)
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

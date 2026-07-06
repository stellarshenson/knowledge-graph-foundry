"""Ontology seeding: none (seedless), YAML/JSON, OWL, or freeform text via LLM."""

from __future__ import annotations

import json
from pathlib import Path
import re

from pydantic import BaseModel, Field, ValidationError
import yaml

from knowledge_graph_foundry.engines.base import Engine
from knowledge_graph_foundry.models import Ontology, RelationshipTypeDef, TypeDef


class SeedError(ValueError):
    """Seed could not be parsed into an ontology."""


class SeedType(BaseModel):
    name: str
    description: str = ""
    properties: list[str] = Field(default_factory=list)


class SeedRelationshipType(BaseModel):
    name: str
    description: str = ""


class SeedNormalization(BaseModel):
    """LLM response model for freeform seed normalization."""

    types: list[SeedType] = Field(default_factory=list)
    relationship_types: list[SeedRelationshipType] = Field(default_factory=list)


_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

_SEED_PROMPT = """You normalize a freeform schema description into a typed ontology.

Graph purpose (guiding principle): {purpose}

Extract entity types (PascalCase names, short descriptions, property names) and
relationship types (UPPER_SNAKE_CASE names, short descriptions) from the user's
schema description. Keep only types relevant to the purpose."""


def normalize_type_name(name: str) -> str:
    """Deterministic PascalCase: 'operating mode', 'operating_mode', 'operatingMode' -> OperatingMode."""
    words: list[str] = []
    for token in re.split(r"[\s_\-]+", name.strip()):
        if token:
            words.extend(_CAMEL_BOUNDARY.split(token))
    return "".join(w[:1].upper() + w[1:] for w in words)


def load_seed(source: Path | str | None, purpose: str, engine: Engine | None = None) -> Ontology:
    """Build a seeded Ontology from a file, freeform text, or nothing (seedless)."""
    if source is None:
        return Ontology(purpose=purpose)
    if isinstance(source, Path):
        return _load_file(source, purpose)
    try:
        if Path(source).exists():
            return _load_file(Path(source), purpose)
    except OSError:
        pass  # not a valid path - treat as freeform text
    if engine is None:
        raise SeedError("freeform seed requires an engine for normalization, none provided")
    return _normalize_freeform(source, purpose, engine)


def _load_file(path: Path, purpose: str) -> Ontology:
    suffix = path.suffix.lower()
    if suffix in {".yml", ".yaml", ".json"}:
        return _load_structured(path, purpose)
    if suffix in {".owl", ".rdf", ".xml"}:
        return _load_owl(path, purpose)
    raise SeedError(f"unsupported seed file extension {suffix!r}: {path}")


def _load_structured(path: Path, purpose: str) -> Ontology:
    """Parse a YAML/JSON seed directly, no LLM involved."""
    try:
        with open(path) as f:
            data = yaml.safe_load(f) if path.suffix.lower() in {".yml", ".yaml"} else json.load(f)
    except (OSError, yaml.YAMLError, json.JSONDecodeError) as exc:
        raise SeedError(f"cannot parse seed file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SeedError(f"cannot parse seed file {path}: expected a mapping at top level")
    try:
        types = [
            SeedType(name=item) if isinstance(item, str) else SeedType(**item)
            for item in data.get("types") or []
        ]
        rel_types = [
            SeedRelationshipType(name=item)
            if isinstance(item, str)
            else SeedRelationshipType(**item)
            for item in data.get("relationship_types") or []
        ]
    except (ValidationError, TypeError) as exc:
        raise SeedError(f"cannot parse seed file {path}: {exc}") from exc
    return _build_ontology(purpose, types, rel_types)


def _load_owl(path: Path, purpose: str) -> Ontology:
    """Parse an OWL/RDF seed: classes -> types, object properties -> relationship types."""
    import owlready2

    try:
        owl = owlready2.get_ontology(f"file://{path.resolve()}").load()
    except Exception as exc:
        raise SeedError(f"cannot parse OWL seed {path}: {exc}") from exc
    types = [
        SeedType(name=cls.label.first() or cls.name, description=cls.comment.first() or "")
        for cls in owl.classes()
    ]
    rel_types = [
        SeedRelationshipType(
            name=prop.label.first() or prop.name, description=prop.comment.first() or ""
        )
        for prop in owl.object_properties()
    ]
    return _build_ontology(purpose, types, rel_types)


def _normalize_freeform(text: str, purpose: str, engine: Engine) -> Ontology:
    """Normalize a natural-language schema description into an ontology via the engine."""
    messages = [
        {"role": "system", "content": _SEED_PROMPT.format(purpose=purpose)},
        {"role": "user", "content": text},
    ]
    result = engine.complete(messages, SeedNormalization)
    return _build_ontology(purpose, result.types, result.relationship_types)


def _build_ontology(
    purpose: str, types: list[SeedType], rel_types: list[SeedRelationshipType]
) -> Ontology:
    """Assemble the Ontology - seeded types carry status "seeded": treated as
    confirmed, and protected from demotion and from being clustered away."""
    ontology = Ontology(purpose=purpose)
    for seed_type in types:
        name = normalize_type_name(seed_type.name)
        ontology.types[name] = TypeDef(
            name=name,
            description=seed_type.description,
            properties=seed_type.properties,
            encounters=0,
            status="seeded",
        )
    for rel in rel_types:
        ontology.relationship_types[rel.name] = RelationshipTypeDef(
            name=rel.name, description=rel.description, encounters=0
        )
    return ontology

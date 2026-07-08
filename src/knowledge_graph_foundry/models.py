"""Core domain models for Knowledge Graph Foundry.

Design rule: entity identity derives from the normalized name (and later,
embedding evidence) - never from type. Types are mutable multi-label
attributes; a dual-role entity (Component and Accessory) is one node with
two labels, not two nodes.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Optional
import unicodedata

from pydantic import BaseModel, Field


def normalize_name(name: str) -> str:
    """Canonical form of an entity name used for identity and lookup."""
    return " ".join(name.strip().lower().split())


# R15-H190 glyph normalization operator (glyph_carryover_r14 notebook, ported
# verbatim). Strip trademark glyphs BEFORE NFKC (NFKC maps U+2122 to the letters
# "TM", which would corrupt the match), NFKC-fold ligatures/fullwidth/nbsp, then
# translate the unicode punctuation family (dashes to "-", curly quotes, exotic
# spaces to " ", zero-width/soft-hyphen deleted). Promoted: 69/69 previously-absent
# names recovered, 0 false conflations on the 2797-name vocabulary.
_SYM_DELETE = dict.fromkeys(map(ord, "™®©℠℗"), None)
_PUNCT = {
    0x2010: "-",
    0x2011: "-",
    0x2012: "-",
    0x2013: "-",
    0x2014: "-",
    0x2015: "-",
    0x2212: "-",
    0x2018: "'",
    0x2019: "'",
    0x201A: "'",
    0x201B: "'",
    0x201C: '"',
    0x201D: '"',
    0x201E: '"',
    0x00A0: " ",
    0x2007: " ",
    0x202F: " ",
    0x2009: " ",
    0x200A: " ",
    0x2002: " ",
    0x2003: " ",
    0x2004: " ",
    0x2005: " ",
    0x2006: " ",
    0x2008: " ",
    0x3000: " ",
    0x200B: "",
    0x200C: "",
    0x200D: "",
    0xFEFF: "",
    0x00AD: "",
}


def glyph_clean_text(text: str) -> str:
    """Structure-preserving glyph cleanup for parsed document text (H190 parser
    post-process). Applies the operator's character transforms - strip trademark
    glyphs, NFKC-fold, translate punctuation variants - but NOT the lowercase and
    whitespace-collapse tail of `glyph_norm`, so casing and newlines survive for
    chunking, table detection and extraction. The name-key form is glyph_norm."""
    text = text or ""
    text = text.translate(_SYM_DELETE)
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_SYM_DELETE)  # NFKC can re-expose composed glyphs
    return text.translate(_PUNCT)


def glyph_norm(name: str) -> str:
    """Glyph-normalized name key for the H190 resolver name-identity detector:
    glyph_clean_text followed by lowercase and whitespace collapse. Used only at
    comparison time - entity ids still derive from `normalize_name`."""
    return " ".join(glyph_clean_text(name).lower().split())


def glyph_nospace(name: str) -> str:
    """Space-insensitive variant of glyph_norm."""
    return re.sub(r"\s+", "", glyph_norm(name))


def entity_id(name: str) -> str:
    """Deterministic entity id from the normalized name only (no type)."""
    return "e_" + hashlib.sha1(normalize_name(name).encode()).hexdigest()[:16]


def chunk_id(document_id: str, index: int, text: str) -> str:
    """Deterministic chunk id, stable across runs."""
    digest = hashlib.sha1(f"{document_id}:{index}:{text}".encode()).hexdigest()[:16]
    return f"c_{digest}"


class Chunk(BaseModel):
    id: str
    document_id: str
    index: int
    text: str
    token_count: int


class Document(BaseModel):
    id: str
    path: str
    format: str
    text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class Entity(BaseModel):
    id: str
    name: str
    types: list[str] = Field(default_factory=list)
    description: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[list[float]] = None
    source_documents: list[str] = Field(default_factory=list)
    source_chunks: list[str] = Field(default_factory=list)

    @classmethod
    def create(cls, name: str, types: list[str], **kwargs: Any) -> "Entity":
        return cls(id=entity_id(name), name=name, types=types, **kwargs)


class Relationship(BaseModel):
    source_id: str
    target_id: str
    type: str
    description: str = ""
    properties: dict[str, Any] = Field(default_factory=dict)
    source_documents: list[str] = Field(default_factory=list)
    source_chunks: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """Validated output of one chunk extraction."""

    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)


class TypeDef(BaseModel):
    """One ontology type with evidence counters."""

    name: str
    description: str = ""
    properties: list[str] = Field(default_factory=list)
    encounters: int = 0
    status: str = "emerging"  # emerging | confirmed | cured


class RelationshipTypeDef(BaseModel):
    name: str
    description: str = ""
    encounters: int = 0


class Ontology(BaseModel):
    """The evolving (fluid) or cured type system."""

    purpose: str = ""
    types: dict[str, TypeDef] = Field(default_factory=dict)
    relationship_types: dict[str, RelationshipTypeDef] = Field(default_factory=dict)
    cured: bool = False


class StabilityMetrics(BaseModel):
    """Decision-free stability signals computed after each document."""

    document_index: int
    type_count: int
    entity_count: int
    shannon_entropy: float
    entropy_delta: float
    jsd: float
    chao1_coverage: float
    heaps_beta: Optional[float] = None


class ResolutionDecision(BaseModel):
    """One pairwise merge decision with full evidence for forensics."""

    left_id: str
    right_id: str
    prior: float
    lr_description: float
    lr_embedding: float
    lr_cooccurrence: float
    posterior: float
    decision: str  # merge | defer | block

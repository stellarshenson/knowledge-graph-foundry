"""Shared Pydantic models - zero logic, pure data contracts."""

from .config import (
    AppConfig,
    ExtractConfig,
    LLMConfig,
    LoadConfig,
    MemoryConfig,
    Neo4jConfig,
    OntologyBufferConfig,
    PathsConfig,
)
from .document import Chunk, ChunkMetadata, DocumentMetadata, TextSegment
from .extraction import (
    Entity,
    ExtractionMetadata,
    ExtractionResult,
    Fact,
    Relationship,
)
from .loading import LoadBatch, LoadResult, ValidationReport
from .ontology import (
    NormDiagnostic,
    OntologyState,
    PropertyDef,
    RelationshipDef,
    TypeDef,
    TypeSignal,
)
from .pipeline import PipelineEvent, PipelineStats, RunReport
from .resolution import NormalizationMeta, ResolvedEntity

__all__ = [
    # config
    "AppConfig",
    "ExtractConfig",
    "LLMConfig",
    "LoadConfig",
    "MemoryConfig",
    "Neo4jConfig",
    "OntologyBufferConfig",
    "PathsConfig",
    # document
    "Chunk",
    "ChunkMetadata",
    "DocumentMetadata",
    "TextSegment",
    # extraction
    "Entity",
    "ExtractionMetadata",
    "ExtractionResult",
    "Fact",
    "Relationship",
    # loading
    "LoadBatch",
    "LoadResult",
    "ValidationReport",
    # ontology
    "NormDiagnostic",
    "OntologyState",
    "PropertyDef",
    "RelationshipDef",
    "TypeDef",
    "TypeSignal",
    # pipeline
    "PipelineEvent",
    "PipelineStats",
    "RunReport",
    # resolution
    "NormalizationMeta",
    "ResolvedEntity",
]

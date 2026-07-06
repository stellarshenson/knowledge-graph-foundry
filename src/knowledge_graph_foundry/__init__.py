"""Knowledge Graph Foundry - public API.

Use KGF as a library component in any host application:

    from knowledge_graph_foundry import Foundry, Settings, Neo4jSettings

    settings = Settings(
        neo4j=Neo4jSettings(uri="bolt://host:7687", user="neo4j", password="pw"),
    )
    with Foundry(settings) as kgf:
        kgf.init_project("compare CPAP machines")
        kgf.ingest("data/manuals/")
        print(kgf.status())
        print(kgf.query("AirSense 11 vs DreamStation pressure range?"))

Every knob is on `Settings` (pydantic) - construct it directly, or load a
config.yml with env overrides via `load_settings`. `Foundry.from_config()`
does the same. The lower-level building blocks (extraction, resolution,
ontology lifecycle, graph loading, temporal reads) are importable from their
subpackages for embedding individual stages.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from knowledge_graph_foundry import config  # noqa: F401  (side-effect: logging + paths)
from knowledge_graph_foundry.engines import Engine, EngineError, create_engine
from knowledge_graph_foundry.events import (
    SIGNALS,
    disable_event_log,
    emit,
    enable_event_log,
    subscribe,
    unsubscribe,
)
from knowledge_graph_foundry.models import (
    Chunk,
    Document,
    Entity,
    Ontology,
    Relationship,
    ResolutionDecision,
    StabilityMetrics,
    TypeDef,
    entity_id,
    normalize_name,
)
from knowledge_graph_foundry.pipeline import Foundry, FoundryError, build
from knowledge_graph_foundry.settings import (
    CuringSettings,
    DriftSettings,
    EmbeddingSettings,
    ExtractionSettings,
    GraphRAGSettings,
    LLMSettings,
    LoadSettings,
    Neo4jSettings,
    ResolutionSettings,
    Settings,
    load_settings,
)

try:
    __version__ = _pkg_version("knowledge-graph-foundry")
except PackageNotFoundError:  # pragma: no cover - source checkout without install
    __version__ = "0.0.0"

__all__ = [
    # entrypoint
    "build",
    "Foundry",
    "FoundryError",
    # configuration (full surface)
    "Settings",
    "load_settings",
    "Neo4jSettings",
    "LLMSettings",
    "EmbeddingSettings",
    "ExtractionSettings",
    "ResolutionSettings",
    "CuringSettings",
    "DriftSettings",
    "GraphRAGSettings",
    "LoadSettings",
    # domain models
    "Entity",
    "Relationship",
    "Document",
    "Chunk",
    "Ontology",
    "TypeDef",
    "StabilityMetrics",
    "ResolutionDecision",
    "entity_id",
    "normalize_name",
    # LLM engines
    "Engine",
    "EngineError",
    "create_engine",
    # events
    "emit",
    "subscribe",
    "unsubscribe",
    "enable_event_log",
    "disable_event_log",
    "SIGNALS",
    # metadata
    "__version__",
]

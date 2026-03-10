"""In-memory ontology buffer that accumulates type signals during ingestion."""
from __future__ import annotations

from pathlib import Path

import yaml
from loguru import logger

from kg_builder_cli.types.config import OntologyBufferConfig
from kg_builder_cli.types.extraction import Entity, Relationship
from kg_builder_cli.types.ontology import (
    OntologyState,
    RelationshipDef,
    TypeDef,
    TypeSignal,
)


class OntologyBuffer:
    """Mutable ontology buffer that evolves during ingestion.

    Tracks entity types, relationship types, frequencies, and variants.
    Produces frozen OntologyState snapshots for extraction.
    """

    def __init__(self, config: OntologyBufferConfig):
        self._entity_types: dict[str, TypeDef] = {}
        self._relationship_types: dict[str, RelationshipDef] = {}
        self._frequencies: dict[str, int] = {}
        self._variants: dict[str, str] = {}
        self._seed_types: set[str] = set()
        self._seed_rel_types: set[str] = set()
        self._config = config

    @classmethod
    def from_yaml(cls, path: Path, config: OntologyBufferConfig) -> OntologyBuffer:
        """Load ontology from YAML seed file and pre-confirm seed types."""
        buffer = cls(config)

        with open(path) as f:
            data = yaml.safe_load(f)

        if not data or not isinstance(data, dict):
            logger.warning("Empty or invalid ontology YAML: {}", path)
            return buffer

        # Load entity types
        for type_data in data.get("entity_types", []):
            name = type_data.get("name", "")
            if not name:
                continue
            typedef = TypeDef(
                name=name,
                description=type_data.get("description", ""),
                properties=type_data.get("properties", {}),
            )
            buffer._entity_types[name] = typedef
            buffer._seed_types.add(name)
            # Pre-confirm seed types above threshold
            buffer._frequencies[name] = config.min_frequency_to_confirm

        # Load relationship types
        for rel_data in data.get("relationship_types", []):
            name = rel_data.get("name", "")
            if not name:
                continue
            reldef = RelationshipDef(
                name=name,
                source_type=rel_data.get("source_type", ""),
                target_type=rel_data.get("target_type", ""),
                description=rel_data.get("description", ""),
            )
            buffer._relationship_types[name] = reldef
            buffer._seed_rel_types.add(name)
            buffer._frequencies[name] = config.min_frequency_to_confirm

        logger.info(
            "Loaded ontology seed: {} entity types, {} relationship types from {}",
            len(buffer._entity_types),
            len(buffer._relationship_types),
            path,
        )
        return buffer

    def snapshot(self) -> OntologyState:
        """Return a frozen snapshot of the current ontology state.

        Types are tiered by frequency:
        - confirmed: seed types OR frequency >= threshold (included in prompt)
        - emerging: frequency >= 2 but < threshold (shown as suggestions)
        - noise: frequency == 1 and not seed (excluded from prompt)
        """
        threshold = self._config.min_frequency_to_confirm
        confirmed = frozenset(
            name for name, freq in self._frequencies.items()
            if freq >= threshold and name in self._entity_types
        )
        emerging = frozenset(
            name for name in self._entity_types
            if name not in confirmed
            and self._frequencies.get(name, 0) >= 2
        )
        candidate = frozenset(
            name for name in self._entity_types
            if name not in confirmed
        )

        # Filter entity types: include confirmed + emerging, exclude noise
        included_names = confirmed | emerging
        filtered_types = tuple(
            td for td in self._entity_types.values()
            if td.name in included_names
        )
        # Relationship types: include seed + confirmed frequency
        filtered_rels = tuple(
            rd for rd in self._relationship_types.values()
            if rd.name in self._seed_rel_types
            or self._frequencies.get(rd.name, 0) >= threshold
        )

        total = len(self._entity_types)
        cov = len(confirmed) / total if total > 0 else 0.0

        return OntologyState(
            entity_types=filtered_types,
            relationship_types=filtered_rels,
            coverage=cov,
            variants=dict(self._variants),
            confirmed_types=confirmed,
            candidate_types=candidate,
            type_frequencies=dict(self._frequencies),
            emerging_types=emerging,
        )

    def accumulate(self, signals: list[TypeSignal]) -> None:
        """Increment frequencies and add new types from signals."""
        for signal in signals:
            name = signal.type_name
            self._frequencies[name] = self._frequencies.get(name, 0) + signal.frequency

            if signal.is_relationship:
                if name not in self._relationship_types:
                    self._relationship_types[name] = RelationshipDef(
                        name=name, source_type="", target_type="",
                    )
            else:
                if name not in self._entity_types:
                    self._entity_types[name] = TypeDef(name=name)

    def accumulate_from_result(
        self, entities: list[Entity], relationships: list[Relationship]
    ) -> None:
        """Convenience wrapper: extract type signals from extraction results."""
        signals: list[TypeSignal] = []

        # Entity type signals
        type_counts: dict[str, int] = {}
        for entity in entities:
            type_counts[entity.type] = type_counts.get(entity.type, 0) + 1
        for type_name, count in type_counts.items():
            signals.append(TypeSignal(type_name=type_name, frequency=count))

        # Relationship type signals
        rel_counts: dict[str, int] = {}
        for rel in relationships:
            rel_counts[rel.type] = rel_counts.get(rel.type, 0) + 1
        for rel_type, count in rel_counts.items():
            signals.append(
                TypeSignal(type_name=rel_type, frequency=count, is_relationship=True)
            )

        self.accumulate(signals)

    def coverage(self) -> float:
        """Return fraction of confirmed types over total entity types."""
        total = len(self._entity_types)
        if total == 0:
            return 0.0
        threshold = self._config.min_frequency_to_confirm
        confirmed = sum(
            1 for name in self._entity_types
            if self._frequencies.get(name, 0) >= threshold
        )
        return confirmed / total

    def flush(self, path: Path) -> None:
        """Write confirmed types to YAML file."""
        threshold = self._config.min_frequency_to_confirm

        entity_types = []
        for name, typedef in self._entity_types.items():
            if self._frequencies.get(name, 0) >= threshold:
                entry = {"name": typedef.name, "description": typedef.description}
                if typedef.properties:
                    entry["properties"] = typedef.properties
                entity_types.append(entry)

        rel_types = []
        for name, reldef in self._relationship_types.items():
            if self._frequencies.get(name, 0) >= threshold:
                entry = {
                    "name": reldef.name,
                    "source_type": reldef.source_type,
                    "target_type": reldef.target_type,
                    "description": reldef.description,
                }
                rel_types.append(entry)

        data = {
            "entity_types": entity_types,
            "relationship_types": rel_types,
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        logger.info(
            "Flushed ontology: {} entity types, {} relationship types to {}",
            len(entity_types),
            len(rel_types),
            path,
        )

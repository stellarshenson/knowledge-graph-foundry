"""In-memory ontology buffer that accumulates type signals during ingestion."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
import yaml

from kg_builder_cli.extraction.dedup import normalize_type_name
from kg_builder_cli.types.config import OntologyBufferConfig
from kg_builder_cli.types.extraction import Entity, Relationship
from kg_builder_cli.types.ontology import (
    OntologyState,
    RelationshipDef,
    TypeDef,
    TypeExemplar,
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
        # Maps normalized PascalCase -> first-seen raw form
        self._canonical_map: dict[str, str] = {}
        # Type exemplars: canonical type name -> list of representative entities
        self._type_exemplars: dict[str, list[TypeExemplar]] = {}

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
            buffer._register_canonical(name)
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
            buffer._register_canonical(name)
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
            name
            for name, freq in self._frequencies.items()
            if freq >= threshold and name in self._entity_types
        )
        emerge_threshold = self._config.min_frequency_to_emerge
        emerging = frozenset(
            name
            for name in self._entity_types
            if name not in confirmed and self._frequencies.get(name, 0) >= emerge_threshold
        )
        candidate = frozenset(name for name in self._entity_types if name not in confirmed)

        # Filter entity types: include confirmed + emerging, exclude noise
        included_names = confirmed | emerging
        filtered_types = tuple(
            td for td in self._entity_types.values() if td.name in included_names
        )
        # Relationship types: include seed + confirmed frequency
        filtered_rels = tuple(
            rd
            for rd in self._relationship_types.values()
            if rd.name in self._seed_rel_types or self._frequencies.get(rd.name, 0) >= threshold
        )

        total = len(self._entity_types)
        cov = len(confirmed) / total if total > 0 else 0.0

        # Freeze type exemplars (only for included types)
        frozen_exemplars: dict[str, tuple[TypeExemplar, ...]] = {}
        for type_name in included_names:
            exs = self._type_exemplars.get(type_name, [])
            if exs:
                frozen_exemplars[type_name] = tuple(sorted(exs, key=lambda e: -e.frequency))

        return OntologyState(
            entity_types=filtered_types,
            relationship_types=filtered_rels,
            coverage=cov,
            variants=dict(self._variants),
            confirmed_types=confirmed,
            candidate_types=candidate,
            type_frequencies=dict(self._frequencies),
            emerging_types=emerging,
            type_exemplars=frozen_exemplars,
        )

    def canonical_type(self, raw: str) -> str:
        """Return the canonical (first-seen) form for a raw type name.

        If the normalized form is unknown, returns the raw name unchanged.
        """
        canonical = normalize_type_name(raw)
        return self._canonical_map.get(canonical, raw)

    def _register_canonical(self, raw: str) -> str:
        """Register a raw type name and return its canonical form.

        First-seen raw form wins. All subsequent surface variants are
        collapsed to the first-seen form.
        """
        normalized = normalize_type_name(raw)
        if normalized not in self._canonical_map:
            self._canonical_map[normalized] = raw
        return self._canonical_map[normalized]

    def accumulate(self, signals: list[TypeSignal]) -> None:
        """Increment frequencies and add new types from signals.

        Surface variants are collapsed via canonical mapping so that
        e.g. "Work_Mode", "work mode", "WorkMode" all track as one type.
        """
        for signal in signals:
            raw_name = signal.type_name
            canonical_name = self._register_canonical(raw_name)
            self._frequencies[canonical_name] = (
                self._frequencies.get(canonical_name, 0) + signal.frequency
            )

            if signal.is_relationship:
                if canonical_name not in self._relationship_types:
                    self._relationship_types[canonical_name] = RelationshipDef(
                        name=canonical_name,
                        source_type="",
                        target_type="",
                    )
            else:
                if canonical_name not in self._entity_types:
                    self._entity_types[canonical_name] = TypeDef(name=canonical_name)

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
            signals.append(TypeSignal(type_name=rel_type, frequency=count, is_relationship=True))

        self.accumulate(signals)

        # Update type exemplars
        self._update_exemplars(entities)

    def _update_exemplars(self, entities: list[Entity]) -> None:
        """Update type exemplars from extracted entities."""
        max_exemplars = self._config.max_type_exemplars
        # Count entity occurrences by (type, normalized_name), track description
        entity_counts: dict[tuple[str, str], tuple[str, int, str]] = {}
        for entity in entities:
            canonical_type = self.canonical_type(entity.type)
            norm_name = entity.name.strip().lower()
            key = (canonical_type, norm_name)
            if key in entity_counts:
                raw_name, count, desc = entity_counts[key]
                # Keep the longest description seen
                if len(entity.description) > len(desc):
                    desc = entity.description
                entity_counts[key] = (raw_name, count + 1, desc)
            else:
                entity_counts[key] = (entity.name, 1, entity.description)

        for (canonical_type, norm_name), (raw_name, count, desc) in entity_counts.items():
            if canonical_type not in self._entity_types:
                continue
            exemplars = self._type_exemplars.setdefault(canonical_type, [])
            # Check if already present (deduplicate by normalized name)
            existing = next((e for e in exemplars if e.name.strip().lower() == norm_name), None)
            if existing:
                existing.frequency += count
                if desc and len(desc) > len(existing.description):
                    existing.description = desc
                continue
            if len(exemplars) < max_exemplars:
                exemplars.append(
                    TypeExemplar(
                        name=raw_name,
                        entity_type=canonical_type,
                        frequency=count,
                        description=desc,
                    )
                )
            else:
                # Replace lowest-frequency exemplar if new entity has higher frequency
                min_ex = min(exemplars, key=lambda e: e.frequency)
                if count > min_ex.frequency:
                    exemplars.remove(min_ex)
                    exemplars.append(
                        TypeExemplar(
                            name=raw_name,
                            entity_type=canonical_type,
                            frequency=count,
                            description=desc,
                        )
                    )

    def frequencies(self) -> dict[str, int]:
        """Return copy of current type frequency counts."""
        return dict(self._frequencies)

    def type_names(self) -> set[str]:
        """Return the set of all known entity type names."""
        return set(self._entity_types.keys())

    def entity_type_frequencies(self) -> dict[str, int]:
        """Return frequencies for entity types only (excludes relationship types)."""
        return {name: self._frequencies.get(name, 0) for name in self._entity_types}

    def prune_low_frequency_types(self, threshold_pct: float) -> set[str]:
        """Remove entity types below the threshold percentage of total entities.

        Returns the set of pruned type names.
        """
        total_entities = sum(self._frequencies.get(name, 0) for name in self._entity_types)
        if total_entities == 0:
            return set()

        min_count = total_entities * (threshold_pct / 100.0)
        pruned: set[str] = set()

        for name in list(self._entity_types.keys()):
            freq = self._frequencies.get(name, 0)
            if freq < min_count and name not in self._seed_types:
                del self._entity_types[name]
                pruned.add(name)

        if pruned:
            logger.info(
                "Pruned {} low-frequency types (threshold={:.1f}%, min_count={:.0f}): {}",
                len(pruned),
                threshold_pct,
                min_count,
                ", ".join(sorted(pruned)),
            )

        return pruned

    def coverage(self) -> float:
        """Return fraction of confirmed types over total entity types."""
        total = len(self._entity_types)
        if total == 0:
            return 0.0
        threshold = self._config.min_frequency_to_confirm
        confirmed = sum(
            1 for name in self._entity_types if self._frequencies.get(name, 0) >= threshold
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

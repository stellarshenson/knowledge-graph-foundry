"""In-memory ontology buffer that accumulates type signals during ingestion."""

from __future__ import annotations

import hashlib
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
    TypeHierarchyEntry,
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
        # H5g: type hierarchy, resolution guide, cross-type stats
        self._type_hierarchy: list[TypeHierarchyEntry] = []
        self._child_to_parent: dict[str, str] = {}
        self._resolution_guide: str = ""
        # Cross-type stats: (norm_name, type_a, type_b) -> {doc_indices, type_a_count, type_b_count}
        self._cross_type_stats: dict[tuple[str, str, str], dict] = {}
        # Track which (norm_name, type_a, type_b) keys have already generated guide rules
        self._evolved_guide_keys: set[tuple[str, str, str]] = set()

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

        # Load type hierarchy (H5g)
        for hier_data in data.get("type_hierarchy", []):
            name = hier_data.get("name", "")
            if not name:
                continue
            entry = TypeHierarchyEntry(
                name=name,
                description=hier_data.get("description", ""),
                children=hier_data.get("children", []),
            )
            buffer._type_hierarchy.append(entry)
            for child in entry.children:
                buffer._child_to_parent[child] = name

        # Load resolution guide (H5g) - resolution_intent lives in config.yml only
        buffer._resolution_guide = data.get("resolution_guide", "") or ""

        # Load type exemplars from YAML (H5g)
        for type_name, exemplar_list in data.get("type_exemplars", {}).items():
            if not isinstance(exemplar_list, list):
                continue
            for ex_data in exemplar_list:
                if not isinstance(ex_data, dict):
                    continue
                ex = TypeExemplar(
                    name=ex_data.get("name", ""),
                    entity_type=type_name,
                    frequency=ex_data.get("frequency", 1),
                    description=ex_data.get("description", ""),
                )
                buffer._type_exemplars.setdefault(type_name, []).append(ex)

        logger.info(
            "Loaded ontology seed: {} entity types, {} relationship types, "
            "{} hierarchy entries from {}",
            len(buffer._entity_types),
            len(buffer._relationship_types),
            len(buffer._type_hierarchy),
            path,
        )
        return buffer

    def compute_hash(self) -> str:
        """Compute a deterministic hash of confirmed entity and relationship types.

        Returns 16 hex chars of SHA256 over sorted confirmed type names and
        sorted confirmed relationship type names. Changes when confirmed types change.
        """
        threshold = self._config.min_frequency_to_confirm
        confirmed_entities = sorted(
            name
            for name, freq in self._frequencies.items()
            if freq >= threshold and name in self._entity_types
        )
        confirmed_rels = sorted(
            name
            for name, freq in self._frequencies.items()
            if freq >= threshold and name in self._relationship_types
        )
        content = "|".join(confirmed_entities) + "||" + "|".join(confirmed_rels)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @classmethod
    def from_graph(cls, driver, config: OntologyBufferConfig) -> OntologyBuffer:
        """Reconstruct an OntologyBuffer from graph-resident control plane data.

        Queries entity type frequencies from domain nodes, relationship types
        from domain relationships, type definitions from KGFOntologyType nodes,
        hierarchy from IS_A relationships, resolution guide from
        KGFResolutionGuide nodes, exemplars from entity samples, and calibration
        state from KGFTypeCalibration nodes.
        """
        buffer = cls(config)

        with driver.session() as session:
            # Query 1: entity type frequencies from domain nodes
            result = session.run(
                "MATCH (n:Entity) WHERE NOT n:KGFControl "
                "RETURN n.type AS t, count(n) AS freq ORDER BY freq DESC"
            )
            for record in result:
                type_name = record["t"]
                freq = record["freq"]
                if type_name:
                    buffer._entity_types[type_name] = TypeDef(name=type_name)
                    buffer._frequencies[type_name] = freq
                    buffer._register_canonical(type_name)
                    if freq >= config.min_frequency_to_confirm:
                        buffer._seed_types.add(type_name)

            # Query 2: relationship types from domain relationships
            result = session.run(
                "MATCH (a:Entity)-[r]->(b:Entity) "
                "WHERE NOT a:KGFControl AND NOT b:KGFControl "
                "RETURN DISTINCT type(r) AS t"
            )
            for record in result:
                rel_type = record["t"]
                if rel_type:
                    buffer._relationship_types[rel_type] = RelationshipDef(
                        name=rel_type, source_type="", target_type=""
                    )
                    buffer._register_canonical(rel_type)
                    if rel_type not in buffer._frequencies:
                        buffer._frequencies[rel_type] = config.min_frequency_to_confirm
                    buffer._seed_rel_types.add(rel_type)

            # Query 3: type definitions from control plane
            result = session.run("MATCH (n:KGFControl:KGFOntologyType) RETURN n")
            for record in result:
                node = record["n"]
                name = node.get("name", "")
                if not name:
                    continue
                desc = node.get("description", "")
                props_raw = node.get("properties")
                props = {}
                if props_raw and isinstance(props_raw, str):
                    try:
                        import json

                        props = json.loads(props_raw)
                    except (json.JSONDecodeError, TypeError):
                        pass
                elif isinstance(props_raw, dict):
                    props = props_raw
                buffer._entity_types[name] = TypeDef(name=name, description=desc, properties=props)
                buffer._register_canonical(name)

            # Query 4: type hierarchy from IS_A relationships
            result = session.run(
                "MATCH (c:KGFControl:KGFOntologyType)-[:IS_A]->(p:KGFControl:KGFOntologyType) "
                "RETURN c.name AS child, p.name AS parent"
            )
            hierarchy_map: dict[str, list[str]] = {}
            for record in result:
                child = record["child"]
                parent = record["parent"]
                if child and parent:
                    hierarchy_map.setdefault(parent, []).append(child)
                    buffer._child_to_parent[child] = parent
            for parent_name, children in hierarchy_map.items():
                entry = TypeHierarchyEntry(
                    name=parent_name,
                    description=f"Parent category for {', '.join(sorted(children))}",
                    children=sorted(children),
                )
                buffer._type_hierarchy.append(entry)

            # Query 5: resolution guide
            result = session.run(
                "MATCH (n:KGFControl:KGFResolutionGuide) RETURN n.rules AS rules LIMIT 1"
            )
            guide_record = result.single()
            if guide_record and guide_record["rules"]:
                buffer._resolution_guide = guide_record["rules"]

            # Query 6: sample exemplars per type
            result = session.run(
                "MATCH (n:Entity) WHERE NOT n:KGFControl "
                "WITH n.type AS t, collect({name: n.name, description: n.description})[0..5] AS exs "
                "RETURN t, exs"
            )
            for record in result:
                type_name = record["t"]
                exs = record["exs"]
                if not type_name or not exs:
                    continue
                for ex_data in exs:
                    if not isinstance(ex_data, dict):
                        continue
                    ex = TypeExemplar(
                        name=ex_data.get("name", ""),
                        entity_type=type_name,
                        frequency=1,
                        description=ex_data.get("description", ""),
                    )
                    buffer._type_exemplars.setdefault(type_name, []).append(ex)

            # Query 7: calibration state (loaded but not yet applied to resolver)
            result = session.run("MATCH (n:KGFControl:KGFTypeCalibration) RETURN n")
            calibration_data: dict[str, dict] = {}
            for record in result:
                node = record["n"]
                name = node.get("name", "")
                if name:
                    calibration_data[name] = {
                        "entity_count": node.get("entity_count", 0),
                        "mean_posterior": node.get("mean_posterior", 0.0),
                        "observation_count": node.get("observation_count", 0),
                        "remap_count": node.get("remap_count", 0),
                        "prior_strength": node.get("prior_strength", 1.0),
                    }

        # Store calibration data for downstream consumers
        buffer._calibration_data = calibration_data

        logger.info(
            "ontology buffer loaded from graph: {} types, {} rels, {} hierarchy entries",
            len(buffer._entity_types),
            len(buffer._relationship_types),
            len(buffer._type_hierarchy),
        )
        return buffer

    def snapshot(self, resolution_intent: str = "") -> OntologyState:
        """Return a frozen snapshot of the current ontology state.

        Args:
            resolution_intent: User-provided extraction intent from config.yml.
                Flows through to OntologyState for prompt injection.

        Types are tiered by frequency:
        - confirmed: seed types OR frequency >= threshold (included in prompt)
        - emerging: frequency >= emerge threshold but < confirm threshold
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
        # Relationship types: include seed + discovered (emerge threshold)
        filtered_rels = tuple(
            rd
            for rd in self._relationship_types.values()
            if rd.name in self._seed_rel_types
            or self._frequencies.get(rd.name, 0) >= emerge_threshold
        )

        total = len(self._entity_types)
        cov = len(confirmed) / total if total > 0 else 0.0

        # Freeze type exemplars (only for included types)
        frozen_exemplars: dict[str, tuple[TypeExemplar, ...]] = {}
        for type_name in included_names:
            exs = self._type_exemplars.get(type_name, [])
            if exs:
                frozen_exemplars[type_name] = tuple(sorted(exs, key=lambda e: -e.frequency))

        from kg_builder_cli.events import signals as evt_signals
        from kg_builder_cli.events import types as etypes

        evt_signals.buffer_snapshot_taken.send(
            evt_signals.buffer_snapshot_taken,
            event=etypes.BufferSnapshotTaken(
                path="",
                entity_type_count=len(filtered_types),
                rel_type_count=len(filtered_rels),
            ),
        )

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
            type_hierarchy=tuple(self._type_hierarchy),
            resolution_intent=resolution_intent,
            resolution_guide=self._resolution_guide,
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

        from kg_builder_cli.events import signals as evt_signals
        from kg_builder_cli.events import types as etypes

        evt_signals.ontology_signals_accumulated.send(
            evt_signals.ontology_signals_accumulated,
            event=etypes.OntologySignalsAccumulated(
                new_entity_types=len([s for s in signals if not s.is_relationship]),
                new_rel_types=len([s for s in signals if s.is_relationship]),
                total_entity_types=len(self._entity_types),
                total_rel_types=len(self._relationship_types),
            ),
        )

    def _update_exemplars(self, entities: list[Entity]) -> None:
        """Update type exemplars from extracted entities."""
        max_exemplars = self._config.max_type_exemplars
        updated_types: set[str] = set()
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
                updated_types.add(canonical_type)
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
                updated_types.add(canonical_type)
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
                    updated_types.add(canonical_type)

        if updated_types:
            from kg_builder_cli.events import signals as evt_signals
            from kg_builder_cli.events import types as etypes

            for type_name in updated_types:
                evt_signals.buffer_exemplars_updated.send(
                    evt_signals.buffer_exemplars_updated,
                    event=etypes.BufferExemplarsUpdated(
                        entity_type=type_name,
                        exemplar_count=len(self._type_exemplars.get(type_name, [])),
                    ),
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

            from kg_builder_cli.events import signals as evt_signals
            from kg_builder_cli.events import types as etypes

            evt_signals.buffer_types_pruned.send(
                evt_signals.buffer_types_pruned,
                event=etypes.BufferTypesPruned(
                    pruned_entity_types=sorted(pruned),
                    pruned_rel_types=[],
                    remaining_entity_types=len(self._entity_types),
                    remaining_rel_types=len(self._relationship_types),
                ),
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

        # Type hierarchy
        hierarchy_data = []
        for entry in self._type_hierarchy:
            # Only include hierarchy entries whose children are confirmed types
            confirmed_children = [
                c for c in entry.children if self._frequencies.get(c, 0) >= threshold
            ]
            if confirmed_children:
                hierarchy_data.append(
                    {
                        "name": entry.name,
                        "description": entry.description,
                        "children": confirmed_children,
                    }
                )

        # Type exemplars (top N per confirmed type)
        exemplar_data: dict[str, list[dict]] = {}
        max_exemplars = self._config.max_type_exemplars
        confirmed_names = {
            name
            for name, freq in self._frequencies.items()
            if freq >= threshold and name in self._entity_types
        }
        for type_name in confirmed_names:
            exs = self._type_exemplars.get(type_name, [])
            if exs:
                sorted_exs = sorted(exs, key=lambda e: -e.frequency)[:max_exemplars]
                exemplar_data[type_name] = [
                    {"name": e.name, "frequency": e.frequency, "description": e.description}
                    for e in sorted_exs
                ]

        data: dict = {
            "entity_types": entity_types,
            "relationship_types": rel_types,
        }
        if hierarchy_data:
            data["type_hierarchy"] = hierarchy_data
        if self._resolution_guide:
            data["resolution_guide"] = self._resolution_guide
        if exemplar_data:
            data["type_exemplars"] = exemplar_data

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        logger.info(
            "Flushed ontology: {} entity types, {} relationship types, "
            "{} hierarchy entries, {} exemplar types to {}",
            len(entity_types),
            len(rel_types),
            len(hierarchy_data),
            len(exemplar_data),
            path,
        )
        if self._resolution_guide:
            logger.info(
                "[guide] resolution_guide flushed:\n{}",
                self._resolution_guide.strip(),
            )

        from kg_builder_cli.events import signals as evt_signals
        from kg_builder_cli.events import types as etypes

        evt_signals.ontology_flushed.send(
            evt_signals.ontology_flushed,
            event=etypes.OntologyFlushed(
                path=str(path),
                entity_type_count=len(entity_types),
                rel_type_count=len(rel_types),
                has_guide=bool(self._resolution_guide),
            ),
        )

    def shared_parent(self, type_a: str, type_b: str) -> str | None:
        """Return shared parent name if both types are siblings, else None."""
        parent_a = self._child_to_parent.get(type_a)
        parent_b = self._child_to_parent.get(type_b)
        if parent_a and parent_b and parent_a == parent_b:
            return parent_a
        return None

    def has_different_parents(self, type_a: str, type_b: str) -> bool:
        """Return True if both types have parents but different ones."""
        parent_a = self._child_to_parent.get(type_a)
        parent_b = self._child_to_parent.get(type_b)
        return bool(parent_a and parent_b and parent_a != parent_b)

    def record_cross_type_stats(
        self,
        stats: list[tuple[str, str, str, int, str]],
    ) -> None:
        """Record cross-type pair observations for hierarchy/guide evolution.

        Each stat is (norm_name, type_a, type_b, doc_index, action).
        """
        for norm_name, type_a, type_b, doc_index, action in stats:
            # Normalize key order for consistent tracking
            key = (norm_name, *sorted([type_a, type_b]))
            entry = self._cross_type_stats.setdefault(
                key, {"doc_indices": set(), "type_counts": {}}
            )
            entry["doc_indices"].add(doc_index)
            entry["type_counts"][type_a] = entry["type_counts"].get(type_a, 0) + 1
            entry["type_counts"][type_b] = entry["type_counts"].get(type_b, 0) + 1

        # Auto-evolve when evidence crosses thresholds
        self._maybe_evolve()

    def _maybe_evolve(self) -> None:
        """Auto-evolve hierarchy and guide when any type pair reaches encounter threshold.

        Aggregates encounters per (type_a, type_b) pair across all entity names,
        matching the aggregation logic in evolve_type_hierarchy().
        Hierarchy always evolves when evidence is sufficient.
        Resolution guide evolution is gated by config.resolution_guide_evolution.
        """
        from kg_builder_cli.settings.defaults import GUIDE_EVOLUTION_MIN_ENCOUNTERS

        # Aggregate encounters per type pair across all names
        pair_encounters: dict[tuple[str, str], int] = {}
        for (_norm_name, type_a, type_b), entry in self._cross_type_stats.items():
            pair_key = (type_a, type_b)
            encounters = sum(entry["type_counts"].values()) // 2
            pair_encounters[pair_key] = pair_encounters.get(pair_key, 0) + encounters

        for pair_key, encounters in pair_encounters.items():
            if encounters >= GUIDE_EVOLUTION_MIN_ENCOUNTERS:
                hierarchy_before = len(self._type_hierarchy)
                self.evolve_type_hierarchy()
                hierarchy_changes = len(self._type_hierarchy) - hierarchy_before
                guide_rules = 0
                if self._config.resolution_guide_evolution:
                    guide_keys_before = len(self._evolved_guide_keys)
                    self.evolve_resolution_guide()
                    guide_rules = len(self._evolved_guide_keys) - guide_keys_before

                if hierarchy_changes or guide_rules:
                    from kg_builder_cli.events import signals as evt_signals
                    from kg_builder_cli.events import types as etypes

                    evt_signals.ontology_evolved.send(
                        evt_signals.ontology_evolved,
                        event=etypes.OntologyEvolved(
                            hierarchy_changes=hierarchy_changes,
                            guide_rules_added=guide_rules,
                            trigger="cross_type_evidence",
                        ),
                    )
                return

    def evolve_type_hierarchy(self) -> None:
        """Discover parent-child groupings from recurring cross-type patterns.

        Conservative: a hierarchy entry is created only when two types have
        accumulated >= GUIDE_EVOLUTION_MIN_ENCOUNTERS total pair encounters
        (frequency-based, not document-based).
        """
        from kg_builder_cli.settings.defaults import GUIDE_EVOLUTION_MIN_ENCOUNTERS

        if not self._cross_type_stats:
            return

        # Aggregate encounter counts per type pair across all entity names
        pair_encounters: dict[tuple[str, str], int] = {}
        for (_norm_name, type_a, type_b), entry in self._cross_type_stats.items():
            pair_key = (type_a, type_b)
            encounters = sum(entry["type_counts"].values()) // 2
            pair_encounters[pair_key] = pair_encounters.get(pair_key, 0) + encounters

        # Build hierarchy for qualifying pairs
        new_entries: dict[str, set[str]] = {}
        existing_children = set(self._child_to_parent.keys())

        for (type_a, type_b), encounters in pair_encounters.items():
            if encounters < GUIDE_EVOLUTION_MIN_ENCOUNTERS:
                logger.debug(
                    "[hierarchy] pair ({}, {}) has {} encounters < {} threshold",
                    type_a,
                    type_b,
                    encounters,
                    GUIDE_EVOLUTION_MIN_ENCOUNTERS,
                )
                from kg_builder_cli.events import signals as evt_signals
                from kg_builder_cli.events import types as etypes

                evt_signals.hierarchy_skipped.send(
                    evt_signals.hierarchy_skipped,
                    event=etypes.HierarchySkipped(
                        type_a=type_a,
                        type_b=type_b,
                        encounters=encounters,
                        threshold=GUIDE_EVOLUTION_MIN_ENCOUNTERS,
                        reason="below_encounter_threshold",
                    ),
                )
                continue
            # Skip if both already have parents
            if type_a in existing_children and type_b in existing_children:
                continue

            logger.info(
                "[hierarchy] qualifying pair ({}, {}) with {} encounters >= {} threshold",
                type_a,
                type_b,
                encounters,
                GUIDE_EVOLUTION_MIN_ENCOUNTERS,
            )
            from kg_builder_cli.events import signals as evt_signals
            from kg_builder_cli.events import types as etypes

            evt_signals.hierarchy_pair_qualifying.send(
                evt_signals.hierarchy_pair_qualifying,
                event=etypes.HierarchyPairQualifying(
                    type_a=type_a,
                    type_b=type_b,
                    encounters=encounters,
                    threshold=GUIDE_EVOLUTION_MIN_ENCOUNTERS,
                ),
            )
            # Generate parent name from type descriptions or simple heuristic
            parent_name = self._infer_parent_name(type_a, type_b)
            new_entries.setdefault(parent_name, set()).update([type_a, type_b])

        if not new_entries:
            return

        for parent_name, children in new_entries.items():
            # Check if parent already exists in hierarchy
            existing = next((e for e in self._type_hierarchy if e.name == parent_name), None)
            if existing:
                new_children = []
                for child in children:
                    if child not in existing.children:
                        existing.children.append(child)
                        self._child_to_parent[child] = parent_name
                        new_children.append(child)
                if new_children:
                    logger.info(
                        "[hierarchy] evolved parent '{}': added children {} to existing {}",
                        parent_name,
                        sorted(new_children),
                        existing.children,
                    )
                    from kg_builder_cli.events import signals as evt_signals
                    from kg_builder_cli.events import types as etypes

                    evt_signals.hierarchy_evolved.send(
                        evt_signals.hierarchy_evolved,
                        event=etypes.HierarchyEvolved(
                            parent_name=parent_name,
                            children=sorted(existing.children),
                            is_new=False,
                        ),
                    )
            else:
                entry = TypeHierarchyEntry(
                    name=parent_name,
                    description=f"Parent category for {', '.join(sorted(children))}",
                    children=sorted(children),
                )
                self._type_hierarchy.append(entry)
                for child in children:
                    self._child_to_parent[child] = parent_name
                logger.info(
                    "[hierarchy] evolved new parent '{}' with children: {}",
                    parent_name,
                    sorted(children),
                )
                from kg_builder_cli.events import signals as evt_signals
                from kg_builder_cli.events import types as etypes

                evt_signals.hierarchy_evolved.send(
                    evt_signals.hierarchy_evolved,
                    event=etypes.HierarchyEvolved(
                        parent_name=parent_name,
                        children=sorted(children),
                        is_new=True,
                    ),
                )

    def _infer_parent_name(self, type_a: str, type_b: str) -> str:
        """Infer a parent category name for two sibling types."""
        # Simple heuristics based on known domain patterns
        physical_types = {"Component", "Accessory", "Part"}
        behavior_types = {"Feature", "Setting", "WorkMode", "Mode"}
        spec_types = {"Specification", "Parameter", "Metric"}

        types = {type_a, type_b}
        if types & physical_types:
            return "Part"
        if types & behavior_types:
            return "Behavior"
        if types & spec_types:
            return "Measurement"
        # Fallback: concatenate
        return f"{type_a}Or{type_b}"

    def evolve_resolution_guide(self) -> None:
        """Generate disambiguation rules from recurring cross-type patterns.

        Conservative: rules only generated when a pattern meets all thresholds
        for encounter frequency, type dominance, and hierarchy coverage.
        Deduplicated via _evolved_guide_keys to prevent repeated calls from
        producing duplicate rules.
        """
        from kg_builder_cli.settings.defaults import (
            GUIDE_EVOLUTION_MIN_DOMINANCE,
            GUIDE_EVOLUTION_MIN_ENCOUNTERS,
        )

        if not self._cross_type_stats:
            return

        new_rules: list[str] = []

        from kg_builder_cli.events import signals as evt_signals
        from kg_builder_cli.events import types as etypes

        for (norm_name, type_a, type_b), entry in self._cross_type_stats.items():
            key = (norm_name, type_a, type_b)

            # Skip if already generated a rule for this key
            if key in self._evolved_guide_keys:
                evt_signals.guide_rule_skipped.send(
                    evt_signals.guide_rule_skipped,
                    event=etypes.GuideRuleSkipped(
                        entity_name=norm_name,
                        type_a=type_a,
                        type_b=type_b,
                        dominance=0.0,
                        encounters=0,
                        reason="already_generated",
                    ),
                )
                continue

            # Threshold 1: encounter frequency
            pair_encounters = sum(entry["type_counts"].values()) // 2
            if pair_encounters < GUIDE_EVOLUTION_MIN_ENCOUNTERS:
                evt_signals.guide_rule_skipped.send(
                    evt_signals.guide_rule_skipped,
                    event=etypes.GuideRuleSkipped(
                        entity_name=norm_name,
                        type_a=type_a,
                        type_b=type_b,
                        dominance=0.0,
                        encounters=pair_encounters,
                        reason="below_encounter_threshold",
                    ),
                )
                continue

            # Threshold 2: type dominance
            counts = entry["type_counts"]
            total = sum(counts.values())
            if total == 0:
                continue
            dominant_type = max(counts, key=lambda t: counts[t])
            dominance = counts[dominant_type] / total
            if dominance < GUIDE_EVOLUTION_MIN_DOMINANCE:
                evt_signals.guide_rule_skipped.send(
                    evt_signals.guide_rule_skipped,
                    event=etypes.GuideRuleSkipped(
                        entity_name=norm_name,
                        type_a=type_a,
                        type_b=type_b,
                        dominance=dominance,
                        encounters=pair_encounters,
                        reason="below_dominance_threshold",
                    ),
                )
                continue

            # Threshold 3: hierarchy coverage (siblings only)
            if not self.shared_parent(type_a, type_b):
                evt_signals.guide_rule_skipped.send(
                    evt_signals.guide_rule_skipped,
                    event=etypes.GuideRuleSkipped(
                        entity_name=norm_name,
                        type_a=type_a,
                        type_b=type_b,
                        dominance=dominance,
                        encounters=pair_encounters,
                        reason="no_shared_parent",
                    ),
                )
                continue

            # Generate rule
            other_type = type_b if dominant_type == type_a else type_a
            rule = (
                f'"{norm_name}" should be typed as {dominant_type}, not {other_type} '
                f"({counts[dominant_type]}/{total} occurrences, "
                f"{pair_encounters} encounters)."
            )
            new_rules.append(rule)
            self._evolved_guide_keys.add(key)

            logger.info(
                "[guide] new rule: '{}' -> {} (dominance={:.0%}, encounters={})",
                norm_name,
                dominant_type,
                dominance,
                pair_encounters,
            )
            evt_signals.guide_rule_generated.send(
                evt_signals.guide_rule_generated,
                event=etypes.GuideRuleGenerated(
                    entity_name=norm_name,
                    dominant_type=dominant_type,
                    other_type=other_type,
                    dominance=dominance,
                    encounters=pair_encounters,
                ),
            )

        if not new_rules:
            return

        # Append to guide with run marker
        import datetime

        stamp = datetime.datetime.now().strftime("%Y-%m-%d")
        header = f"\n# Auto-generated rules ({stamp})\n"
        self._resolution_guide += header + "\n".join(new_rules) + "\n"

        logger.info(
            "[guide] evolved {} new resolution guide rules",
            len(new_rules),
        )

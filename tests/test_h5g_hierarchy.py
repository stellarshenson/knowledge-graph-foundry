"""Tests for H5g ontology-enriched type resolution.

Covers hierarchy auto-merge, multi-facet labels, resolution guidance block,
cross-type stats recording, and guide/hierarchy evolution.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kg_builder_cli.extraction.prompts import (
    _build_resolution_guidance_block,
    build_extraction_prompt,
)
from kg_builder_cli.extraction.resolution import (
    CrossTypeStat,
    resolve_entities,
)
from kg_builder_cli.ontology.buffer import OntologyBuffer
from kg_builder_cli.types.config import OntologyBufferConfig
from kg_builder_cli.types.document import Chunk, ChunkMetadata
from kg_builder_cli.types.extraction import Entity
from kg_builder_cli.types.ontology import (
    OntologyState,
    TypeDef,
    TypeHierarchyEntry,
)


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def hierarchy_ontology():
    """Ontology with Part -> [Component, Accessory] and Behavior -> [Feature, Setting]."""
    return OntologyState(
        entity_types=(
            TypeDef(name="Component", description="Integral device part"),
            TypeDef(name="Accessory", description="Sold separately"),
            TypeDef(name="Feature", description="Device capability"),
            TypeDef(name="Setting", description="User-adjustable parameter"),
        ),
        confirmed_types=frozenset({"Component", "Accessory", "Feature", "Setting"}),
        type_frequencies={"Component": 20, "Accessory": 10, "Feature": 15, "Setting": 8},
        type_hierarchy=(
            TypeHierarchyEntry(
                name="Part",
                description="Physical parts",
                children=["Component", "Accessory"],
            ),
            TypeHierarchyEntry(
                name="Behavior",
                description="Device behaviors",
                children=["Feature", "Setting"],
            ),
        ),
    )


@pytest.fixture
def buffer_config():
    return OntologyBufferConfig(min_frequency_to_confirm=2)


def _make_chunk(text: str = "Test text.") -> Chunk:
    return Chunk(id="test123", text=text, index=0, metadata=ChunkMetadata(), token_count=5)


# ── Resolution: Hierarchy Auto-Merge ────────────────────────────────────


class TestHierarchyAutoMerge:
    def test_sibling_types_auto_merge(self, hierarchy_ontology):
        """Component and Accessory under same parent Part -> auto-merge."""
        entities = [
            Entity(
                id="e1",
                name="Heated Humidifier",
                type="Component",
                source_chunks=["c1"],
                description="integral heated humidifier",
            ),
            Entity(
                id="e2",
                name="Heated Humidifier",
                type="Accessory",
                source_chunks=["c2"],
                description="optional heated humidifier accessory",
            ),
        ]
        resolved = resolve_entities(
            entities,
            threshold=0.85,
            ontology_state=hierarchy_ontology,
            hierarchy_resolution=True,
        )
        assert len(resolved) == 1
        assert resolved[0].type == "Component"
        assert set(resolved[0].source_chunks) == {"c1", "c2"}

    def test_cross_parent_types_get_multi_labels(self, hierarchy_ontology):
        """Feature (Behavior) and Component (Part) -> multi-facet labels."""
        entities = [
            Entity(
                id="e1",
                name="Ramp",
                type="Feature",
                source_chunks=["c1"],
                description="gradual pressure ramp capability",
            ),
            Entity(
                id="e2",
                name="Ramp",
                type="Component",
                source_chunks=["c2"],
                description="physical ramp mechanism component",
            ),
        ]
        resolved = resolve_entities(
            entities,
            threshold=0.85,
            ontology_state=hierarchy_ontology,
            hierarchy_resolution=True,
        )
        # Multi-facet: merged into one entity with both labels
        assert len(resolved) == 1
        assert "Feature" in resolved[0].labels
        assert "Component" in resolved[0].labels

    def test_no_hierarchy_falls_through_to_bayesian(self):
        """Without hierarchy, cross-type resolution uses Bayesian posterior."""
        ontology = OntologyState(
            entity_types=(
                TypeDef(name="Feature"),
                TypeDef(name="Component"),
            ),
            confirmed_types=frozenset({"Feature", "Component"}),
            type_hierarchy=(),
        )
        entities = [
            Entity(
                id="e1",
                name="Filter",
                type="Component",
                source_chunks=["c1"],
                description="physical air filter for removing particulates",
            ),
            Entity(
                id="e2",
                name="Filter",
                type="Feature",
                source_chunks=["c2"],
                description="data smoothing algorithm for signal processing",
            ),
        ]
        resolved = resolve_entities(
            entities,
            threshold=0.85,
            cross_type_merge_threshold=0.6,
            ontology_state=ontology,
            hierarchy_resolution=True,
        )
        # Divergent descriptions -> Bayesian blocks merge
        assert len(resolved) == 2

    def test_hierarchy_disabled_falls_through(self, hierarchy_ontology):
        """With hierarchy_resolution=False, siblings go through Bayesian."""
        entities = [
            Entity(
                id="e1",
                name="Heated Humidifier",
                type="Component",
                source_chunks=["c1"],
                description="integral heated humidifier",
            ),
            Entity(
                id="e2",
                name="Heated Humidifier",
                type="Accessory",
                source_chunks=["c2"],
                description="optional heated humidifier accessory",
            ),
        ]
        resolved = resolve_entities(
            entities,
            threshold=0.85,
            ontology_state=hierarchy_ontology,
            hierarchy_resolution=False,
        )
        # Falls through to Bayesian, which should merge (overlapping descriptions)
        assert len(resolved) == 1


# ── Resolution: CrossTypeStat Reporting ─────────────────────────────────


class TestCrossTypeStats:
    def test_hierarchy_merge_reports_stat(self, hierarchy_ontology):
        """Hierarchy auto-merge produces a CrossTypeStat with action 'hierarchy_merge'."""
        entities = [
            Entity(
                id="e1",
                name="Tubing",
                type="Component",
                source_chunks=["c1"],
                description="tubing",
            ),
            Entity(
                id="e2",
                name="Tubing",
                type="Accessory",
                source_chunks=["c2"],
                description="tubing kit",
            ),
        ]
        resolve_entities(
            entities,
            threshold=0.85,
            ontology_state=hierarchy_ontology,
            hierarchy_resolution=True,
            doc_index=3,
        )
        stats = getattr(resolve_entities, "_last_cross_type_stats", [])
        assert len(stats) >= 1
        assert any(s.action == "hierarchy_merge" for s in stats)

    def test_multi_facet_reports_stat(self, hierarchy_ontology):
        """Cross-parent merge produces a CrossTypeStat with action 'multi_facet'."""
        entities = [
            Entity(
                id="e1",
                name="Pressure",
                type="Setting",
                source_chunks=["c1"],
                description="user pressure setting",
            ),
            Entity(
                id="e2",
                name="Pressure",
                type="Component",
                source_chunks=["c2"],
                description="pressure valve component",
            ),
        ]
        resolve_entities(
            entities,
            threshold=0.85,
            ontology_state=hierarchy_ontology,
            hierarchy_resolution=True,
        )
        stats = getattr(resolve_entities, "_last_cross_type_stats", [])
        assert any(s.action == "multi_facet" for s in stats)


# ── Buffer: Hierarchy Loading and Flushing ──────────────────────────────


class TestBufferHierarchy:
    def test_from_yaml_loads_hierarchy(self, tmp_path, buffer_config):
        """from_yaml parses type_hierarchy, resolution_intent, resolution_guide."""
        ontology_file = tmp_path / "ontology.yml"
        ontology_file.write_text(
            yaml.dump(
                {
                    "entity_types": [{"name": "Component"}, {"name": "Accessory"}],
                    "relationship_types": [],
                    "type_hierarchy": [
                        {
                            "name": "Part",
                            "description": "Physical parts",
                            "children": ["Component", "Accessory"],
                        }
                    ],
                    "resolution_intent": "Prefer Component over Accessory for integral parts.",
                    "resolution_guide": '"humidifier" is always Component.',
                    "type_exemplars": {
                        "Component": [
                            {"name": "Heated Humidifier", "frequency": 5, "description": "integral part"}
                        ]
                    },
                }
            )
        )
        buffer = OntologyBuffer.from_yaml(ontology_file, buffer_config)
        snapshot = buffer.snapshot()

        assert len(snapshot.type_hierarchy) == 1
        assert snapshot.type_hierarchy[0].name == "Part"
        assert "Component" in snapshot.type_hierarchy[0].children
        assert snapshot.resolution_intent == "Prefer Component over Accessory for integral parts."
        assert snapshot.resolution_guide == '"humidifier" is always Component.'
        assert "Component" in snapshot.type_exemplars

    def test_shared_parent(self, tmp_path, buffer_config):
        """shared_parent returns parent name for siblings, None for non-siblings."""
        ontology_file = tmp_path / "ontology.yml"
        ontology_file.write_text(
            yaml.dump(
                {
                    "entity_types": [
                        {"name": "Component"},
                        {"name": "Accessory"},
                        {"name": "Feature"},
                    ],
                    "relationship_types": [],
                    "type_hierarchy": [
                        {"name": "Part", "children": ["Component", "Accessory"]},
                        {"name": "Behavior", "children": ["Feature"]},
                    ],
                }
            )
        )
        buffer = OntologyBuffer.from_yaml(ontology_file, buffer_config)
        assert buffer.shared_parent("Component", "Accessory") == "Part"
        assert buffer.shared_parent("Component", "Feature") is None
        assert buffer.shared_parent("Unknown", "Component") is None

    def test_flush_includes_hierarchy_and_guide(self, tmp_path, buffer_config):
        """Flush writes hierarchy, intent, guide, and exemplars to YAML."""
        ontology_file = tmp_path / "seed.yml"
        ontology_file.write_text(
            yaml.dump(
                {
                    "entity_types": [{"name": "Component"}, {"name": "Accessory"}],
                    "relationship_types": [],
                    "type_hierarchy": [
                        {"name": "Part", "children": ["Component", "Accessory"]}
                    ],
                    "resolution_intent": "Always prefer Component.",
                    "resolution_guide": "Rule 1.",
                }
            )
        )
        buffer = OntologyBuffer.from_yaml(ontology_file, buffer_config)
        out = tmp_path / "out.yml"
        buffer.flush(out)

        data = yaml.safe_load(out.read_text())
        assert "type_hierarchy" in data
        assert data["type_hierarchy"][0]["name"] == "Part"
        assert data["resolution_intent"] == "Always prefer Component."
        assert data["resolution_guide"] == "Rule 1."

    def test_record_cross_type_stats(self, buffer_config):
        """record_cross_type_stats accumulates stats by normalized key."""
        buffer = OntologyBuffer(buffer_config)
        buffer.record_cross_type_stats([
            ("humidifier", "Component", "Accessory", 0, "merged"),
            ("humidifier", "Component", "Accessory", 1, "merged"),
            ("humidifier", "Component", "Accessory", 2, "blocked"),
        ])
        key = ("humidifier", "Accessory", "Component")
        assert key in buffer._cross_type_stats
        assert len(buffer._cross_type_stats[key]["doc_indices"]) == 3


# ── Buffer: Hierarchy and Guide Evolution ───────────────────────────────


class TestBufferEvolution:
    def test_evolve_type_hierarchy_conservative(self, buffer_config):
        """Hierarchy created only when pattern appears in >= 3 documents."""
        buffer = OntologyBuffer(buffer_config)
        buffer.accumulate_from_result(
            [
                Entity(id="e1", name="A", type="Component", source_chunks=["c1"]),
                Entity(id="e2", name="B", type="Accessory", source_chunks=["c2"]),
            ],
            [],
        )
        # Record stats across 3 documents
        buffer.record_cross_type_stats([
            ("humidifier", "Component", "Accessory", 0, "merged"),
            ("humidifier", "Component", "Accessory", 1, "merged"),
            ("humidifier", "Component", "Accessory", 2, "blocked"),
        ])
        buffer.evolve_type_hierarchy()
        assert len(buffer._type_hierarchy) == 1
        assert buffer._type_hierarchy[0].name == "Part"
        assert "Component" in buffer._type_hierarchy[0].children

    def test_evolve_type_hierarchy_below_threshold(self, buffer_config):
        """No hierarchy when pattern appears in < 3 documents."""
        buffer = OntologyBuffer(buffer_config)
        buffer.record_cross_type_stats([
            ("humidifier", "Component", "Accessory", 0, "merged"),
            ("humidifier", "Component", "Accessory", 1, "merged"),
        ])
        buffer.evolve_type_hierarchy()
        assert len(buffer._type_hierarchy) == 0

    def test_evolve_resolution_guide_with_hierarchy(self, buffer_config):
        """Guide rule generated when all thresholds met: docs >= 3, dominance >= 75%, siblings."""
        buffer = OntologyBuffer(buffer_config)
        # Seed hierarchy first
        buffer._type_hierarchy.append(
            TypeHierarchyEntry(name="Part", children=["Component", "Accessory"])
        )
        buffer._child_to_parent = {"Component": "Part", "Accessory": "Part"}
        # Record dominated pattern (Component 4x, Accessory 1x = 80% dominance)
        buffer._cross_type_stats[("humidifier", "Accessory", "Component")] = {
            "doc_indices": {0, 1, 2, 3},
            "type_counts": {"Component": 4, "Accessory": 1},
        }
        buffer.evolve_resolution_guide()
        assert "Component" in buffer._resolution_guide
        assert "humidifier" in buffer._resolution_guide

    def test_evolve_resolution_guide_no_hierarchy_no_rule(self, buffer_config):
        """No guide rule when types are not siblings (no shared parent)."""
        buffer = OntologyBuffer(buffer_config)
        buffer._cross_type_stats[("ramp", "Feature", "Specification")] = {
            "doc_indices": {0, 1, 2, 3},
            "type_counts": {"Feature": 4, "Specification": 1},
        }
        buffer.evolve_resolution_guide()
        assert buffer._resolution_guide == ""

    def test_evolve_resolution_guide_low_dominance_no_rule(self, buffer_config):
        """No guide rule when dominance < 75%."""
        buffer = OntologyBuffer(buffer_config)
        buffer._type_hierarchy.append(
            TypeHierarchyEntry(name="Part", children=["Component", "Accessory"])
        )
        buffer._child_to_parent = {"Component": "Part", "Accessory": "Part"}
        # 60% dominance (3/5) < 75%
        buffer._cross_type_stats[("humidifier", "Accessory", "Component")] = {
            "doc_indices": {0, 1, 2},
            "type_counts": {"Component": 3, "Accessory": 2},
        }
        buffer.evolve_resolution_guide()
        assert buffer._resolution_guide == ""


# ── Prompts: Resolution Guidance Block ──────────────────────────────────


class TestResolutionGuidanceBlock:
    def test_empty_guidance_returns_empty(self):
        """No intent or guide -> empty string."""
        ontology = OntologyState()
        assert _build_resolution_guidance_block(ontology) == ""

    def test_intent_only(self):
        """Intent without guide produces domain expert block."""
        ontology = OntologyState(
            resolution_intent="Prefer Component over Accessory for integral parts.",
        )
        block = _build_resolution_guidance_block(ontology)
        assert "domain expert" in block
        assert "Prefer Component" in block

    def test_guide_only(self):
        """Guide without intent produces learned rules block."""
        ontology = OntologyState(
            resolution_guide='"humidifier" is always Component.',
        )
        block = _build_resolution_guidance_block(ontology)
        assert "Learned disambiguation" in block
        assert "humidifier" in block

    def test_intent_plus_guide(self):
        """Both intent and guide combined."""
        ontology = OntologyState(
            resolution_intent="Prefer Component.",
            resolution_guide='"humidifier" is Component.',
        )
        block = _build_resolution_guidance_block(ontology)
        assert "domain expert" in block
        assert "Learned disambiguation" in block

    def test_guidance_in_constrained_prompt(self):
        """Resolution guidance block appears in constrained extraction prompt."""
        chunk = _make_chunk()
        ontology = OntologyState(
            entity_types=(TypeDef(name="Component"),),
            confirmed_types=frozenset({"Component"}),
            resolution_intent="Prefer Component.",
        )
        prompt = build_extraction_prompt(chunk, ontology)
        assert "domain expert" in prompt
        assert "Prefer Component" in prompt

    def test_no_guidance_in_free_prompt(self):
        """Free prompt (no ontology) has no resolution guidance."""
        chunk = _make_chunk()
        prompt = build_extraction_prompt(chunk)
        assert "domain expert" not in prompt
        assert "Learned disambiguation" not in prompt

"""Tests for OWL/RDF ontology import."""
from __future__ import annotations

from pathlib import Path

import pytest

from kg_builder_cli.ontology.owl_import import import_owl

OWL_FIXTURE = Path(__file__).parent / "fixtures" / "cpap_ontology.owl"


class TestOwlImport:
    def test_import_loads_entity_types(self):
        """OWL classes become entity types."""
        types, _ = import_owl(OWL_FIXTURE)
        type_names = {t.name for t in types}
        assert "MedicalDevice" in type_names
        assert "CPAPDevice" in type_names
        assert "Organization" in type_names
        assert "Specification" in type_names
        assert "Feature" in type_names
        assert "Component" in type_names

    def test_import_loads_relationship_types(self):
        """OWL object properties become relationship types."""
        _, rels = import_owl(OWL_FIXTURE)
        rel_names = {r.name for r in rels}
        assert "manufactures" in rel_names
        assert "hasSpecification" in rel_names
        assert "hasFeature" in rel_names
        assert "hasComponent" in rel_names

    def test_import_relationship_domain_range(self):
        """Object property domain/range map to source/target types."""
        _, rels = import_owl(OWL_FIXTURE)
        mfg = next(r for r in rels if r.name == "manufactures")
        assert mfg.source_type == "Organization"
        assert mfg.target_type == "MedicalDevice"

        spec = next(r for r in rels if r.name == "hasSpecification")
        assert spec.source_type == "MedicalDevice"
        assert spec.target_type == "Specification"

    def test_import_subclass_hierarchy(self):
        """rdfs:subClassOf creates parent links."""
        types, _ = import_owl(OWL_FIXTURE)
        type_map = {t.name: t for t in types}
        assert type_map["CPAPDevice"].parent == "MedicalDevice"
        assert type_map["AutoCPAP"].parent == "CPAPDevice"
        assert type_map["MedicalDevice"].parent is None

    def test_import_descriptions_from_comments(self):
        """rdfs:comment becomes type description."""
        types, _ = import_owl(OWL_FIXTURE)
        type_map = {t.name: t for t in types}
        assert "Continuous Positive Airway Pressure" in type_map["CPAPDevice"].description
        assert "auto-titrating" in type_map["AutoCPAP"].description.lower()

    def test_import_datatype_properties(self):
        """OWL datatype properties become PropertyDef on domain type."""
        types, _ = import_owl(OWL_FIXTURE)
        type_map = {t.name: t for t in types}
        spec_props = {p.name for p in type_map["Specification"].property_defs}
        assert "pressureMin" in spec_props
        assert "pressureMax" in spec_props
        assert "unit" in spec_props

    def test_import_property_types(self):
        """Datatype property ranges map to property types."""
        types, _ = import_owl(OWL_FIXTURE)
        type_map = {t.name: t for t in types}
        prop_map = {p.name: p for p in type_map["Specification"].property_defs}
        assert prop_map["pressureMin"].type == "number"
        assert prop_map["unit"].type == "string"

    def test_import_depth_limit(self):
        """max_depth=1 excludes AutoCPAP (depth 2)."""
        types, _ = import_owl(OWL_FIXTURE, max_depth=1)
        type_names = {t.name for t in types}
        assert "MedicalDevice" in type_names
        assert "CPAPDevice" in type_names
        assert "AutoCPAP" not in type_names

    def test_import_branch_filter(self):
        """branch_filter limits to subtree."""
        types, _ = import_owl(OWL_FIXTURE, branch_filter="CPAPDevice")
        type_names = {t.name for t in types}
        assert "CPAPDevice" in type_names
        assert "AutoCPAP" in type_names
        assert "Organization" not in type_names
        assert "Feature" not in type_names

    def test_import_feeds_buffer(self):
        """OWL import results can seed an OntologyBuffer."""
        from kg_builder_cli.ontology.buffer import OntologyBuffer
        from kg_builder_cli.types.config import OntologyBufferConfig

        entity_types, rel_types = import_owl(OWL_FIXTURE)
        config = OntologyBufferConfig(min_frequency_to_confirm=1)
        buffer = OntologyBuffer(config)

        # Manually seed buffer with OWL types
        for typedef in entity_types:
            buffer._entity_types[typedef.name] = typedef
            buffer._frequencies[typedef.name] = config.min_frequency_to_confirm
        for reldef in rel_types:
            buffer._relationship_types[reldef.name] = reldef
            buffer._frequencies[reldef.name] = config.min_frequency_to_confirm

        snapshot = buffer.snapshot()
        assert len(snapshot.entity_types) >= 6
        assert len(snapshot.relationship_types) >= 4
        assert "CPAPDevice" in snapshot.confirmed_types
        assert buffer.coverage() == 1.0

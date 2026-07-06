"""Tests for ontology seeding - seedless, YAML/JSON, OWL, freeform via engine."""

import json

from pydantic import BaseModel
import pytest

from knowledge_graph_foundry.ontology.seed import (
    SeedError,
    SeedNormalization,
    SeedRelationshipType,
    SeedType,
    load_seed,
    normalize_type_name,
)

PURPOSE = "map CPAP devices, their components and operating modes"

OWL_SEED = """<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
         xmlns:owl="http://www.w3.org/2002/07/owl#"
         xml:base="http://example.org/cpap"
         xmlns="http://example.org/cpap#">
  <owl:Ontology rdf:about="http://example.org/cpap"/>
  <owl:Class rdf:about="http://example.org/cpap#Device">
    <rdfs:label>Device</rdfs:label>
    <rdfs:comment>A CPAP therapy device</rdfs:comment>
  </owl:Class>
  <owl:Class rdf:about="http://example.org/cpap#OperatingMode">
    <rdfs:label>operating mode</rdfs:label>
  </owl:Class>
  <owl:ObjectProperty rdf:about="http://example.org/cpap#supportsMode">
    <rdfs:label>SUPPORTS_MODE</rdfs:label>
  </owl:ObjectProperty>
</rdf:RDF>
"""


class FakeEngine:
    """Canned-response engine capturing the messages it was called with."""

    name = "fake"

    def __init__(self, response: BaseModel):
        self.response = response
        self.messages: list[dict[str, str]] | None = None

    def complete(self, messages: list[dict[str, str]], response_model: type) -> BaseModel:
        self.messages = messages
        assert isinstance(self.response, response_model)
        return self.response


class TestNormalizeTypeName:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("operating mode", "OperatingMode"),
            ("operating_mode", "OperatingMode"),
            ("operatingMode", "OperatingMode"),
            ("OperatingMode", "OperatingMode"),
            ("device", "Device"),
            ("power-supply unit", "PowerSupplyUnit"),
        ],
    )
    def test_variants(self, raw, expected):
        assert normalize_type_name(raw) == expected


class TestSeedless:
    def test_none_source_gives_empty_ontology_with_purpose(self):
        ontology = load_seed(None, PURPOSE)
        assert ontology.purpose == PURPOSE
        assert ontology.types == {}
        assert ontology.relationship_types == {}
        assert ontology.cured is False


class TestStructuredSeed:
    def test_yaml_full_shape(self, tmp_path):
        seed = tmp_path / "seed.yml"
        seed.write_text(
            "types:\n"
            "  - name: operating mode\n"
            "    description: a device mode\n"
            "    properties: [pressure, ramp]\n"
            "  - name: Device\n"
            "relationship_types:\n"
            "  - name: SUPPORTS_MODE\n"
            "    description: device supports a mode\n"
        )
        ontology = load_seed(seed, PURPOSE)
        assert ontology.purpose == PURPOSE
        assert ontology.cured is False
        assert set(ontology.types) == {"OperatingMode", "Device"}
        mode = ontology.types["OperatingMode"]
        assert mode.description == "a device mode"
        assert mode.properties == ["pressure", "ramp"]
        assert mode.status == "seeded"
        assert mode.encounters == 0
        rel = ontology.relationship_types["SUPPORTS_MODE"]
        assert rel.description == "device supports a mode"
        assert rel.encounters == 0

    def test_yaml_shorthand_list_of_strings(self, tmp_path):
        seed = tmp_path / "seed.yaml"
        seed.write_text("types: [device, operating_mode, Accessory]\n")
        ontology = load_seed(seed, PURPOSE)
        assert set(ontology.types) == {"Device", "OperatingMode", "Accessory"}
        assert all(t.status == "seeded" for t in ontology.types.values())

    def test_json_seed(self, tmp_path):
        seed = tmp_path / "seed.json"
        seed.write_text(
            json.dumps(
                {
                    "types": [{"name": "humidifier chamber", "properties": ["capacity"]}],
                    "relationship_types": [{"name": "PART_OF"}],
                }
            )
        )
        ontology = load_seed(seed, PURPOSE)
        assert ontology.types["HumidifierChamber"].properties == ["capacity"]
        assert "PART_OF" in ontology.relationship_types


class TestOwlSeed:
    def test_owl_classes_and_object_properties(self, tmp_path):
        seed = tmp_path / "seed.owl"
        seed.write_text(OWL_SEED)
        ontology = load_seed(seed, PURPOSE)
        assert ontology.purpose == PURPOSE
        assert set(ontology.types) == {"Device", "OperatingMode"}
        assert ontology.types["Device"].description == "A CPAP therapy device"
        assert ontology.types["Device"].status == "seeded"
        assert set(ontology.relationship_types) == {"SUPPORTS_MODE"}

    def test_unparseable_owl_raises_seed_error_naming_file(self, tmp_path):
        seed = tmp_path / "garbage.owl"
        seed.write_bytes(b"\x00\xffnot an ontology at all")
        with pytest.raises(SeedError) as exc_info:
            load_seed(seed, PURPOSE)
        assert "garbage.owl" in str(exc_info.value)


class TestFreeformSeed:
    def test_freeform_without_engine_raises(self):
        with pytest.raises(SeedError):
            load_seed("devices and the modes they support", PURPOSE)

    def test_freeform_with_engine_normalizes_and_prompt_contains_purpose(self):
        canned = SeedNormalization(
            types=[SeedType(name="sleep mode", description="a mode", properties=["pressure"])],
            relationship_types=[SeedRelationshipType(name="SUPPORTS_MODE")],
        )
        engine = FakeEngine(canned)
        ontology = load_seed("devices and the modes they support", PURPOSE, engine=engine)
        assert engine.messages is not None
        assert any(PURPOSE in m["content"] for m in engine.messages)
        assert ontology.purpose == PURPOSE
        assert set(ontology.types) == {"SleepMode"}
        assert ontology.types["SleepMode"].status == "seeded"
        assert ontology.types["SleepMode"].encounters == 0
        assert "SUPPORTS_MODE" in ontology.relationship_types

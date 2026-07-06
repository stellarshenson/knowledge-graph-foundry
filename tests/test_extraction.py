"""Tests for chunk extraction, structured mapping, and prompt injection."""

from __future__ import annotations

from pydantic import BaseModel
import pytest

from knowledge_graph_foundry.engines.base import EngineError
from knowledge_graph_foundry.events import subscribe, unsubscribe
from knowledge_graph_foundry.extraction.extractor import (
    RelationshipColumn,
    SourceMapping,
    WireEntity,
    WireExtraction,
    WireRelationship,
    apply_mapping,
    extract_chunk,
    extract_document,
    normalize_relationship_type,
    structured_mapping,
)
from knowledge_graph_foundry.extraction.prompts import extraction_messages
from knowledge_graph_foundry.models import (
    Chunk,
    Ontology,
    RelationshipTypeDef,
    TypeDef,
    chunk_id,
    entity_id,
)

PURPOSE = "map CPAP devices, their components and operating modes"


class FakeEngine:
    """Canned-response engine; per-chunk responses selected by text marker."""

    name = "fake"

    def __init__(
        self,
        response: BaseModel | None = None,
        by_marker: dict[str, BaseModel] | None = None,
    ):
        self.response = response
        self.by_marker = by_marker or {}
        self.calls: list[list[dict[str, str]]] = []

    def complete(self, messages: list[dict[str, str]], response_model: type) -> BaseModel:
        self.calls.append(messages)
        user = messages[-1]["content"]
        for marker, response in self.by_marker.items():
            if marker in user:
                return response
        return self.response


class FailingEngine(FakeEngine):
    """FakeEngine variant raising on chunks containing fail_marker."""

    def __init__(self, response: BaseModel, fail_marker: str, **kwargs):
        super().__init__(response, **kwargs)
        self.fail_marker = fail_marker

    def complete(self, messages: list[dict[str, str]], response_model: type) -> BaseModel:
        if self.fail_marker in messages[-1]["content"]:
            raise EngineError("simulated engine failure")
        return super().complete(messages, response_model)


def _chunk(text: str, document_id: str = "doc1", index: int = 0) -> Chunk:
    return Chunk(
        id=chunk_id(document_id, index, text),
        document_id=document_id,
        index=index,
        text=text,
        token_count=len(text.split()),
    )


@pytest.fixture()
def warnings():
    """Collect extraction.warning payloads for the duration of a test."""
    received: list[dict] = []

    def _receiver(sender, **payload):
        received.append(payload)

    subscribe("extraction.warning", _receiver)
    yield received
    unsubscribe("extraction.warning", _receiver)


class TestExtractChunk:
    def test_wire_to_domain_with_type_normalization(self):
        wire = WireExtraction(
            entities=[
                WireEntity(
                    name="AutoRamp",
                    types=["operating mode"],
                    description="Pressure ramp mode",
                    properties={"max_pressure": "20", "max_pressure_unit": "cmH2O"},
                )
            ]
        )
        chunk = _chunk("AutoRamp text")

        result = extract_chunk(chunk, PURPOSE, Ontology(purpose=PURPOSE), FakeEngine(wire))

        assert len(result.entities) == 1
        entity = result.entities[0]
        assert entity.id == entity_id("AutoRamp")
        assert entity.types == ["OperatingMode"]
        assert entity.description == "Pressure ramp mode"
        assert entity.properties == {"max_pressure": "20", "max_pressure_unit": "cmH2O"}

    def test_provenance_stamped(self):
        wire = WireExtraction(
            entities=[
                WireEntity(name="DreamStation", types=["Product"]),
                WireEntity(name="Philips", types=["Manufacturer"]),
            ],
            relationships=[
                WireRelationship(source="DreamStation", target="Philips", type="made by")
            ],
        )
        chunk = _chunk("provenance text", document_id="doc42", index=3)

        result = extract_chunk(chunk, PURPOSE, Ontology(), FakeEngine(wire))

        for entity in result.entities:
            assert entity.source_documents == ["doc42"]
            assert entity.source_chunks == [chunk.id]
        rel = result.relationships[0]
        assert rel.type == "MADE_BY"
        assert rel.source_id == entity_id("DreamStation")
        assert rel.target_id == entity_id("Philips")
        assert rel.source_documents == ["doc42"]
        assert rel.source_chunks == [chunk.id]

    def test_dangling_relationship_dropped_with_warning(self, warnings):
        wire = WireExtraction(
            entities=[WireEntity(name="DreamStation", types=["Product"])],
            relationships=[
                WireRelationship(source="DreamStation", target="Ghost", type="HAS_PART")
            ],
        )
        chunk = _chunk("dangling text")

        result = extract_chunk(chunk, PURPOSE, Ontology(), FakeEngine(wire))

        assert result.relationships == []
        assert len(warnings) == 1
        assert "dangling" in warnings[0]["reason"]
        assert warnings[0]["chunk"] == chunk.id

    def test_self_reference_dropped_with_warning(self, warnings):
        wire = WireExtraction(
            entities=[WireEntity(name="DreamStation", types=["Product"])],
            relationships=[
                WireRelationship(source="DreamStation", target="DreamStation", type="HAS_PART")
            ],
        )
        chunk = _chunk("self ref text")

        result = extract_chunk(chunk, PURPOSE, Ontology(), FakeEngine(wire))

        assert result.relationships == []
        assert len(warnings) == 1
        assert "self-referencing" in warnings[0]["reason"]

    def test_empty_extraction_accepted(self):
        result = extract_chunk(
            _chunk("nothing here"), PURPOSE, Ontology(), FakeEngine(WireExtraction())
        )
        assert result.entities == []
        assert result.relationships == []


class TestExtractDocument:
    def test_failing_chunk_skipped_document_continues(self, warnings):
        chunks = [_chunk("alpha text", index=0), _chunk("BOOM text", index=1)]
        wire = WireExtraction(entities=[WireEntity(name="Alpha", types=["Product"])])
        engine = FailingEngine(wire, fail_marker="BOOM")

        result = extract_document(chunks, PURPOSE, Ontology(), engine)

        assert [e.name for e in result.entities] == ["Alpha"]
        assert any("chunk extraction failed" in w["reason"] for w in warnings)
        failed = [w for w in warnings if "failed" in w["reason"]]
        assert failed[0]["chunk"] == chunks[1].id

    def test_chunk_order_preserved(self):
        texts = ["first text", "second text", "third text", "fourth text"]
        chunks = [_chunk(text, index=i) for i, text in enumerate(texts)]
        by_marker = {
            text: WireExtraction(entities=[WireEntity(name=f"E{i}", types=["Product"])])
            for i, text in enumerate(texts)
        }
        engine = FakeEngine(WireExtraction(), by_marker=by_marker)

        result = extract_document(chunks, PURPOSE, Ontology(), engine, concurrency=4)

        assert [e.name for e in result.entities] == ["E0", "E1", "E2", "E3"]

    def test_completed_event_emitted(self):
        received: list[dict] = []

        def _receiver(sender, **payload):
            received.append(payload)

        subscribe("extraction.completed", _receiver)
        try:
            wire = WireExtraction(entities=[WireEntity(name="Alpha", types=["Product"])])
            extract_document([_chunk("alpha")], PURPOSE, Ontology(), FakeEngine(wire))
        finally:
            unsubscribe("extraction.completed", _receiver)

        assert received == [{"chunks": 1, "entities": 1, "relationships": 0}]


class TestPromptInjection:
    def test_purpose_present_in_prompt(self):
        messages = extraction_messages("chunk text", PURPOSE, Ontology(purpose=PURPOSE))
        assert PURPOSE in messages[0]["content"]
        assert messages[1] == {"role": "user", "content": "chunk text"}

    def test_ontology_types_present_in_prompt(self):
        ontology = Ontology(
            purpose=PURPOSE,
            types={
                "Device": TypeDef(
                    name="Device", description="A CPAP therapy device", status="confirmed"
                ),
                "OperatingMode": TypeDef(name="OperatingMode", status="emerging"),
            },
            relationship_types={"SUPPORTS_MODE": RelationshipTypeDef(name="SUPPORTS_MODE")},
        )
        system = extraction_messages("chunk text", PURPOSE, ontology)[0]["content"]
        assert "Device" in system
        assert "A CPAP therapy device" in system
        assert "confirmed" in system
        assert "emerging" in system
        assert "SUPPORTS_MODE" in system


class TestStructuredMapping:
    MAPPING = SourceMapping(
        entity_column="name",
        entity_type="product",
        property_columns=["price", "color"],
        relationship_columns=[
            RelationshipColumn(
                column="brand", relationship_type="made by", target_type="manufacturer"
            )
        ],
    )

    def test_mapping_inferred_once_via_engine(self):
        engine = FakeEngine(self.MAPPING)
        rows = [{"name": "DreamStation", "price": "500"}]

        mapping = structured_mapping(rows, PURPOSE, engine)

        assert mapping is self.MAPPING
        assert len(engine.calls) == 1
        assert PURPOSE in engine.calls[0][0]["content"]
        assert "DreamStation" in engine.calls[0][1]["content"]

    def test_apply_mapping_deterministic(self):
        rows = [
            {"name": "DreamStation", "price": "500", "color": None, "brand": "Philips"},
            {"name": None, "price": "10", "color": "red", "brand": "Acme"},
            {"name": "AirSense", "price": "600", "color": "white", "brand": "ResMed"},
        ]

        result = apply_mapping(rows, self.MAPPING, "doc-csv")

        names = [e.name for e in result.entities]
        assert names == ["DreamStation", "Philips", "AirSense", "ResMed"]

        dream = result.entities[0]
        assert dream.types == ["Product"]
        assert dream.properties == {"price": "500"}  # None color skipped
        assert dream.source_documents == ["doc-csv"]

        airsense = result.entities[2]
        assert airsense.properties == {"price": "600", "color": "white"}

        philips = result.entities[1]
        assert philips.types == ["Manufacturer"]

        assert len(result.relationships) == 2
        rel = result.relationships[0]
        assert rel.type == "MADE_BY"
        assert rel.source_id == entity_id("DreamStation")
        assert rel.target_id == entity_id("Philips")


class TestNormalizeRelationshipType:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("made by", "MADE_BY"),
            ("supportsMode", "SUPPORTS_MODE"),
            ("SUPPORTS_MODE", "SUPPORTS_MODE"),
            ("has-part", "HAS_PART"),
        ],
    )
    def test_normalization(self, raw, expected):
        assert normalize_relationship_type(raw) == expected

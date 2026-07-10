"""Tests for chunk extraction, structured mapping, and prompt injection."""

from __future__ import annotations

import json

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
    _parse_enumeration,
    apply_mapping,
    extract_chunk,
    extract_document,
    normalize_relationship_type,
    structured_mapping,
)
from knowledge_graph_foundry.extraction.prompts import (
    entity_only_messages,
    extraction_messages,
    gleaning_messages,
    relation_only_messages,
)
from knowledge_graph_foundry.models import (
    Chunk,
    Ontology,
    RelationshipTypeDef,
    TypeDef,
    chunk_id,
    entity_id,
)
from knowledge_graph_foundry.settings import ExtractionSettings

PURPOSE = "map CPAP devices, their components and operating modes"

# Single-path tests pin the recipe explicitly; the shipped default is enumerate (SLOT-2/SLOT-4)
SINGLE = ExtractionSettings(recipe="single")


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

        result = extract_chunk(chunk, PURPOSE, Ontology(purpose=PURPOSE), FakeEngine(wire), SINGLE)

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

        result = extract_chunk(chunk, PURPOSE, Ontology(), FakeEngine(wire), SINGLE)

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

        result = extract_chunk(chunk, PURPOSE, Ontology(), FakeEngine(wire), SINGLE)

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

        result = extract_chunk(chunk, PURPOSE, Ontology(), FakeEngine(wire), SINGLE)

        assert result.relationships == []
        assert len(warnings) == 1
        assert "self-referencing" in warnings[0]["reason"]

    def test_empty_extraction_accepted(self):
        result = extract_chunk(
            _chunk("nothing here"), PURPOSE, Ontology(), FakeEngine(WireExtraction()), SINGLE
        )
        assert result.entities == []
        assert result.relationships == []


class TestExtractDocument:
    def test_failing_chunk_skipped_document_continues(self, warnings):
        chunks = [_chunk("alpha text", index=0), _chunk("BOOM text", index=1)]
        wire = WireExtraction(entities=[WireEntity(name="Alpha", types=["Product"])])
        engine = FailingEngine(wire, fail_marker="BOOM")

        result = extract_document(chunks, PURPOSE, Ontology(), engine, extraction_cfg=SINGLE)

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

        result = extract_document(
            chunks, PURPOSE, Ontology(), engine, concurrency=4, extraction_cfg=SINGLE
        )

        assert [e.name for e in result.entities] == ["E0", "E1", "E2", "E3"]

    def test_completed_event_emitted(self):
        received: list[dict] = []

        def _receiver(sender, **payload):
            received.append(payload)

        subscribe("extraction.completed", _receiver)
        try:
            wire = WireExtraction(entities=[WireEntity(name="Alpha", types=["Product"])])
            extract_document(
                [_chunk("alpha")], PURPOSE, Ontology(), FakeEngine(wire), extraction_cfg=SINGLE
            )
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


class SequenceEngine:
    """Returns canned WireExtraction responses in call order; records messages."""

    name = "sequence"

    def __init__(self, responses: list[BaseModel]):
        self.responses = list(responses)
        self.calls: list[list[dict[str, str]]] = []

    def complete(self, messages: list[dict[str, str]], response_model: type) -> BaseModel:
        self.calls.append(messages)
        if self.responses:
            return self.responses.pop(0)
        return WireExtraction()


class TestGleaning:
    def test_gleaning_adds_missed_entities_without_duplicating(self):
        first = WireExtraction(entities=[WireEntity(name="E1", types=["Product"])])
        glean = WireExtraction(
            entities=[
                WireEntity(name="E1", types=["Product"]),  # duplicate, must not repeat
                WireEntity(name="E2", types=["Product"]),  # newly gleaned
            ]
        )
        engine = SequenceEngine([first, glean])
        cfg = ExtractionSettings(recipe="single", split_entity_relation=False, gleaning_rounds=1)

        result = extract_chunk(_chunk("glean text"), PURPOSE, Ontology(), engine, cfg)

        assert [e.name for e in result.entities] == ["E1", "E2"]
        assert len(engine.calls) == 2  # first pass + one gleaning round

    def test_gleaning_stops_on_empty_round(self):
        first = WireExtraction(entities=[WireEntity(name="E1", types=["Product"])])
        engine = SequenceEngine([first, WireExtraction()])  # empty gleaning round
        cfg = ExtractionSettings(recipe="single", split_entity_relation=False, gleaning_rounds=3)

        result = extract_chunk(_chunk("stop text"), PURPOSE, Ontology(), engine, cfg)

        assert [e.name for e in result.entities] == ["E1"]
        assert len(engine.calls) == 2  # stopped after the empty round, not 4

    def test_gleaning_rounds_zero_disables(self):
        first = WireExtraction(entities=[WireEntity(name="E1", types=["Product"])])
        would_glean = WireExtraction(entities=[WireEntity(name="E2", types=["Product"])])
        engine = SequenceEngine([first, would_glean])
        cfg = ExtractionSettings(recipe="single", split_entity_relation=False, gleaning_rounds=0)

        result = extract_chunk(_chunk("noglean text"), PURPOSE, Ontology(), engine, cfg)

        assert [e.name for e in result.entities] == ["E1"]
        assert len(engine.calls) == 1  # gleaning disabled, single call


class TestSplitEntityRelation:
    def test_split_mode_issues_separate_entity_then_relation_calls(self):
        entities = WireExtraction(
            entities=[
                WireEntity(name="DreamStation", types=["Product"]),
                WireEntity(name="Philips", types=["Manufacturer"]),
            ]
        )
        relations = WireExtraction(
            relationships=[
                WireRelationship(source="DreamStation", target="Philips", type="made by")
            ]
        )
        engine = SequenceEngine([entities, relations])
        cfg = ExtractionSettings(recipe="single", split_entity_relation=True, gleaning_rounds=0)

        result = extract_chunk(_chunk("split text"), PURPOSE, Ontology(), engine, cfg)

        assert len(engine.calls) == 2
        assert "ENTITIES ONLY" in engine.calls[0][0]["content"]
        assert "RELATIONSHIPS ONLY" in engine.calls[1][0]["content"]
        # relation pass is told which entities were extracted
        assert "DreamStation" in engine.calls[1][0]["content"]
        assert [e.name for e in result.entities] == ["DreamStation", "Philips"]
        assert result.relationships[0].type == "MADE_BY"

    def test_split_false_keeps_single_combined_call(self):
        combined = WireExtraction(
            entities=[WireEntity(name="DreamStation", types=["Product"])],
        )
        engine = SequenceEngine([combined])
        cfg = ExtractionSettings(recipe="single", split_entity_relation=False, gleaning_rounds=0)

        result = extract_chunk(_chunk("combined text"), PURPOSE, Ontology(), engine, cfg)

        assert len(engine.calls) == 1
        assert "ENTITIES ONLY" not in engine.calls[0][0]["content"]
        assert [e.name for e in result.entities] == ["DreamStation"]


class TestSplitAndGleaningPrompts:
    def test_purpose_present_in_entity_relation_gleaning_prompts(self):
        ontology = Ontology(purpose=PURPOSE)
        entity_msgs = entity_only_messages("chunk text", PURPOSE, ontology)
        relation_msgs = relation_only_messages("chunk text", ["DreamStation"], PURPOSE, ontology)
        gleaning_msgs = gleaning_messages("chunk text", ["DreamStation"], PURPOSE, ontology)

        assert PURPOSE in entity_msgs[0]["content"]
        assert PURPOSE in relation_msgs[0]["content"]
        assert PURPOSE in gleaning_msgs[0]["content"]
        # extracted entity names are injected into the relation and gleaning prompts
        assert "DreamStation" in relation_msgs[0]["content"]
        assert "DreamStation" in gleaning_msgs[0]["content"]
        # user turn carries the chunk text
        assert entity_msgs[1] == {"role": "user", "content": "chunk text"}


class EnumerateEngine:
    """Records the stage-1 text call and stage-2 structured call for the enumerate recipe."""

    name = "enumerate"

    def __init__(self, enum_raw: str, extraction_response: BaseModel):
        self.enum_raw = enum_raw
        self.extraction_response = extraction_response
        self.text_calls: list[tuple[str, str]] = []
        self.calls: list[list[dict[str, str]]] = []

    def complete_text(self, system: str, user: str) -> str:
        self.text_calls.append((system, user))
        return self.enum_raw

    def complete(self, messages: list[dict[str, str]], response_model: type) -> BaseModel:
        self.calls.append(messages)
        return self.extraction_response


class TestEnumerationParser:
    def test_clean_json(self):
        raw = '{"entities": [{"name": "DreamStation"}, {"name": "Philips"}], "relationships": []}'
        assert _parse_enumeration(raw) == ["DreamStation", "Philips"]

    def test_fenced_json(self):
        raw = '```json\n{"entities": [{"name": "AirSense"}], "relationships": []}\n```'
        assert _parse_enumeration(raw) == ["AirSense"]

    def test_garbage_with_name_fields_falls_back_to_regex(self):
        raw = 'sure! here you go: "name": "ResMed", junk "name": "AirMini" trailing'
        assert _parse_enumeration(raw) == ["ResMed", "AirMini"]

    def test_order_preserving_dedup_and_cap(self):
        entries = [{"name": "Dup"}, {"name": "Dup"}] + [{"name": f"E{i}"} for i in range(200)]
        raw = json.dumps({"entities": entries, "relationships": []})
        names = _parse_enumeration(raw)
        assert len(names) == 150
        assert names[0] == "Dup"  # first-seen order, single copy
        assert names.count("Dup") == 1


class TestExtractionRecipes:
    def test_enumerate_primes_stage2_with_candidates(self):
        enum_raw = (
            '{"entities": [{"name": "DreamStation"}, {"name": "Philips"}], "relationships": []}'
        )
        extraction = WireExtraction(entities=[WireEntity(name="DreamStation", types=["Product"])])
        engine = EnumerateEngine(enum_raw, extraction)
        cfg = ExtractionSettings(recipe="enumerate", gleaning_rounds=0)

        result = extract_chunk(_chunk("enum text"), PURPOSE, Ontology(), engine, cfg)

        assert len(engine.text_calls) == 1  # stage 1 names-only
        assert len(engine.calls) == 1  # stage 2 extraction
        stage2_system = engine.calls[0][0]["content"]
        assert "Candidate names detected" in stage2_system
        assert "- DreamStation" in stage2_system
        assert "- Philips" in stage2_system
        # candidate order preserved as enumerated
        assert stage2_system.index("- DreamStation") < stage2_system.index("- Philips")
        assert [e.name for e in result.entities] == ["DreamStation"]

    def test_mention_recipe_single_call_with_no_dedup_instruction(self):
        extraction = WireExtraction(entities=[WireEntity(name="DreamStation", types=["Product"])])
        engine = SequenceEngine([extraction])
        cfg = ExtractionSettings(recipe="mention", gleaning_rounds=0)

        extract_chunk(_chunk("mention text"), PURPOSE, Ontology(), engine, cfg)

        assert len(engine.calls) == 1  # single combined call
        system = engine.calls[0][0]["content"]
        assert "do NOT deduplicate" in system
        assert "surface MENTION" in system


class TestRecipePrompts:
    def test_mention_prompt_contains_no_dedup_instruction(self):
        system = extraction_messages("chunk text", PURPOSE, Ontology(), mention=True)[0]["content"]
        assert "do NOT deduplicate or canonicalize" in system
        assert PURPOSE in system

    def test_candidate_block_appended_when_names_given(self):
        system = extraction_messages(
            "chunk text", PURPOSE, Ontology(), candidate_names=["Alpha", "Beta"]
        )[0]["content"]
        assert "Candidate names detected" in system
        assert "- Alpha" in system
        assert "- Beta" in system

    def test_single_prompt_byte_identical_regression(self):
        plain = extraction_messages("chunk text", PURPOSE, Ontology())
        explicit = extraction_messages(
            "chunk text", PURPOSE, Ontology(), candidate_names=None, mention=False
        )
        assert plain == explicit
        assert "Candidate names" not in plain[0]["content"]
        assert "surface MENTION" not in plain[0]["content"]


class ChurnEngine:
    """Engine returning a different canned response per successive call -
    simulates the run-to-run emission churn union-of-K exists to harvest."""

    name = "churn"

    def __init__(self, responses: list[BaseModel], fail_first: bool = False):
        import threading

        self.responses = list(responses)
        self.fail_first = fail_first
        self.calls = 0
        self._lock = threading.Lock()

    def complete(self, messages: list[dict[str, str]], response_model: type) -> BaseModel:
        with self._lock:
            self.calls += 1
            if self.fail_first and self.calls == 1:
                raise EngineError("simulated pass failure")
            return self.responses.pop(0)


class TestUnionOfK:
    """DEF-11/DEF-13/R31-H349: union_k independent passes per chunk, unioned."""

    CFG_ONE_CALL = dict(recipe="single", gleaning_rounds=0, split_entity_relation=False)

    def test_default_single_pass_no_union_metadata(self):
        wire = WireExtraction(entities=[WireEntity(name="Alpha", types=["Product"])])
        cfg = ExtractionSettings(**self.CFG_ONE_CALL)
        engine = ChurnEngine([wire])
        result = extract_document([_chunk("alpha")], PURPOSE, Ontology(), engine, extraction_cfg=cfg)
        assert engine.calls == 1
        assert "union_passes" not in result.entities[0].properties

    def test_union_recovers_entities_across_passes(self):
        pass_a = WireExtraction(
            entities=[WireEntity(name="Alpha", types=["Product"], description="short")]
        )
        pass_b = WireExtraction(
            entities=[
                WireEntity(name="Alpha", types=["Device"], description="a much longer description"),
                WireEntity(name="Beta", types=["Product"]),
            ]
        )
        cfg = ExtractionSettings(union_k=2, **self.CFG_ONE_CALL)
        engine = ChurnEngine([pass_a, pass_b])
        result = extract_document(
            [_chunk("alpha")], PURPOSE, Ontology(), engine, concurrency=1, extraction_cfg=cfg
        )
        assert engine.calls == 2
        by_name = {e.name: e for e in result.entities}
        assert set(by_name) == {"Alpha", "Beta"}  # union, not intersection
        assert by_name["Alpha"].properties["union_passes"] == 2
        assert by_name["Beta"].properties["union_passes"] == 1
        assert by_name["Alpha"].properties["union_k"] == 2
        assert by_name["Alpha"].description == "a much longer description"
        assert set(by_name["Alpha"].types) == {"Product", "Device"}

    def test_union_dedupes_relationships(self):
        entities = [WireEntity(name="Alpha", types=["Product"]), WireEntity(name="Beta", types=["Product"])]
        rel = WireRelationship(source="Alpha", target="Beta", type="HAS_PART")
        both = WireExtraction(entities=entities, relationships=[rel])
        cfg = ExtractionSettings(union_k=2, **self.CFG_ONE_CALL)
        result = extract_document(
            [_chunk("alpha")], PURPOSE, Ontology(), ChurnEngine([both, both]),
            concurrency=1, extraction_cfg=cfg,
        )
        assert len(result.relationships) == 1  # deduped by (source, target, type)
        assert len(result.entities) == 2

    def test_failed_pass_survived_by_the_other(self, warnings):
        wire = WireExtraction(entities=[WireEntity(name="Alpha", types=["Product"])])
        cfg = ExtractionSettings(union_k=2, **self.CFG_ONE_CALL)
        result = extract_document(
            [_chunk("alpha")], PURPOSE, Ontology(), ChurnEngine([wire], fail_first=True),
            concurrency=1, extraction_cfg=cfg,
        )
        assert [e.name for e in result.entities] == ["Alpha"]
        assert result.entities[0].properties["union_passes"] == 1
        assert any("chunk extraction failed" in w["reason"] for w in warnings)

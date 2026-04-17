"""Tests for type exemplar accumulation, snapshot, and prompt formatting."""
from kgf.ontology.buffer import OntologyBuffer
from kgf.extraction.prompts import build_extraction_prompt
from kgf.types.config import OntologyBufferConfig
from kgf.types.document import Chunk
from kgf.types.extraction import Entity, Relationship
from kgf.types.ontology import TypeExemplar


def _make_buffer(max_exemplars=5) -> OntologyBuffer:
    config = OntologyBufferConfig(
        min_frequency_to_confirm=1,
        min_frequency_to_emerge=1,
        max_type_exemplars=max_exemplars,
    )
    buf = OntologyBuffer(config)
    return buf


def _make_entities(type_name: str, names: list[str]) -> list[Entity]:
    return [
        Entity(id=f"{type_name.lower()}_{n.lower().replace(' ', '_')}", name=n, type=type_name)
        for n in names
    ]


class TestExemplarAccumulation:
    def test_basic_accumulation(self):
        buf = _make_buffer()
        entities = _make_entities("Component", ["Humidifier", "Tubing", "Filter"])
        buf.accumulate_from_result(entities, [])

        snapshot = buf.snapshot()
        assert "Component" in snapshot.type_exemplars
        exemplars = snapshot.type_exemplars["Component"]
        assert len(exemplars) == 3
        names = {e.name for e in exemplars}
        assert names == {"Humidifier", "Tubing", "Filter"}

    def test_max_exemplars_cap(self):
        buf = _make_buffer(max_exemplars=2)
        entities = _make_entities("Component", ["A", "B", "C"])
        buf.accumulate_from_result(entities, [])

        snapshot = buf.snapshot()
        assert len(snapshot.type_exemplars["Component"]) == 2

    def test_dedup_by_normalized_name(self):
        buf = _make_buffer()
        entities = [
            Entity(id="comp_hepa", name="HEPA Filter", type="Component"),
            Entity(id="comp_hepa2", name="hepa filter", type="Component"),
            Entity(id="comp_hepa3", name="Hepa Filter", type="Component"),
        ]
        buf.accumulate_from_result(entities, [])

        snapshot = buf.snapshot()
        exemplars = snapshot.type_exemplars["Component"]
        assert len(exemplars) == 1
        assert exemplars[0].frequency == 3

    def test_frequency_replacement(self):
        buf = _make_buffer(max_exemplars=2)
        # First batch: A(1), B(1) fill the slots
        entities1 = _make_entities("Component", ["A", "B"])
        buf.accumulate_from_result(entities1, [])

        # Second batch: C appears 3 times, should replace lowest
        entities2 = _make_entities("Component", ["C", "C", "C"])
        buf.accumulate_from_result(entities2, [])

        snapshot = buf.snapshot()
        exemplars = snapshot.type_exemplars["Component"]
        names = {e.name for e in exemplars}
        assert "C" in names
        assert len(exemplars) == 2

    def test_exemplars_only_for_known_types(self):
        buf = _make_buffer()
        # Register type first
        entities1 = _make_entities("Product", ["Widget"])
        buf.accumulate_from_result(entities1, [])

        snapshot = buf.snapshot()
        assert "Product" in snapshot.type_exemplars
        # Unknown types should not appear
        assert "FakeType" not in snapshot.type_exemplars

    def test_snapshot_freezes_exemplars(self):
        buf = _make_buffer()
        entities = _make_entities("Component", ["Humidifier"])
        buf.accumulate_from_result(entities, [])

        snapshot = buf.snapshot()
        exemplars = snapshot.type_exemplars["Component"]
        assert isinstance(exemplars, tuple)

    def test_exemplars_sorted_by_frequency_descending(self):
        buf = _make_buffer()
        # A appears 3 times, B appears 1 time
        entities = [
            Entity(id="comp_a1", name="A", type="Component"),
            Entity(id="comp_a2", name="A", type="Component"),
            Entity(id="comp_a3", name="A", type="Component"),
            Entity(id="comp_b1", name="B", type="Component"),
        ]
        buf.accumulate_from_result(entities, [])

        snapshot = buf.snapshot()
        exemplars = snapshot.type_exemplars["Component"]
        assert exemplars[0].name == "A"
        assert exemplars[0].frequency == 3


class TestPromptExemplarInjection:
    def test_exemplars_in_prompt(self):
        buf = _make_buffer()
        entities = _make_entities("Component", ["Humidifier", "Tubing"])
        buf.accumulate_from_result(entities, [])

        snapshot = buf.snapshot()
        chunk = Chunk(id="test", text="test text", source="test.pdf", index=0)
        prompt = build_extraction_prompt(chunk, snapshot)

        assert "(e.g., Humidifier, Tubing)" in prompt or "(e.g., Tubing, Humidifier)" in prompt

    def test_no_exemplars_no_hint(self):
        buf = _make_buffer()
        # Add type without exemplars (via signal only)
        from kgf.types.ontology import TypeSignal
        buf.accumulate([TypeSignal(type_name="Widget", frequency=2)])

        snapshot = buf.snapshot()
        chunk = Chunk(id="test", text="test text", source="test.pdf", index=0)
        prompt = build_extraction_prompt(chunk, snapshot)

        # Check the Widget line specifically has no exemplar hint
        assert "Widget (e.g.," not in prompt

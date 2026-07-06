"""Tests for cure-time type clustering."""

from knowledge_graph_foundry.models import Ontology, TypeDef
from knowledge_graph_foundry.ontology.clustering import (
    TypeClustering,
    TypeMerge,
    apply_type_remap,
    cluster_types,
)


class FakeEngine:
    name = "fake"

    def __init__(self, clustering: TypeClustering):
        self.clustering = clustering
        self.messages = None

    def complete(self, messages, response_model):
        self.messages = messages
        return self.clustering


def _ontology(*names: str) -> Ontology:
    return Ontology(
        purpose="compare CPAP machines",
        types={n: TypeDef(name=n, encounters=3, status="confirmed") for n in names},
    )


class TestClusterTypes:
    def test_synonym_merge_applied(self):
        onto = _ontology("Standard", "RegulatoryStandard", "Product")
        engine = FakeEngine(
            TypeClustering(merges=[TypeMerge(source="RegulatoryStandard", target="Standard")])
        )
        result, remap = cluster_types(onto, onto.purpose, engine)
        assert remap == {"RegulatoryStandard": "Standard"}
        assert "RegulatoryStandard" not in result.types
        assert result.types["Standard"].encounters == 6

    def test_purpose_in_prompt(self):
        onto = _ontology("A", "B")
        engine = FakeEngine(TypeClustering())
        cluster_types(onto, "compare CPAP machines", engine)
        assert any("compare CPAP machines" in m["content"] for m in engine.messages)

    def test_empty_merges_is_valid(self):
        onto = _ontology("Product", "Component")
        result, remap = cluster_types(onto, onto.purpose, FakeEngine(TypeClustering()))
        assert remap == {}
        assert set(result.types) == {"Product", "Component"}

    def test_unknown_type_proposal_ignored(self):
        onto = _ontology("Product", "Component")
        engine = FakeEngine(
            TypeClustering(merges=[TypeMerge(source="Ghost", target="Product")])
        )
        _, remap = cluster_types(onto, onto.purpose, engine)
        assert remap == {}

    def test_chain_collapsed(self):
        onto = _ontology("A", "B", "C")
        engine = FakeEngine(
            TypeClustering(
                merges=[TypeMerge(source="A", target="B"), TypeMerge(source="B", target="C")]
            )
        )
        result, remap = cluster_types(onto, onto.purpose, engine)
        assert remap["A"] == "C"
        assert set(result.types) == {"C"}

    def test_single_type_short_circuits(self):
        onto = _ontology("Product")
        result, remap = cluster_types(onto, onto.purpose, FakeEngine(TypeClustering()))
        assert remap == {}


class TestApplyTypeRemap:
    def test_rewrite_and_dedupe(self):
        assert apply_type_remap(["A", "B"], {"A": "B"}) == ["B"]

    def test_untouched_passthrough(self):
        assert apply_type_remap(["X", "Y"], {}) == ["X", "Y"]

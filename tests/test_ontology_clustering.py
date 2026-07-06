"""Tests for cure-time type clustering."""

from knowledge_graph_foundry.models import Ontology, TypeDef
from knowledge_graph_foundry.ontology.clustering import (
    MERGE_SIMILARITY_THRESHOLD,
    TypeClustering,
    TypeMerge,
    apply_type_remap,
    cluster_types,
    should_recure,
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
        engine = FakeEngine(TypeClustering(merges=[TypeMerge(source="Ghost", target="Product")]))
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


def _fake_embed(texts):
    """Distinct vectors per type; Standard and RegulatoryStandard near-identical."""
    out = []
    for t in texts:
        if "RegulatoryStandard" in t:
            out.append([0.98, 0.02, 0.0])
        elif "Standard" in t:
            out.append([1.0, 0.0, 0.0])
        else:  # Product - orthogonal, never blocked
            out.append([0.0, 1.0, 0.0])
    return out


class VerifyEngine:
    """Fake engine for the embed->block->verify path; records verify contents."""

    name = "fake"

    def __init__(self, verify_same=True):
        self.verify_same = verify_same
        self.verify_contents = []

    def complete(self, messages, response_model):
        content = messages[-1]["content"]
        self.verify_contents.append(content)
        return response_model(same=self.verify_same)


class TestEmbedVerifyPath:
    def test_blocked_and_verified_pair_merges_with_alias(self):
        onto = _ontology("Standard", "RegulatoryStandard", "Product")
        engine = VerifyEngine(verify_same=True)
        result, remap = cluster_types(onto, onto.purpose, engine, embed_fn=_fake_embed)
        assert remap == {"RegulatoryStandard": "Standard"}
        assert "RegulatoryStandard" not in result.types
        assert result.types["Standard"].encounters == 6
        assert "alias:RegulatoryStandard" in result.types["Standard"].properties

    def test_distant_types_never_verified(self):
        onto = _ontology("Standard", "RegulatoryStandard", "Product")
        engine = VerifyEngine(verify_same=True)
        cluster_types(onto, onto.purpose, engine, embed_fn=_fake_embed)
        # exactly one blocked pair verified; Product is orthogonal, never sent
        assert len(engine.verify_contents) == 1
        assert all("Product" not in c for c in engine.verify_contents)

    def test_verified_false_pair_not_merged(self):
        onto = _ontology("Standard", "RegulatoryStandard", "Product")
        engine = VerifyEngine(verify_same=False)
        result, remap = cluster_types(onto, onto.purpose, engine, embed_fn=_fake_embed)
        assert remap == {}
        assert set(result.types) == {"Standard", "RegulatoryStandard", "Product"}
        assert len(engine.verify_contents) == 1  # still blocked and verified, just rejected

    def test_embed_fn_none_uses_legacy_single_pass(self):
        onto = _ontology("Standard", "RegulatoryStandard", "Product")
        engine = FakeEngine(
            TypeClustering(merges=[TypeMerge(source="RegulatoryStandard", target="Standard")])
        )
        result, remap = cluster_types(onto, onto.purpose, engine, embed_fn=None)
        assert remap == {"RegulatoryStandard": "Standard"}
        assert "RegulatoryStandard" not in result.types


class TestShouldRecure:
    def test_at_burst_boundary_true(self):
        assert should_recure(cured_type_count=12, current_type_count=15, burst=3) is True

    def test_below_burst_boundary_false(self):
        assert should_recure(cured_type_count=12, current_type_count=14, burst=3) is False

    def test_threshold_constant_exposed(self):
        assert 0.0 < MERGE_SIMILARITY_THRESHOLD < 1.0


class TestValueTypeDemotion:
    """R02-H10: value-like types (PressureRange, Weight) fold into Specification."""

    def test_value_likeness_scores(self):
        from knowledge_graph_foundry.ontology.clustering import value_likeness

        assert value_likeness("4-20 cmH2O") == 1.0
        assert value_likeness("1.2 kg") == 1.0
        assert value_likeness("AirSense 11") == 0.5
        assert value_likeness("ResMed") == 0.0
        assert value_likeness("") == 0.0

    def test_value_type_demoted_to_target(self):
        from knowledge_graph_foundry.ontology.clustering import demote_value_types

        onto = _ontology("PressureRange", "Manufacturer")
        members = {
            "PressureRange": ["4-20 cmH2O", "3-15 cmH2O", "4-25 cmH2O"],
            "Manufacturer": ["ResMed", "Philips", "Fisher & Paykel"],
        }
        result, remap = demote_value_types(onto, members)
        assert remap == {"PressureRange": "Specification"}
        assert "PressureRange" not in result.types
        assert "Specification" in result.types
        assert "Manufacturer" in result.types
        assert "alias:PressureRange" in result.types["Specification"].properties

    def test_mixed_member_type_kept(self):
        from knowledge_graph_foundry.ontology.clustering import demote_value_types

        onto = _ontology("Warranty")
        members = {"Warranty": ["2 years", "limited warranty", "manufacturer warranty"]}
        result, remap = demote_value_types(onto, members)
        assert remap == {}
        assert "Warranty" in result.types

    def test_no_demotion_returns_same_ontology(self):
        from knowledge_graph_foundry.ontology.clustering import demote_value_types

        onto = _ontology("Manufacturer", "CPAPDevice")
        members = {"Manufacturer": ["ResMed"], "CPAPDevice": ["AirSense 11"]}
        result, remap = demote_value_types(onto, members)
        assert remap == {}
        assert result is onto

    def test_target_never_demotes_itself(self):
        from knowledge_graph_foundry.ontology.clustering import demote_value_types

        onto = _ontology("Specification")
        members = {"Specification": ["4-20 cmH2O", "26 dBA"]}
        result, remap = demote_value_types(onto, members)
        assert remap == {}

    def test_encounters_fold_into_target(self):
        from knowledge_graph_foundry.ontology.clustering import demote_value_types

        onto = _ontology("Weight", "Dimension")
        members = {
            "Weight": ["1.2 kg", "1130 g"],
            "Dimension": ["116 mm", "255 mm"],
        }
        result, remap = demote_value_types(onto, members)
        assert remap == {"Weight": "Specification", "Dimension": "Specification"}
        assert result.types["Specification"].encounters == 6  # 3 + 3 from _ontology helper


class TestSeededTypeProtection:
    """S7 scenario: seeded (user-governed) types are never demoted or clustered away."""

    def test_seeded_value_like_type_not_demoted(self):
        from knowledge_graph_foundry.ontology.clustering import demote_value_types

        onto = _ontology("PressureRange")
        onto.types["PressureRange"].status = "seeded"
        members = {"PressureRange": ["4-20 cmH2O", "3-15 cmH2O"]}
        result, remap = demote_value_types(onto, members)
        assert remap == {}
        assert "PressureRange" in result.types

    def test_seeded_type_never_merges_away(self):
        onto = _ontology("Standard", "RegulatoryStandard", "Product")
        onto.types["RegulatoryStandard"].status = "seeded"
        engine = VerifyEngine(verify_same=True)
        result, remap = cluster_types(onto, onto.purpose, engine, embed_fn=_fake_embed)
        assert "RegulatoryStandard" in result.types
        assert "RegulatoryStandard" not in remap

    def test_seeded_type_can_absorb_others(self):
        onto = _ontology("Standard", "RegulatoryStandard", "Product")
        # seeded target with more encounters wins merge direction
        onto.types["Standard"].status = "seeded"
        onto.types["Standard"].encounters = 10
        engine = VerifyEngine(verify_same=True)
        result, remap = cluster_types(onto, onto.purpose, engine, embed_fn=_fake_embed)
        assert remap == {"RegulatoryStandard": "Standard"}
        assert "Standard" in result.types

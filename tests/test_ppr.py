"""Tests for R2/R6: PPR retrieval and the global/local query router."""

import os

import pytest

from knowledge_graph_foundry.graph.graphrag import is_global_query, ppr_query

pytestmark_integration = pytest.mark.skipif(
    os.environ.get("KGF_INTEGRATION") != "1", reason="needs live neo4j (KGF_INTEGRATION=1)"
)


class TestRouter:
    def test_entity_questions_are_local(self):
        assert not is_global_query("What is the pressure range of the AirSense 11?")
        assert not is_global_query("Compare DreamStation and AirSense comfort features")

    def test_thematic_questions_are_global(self):
        assert is_global_query("Summarize the main themes across all CPAP devices")
        assert is_global_query("What types of comfort features exist overall?")
        assert is_global_query("Give a high-level landscape of the manufacturers")


class TestPprUnit:
    def test_empty_seeds_returns_empty(self):
        from unittest.mock import MagicMock

        assert ppr_query(MagicMock(), [], top_n=10) == []


@pytest.mark.integration
@pytestmark_integration
class TestPprIntegration:
    @pytest.fixture()
    def driver(self):
        from knowledge_graph_foundry.graphdb import create_driver
        from knowledge_graph_foundry.settings import load_settings

        driver = create_driver(load_settings().neo4j)
        marker = "kgf_ppr_probe"
        with driver.session() as s:
            s.run(f"MATCH (n:Entity) WHERE n.prop_probe='{marker}' DETACH DELETE n").consume()
        yield driver, marker
        with driver.session() as s:
            s.run(f"MATCH (n:Entity) WHERE n.prop_probe='{marker}' DETACH DELETE n").consume()
        driver.close()

    def test_ppr_reaches_two_hops(self, driver):
        """A chain A-B-C: seeding from A, PPR must surface C (two hops out),
        which a fixed 1-hop expansion never reaches."""
        from knowledge_graph_foundry.graph.loader import load_entities, load_relationships
        from knowledge_graph_foundry.models import Entity, Relationship

        drv, marker = driver
        ents = []
        for name in ("Alpha", "Beta", "Gamma", "Delta"):
            e = Entity.create(f"PPR {name}", types=["Node"], description=name)
            e.properties["probe"] = marker
            ents.append(e)
        load_entities(drv, ents)
        a, b, c, d = [e.id for e in ents]
        rels = [
            Relationship(source_id=a, target_id=b, type="LINK"),
            Relationship(source_id=b, target_id=c, type="LINK"),
            Relationship(source_id=c, target_id=d, type="LINK"),
        ]
        load_relationships(drv, rels)

        ranked = ppr_query(drv, [a], top_n=10)
        ids = {r["id"] for r in ranked}
        # C and D are 2-3 hops from the A seed; PPR should reach beyond 1 hop
        assert c in ids or d in ids


class TestDecomposeComparison:
    """R03-H15: structural comparison decomposition, no LLM."""

    def test_compare_and_form(self):
        from knowledge_graph_foundry.graph.graphrag import decompose_comparison

        subs = decompose_comparison(
            "Compare the AirSense 11 and the iBreeze Auto CPAP: pressure ranges, ramp features"
        )
        assert subs == [
            "AirSense 11 pressure ranges, ramp features",
            "iBreeze Auto CPAP pressure ranges, ramp features",
        ]

    def test_vs_form(self):
        from knowledge_graph_foundry.graph.graphrag import decompose_comparison

        subs = decompose_comparison("AirSense 11 vs DreamStation: pressure range?")
        assert subs == ["AirSense 11 pressure range", "DreamStation pressure range"]

    def test_which_is_form(self):
        from knowledge_graph_foundry.graph.graphrag import decompose_comparison

        subs = decompose_comparison("Which is lighter, the AirSense 11 or the DreamStation?")
        assert subs == ["AirSense 11 lighter", "DreamStation lighter"]

    def test_non_comparison_returns_none(self):
        from knowledge_graph_foundry.graph.graphrag import decompose_comparison

        assert decompose_comparison("What is the weight of the AirSense 11?") is None
        assert decompose_comparison("What warranty does ResMed provide?") is None

"""Tests for R1: bitemporal edges, contradiction reconciliation, versioning.

Unit tests pin the reconciliation Cypher and filter logic; the integration
suite (KGF_INTEGRATION=1) runs the temporal capability probe against live
Neo4j: a superseding fact must invalidate the prior edge non-lossily and the
current read must return the new value while history retains the old.
"""

import os

import pytest

from knowledge_graph_foundry.graph.temporal import reconcile_contradictions
from knowledge_graph_foundry.models import Entity, Relationship

pytestmark_integration = pytest.mark.skipif(
    os.environ.get("KGF_INTEGRATION") != "1", reason="needs live neo4j (KGF_INTEGRATION=1)"
)


class TestReconcileUnit:
    def test_no_functional_types_is_noop(self):
        from unittest.mock import MagicMock

        driver = MagicMock()
        rels = [Relationship(source_id="a", target_id="b", type="HAS_FEATURE")]
        assert reconcile_contradictions(driver, rels, functional_types=[]) == 0
        driver.session.assert_not_called()

    def test_only_functional_rows_sent(self):
        from unittest.mock import MagicMock

        driver = MagicMock()
        session = driver.session.return_value.__enter__.return_value
        session.run.return_value.single.return_value = {"invalidated": 1}
        rels = [
            Relationship(source_id="c", target_id="alice", type="HAS_CEO"),
            Relationship(source_id="c", target_id="x", type="HAS_FEATURE"),
        ]
        reconcile_contradictions(driver, rels, functional_types=["HAS_CEO"])
        sent = session.run.call_args.kwargs["rows"]
        assert len(sent) == 1
        assert sent[0]["type"] == "HAS_CEO"


@pytest.mark.integration
@pytestmark_integration
class TestTemporalProbe:
    @pytest.fixture()
    def driver(self):
        from knowledge_graph_foundry.graphdb import create_driver
        from knowledge_graph_foundry.settings import load_settings

        driver = create_driver(load_settings().neo4j)
        marker = "kgf_temporal_probe"
        with driver.session() as s:
            s.run("MATCH (v:KGFEntityVersion) WHERE v.prop_probe = $m DETACH DELETE v", m=marker).consume()
            s.run(f"MATCH (n:Entity) WHERE n.prop_probe = '{marker}' DETACH DELETE n").consume()
        yield driver, marker
        with driver.session() as s:
            s.run("MATCH (v:KGFEntityVersion) WHERE v.prop_probe = $m DETACH DELETE v", m=marker).consume()
            s.run(f"MATCH (n:Entity) WHERE n.prop_probe = '{marker}' DETACH DELETE n").consume()
        driver.close()

    def _company(self, marker, name="Acme Corp"):
        c = Entity.create(name, types=["Company"], description="a company")
        c.properties["probe"] = marker
        return c

    def _person(self, name, marker):
        p = Entity.create(name, types=["Person"], description=f"person {name}")
        p.properties["probe"] = marker
        return p

    def test_superseding_fact_invalidates_prior_nonlossy(self, driver):
        from knowledge_graph_foundry.graph.loader import load_entities, load_relationships
        from knowledge_graph_foundry.graph.temporal import (
            current_relationships,
            reconcile_contradictions,
            relationship_history,
        )

        drv, marker = driver
        company = self._company(marker)
        alice = self._person("Alice", marker)
        bob = self._person("Bob", marker)
        load_entities(drv, [company, alice, bob])

        # First fact: Acme CEO = Alice
        r1 = Relationship(source_id=company.id, target_id=alice.id, type="HAS_CEO")
        load_relationships(drv, [r1])
        reconcile_contradictions(drv, [r1], ["HAS_CEO"])

        current = current_relationships(drv, company.id)
        assert [c["target_name"] for c in current] == ["Alice"]

        # Superseding fact: Acme CEO = Bob
        r2 = Relationship(source_id=company.id, target_id=bob.id, type="HAS_CEO")
        load_relationships(drv, [r2])
        invalidated = reconcile_contradictions(drv, [r2], ["HAS_CEO"])
        assert invalidated == 1

        # Current read returns Bob only
        current = current_relationships(drv, company.id)
        assert [c["target_name"] for c in current] == ["Bob"]

        # History is non-lossy: Alice's edge retained with valid_to set
        history = relationship_history(drv, company.id, "HAS_CEO")
        names = {h["target_name"] for h in history}
        assert names == {"Alice", "Bob"}
        alice_edge = next(h for h in history if h["target_name"] == "Alice")
        assert alice_edge["valid_to"] is not None

    def test_entity_versioning_snapshots_prior_state(self, driver):
        from knowledge_graph_foundry.graph.loader import load_entities

        drv, marker = driver
        e = self._company(marker, name="Versioned Co")
        load_entities(drv, [e], versioning=True)

        # content change: longer description
        e2 = Entity(
            id=e.id, name="Versioned Co", types=["Company"],
            description="a much longer and more detailed company description than before",
            properties={"probe": marker},
        )
        load_entities(drv, [e2], versioning=True)

        with drv.session() as s:
            versions = s.run(
                "MATCH (:Entity {id: $id})-[:HAD_VERSION]->(v) RETURN v.description AS d",
                id=e.id,
            ).data()
        assert len(versions) == 1
        assert versions[0]["d"] == "a company"

    def test_no_version_on_idempotent_reload(self, driver):
        from knowledge_graph_foundry.graph.loader import load_entities

        drv, marker = driver
        e = self._company(marker, name="Idempotent Co")
        load_entities(drv, [e], versioning=True)
        load_entities(drv, [e], versioning=True)  # identical reload
        with drv.session() as s:
            n = s.run(
                "MATCH (:Entity {id: $id})-[:HAD_VERSION]->(v) RETURN count(v) AS n", id=e.id
            ).single()["n"]
        assert n == 0

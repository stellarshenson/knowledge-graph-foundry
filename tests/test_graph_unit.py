"""Unit tests for the graph package using mocked drivers."""

import json
from unittest.mock import MagicMock

from knowledge_graph_foundry.graph.loader import (
    ensure_indexes,
    load_entities,
    load_relationships,
)
from knowledge_graph_foundry.graph.metanode import read_control, write_control
from knowledge_graph_foundry.models import Entity, Relationship


def make_driver():
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    return driver, session


def run_queries(session):
    return [call.args[0] for call in session.run.call_args_list]


class TestEnsureIndexes:
    def test_index_cypher(self):
        driver, session = make_driver()
        ensure_indexes(driver, vector_dimensions=1024, vector_index_name="kgf_vec")
        queries = run_queries(session)
        assert len(queries) == 3
        assert all("IF NOT EXISTS" in q for q in queries)
        assert any("FOR (e:Entity) ON (e.id)" in q for q in queries)
        assert any("FOR (e:Entity) ON (e.name)" in q for q in queries)
        vector = next(q for q in queries if "VECTOR INDEX" in q)
        assert "`kgf_vec`" in vector
        assert "`vector.dimensions`: 1024" in vector
        assert "cosine" in vector


class TestLoadEntities:
    def entities(self, n):
        return [
            Entity.create(f"entity {i}", ["Device"], properties={"color": "red"}) for i in range(n)
        ]

    def test_merge_and_labels_cypher(self):
        driver, session = make_driver()
        load_entities(driver, self.entities(1))
        query = run_queries(session)[0]
        assert "UNWIND $rows AS row" in query
        assert "MERGE (e:Entity {id: row.id})" in query
        assert "apoc.create.addLabels" in query
        assert "apoc.coll.toSet" in query

    def test_batching(self):
        driver, session = make_driver()
        load_entities(driver, self.entities(3), batch_size=2)
        assert session.run.call_count == 2
        rows_first = session.run.call_args_list[0].kwargs["rows"]
        rows_second = session.run.call_args_list[1].kwargs["rows"]
        assert len(rows_first) == 2
        assert len(rows_second) == 1

    def test_properties_flattened(self):
        driver, session = make_driver()
        load_entities(driver, self.entities(1))
        row = session.run.call_args.kwargs["rows"][0]
        assert row["props"] == {"prop_color": "red"}
        assert row["types"] == ["Device"]


class TestLoadRelationships:
    def relationships(self, n):
        return [
            Relationship(source_id=f"e_{i}", target_id=f"e_{i + 1}", type="CONNECTS_TO")
            for i in range(n)
        ]

    def test_apoc_merge_cypher(self):
        driver, session = make_driver()
        load_relationships(driver, self.relationships(1))
        query = run_queries(session)[0]
        assert "MATCH (s:Entity {id: row.source_id})" in query
        assert "MATCH (t:Entity {id: row.target_id})" in query
        assert "apoc.merge.relationship(" in query
        assert "valid_from: timestamp()" in query  # bitemporal on-create stamp
        assert "valid_to: null" in query
        assert "apoc.coll.toSet" in query

    def test_batching(self):
        driver, session = make_driver()
        load_relationships(driver, self.relationships(3), batch_size=2)
        assert session.run.call_count == 2
        assert len(session.run.call_args_list[0].kwargs["rows"]) == 2
        assert len(session.run.call_args_list[1].kwargs["rows"]) == 1


class TestMetanode:
    def test_read_control_none_on_empty(self):
        driver, session = make_driver()
        session.run.return_value.single.return_value = None
        assert read_control(driver) is None

    def test_write_control_serializes_json(self):
        driver, session = make_driver()
        write_control(
            driver,
            {
                "fsm_state": "STABLE",
                "purpose": "cpap",
                "ontology": {"types": {"Device": {"encounters": 3}}},
                "metrics_history": [{"jsd": 0.01}],
            },
        )
        query = session.run.call_args.args[0]
        assert "MERGE (c:KGFControl {id: $id})" in query
        props = session.run.call_args.kwargs["props"]
        assert props["fsm_state"] == "STABLE"
        assert props["purpose"] == "cpap"
        assert json.loads(props["json_ontology"]) == {"types": {"Device": {"encounters": 3}}}
        assert json.loads(props["json_metrics_history"]) == [{"jsd": 0.01}]
        assert "updated_at" in props

    def test_read_control_parses_json(self):
        driver, session = make_driver()
        record = MagicMock()
        record.__getitem__.return_value = {
            "id": "kgf",
            "fsm_state": "CURING",
            "json_ontology": '{"purpose": "cpap"}',
            "updated_at": "2026-07-06T00:00:00+00:00",
        }
        session.run.return_value.single.return_value = record
        state = read_control(driver)
        assert state == {
            "fsm_state": "CURING",
            "ontology": {"purpose": "cpap"},
            "updated_at": "2026-07-06T00:00:00+00:00",
        }

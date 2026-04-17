"""Tests for graph query tool backends."""

from unittest.mock import MagicMock, patch

import pytest

from kgf.curing.graph_query import (
    GraphQueryRequest,
    GraphQueryResult,
    query_fluid,
    query_graph,
)
from kgf.types.extraction import Entity, Relationship


@pytest.fixture
def mock_accumulator():
    """Create a mock FluidAccumulator with known data."""
    acc = MagicMock()
    acc.all_entities.return_value = [
        Entity(id="person_alice", name="Alice", type="Person", description="A researcher"),
        Entity(id="person_bob", name="Bob", type="Person", description="An engineer"),
        Entity(id="device_pump", name="CPAP Pump", type="Device", description="Air pump component"),
        Entity(id="org_acme", name="Acme Corp", type="Organization", description="Manufacturer"),
    ]
    acc.all_relationships.return_value = [
        Relationship(source="person_alice", target="org_acme", type="WORKS_FOR"),
        Relationship(source="person_bob", target="device_pump", type="DESIGNED"),
        Relationship(source="org_acme", target="device_pump", type="MANUFACTURES"),
    ]
    return acc


class TestQueryFluidEntityCounts:
    def test_counts_all_types(self, mock_accumulator):
        req = GraphQueryRequest(query_type="entity_counts")
        result = query_fluid(req, mock_accumulator)
        assert result.record_count == 3
        type_map = {r["type"]: r["count"] for r in result.records}
        assert type_map["Person"] == 2
        assert type_map["Device"] == 1
        assert type_map["Organization"] == 1

    def test_filter_by_type(self, mock_accumulator):
        req = GraphQueryRequest(query_type="entity_counts", filter_type="Person")
        result = query_fluid(req, mock_accumulator)
        assert result.record_count == 1
        assert result.records[0]["type"] == "Person"
        assert result.records[0]["count"] == 2


class TestQueryFluidRelationshipPatterns:
    def test_counts_patterns(self, mock_accumulator):
        req = GraphQueryRequest(query_type="relationship_patterns")
        result = query_fluid(req, mock_accumulator)
        assert result.record_count == 3
        # Each pattern appears once
        for r in result.records:
            assert r["count"] == 1


class TestQueryFluidEntitySearch:
    def test_search_by_name(self, mock_accumulator):
        req = GraphQueryRequest(query_type="entity_search", filter_name="Alice")
        result = query_fluid(req, mock_accumulator)
        assert result.record_count == 1
        assert result.records[0]["name"] == "Alice"

    def test_search_by_type(self, mock_accumulator):
        req = GraphQueryRequest(query_type="entity_search", filter_type="Person")
        result = query_fluid(req, mock_accumulator)
        assert result.record_count == 2

    def test_search_by_name_and_type(self, mock_accumulator):
        req = GraphQueryRequest(query_type="entity_search", filter_name="Bob", filter_type="Person")
        result = query_fluid(req, mock_accumulator)
        assert result.record_count == 1
        assert result.records[0]["name"] == "Bob"

    def test_search_limit(self, mock_accumulator):
        req = GraphQueryRequest(query_type="entity_search", limit=1)
        result = query_fluid(req, mock_accumulator)
        assert result.record_count == 1


class TestQueryGraphEntityCounts:
    def test_counts_from_neo4j(self):
        mock_session = MagicMock()
        mock_session.run.return_value = [
            {"type": "Person", "count": 10},
            {"type": "Device", "count": 5},
        ]
        neo4j_config = MagicMock()
        neo4j_config.uri = "bolt://localhost:7687"
        neo4j_config.user = "neo4j"
        neo4j_config.password = "test"

        mock_driver = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("neo4j.GraphDatabase") as mock_gdb:
            mock_gdb.driver.return_value = mock_driver
            req = GraphQueryRequest(query_type="entity_counts")
            result = query_graph(req, neo4j_config)
            assert result.record_count == 2
            assert result.records[0]["type"] == "Person"


class TestQueryGraphEntitySearch:
    def test_search_from_neo4j(self):
        mock_session = MagicMock()
        mock_session.run.return_value = [
            {"name": "Alice", "type": "Person", "description": "A researcher"},
        ]
        neo4j_config = MagicMock()
        neo4j_config.uri = "bolt://localhost:7687"
        neo4j_config.user = "neo4j"
        neo4j_config.password = "test"

        mock_driver = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("neo4j.GraphDatabase") as mock_gdb:
            mock_gdb.driver.return_value = mock_driver
            req = GraphQueryRequest(query_type="entity_search", filter_name="Alice")
            result = query_graph(req, neo4j_config)
            assert result.record_count == 1
            assert result.records[0]["name"] == "Alice"

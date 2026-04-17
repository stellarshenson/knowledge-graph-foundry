"""Tests for graph-aware entity resolution during cured phase."""
from unittest.mock import MagicMock, patch

import pytest

from kgf.loading.loader import resolve_against_graph
from kgf.types.config import AppConfig, Neo4jConfig
from kgf.types.extraction import Entity, ExtractionResult, Relationship


@pytest.fixture
def config():
    return AppConfig(neo4j=Neo4jConfig(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="test",
    ))


def _make_result(entities, relationships=None):
    return ExtractionResult(
        entities=entities,
        relationships=relationships or [],
    )


def test_resolve_remaps_type_to_existing(config):
    """Incoming entity with different type should adopt graph entity's type."""
    incoming = _make_result([
        Entity(id="product_abc123", name="AirSense 10", type="Product",
               description="AirSense 10 CPAP therapy device"),
    ])

    mock_records = [
        {"id": "device_abc123", "name": "AirSense 10", "type": "Device",
         "description": "AirSense 10 CPAP therapy device"},
    ]

    with patch("kgf.loading.loader.GraphDatabase") as mock_gdb:
        mock_session = MagicMock()
        mock_session.run.return_value = mock_records
        mock_driver = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_gdb.driver.return_value = mock_driver

        result = resolve_against_graph(incoming, config)

    assert result.entities[0].type == "Device"
    assert result.entities[0].id == "device_abc123"


def test_resolve_rewires_relationships(config):
    """Relationships should be rewired when entity IDs change."""
    incoming = _make_result(
        entities=[
            Entity(id="product_abc", name="AirSense 10", type="Product",
                   description="AirSense 10 CPAP therapy device"),
            Entity(id="manufacturer_xyz", name="ResMed", type="Manufacturer"),
        ],
        relationships=[
            Relationship(
                source="manufacturer_xyz", target="product_abc",
                type="MANUFACTURES",
            ),
        ],
    )

    mock_records = [
        {"id": "device_abc", "name": "AirSense 10", "type": "Device",
         "description": "AirSense 10 CPAP therapy device"},
    ]

    with patch("kgf.loading.loader.GraphDatabase") as mock_gdb:
        mock_session = MagicMock()
        mock_session.run.return_value = mock_records
        mock_driver = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_gdb.driver.return_value = mock_driver

        result = resolve_against_graph(incoming, config)

    assert result.relationships[0].target == "device_abc"
    assert result.relationships[0].source == "manufacturer_xyz"


def test_resolve_no_change_when_types_match(config):
    """Entities with matching types should not be remapped."""
    incoming = _make_result([
        Entity(id="device_abc", name="AirSense 10", type="Device"),
    ])

    mock_records = [
        {"id": "device_abc", "name": "AirSense 10", "type": "Device"},
    ]

    with patch("kgf.loading.loader.GraphDatabase") as mock_gdb:
        mock_session = MagicMock()
        mock_session.run.return_value = mock_records
        mock_driver = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_gdb.driver.return_value = mock_driver

        result = resolve_against_graph(incoming, config)

    assert result.entities[0].type == "Device"
    assert result.entities[0].id == "device_abc"


def test_resolve_empty_entities(config):
    """Should return unchanged result when no entities."""
    incoming = _make_result([])
    result = resolve_against_graph(incoming, config)
    assert result.entities == []


def test_resolve_no_graph_matches(config):
    """Should return unchanged result when no graph matches found."""
    incoming = _make_result([
        Entity(id="product_abc", name="NewProduct", type="Product"),
    ])

    with patch("kgf.loading.loader.GraphDatabase") as mock_gdb:
        mock_session = MagicMock()
        mock_session.run.return_value = []
        mock_driver = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
        mock_gdb.driver.return_value = mock_driver

        result = resolve_against_graph(incoming, config)

    assert result.entities[0].type == "Product"
    assert result.entities[0].id == "product_abc"

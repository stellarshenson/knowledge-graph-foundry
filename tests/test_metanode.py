"""Tests for KGFControl metanode operations (mocked Neo4j)."""

from unittest.mock import MagicMock

import pytest

from kg_builder_cli.fsm.metanode import (
    create_control_metanode,
    detect_graph_state,
    read_control_metanode,
    update_control_metanode,
    write_run_node,
    write_transition_node,
)


@pytest.fixture
def mock_driver():
    """Mock Neo4j driver with session context manager."""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)
    return driver, session


class TestCreateControlMetanode:
    def test_creates_metanode(self, mock_driver):
        driver, session = mock_driver
        props = {
            "graph_id": "test-123",
            "fsm_state": "empty",
            "run_id": None,
            "run_count": 0,
            "ontology_source": None,
            "extraction_mechanism": None,
            "consolidation_started_at": None,
            "ontology_type_count": 0,
            "ontology_hash": None,
            "created_at": "2026-01-01T00:00:00Z",
            "last_completed_at": None,
            "last_error": None,
        }
        create_control_metanode(driver, props)
        session.run.assert_called_once()
        call_args = session.run.call_args
        assert "MERGE (c:KGFControl" in call_args[0][0]
        assert call_args[0][1]["graph_id"] == "test-123"


class TestReadControlMetanode:
    def test_reads_existing_metanode(self, mock_driver):
        driver, session = mock_driver
        mock_record = MagicMock()
        mock_record.__getitem__ = MagicMock(
            return_value={"graph_id": "abc", "fsm_state": "stable", "run_count": 2}
        )
        session.run.return_value.single.return_value = mock_record

        result = read_control_metanode(driver)
        assert result is not None

    def test_returns_none_when_no_metanode(self, mock_driver):
        driver, session = mock_driver
        session.run.return_value.single.return_value = None

        result = read_control_metanode(driver)
        assert result is None


class TestUpdateControlMetanode:
    def test_updates_properties(self, mock_driver):
        driver, session = mock_driver
        update_control_metanode(driver, {"fsm_state": "curing", "run_id": "run-1"})
        session.run.assert_called_once()
        query = session.run.call_args[0][0]
        assert "c.fsm_state" in query
        assert "c.run_id" in query

    def test_no_op_on_empty_updates(self, mock_driver):
        driver, session = mock_driver
        update_control_metanode(driver, {})
        session.run.assert_not_called()


class TestWriteRunNode:
    def test_creates_run_node(self, mock_driver):
        driver, session = mock_driver
        write_run_node(
            driver,
            run_id="run-001",
            graph_id="test-123",
            doc_count=10,
            entity_count=500,
            trigger_type="fluid",
        )
        session.run.assert_called_once()
        query = session.run.call_args[0][0]
        assert "KGFRun" in query
        assert "HAS_RUN" in query


class TestWriteTransitionNode:
    def test_creates_transition_node(self, mock_driver):
        driver, session = mock_driver
        write_transition_node(
            driver,
            graph_id="test-123",
            from_state="curing",
            to_state="stable",
            trigger="stabilize",
            run_id="run-001",
        )
        session.run.assert_called_once()
        query = session.run.call_args[0][0]
        assert "KGFTransition" in query
        assert "HAS_TRANSITION" in query


class TestDetectGraphState:
    def test_detects_empty_graph(self, mock_driver):
        driver, session = mock_driver
        # No metanode
        session.run.return_value.single.side_effect = [
            None,  # read_control_metanode returns None
            {"cnt": 0},  # entity count query
        ]

        result = detect_graph_state(driver)
        assert result["is_empty"] is True
        assert result["has_metanode"] is False
        assert result["has_entities"] is False

    def test_detects_existing_metanode(self, mock_driver):
        driver, session = mock_driver
        mock_record = MagicMock()
        mock_record.__getitem__ = MagicMock(
            return_value={"graph_id": "abc", "fsm_state": "stable"}
        )
        session.run.return_value.single.return_value = mock_record

        result = detect_graph_state(driver)
        assert result["has_metanode"] is True
        assert result["is_empty"] is False

    def test_detects_legacy_graph(self, mock_driver):
        driver, session = mock_driver
        # No metanode but has entities
        session.run.return_value.single.side_effect = [
            None,  # read_control_metanode
            {"cnt": 500},  # entity count
        ]

        result = detect_graph_state(driver)
        assert result["has_metanode"] is False
        assert result["has_entities"] is True
        assert result["is_empty"] is False

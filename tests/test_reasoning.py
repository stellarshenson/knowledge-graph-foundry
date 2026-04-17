"""Tests for post-load reasoning (subclass propagation)."""

from unittest.mock import MagicMock

from kgf.loading.reasoning import run_subclass_propagation, _SUBCLASS_PROPAGATION_QUERY


class TestSubclassPropagation:
    def test_returns_edge_count(self):
        mock_session = MagicMock()
        mock_record = {"new_edges": 5}
        mock_session.run.return_value.single.return_value = mock_record

        count = run_subclass_propagation(mock_session)
        assert count == 5
        mock_session.run.assert_called_once_with(_SUBCLASS_PROPAGATION_QUERY)

    def test_zero_edges(self):
        mock_session = MagicMock()
        mock_record = {"new_edges": 0}
        mock_session.run.return_value.single.return_value = mock_record

        count = run_subclass_propagation(mock_session)
        assert count == 0

    def test_no_record_returns_zero(self):
        mock_session = MagicMock()
        mock_session.run.return_value.single.return_value = None

        count = run_subclass_propagation(mock_session)
        assert count == 0

    def test_cypher_query_structure(self):
        """Verify the Cypher query has the expected pattern."""
        assert "INSTANCE_OF" in _SUBCLASS_PROPAGATION_QUERY
        assert "SUBCLASS_OF*" in _SUBCLASS_PROPAGATION_QUERY
        assert "MERGE" in _SUBCLASS_PROPAGATION_QUERY

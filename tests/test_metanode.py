"""Tests for KGFControl metanode operations (mocked Neo4j)."""

from unittest.mock import MagicMock

import pytest

from kgf.fsm.metanode import (
    _compress,
    _decompress,
    check_fluid_cache_exists,
    create_control_metanode,
    delete_fluid_results,
    delete_fluid_state,
    detect_graph_state,
    read_control_metanode,
    read_fluid_results,
    read_fluid_state,
    update_control_metanode,
    write_fluid_result,
    write_fluid_state,
    write_ontology_types,
    write_resolution_guide,
    write_run_node,
    write_transition_node,
    write_type_calibration,
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
        assert "MERGE (c:KGFControl:KGFState" in call_args[0][0]
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
        assert "KGFControl:KGFRun" in query
        assert "KGFControl:KGFState" in query
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
        assert "KGFControl:KGFTransition" in query
        assert "KGFControl:KGFState" in query
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


class TestWriteOntologyTypes:
    def test_writes_type_nodes(self, mock_driver):
        driver, session = mock_driver
        types = [
            {"name": "Product", "description": "A product", "properties": {"brand": "string"}},
            {"name": "Component", "description": "A component", "properties": {}},
        ]
        write_ontology_types(driver, "test-123", types, [])
        session.run.assert_called_once()
        query = session.run.call_args[0][0]
        assert "KGFControl:KGFOntologyType" in query

    def test_writes_hierarchy_relationships(self, mock_driver):
        driver, session = mock_driver
        types = [
            {"name": "Part", "description": "Parent"},
            {"name": "Component", "description": "Child"},
        ]
        hierarchy = [("Component", "Part")]
        write_ontology_types(driver, "test-123", types, hierarchy)
        assert session.run.call_count == 2
        hier_query = session.run.call_args_list[1][0][0]
        assert "IS_A" in hier_query

    def test_skips_empty_types(self, mock_driver):
        driver, session = mock_driver
        write_ontology_types(driver, "test-123", [], [])
        session.run.assert_not_called()


class TestWriteResolutionGuide:
    def test_writes_guide(self, mock_driver):
        driver, session = mock_driver
        write_resolution_guide(driver, "test-123", "rule1\nrule2")
        session.run.assert_called_once()
        query = session.run.call_args[0][0]
        assert "KGFControl:KGFResolutionGuide" in query
        assert session.run.call_args[0][1]["rules"] == "rule1\nrule2"


class TestWriteTypeCalibration:
    def test_writes_calibration_nodes(self, mock_driver):
        driver, session = mock_driver
        calibration = {
            "Product": {
                "entity_count": 100,
                "mean_posterior": 0.85,
                "observation_count": 120,
                "remap_count": 5,
                "prior_strength": 1.2,
            },
        }
        write_type_calibration(driver, "test-123", calibration)
        session.run.assert_called_once()
        query = session.run.call_args[0][0]
        assert "KGFControl:KGFTypeCalibration" in query
        assert "HAS_CALIBRATION" in query
        assert "KGFControl:KGFState" in query

    def test_skips_empty_calibration(self, mock_driver):
        driver, session = mock_driver
        write_type_calibration(driver, "test-123", {})
        session.run.assert_not_called()


class TestCompressDecompress:
    def test_round_trip(self):
        data = {"entities": [{"name": "Foo", "type": "Product"}], "count": 42}
        payload = _compress(data)
        assert isinstance(payload, str)
        result = _decompress(payload)
        assert result == data

    def test_version_mismatch_returns_none(self):
        data = {"key": "value"}
        payload = _compress(data, version=999)
        result = _decompress(payload)
        assert result is None

    def test_list_round_trip(self):
        data = [1, 2, 3, {"nested": True}]
        payload = _compress(data)
        assert _decompress(payload) == data


class TestWriteFluidResult:
    def test_writes_result_node(self, mock_driver):
        driver, session = mock_driver
        from kgf.types.extraction import ExtractionResult

        result = ExtractionResult(
            entities=[],
            relationships=[],
        )
        write_fluid_result(driver, "g-1", "run-1", "doc.pdf", 0, result)
        session.run.assert_called_once()
        query = session.run.call_args[0][0]
        assert "KGFControl:KGFFluidResult" in query
        params = session.run.call_args[0][1]
        assert params["graph_id"] == "g-1"
        assert params["doc_name"] == "doc.pdf"
        assert params["doc_index"] == 0

    def test_excludes_embeddings(self, mock_driver):
        driver, session = mock_driver
        from kgf.types.extraction import Entity, ExtractionResult

        result = ExtractionResult(
            entities=[
                Entity(
                    id="e1",
                    name="Test",
                    type="Product",
                    embedding=[0.1] * 1536,
                )
            ],
        )
        write_fluid_result(driver, "g-1", "run-1", "doc.pdf", 0, result)
        params = session.run.call_args[0][1]
        # Decompress and verify embedding excluded
        data = _decompress(params["payload"])
        assert data is not None
        assert "embedding" not in data["entities"][0]


class TestReadFluidResults:
    def test_reads_and_deserializes(self, mock_driver):
        driver, session = mock_driver
        from kgf.types.extraction import ExtractionResult

        # Prepare a cached result payload
        result = ExtractionResult(entities=[], relationships=[])
        data = result.model_dump()
        data.pop("chunks", None)
        payload = _compress(data)

        mock_record = {"doc_name": "doc.pdf", "doc_index": 0, "payload": payload}
        session.run.return_value = [mock_record]

        results = read_fluid_results(driver, "g-1")
        assert len(results) == 1
        assert results[0][0] == "doc.pdf"
        assert results[0][1] == 0
        assert isinstance(results[0][2], ExtractionResult)

    def test_returns_empty_on_version_mismatch(self, mock_driver):
        driver, session = mock_driver
        payload = _compress({"entities": [], "relationships": []}, version=999)
        mock_record = {"doc_name": "doc.pdf", "doc_index": 0, "payload": payload}
        session.run.return_value = [mock_record]

        results = read_fluid_results(driver, "g-1")
        assert results == []


class TestDeleteFluidResults:
    def test_deletes_nodes(self, mock_driver):
        driver, session = mock_driver
        delete_fluid_results(driver, "g-1")
        session.run.assert_called_once()
        query = session.run.call_args[0][0]
        assert "KGFFluidResult" in query
        assert "DETACH DELETE" in query


class TestWriteFluidState:
    def test_writes_state_node(self, mock_driver):
        driver, session = mock_driver
        detector_data = {"docs_processed": 5, "coverage_history": [0.5, 0.7]}
        metrics_data = {"history": [], "variance_window": 5}
        write_fluid_state(driver, "g-1", "run-1", detector_data, metrics_data)
        session.run.assert_called_once()
        query = session.run.call_args[0][0]
        assert "KGFControl:KGFFluidState" in query
        params = session.run.call_args[0][1]
        assert params["docs_processed"] == 5


class TestReadFluidState:
    def test_reads_state(self, mock_driver):
        driver, session = mock_driver
        state = {"detector": {"docs_processed": 3}, "metrics": {"history": []}}
        payload = _compress(state)
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, k: payload
        session.run.return_value.single.return_value = mock_record

        result = read_fluid_state(driver, "g-1")
        assert result is not None
        assert result["detector"]["docs_processed"] == 3

    def test_returns_none_when_absent(self, mock_driver):
        driver, session = mock_driver
        session.run.return_value.single.return_value = None
        assert read_fluid_state(driver, "g-1") is None


class TestDeleteFluidState:
    def test_deletes_node(self, mock_driver):
        driver, session = mock_driver
        delete_fluid_state(driver, "g-1")
        session.run.assert_called_once()
        query = session.run.call_args[0][0]
        assert "KGFFluidState" in query
        assert "DETACH DELETE" in query


class TestCheckFluidCacheExists:
    def test_returns_true_when_exists(self, mock_driver):
        driver, session = mock_driver
        session.run.return_value.single.return_value = {"cnt": 3}
        assert check_fluid_cache_exists(driver, "g-1") is True

    def test_returns_false_when_empty(self, mock_driver):
        driver, session = mock_driver
        session.run.return_value.single.return_value = {"cnt": 0}
        assert check_fluid_cache_exists(driver, "g-1") is False


class TestSerializationRoundTrips:
    """Round-trip tests for detector, metrics, and deferred buffer serialization."""

    def test_curing_detector_round_trip(self):
        from kgf.curing.detector import CuringDetector
        from kgf.types.config import CuringConfig

        config = CuringConfig()
        det = CuringDetector(config)
        det.record(0.5, {"Product"}, {"js_divergence": 0.1})
        det.record(0.7, set(), {"js_divergence": 0.05})
        det.record(0.8, {"Component"}, {"js_divergence": 0.02})

        data = det.to_dict()
        restored = CuringDetector.from_dict(data, config)

        assert restored.docs_processed == 3
        assert restored._coverage_history == det._coverage_history
        assert restored._new_types_history == det._new_types_history
        assert restored._metrics_history == det._metrics_history

    def test_stability_metrics_round_trip(self):
        from kgf.curing.metrics import StabilityMetrics

        m = StabilityMetrics(variance_window=3)
        m.record({"Product": 10, "Component": 5})
        m.record({"Product": 12, "Component": 6, "Accessory": 2})

        data = m.to_dict()
        restored = StabilityMetrics.from_dict(data)

        assert len(restored._history) == 2
        assert restored._type_counts_history == m._type_counts_history
        assert restored._total_occurrences_history == m._total_occurrences_history
        assert restored._prev_probs == m._prev_probs

    def test_deferred_dedup_round_trip(self):
        from kgf.extraction.deferred_dedup import DeferredDedupBuffer
        from kgf.types.extraction import Entity

        buf = DeferredDedupBuffer()
        e1 = Entity(id="e1", name="Widget", type="Product", source_chunks=["c1"])
        e2 = Entity(id="e2", name="Widget", type="Component", source_chunks=["c1"])
        buf.defer(e1, e2, posterior=0.5, doc_index=0)
        buf.defer(e1, e2, posterior=0.55, doc_index=1)

        data = buf.to_dict()
        restored = DeferredDedupBuffer.from_dict(data)

        assert restored.pair_count == 1
        key = list(restored._pairs.keys())[0]
        pair = restored._pairs[key]
        assert pair.entity_a_name == "widget"
        assert len(pair.posteriors) == 2
        assert pair.shared_chunks == 2  # c1 shared both times

    def test_extraction_result_serialize_without_embeddings(self):
        from kgf.types.extraction import Entity, ExtractionResult, Relationship

        result = ExtractionResult(
            entities=[
                Entity(
                    id="e1",
                    name="Test",
                    type="Product",
                    embedding=[0.1] * 100,
                    source_chunks=["c1"],
                ),
            ],
            relationships=[
                Relationship(source="e1", target="e2", type="RELATED_TO"),
            ],
        )
        data = result.model_dump()
        for ent in data.get("entities", []):
            ent.pop("embedding", None)
        data.pop("chunks", None)

        payload = _compress(data)
        restored_data = _decompress(payload)
        restored = ExtractionResult.model_validate(restored_data)

        assert len(restored.entities) == 1
        assert restored.entities[0].embedding is None
        assert len(restored.relationships) == 1

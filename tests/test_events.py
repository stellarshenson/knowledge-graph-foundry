"""Tests for the KGF event system: signal dispatch, event models, and handlers."""

from __future__ import annotations

import blinker

from kg_builder_cli.events import (
    clear_event_log,
    get_event_log,
    register_default_handlers,
    register_event_accumulator,
    register_verbose_handlers,
    signals,
    types,
)


def _disconnect_all():
    """Disconnect all receivers from all signals to isolate tests."""
    for name in dir(signals):
        obj = getattr(signals, name)
        if isinstance(obj, blinker.Signal):
            obj.receivers.clear()


class TestSignalDispatch:
    """Test that signals dispatch correctly with event payloads."""

    def setup_method(self):
        _disconnect_all()
        clear_event_log()

    def teardown_method(self):
        _disconnect_all()
        clear_event_log()

    def test_signal_send_receives_event(self):
        received = []

        def handler(sender, event=None, **kwargs):
            received.append(event)

        signals.ingestion_started.connect(handler)
        event = types.IngestionStarted(files=["a.pdf", "b.pdf"], mode="fluid", model="test-model")
        signals.ingestion_started.send(signals.ingestion_started, event=event)

        assert len(received) == 1
        assert received[0].files == ["a.pdf", "b.pdf"]
        assert received[0].mode == "fluid"

    def test_multiple_handlers_receive_same_event(self):
        received_a = []
        received_b = []

        def handler_a(sender, event=None, **kw):
            received_a.append(event)

        def handler_b(sender, event=None, **kw):
            received_b.append(event)

        signals.phase_transition.connect(handler_a)
        signals.phase_transition.connect(handler_b)

        event = types.PhaseTransition(
            from_phase="fluid", to_phase="cured", trigger="converged", doc_index=4
        )
        signals.phase_transition.send(signals.phase_transition, event=event)

        assert len(received_a) == 1
        assert len(received_b) == 1
        assert received_a[0].trigger == "converged"

    def test_unconnected_signal_does_not_fail(self):
        event = types.IngestionCompleted(total_docs=10, total_entities=100, total_rels=50)
        # No handlers connected - should not raise
        signals.ingestion_completed.send(signals.ingestion_completed, event=event)


class TestEventModels:
    """Test Pydantic event model construction and serialization."""

    def test_cross_type_decision_fields(self):
        event = types.CrossTypeDecision(
            entity_name="Humidifier",
            type_a="Component",
            type_b="Accessory",
            prior=0.8,
            posterior=0.72,
            action="merged",
            lr_desc=0.6,
            lr_emb=1.2,
            lr_cooc=1.5,
            has_hierarchy=True,
            sibling=True,
            doc_index=3,
        )
        assert event.entity_name == "Humidifier"
        assert event.posterior == 0.72
        data = event.model_dump()
        assert "lr_desc" in data
        assert data["action"] == "merged"

    def test_stability_metrics_recorded(self):
        event = types.StabilityMetricsRecorded(
            doc_index=5,
            entity_count=200,
            type_count=8,
            entropy_shannon=2.5,
            entropy_shannon_delta=0.01,
            kl_divergence=0.001,
            js_divergence=0.002,
            type_accumulation_rate=0.0,
            gini_coefficient=0.35,
            zipf_r_squared=0.92,
            heaps_beta=0.4,
            chao1_estimate=9.0,
            chao1_coverage=0.89,
            ace_estimate=8.5,
            rolling_jsd_var=0.0001,
            rolling_entropy_var=0.0002,
        )
        assert event.doc_index == 5
        assert event.chao1_coverage == 0.89

    def test_llm_call_started_optional_fields(self):
        event = types.LLMCallStarted(
            call_type="chunk_extraction",
            model="bedrock/claude-sonnet",
        )
        assert event.doc_index is None
        assert event.context == {}

    def test_consolidation_completed(self):
        event = types.ConsolidationCompleted(
            entities_before=500,
            entities_after=200,
            rels_before=1000,
            rels_after=800,
            deferred_resolved=5,
            steps_completed=["type_enforcement", "dedup", "resolution", "deferred"],
        )
        assert len(event.steps_completed) == 4

    def test_event_json_serialization(self):
        event = types.GraphLoadCompleted(
            entities_created=100,
            entities_merged=100,
            rels_created=300,
            duration_ms=1500,
        )
        json_str = event.model_dump_json()
        assert "entities_created" in json_str
        assert "1500" in json_str

    def test_curing_condition_blocked(self):
        event = types.CuringConditionBlocked(
            method="is_cured",
            condition="chao1_coverage < min",
            actual_value=0.394,
            threshold=0.5,
            doc_index=3,
        )
        assert event.actual_value == 0.394


class TestHandlerRegistration:
    """Test default and verbose handler registration."""

    def setup_method(self):
        _disconnect_all()
        clear_event_log()

    def teardown_method(self):
        _disconnect_all()
        clear_event_log()

    def test_register_default_handlers(self):
        register_default_handlers()
        # Default handlers connect to key signals
        assert len(signals.ingestion_started.receivers) > 0
        assert len(signals.ingestion_completed.receivers) > 0
        assert len(signals.curing_triggered.receivers) > 0

    def test_register_verbose_handlers(self):
        register_verbose_handlers()
        # Verbose connects to all signals
        assert len(signals.ingestion_started.receivers) > 0
        assert len(signals.cross_type_decision.receivers) > 0
        assert len(signals.stability_metrics_recorded.receivers) > 0

    def test_event_accumulator(self):
        register_event_accumulator()

        event1 = types.IngestionStarted(files=["a.pdf"], mode="fluid", model="test")
        signals.ingestion_started.send(signals.ingestion_started, event=event1)

        event2 = types.IngestionCompleted(total_docs=1, total_entities=10, total_rels=5)
        signals.ingestion_completed.send(signals.ingestion_completed, event=event2)

        log = get_event_log()
        assert len(log) == 2
        assert log[0]["signal"] == "ingestion-started"
        assert log[1]["signal"] == "ingestion-completed"

    def test_clear_event_log(self):
        register_event_accumulator()
        event = types.IngestionStarted(files=["a.pdf"], mode="fluid", model="test")
        signals.ingestion_started.send(signals.ingestion_started, event=event)
        assert len(get_event_log()) == 1

        clear_event_log()
        assert len(get_event_log()) == 0


class TestSignalCoverage:
    """Verify all expected signals exist."""

    def test_signal_count(self):
        sig_names = [
            name
            for name in dir(signals)
            if isinstance(getattr(signals, name), blinker.Signal) and not name.startswith("_")
        ]
        # 41 signals across 10 categories
        assert len(sig_names) >= 41

    def test_all_categories_present(self):
        # Spot-check one signal from each category
        assert hasattr(signals, "ingestion_started")  # pipeline
        assert hasattr(signals, "document_extraction_started")  # extraction
        assert hasattr(signals, "cross_type_decision")  # resolution
        assert hasattr(signals, "ontology_signals_accumulated")  # ontology
        assert hasattr(signals, "stability_metrics_recorded")  # stability
        assert hasattr(signals, "curing_check_performed")  # curing
        assert hasattr(signals, "llm_call_started")  # llm
        assert hasattr(signals, "merge_blocked")  # blocked
        assert hasattr(signals, "buffer_types_pruned")  # buffer
        assert hasattr(signals, "graph_load_started")  # loading

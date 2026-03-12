"""Tests for the KGF event system: signal dispatch, event models, and handlers."""

from __future__ import annotations

import blinker

from kg_builder_cli.events import (
    clear_event_log,
    get_event_log_count,
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

    def test_document_extraction_started_has_total_docs(self):
        event = types.DocumentExtractionStarted(
            document_source="test.pdf",
            doc_index=2,
            total_docs=10,
            chunk_count=15,
            phase="fluid",
        )
        assert event.doc_index == 2
        assert event.total_docs == 10

    def test_document_extraction_completed_has_total_docs(self):
        event = types.DocumentExtractionCompleted(
            document_source="test.pdf",
            doc_index=2,
            total_docs=10,
            entity_count=50,
            rel_count=30,
            remap_count=3,
            phase="cured",
        )
        assert event.total_docs == 10

    def test_merge_blocked_fields(self):
        event = types.MergeBlocked(
            entity_name="Tube",
            type_a="Component",
            type_b="Accessory",
            posterior=0.35,
            reason="below_threshold",
            doc_index=3,
        )
        assert event.posterior == 0.35

    def test_cross_type_pair_deferred(self):
        event = types.CrossTypePairDeferred(
            entity_name="Filter",
            type_a="Component",
            type_b="Accessory",
            posterior=0.52,
            ambiguous_lower=0.4,
            merge_threshold=0.6,
            doc_index=2,
        )
        assert event.posterior == 0.52

    def test_deferred_resolution_completed(self):
        event = types.DeferredResolutionCompleted(
            pairs_resolved=10,
            merges=6,
            blocks=3,
            llm_escalations=1,
        )
        assert event.pairs_resolved == 10

    def test_ontology_signals_accumulated(self):
        event = types.OntologySignalsAccumulated(
            new_entity_types=3,
            new_rel_types=2,
            total_entity_types=8,
            total_rel_types=12,
        )
        assert event.new_entity_types == 3

    def test_hierarchy_pair_qualifying(self):
        event = types.HierarchyPairQualifying(
            type_a="Component",
            type_b="Accessory",
            encounters=5,
            threshold=3,
        )
        assert event.encounters == 5

    def test_hierarchy_evolved(self):
        event = types.HierarchyEvolved(
            parent_name="Part",
            children=["Component", "Accessory"],
            is_new=True,
        )
        assert event.parent_name == "Part"

    def test_guide_rule_generated(self):
        event = types.GuideRuleGenerated(
            entity_name="humidifier",
            dominant_type="Component",
            other_type="Accessory",
            dominance=0.75,
            encounters=6,
        )
        assert event.dominance == 0.75

    def test_guide_rule_skipped(self):
        event = types.GuideRuleSkipped(
            entity_name="tube",
            type_a="Component",
            type_b="Accessory",
            dominance=0.5,
            encounters=2,
            reason="below_encounter_threshold",
        )
        assert event.reason == "below_encounter_threshold"

    def test_hierarchy_skipped(self):
        event = types.HierarchySkipped(
            type_a="Component",
            type_b="Accessory",
            encounters=1,
            threshold=3,
            reason="below_encounter_threshold",
        )
        assert event.encounters == 1

    def test_buffer_types_pruned(self):
        event = types.BufferTypesPruned(
            pruned_entity_types=["ModeX"],
            pruned_rel_types=[],
            remaining_entity_types=7,
            remaining_rel_types=10,
        )
        assert len(event.pruned_entity_types) == 1

    def test_buffer_exemplars_updated(self):
        event = types.BufferExemplarsUpdated(
            entity_type="Product",
            exemplar_count=5,
        )
        assert event.entity_type == "Product"

    def test_buffer_snapshot_taken(self):
        event = types.BufferSnapshotTaken(
            path="",
            entity_type_count=8,
            rel_type_count=12,
        )
        assert event.entity_type_count == 8

    def test_type_enforcement_applied(self):
        event = types.TypeEnforcementApplied(
            document_source="consolidation",
            remap_count=5,
            method="levenshtein",
        )
        assert event.remap_count == 5

    def test_merge_validation_failed(self):
        event = types.MergeValidationFailed(
            cluster_label="Mode->Role",
            entity_names=["Mode"],
            confidence=0.3,
            threshold=0.4,
            reason="name_sim=0.400, desc_coh=0.200, freq_rat=0.100",
        )
        assert event.confidence == 0.3

    def test_stability_snapshot(self):
        event = types.StabilitySnapshot(
            doc_index=4,
            metrics_summary={"entropy_shannon": 2.5},
        )
        assert event.doc_index == 4

    def test_graph_resolution_applied(self):
        event = types.GraphResolutionApplied(
            remapped_count=3,
        )
        assert event.remapped_count == 3

    def test_graph_validated(self):
        event = types.GraphValidated(
            entity_count=100,
            rel_count=300,
            type_coverage=0.95,
            orphan_count=2,
        )
        assert event.type_coverage == 0.95

    def test_patience_exceeded(self):
        event = types.PatienceExceeded(
            docs_processed=8,
            max_patience=8,
            trigger="consecutive_cure_votes",
        )
        assert event.docs_processed == 8

    def test_curing_triggered(self):
        event = types.CuringTriggered(
            trigger="generative",
            doc_index=4,
            accumulated_docs=5,
            type_count=8,
        )
        assert event.trigger == "generative"

    def test_deferred_evidence_updated(self):
        event = types.DeferredEvidenceUpdated(
            entity_name="filter",
            type_a="Component",
            type_b="Accessory",
            shared_chunks=3,
            topology_jaccard=0.25,
            posteriors_count=4,
            desc_similarity=0.0,
        )
        assert event.shared_chunks == 3

    def test_deferred_pair_skipped(self):
        event = types.DeferredPairSkipped(
            entity_name="tube",
            type_a="Component",
            type_b="Accessory",
            final_posterior=0.38,
            reason="posterior 0.380 < 0.6 after 2 encounters",
        )
        assert event.final_posterior == 0.38


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
        assert len(signals.document_extraction_started.receivers) > 0

    def test_register_verbose_handlers(self):
        register_verbose_handlers()
        # Verbose connects to all signals
        assert len(signals.ingestion_started.receivers) > 0
        assert len(signals.cross_type_decision.receivers) > 0
        assert len(signals.stability_metrics_recorded.receivers) > 0

    def test_default_handlers_cover_key_signals(self):
        """Verify all signals with dedicated default handlers are registered."""
        register_default_handlers()
        expected_with_handlers = [
            "ingestion_started",
            "ingestion_completed",
            "phase_transition",
            "document_extraction_started",
            "document_extraction_completed",
            "curing_triggered",
            "ontology_evolved",
            "consolidation_completed",
            "graph_load_completed",
            "graph_validated",
            "llm_call_failed",
            "drift_detected",
            "patience_exceeded",
        ]
        for sig_name in expected_with_handlers:
            sig = getattr(signals, sig_name)
            assert len(sig.receivers) > 0, f"default handler missing for {sig_name}"

    def test_verbose_handlers_cover_all_signals(self):
        """Verbose mode must register a handler on every signal."""
        register_verbose_handlers()
        sig_names = [
            name
            for name in dir(signals)
            if isinstance(getattr(signals, name), blinker.Signal) and not name.startswith("_")
        ]
        for sig_name in sig_names:
            sig = getattr(signals, sig_name)
            assert len(sig.receivers) > 0, f"verbose handler missing for {sig_name}"

    def test_event_accumulator(self, tmp_path):
        log_file = tmp_path / "events.log"
        register_event_accumulator(log_file)

        event1 = types.IngestionStarted(files=["a.pdf"], mode="fluid", model="test")
        signals.ingestion_started.send(signals.ingestion_started, event=event1)

        event2 = types.IngestionCompleted(total_docs=1, total_entities=10, total_rels=5)
        signals.ingestion_completed.send(signals.ingestion_completed, event=event2)

        assert get_event_log_count() == 2
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 2
        import json

        assert json.loads(lines[0])["signal"] == "ingestion-started"
        assert json.loads(lines[1])["signal"] == "ingestion-completed"

    def test_event_accumulator_captures_all_signals(self, tmp_path):
        """Event accumulator writes JSONL for every signal type when connected."""
        import json

        log_file = tmp_path / "events.log"
        register_event_accumulator(log_file)

        # Fire a selection of signals across all categories
        test_events = [
            (signals.ingestion_started, types.IngestionStarted(
                files=["a.pdf"], mode="fluid", model="test")),
            (signals.document_extraction_started, types.DocumentExtractionStarted(
                document_source="a.pdf", doc_index=0, total_docs=1, chunk_count=5, phase="fluid")),
            (signals.cross_type_decision, types.CrossTypeDecision(
                entity_name="X", type_a="A", type_b="B", prior=0.8, posterior=0.7,
                action="merged", lr_desc=0.6, lr_emb=1.0, lr_cooc=1.5,
                has_hierarchy=False, sibling=False, doc_index=0)),
            (signals.merge_blocked, types.MergeBlocked(
                entity_name="Y", type_a="A", type_b="B", posterior=0.3,
                reason="below_threshold", doc_index=0)),
            (signals.ontology_signals_accumulated, types.OntologySignalsAccumulated(
                new_entity_types=2, new_rel_types=1, total_entity_types=5, total_rel_types=3)),
            (signals.buffer_snapshot_taken, types.BufferSnapshotTaken(
                path="", entity_type_count=5, rel_type_count=3)),
            (signals.graph_validated, types.GraphValidated(
                entity_count=100, rel_count=300, type_coverage=0.95, orphan_count=0)),
            (signals.ingestion_completed, types.IngestionCompleted(
                total_docs=1, total_entities=100, total_rels=300)),
        ]

        for sig, evt in test_events:
            sig.send(sig, event=evt)

        assert get_event_log_count() == len(test_events)
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == len(test_events)

        # Verify each line is valid JSONL with signal name and payload
        for line in lines:
            parsed = json.loads(line)
            assert "signal" in parsed
            assert "payload" in parsed

    def test_clear_event_log(self, tmp_path):
        log_file = tmp_path / "events.log"
        register_event_accumulator(log_file)
        event = types.IngestionStarted(files=["a.pdf"], mode="fluid", model="test")
        signals.ingestion_started.send(signals.ingestion_started, event=event)
        assert get_event_log_count() == 1

        clear_event_log()
        assert get_event_log_count() == 0


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

    def test_every_signal_has_matching_event_model(self):
        """Every signal should have a corresponding Pydantic event model in types.py."""
        sig_names = [
            name
            for name in dir(signals)
            if isinstance(getattr(signals, name), blinker.Signal) and not name.startswith("_")
        ]
        # Build case-insensitive lookup for type names (handles acronyms like LLM)
        type_names_lower = {
            name.lower(): name
            for name in dir(types)
            if not name.startswith("_") and isinstance(getattr(types, name), type)
        }

        for sig_name in sig_names:
            pascal = "".join(word.capitalize() for word in sig_name.split("_"))
            assert pascal.lower() in type_names_lower, (
                f"Signal '{sig_name}' has no matching event model '{pascal}' in types.py"
            )


class TestSignalWiring:
    """Verify signals are actually emitted from business logic code.

    These tests exercise real code paths (with mocked external deps where needed)
    and capture signal emissions to verify wiring.
    """

    def setup_method(self):
        _disconnect_all()
        clear_event_log()
        self._captured: dict[str, list] = {}
        self._handlers: list = []  # strong refs prevent GC with blinker weak refs

    def teardown_method(self):
        _disconnect_all()
        clear_event_log()

    def _capture(self, signal_name: str):
        """Return a handler that captures events for the given signal."""
        self._captured[signal_name] = []

        def handler(sender, event=None, **kw):
            self._captured[signal_name].append(event)

        self._handlers.append(handler)
        return handler

    def test_entity_resolution_emits_cross_type_decision(self):
        """resolve_entities emits cross_type_decision for cross-type pairs."""
        from kg_builder_cli.types.extraction import Entity

        signals.cross_type_decision.connect(self._capture("cross_type_decision"))
        signals.entity_resolution_completed.connect(
            self._capture("entity_resolution_completed")
        )

        entities = [
            Entity(id="comp_tube", name="Tube", type="Component", description="A tube"),
            Entity(id="acc_tube", name="Tube", type="Accessory", description="An accessory tube"),
        ]
        from kg_builder_cli.extraction.resolution import resolve_entities

        resolve_entities(entities, cross_type_merge_threshold=0.6)

        assert len(self._captured["entity_resolution_completed"]) == 1
        # At least one cross-type decision (merge or block)
        assert len(self._captured["cross_type_decision"]) >= 1
        evt = self._captured["cross_type_decision"][0]
        assert evt.entity_name == "tube"  # normalized
        assert evt.action in ("merged", "blocked", "deferred")

    def test_entity_resolution_emits_merge_blocked(self):
        """resolve_entities emits merge_blocked when posterior is below threshold."""
        from kg_builder_cli.types.extraction import Entity

        signals.merge_blocked.connect(self._capture("merge_blocked"))

        # Use very different descriptions to ensure low posterior -> blocked
        entities = [
            Entity(
                id="comp_x", name="Widget", type="Component",
                description="A physical metal housing unit for motors",
            ),
            Entity(
                id="std_x", name="Widget", type="Standard",
                description="An ISO certification compliance framework",
            ),
        ]
        from kg_builder_cli.extraction.resolution import resolve_entities

        resolve_entities(entities, cross_type_merge_threshold=0.99)

        # With threshold 0.99, should be blocked
        assert len(self._captured["merge_blocked"]) >= 1
        evt = self._captured["merge_blocked"][0]
        assert evt.reason == "below_threshold"

    def test_deferred_dedup_emits_lifecycle_signals(self):
        """DeferredDedupBuffer emits resolution signals on resolve_all."""
        signals.deferred_pair_skipped.connect(self._capture("deferred_pair_skipped"))
        signals.deferred_resolution_completed.connect(
            self._capture("deferred_resolution_completed")
        )

        from kg_builder_cli.extraction.deferred_dedup import DeferredDedupBuffer
        from kg_builder_cli.types.extraction import Entity

        buf = DeferredDedupBuffer()
        e1 = Entity(id="c1", name="Tube", type="Component", description="tube component")
        e2 = Entity(id="a1", name="Tube", type="Accessory", description="tube accessory")
        buf.defer(e1, e2, 0.45, doc_index=0)

        decisions = buf.resolve_all()
        assert len(decisions) == 1

        assert len(self._captured["deferred_resolution_completed"]) == 1
        evt = self._captured["deferred_resolution_completed"][0]
        assert evt.pairs_resolved == 1

    def test_buffer_accumulate_emits_signals(self):
        """OntologyBuffer.accumulate_from_result emits ontology_signals_accumulated."""
        signals.ontology_signals_accumulated.connect(
            self._capture("ontology_signals_accumulated")
        )

        from kg_builder_cli.ontology.buffer import OntologyBuffer
        from kg_builder_cli.types.config import OntologyBufferConfig
        from kg_builder_cli.types.extraction import Entity, Relationship

        config = OntologyBufferConfig()
        buf = OntologyBuffer(config)
        entities = [
            Entity(id="p1", name="DreamStation", type="Product", description="CPAP device"),
        ]
        rels = [
            Relationship(
                source="p1", target="c1", type="HAS_COMPONENT", description="has component"
            ),
        ]
        buf.accumulate_from_result(entities, rels)

        assert len(self._captured["ontology_signals_accumulated"]) == 1
        evt = self._captured["ontology_signals_accumulated"][0]
        assert evt.total_entity_types >= 1

    def test_buffer_snapshot_emits_signal(self):
        """OntologyBuffer.snapshot emits buffer_snapshot_taken."""
        signals.buffer_snapshot_taken.connect(self._capture("buffer_snapshot_taken"))

        from kg_builder_cli.ontology.buffer import OntologyBuffer
        from kg_builder_cli.types.config import OntologyBufferConfig

        config = OntologyBufferConfig()
        buf = OntologyBuffer(config)
        buf.snapshot(resolution_intent="")

        assert len(self._captured["buffer_snapshot_taken"]) == 1

    def test_buffer_prune_emits_signal(self):
        """OntologyBuffer.prune_low_frequency_types emits buffer_types_pruned."""
        signals.buffer_types_pruned.connect(self._capture("buffer_types_pruned"))

        from kg_builder_cli.ontology.buffer import OntologyBuffer
        from kg_builder_cli.types.config import OntologyBufferConfig
        from kg_builder_cli.types.ontology import TypeSignal

        config = OntologyBufferConfig()
        buf = OntologyBuffer(config)
        # Add a dominant type and a rare type
        buf.accumulate([
            TypeSignal(type_name="Product", frequency=100),
            TypeSignal(type_name="RareType", frequency=1),
        ])

        pruned = buf.prune_low_frequency_types(threshold_pct=5.0)
        # RareType has 1 out of 101 total = ~1%, below 5% threshold
        assert "RareType" in pruned
        assert len(self._captured["buffer_types_pruned"]) == 1
        evt = self._captured["buffer_types_pruned"][0]
        assert "RareType" in evt.pruned_entity_types

    def test_stability_metrics_emits_recorded_signal(self):
        """StabilityMetrics.record emits stability_metrics_recorded."""
        signals.stability_metrics_recorded.connect(
            self._capture("stability_metrics_recorded")
        )

        from kg_builder_cli.curing.metrics import StabilityMetrics

        tracker = StabilityMetrics()
        tracker.record({"Product": 50, "Component": 30, "Feature": 20})

        assert len(self._captured["stability_metrics_recorded"]) == 1
        evt = self._captured["stability_metrics_recorded"][0]
        assert evt.type_count == 3
        assert evt.entity_count == 100

    def test_stability_snapshot_fires_every_5_docs(self):
        """stability_snapshot fires periodically every 5 documents."""
        signals.stability_snapshot.connect(self._capture("stability_snapshot"))
        signals.stability_metrics_recorded.connect(
            self._capture("stability_metrics_recorded")
        )

        from kg_builder_cli.curing.metrics import StabilityMetrics

        tracker = StabilityMetrics()
        for i in range(7):
            tracker.record({"Product": 50 + i, "Component": 30 + i})

        # Should fire at doc 5 (index 4, which is the 5th record)
        assert len(self._captured["stability_snapshot"]) == 1
        assert self._captured["stability_snapshot"][0].doc_index == 4

    def test_merge_validation_emits_failed_signal(self):
        """validate_type_clustering emits merge_validation_failed for flagged merges."""
        signals.merge_validation_failed.connect(
            self._capture("merge_validation_failed")
        )

        from kg_builder_cli.curing.merge_validation import validate_type_clustering
        from kg_builder_cli.types.extraction import Entity

        entities = [
            Entity(id="m1", name="Gas", type="Gas", description="a gas"),
            Entity(id="a1", name="Tube", type="Accessory", description="an accessory"),
        ]
        # Mapping with very different types should get flagged
        mapping = {"Gas": "Accessory"}
        freqs = {"Gas": 1, "Accessory": 50}

        result = validate_type_clustering(mapping, freqs, entities, threshold=0.9)

        if result.flagged_count > 0:
            assert len(self._captured["merge_validation_failed"]) >= 1

    def test_graph_validated_emits_from_validation(self):
        """validate_graph emits graph_validated signal.

        Uses a mock driver to avoid Neo4j dependency.
        """
        signals.graph_validated.connect(self._capture("graph_validated"))

        from unittest.mock import MagicMock

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        # Mock query results
        mock_session.run.side_effect = [
            iter([]),  # orphans
            MagicMock(single=MagicMock(return_value={"cnt": 50})),  # entity count
            MagicMock(single=MagicMock(return_value={"cnt": 100})),  # rel count
            iter([{"type": "Product", "cnt": 30}, {"type": "Component", "cnt": 20}]),  # types
            iter([{"type": "Product"}, {"type": "Component"}]),  # types with rels
        ]

        from kg_builder_cli.loading.validation import validate_graph
        from kg_builder_cli.types.config import AppConfig

        config = MagicMock(spec=AppConfig)
        report = validate_graph(config, driver=mock_driver)

        assert len(self._captured["graph_validated"]) == 1
        evt = self._captured["graph_validated"][0]
        assert evt.entity_count == 50
        assert evt.rel_count == 100

"""Named blinker Signal instances for the KGF pipeline event system.

One signal per event type, organized by category. All signals are synchronous.
"""

from blinker import Signal as _BlinkerSignal


class Signal(_BlinkerSignal):
    """Signal subclass that stores a name for event logging."""

    def __init__(self, name: str):
        super().__init__(name)
        self.name = name


# ── Pipeline phase (3) ──────────────────────────────────────────────
ingestion_started = Signal("ingestion-started")
phase_transition = Signal("phase-transition")
ingestion_completed = Signal("ingestion-completed")

# ── Extraction (4) ──────────────────────────────────────────────────
document_extraction_started = Signal("document-extraction-started")
document_extraction_completed = Signal("document-extraction-completed")
entity_resolution_completed = Signal("entity-resolution-completed")
type_enforcement_applied = Signal("type-enforcement-applied")

# ── Resolution decisions - Bayesian posterior (4) ───────────────────
cross_type_decision = Signal("cross-type-decision")
cross_type_pair_deferred = Signal("cross-type-pair-deferred")
deferred_evidence_updated = Signal("deferred-evidence-updated")
deferred_resolution_completed = Signal("deferred-resolution-completed")

# ── Ontology evolution (6) ──────────────────────────────────────────
ontology_signals_accumulated = Signal("ontology-signals-accumulated")
hierarchy_pair_qualifying = Signal("hierarchy-pair-qualifying")
hierarchy_evolved = Signal("hierarchy-evolved")
guide_rule_generated = Signal("guide-rule-generated")
ontology_evolved = Signal("ontology-evolved")
ontology_flushed = Signal("ontology-flushed")

# ── Stability metrics (2) ──────────────────────────────────────────
stability_metrics_recorded = Signal("stability-metrics-recorded")
stability_snapshot = Signal("stability-snapshot")

# ── Curing detection (6) ───────────────────────────────────────────
curing_check_performed = Signal("curing-check-performed")
curing_condition_blocked = Signal("curing-condition-blocked")
curing_triggered = Signal("curing-triggered")
drift_detected = Signal("drift-detected")
drift_check_passed = Signal("drift-check-passed")
patience_exceeded = Signal("patience-exceeded")

# ── LLM invocations (3) ────────────────────────────────────────────
llm_call_started = Signal("llm-call-started")
llm_call_completed = Signal("llm-call-completed")
llm_call_failed = Signal("llm-call-failed")

# ── Blocked/skipped decisions (5) ──────────────────────────────────
merge_blocked = Signal("merge-blocked")
merge_validation_failed = Signal("merge-validation-failed")
hierarchy_skipped = Signal("hierarchy-skipped")
guide_rule_skipped = Signal("guide-rule-skipped")
deferred_pair_skipped = Signal("deferred-pair-skipped")

# ── Buffer mutations (4) ───────────────────────────────────────────
buffer_types_pruned = Signal("buffer-types-pruned")
buffer_exemplars_updated = Signal("buffer-exemplars-updated")
buffer_snapshot_taken = Signal("buffer-snapshot-taken")
consolidation_completed = Signal("consolidation-completed")

# ── Loading (4) ────────────────────────────────────────────────────
graph_load_started = Signal("graph-load-started")
graph_load_completed = Signal("graph-load-completed")
graph_resolution_applied = Signal("graph-resolution-applied")
graph_validated = Signal("graph-validated")

# ── Calibration (4) ───────────────────────────────────────────────
type_metrics_computed = Signal("type-metrics-computed")
calibration_ground_truth = Signal("calibration-ground-truth")
calibration_fitted = Signal("calibration-fitted")
metric_correlation_computed = Signal("metric-correlation-computed")

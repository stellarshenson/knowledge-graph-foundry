"""Default and verbose event handlers for the KGF pipeline event system.

Handlers are plain functions connected to blinker signals via signal.connect().
Default handlers log key events at INFO level. Verbose handlers log full payloads
at DEBUG level for every event.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from . import signals
from .signals import Signal


def _log_event(sender, event=None, **kwargs):
    """Generic verbose handler that logs every event with its full payload."""
    event_name = getattr(sender, "name", str(sender))
    if event is not None:
        logger.debug("[event] {} | {}", event_name, event.model_dump_json())
    else:
        logger.debug("[event] {}", event_name)


def _on_ingestion_started(sender, event=None, **kwargs):
    if event:
        logger.info(
            "[event] ingestion started: {} files, mode={}, model={}",
            len(event.files),
            event.mode,
            event.model,
        )


def _on_ingestion_completed(sender, event=None, **kwargs):
    if event:
        logger.info(
            "[event] ingestion completed: {} docs, {} entities, {} rels",
            event.total_docs,
            event.total_entities,
            event.total_rels,
        )


def _on_phase_transition(sender, event=None, **kwargs):
    if event:
        logger.info(
            "[event] phase transition: {} -> {} (trigger={}, doc={})",
            event.from_phase,
            event.to_phase,
            event.trigger,
            event.doc_index,
        )


def _on_document_extraction_started(sender, event=None, **kwargs):
    if event:
        logger.info(
            "[event] extraction started: {} ({}/{}) [{}, {} chunks]",
            event.document_source,
            event.doc_index + 1,
            event.total_docs,
            event.phase,
            event.chunk_count,
        )


def _on_document_extraction_completed(sender, event=None, **kwargs):
    if event:
        logger.info(
            "[event] extraction done: {} ({}/{}) ({} entities, {} rels, {} remapped) [{}]",
            event.document_source,
            event.doc_index + 1,
            event.total_docs,
            event.entity_count,
            event.rel_count,
            event.remap_count,
            event.phase,
        )


def _on_curing_triggered(sender, event=None, **kwargs):
    if event:
        logger.info(
            "[event] curing triggered: {} at doc {} ({} docs, {} types)",
            event.trigger,
            event.doc_index,
            event.accumulated_docs,
            event.type_count,
        )


def _on_ontology_evolved(sender, event=None, **kwargs):
    if event:
        logger.info(
            "[event] ontology evolved: {} hierarchy changes, {} guide rules (trigger={})",
            event.hierarchy_changes,
            event.guide_rules_added,
            event.trigger,
        )


def _on_consolidation_completed(sender, event=None, **kwargs):
    if event:
        logger.info(
            "[event] consolidation: {} -> {} entities, {} -> {} rels, {} deferred resolved",
            event.entities_before,
            event.entities_after,
            event.rels_before,
            event.rels_after,
            event.deferred_resolved,
        )


def _on_graph_load_completed(sender, event=None, **kwargs):
    if event:
        logger.info(
            "[event] graph loaded: {} entities, {} rels in {}ms",
            event.entities_created,
            event.rels_created,
            event.duration_ms,
        )


def _on_graph_validated(sender, event=None, **kwargs):
    if event:
        logger.info(
            "[event] graph validated: {} entities, {} rels, {:.0%} type coverage, {} orphans",
            event.entity_count,
            event.rel_count,
            event.type_coverage,
            event.orphan_count,
        )


def _on_llm_call_failed(sender, event=None, **kwargs):
    if event:
        logger.warning(
            "[event] LLM call failed: {} ({}: {})",
            event.call_type,
            event.error_type,
            event.error_message,
        )


def _on_drift_detected(sender, event=None, **kwargs):
    if event:
        logger.warning(
            "[event] drift detected: remap_rate={:.0%}, {} consecutive docs, action={}",
            event.remap_rate,
            event.consecutive_docs,
            event.action,
        )


def _on_patience_exceeded(sender, event=None, **kwargs):
    if event:
        logger.info(
            "[event] patience exceeded: {} docs, max={}, trigger={}",
            event.docs_processed,
            event.max_patience,
            event.trigger,
        )


# Streaming event log writer
_event_log_path: Path | None = None
_event_log_count: int = 0


def _stream_event(sender, event=None, **kwargs):
    """Append each event as a JSONL line to the event log file."""
    global _event_log_count
    if event is None or _event_log_path is None:
        return
    import json

    line = json.dumps(
        {
            "signal": getattr(sender, "name", str(sender)),
            "payload": event.model_dump() if hasattr(event, "model_dump") else str(event),
        }
    )
    with open(_event_log_path, "a") as f:
        f.write(line + "\n")
    _event_log_count += 1


def get_event_log_count() -> int:
    """Return the number of events written to the log."""
    return _event_log_count


def clear_event_log() -> None:
    """Reset event log state."""
    global _event_log_path, _event_log_count
    _event_log_path = None
    _event_log_count = 0


def register_default_handlers() -> None:
    """Connect INFO-level log handlers for key pipeline events."""
    signals.ingestion_started.connect(_on_ingestion_started)
    signals.ingestion_completed.connect(_on_ingestion_completed)
    signals.phase_transition.connect(_on_phase_transition)
    signals.document_extraction_started.connect(_on_document_extraction_started)
    signals.document_extraction_completed.connect(_on_document_extraction_completed)
    signals.curing_triggered.connect(_on_curing_triggered)
    signals.ontology_evolved.connect(_on_ontology_evolved)
    signals.consolidation_completed.connect(_on_consolidation_completed)
    signals.graph_load_completed.connect(_on_graph_load_completed)
    signals.graph_validated.connect(_on_graph_validated)
    signals.llm_call_failed.connect(_on_llm_call_failed)
    signals.drift_detected.connect(_on_drift_detected)
    signals.patience_exceeded.connect(_on_patience_exceeded)


def register_verbose_handlers() -> None:
    """Connect DEBUG-level handlers that log full event payloads for every signal."""
    for name in dir(signals):
        obj = getattr(signals, name)
        if isinstance(obj, Signal) and not name.startswith("_"):
            obj.connect(_log_event)


def register_event_accumulator(log_path: Path) -> None:
    """Connect the streaming event writer to all signals, writing JSONL to log_path."""
    global _event_log_path
    _event_log_path = log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # Truncate file at start of run
    log_path.write_text("")
    for name in dir(signals):
        obj = getattr(signals, name)
        if isinstance(obj, Signal) and not name.startswith("_"):
            obj.connect(_stream_event)

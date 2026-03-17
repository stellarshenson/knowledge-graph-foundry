"""PipelineContext - the model object the FSM attaches to.

Tracks metanode properties, guard conditions, and transition callbacks.
The transitions library attaches state management via Machine mixin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from loguru import logger
from transitions import Machine

from kg_builder_cli.events.signals import phase_transition as phase_transition_signal
from kg_builder_cli.events.types import PhaseTransition
from kg_builder_cli.fsm.states import STATES, TRANSITIONS, GraphState


@dataclass
class PipelineContext:
    """Model object for the pipeline lifecycle FSM.

    The ``transitions`` library attaches ``state`` and trigger methods
    (``start_run``, ``begin_curing``, etc.) via :func:`create_fsm`.
    """

    # --- Metanode properties (persisted to :KGFControl in Neo4j) ---
    graph_id: str = field(default_factory=lambda: str(uuid4())[:8])
    run_id: str | None = None
    run_count: int = 0
    ontology_source: str | None = None
    extraction_mechanism: str | None = None
    consolidation_started_at: str | None = None
    ontology_type_count: int = 0
    ontology_hash: str | None = None
    created_at: str | None = None
    last_completed_at: str | None = None
    last_error: str | None = None

    # --- Runtime (not persisted to metanode) ---
    needs_calibration: bool = True
    drift_confirmed: bool = False
    _prev_state: str = GraphState.EMPTY

    # FSM state attribute - set by transitions library
    state: str = GraphState.EMPTY

    # --- Guard conditions ---

    def _needs_calibration(self) -> bool:
        return self.needs_calibration

    def _already_calibrated(self) -> bool:
        return not self.needs_calibration

    def _drift_exceeds_threshold(self) -> bool:
        return self.drift_confirmed

    # --- State entry callbacks ---

    def _on_enter_initializing(self) -> None:
        self._emit_transition("start_run")

    def _on_enter_curing(self) -> None:
        trigger = "begin_curing" if self._prev_state == GraphState.INITIALIZING else "authorize_revision"
        self._emit_transition(trigger)

    def _on_enter_stable(self) -> None:
        trigger = "begin_stable" if self._prev_state == GraphState.INITIALIZING else (
            "stabilize" if self._prev_state == GraphState.CURING else "dismiss_drift"
        )
        self._emit_transition(trigger)

    def _on_enter_recuring(self) -> None:
        self._emit_transition("detect_drift")

    def _on_enter_failed(self) -> None:
        self._emit_transition("fail")

    # --- Helpers ---

    def _emit_transition(self, trigger: str) -> None:
        """Emit phase_transition blinker signal and log."""
        from_state = self._prev_state
        to_state = self.state
        logger.info(
            "FSM transition: {} -> {} (trigger={})",
            from_state,
            to_state,
            trigger,
        )
        phase_transition_signal.send(
            phase_transition_signal,
            event=PhaseTransition(
                from_phase=from_state,
                to_phase=to_state,
                trigger=trigger,
                doc_index=0,
            ),
        )

    def begin_run(self) -> None:
        """Start a new ingestion run. Sets run_id and timestamps."""
        self.run_id = str(uuid4())[:12]
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def complete_run(self) -> None:
        """Finalize a completed run. Clears run_id, increments count."""
        self.run_id = None
        self.run_count += 1
        self.last_completed_at = datetime.now(timezone.utc).isoformat()

    def mark_consolidation_start(self) -> None:
        """Record that consolidation has begun (crash recovery marker)."""
        self.consolidation_started_at = datetime.now(timezone.utc).isoformat()

    def mark_consolidation_end(self) -> None:
        """Record that consolidation completed successfully."""
        self.consolidation_started_at = None

    def is_active_run(self) -> bool:
        """True if a run is currently in progress."""
        return self.run_id is not None

    def in_curing(self) -> bool:
        """True if FSM is in CURING state."""
        return self.state == GraphState.CURING

    def in_stable(self) -> bool:
        """True if FSM is in STABLE state."""
        return self.state == GraphState.STABLE


def create_fsm(
    initial_state: str = GraphState.EMPTY,
    **ctx_kwargs: Any,
) -> PipelineContext:
    """Create a PipelineContext with attached FSM.

    Parameters
    ----------
    initial_state:
        Starting state. EMPTY for new graphs, STABLE for existing.
    **ctx_kwargs:
        Passed to PipelineContext constructor (e.g. graph_id, run_count).

    Returns
    -------
    PipelineContext with ``state``, trigger methods, and callbacks attached.
    """
    ctx = PipelineContext(**ctx_kwargs)

    # Patch trigger methods to capture prev_state before transition
    Machine(
        model=ctx,
        states=STATES,
        transitions=TRANSITIONS,
        initial=initial_state,
        send_event=False,
        auto_transitions=False,
    )

    # Wrap each trigger to record prev_state
    for t_def in TRANSITIONS:
        trigger_name = t_def["trigger"]
        orig_fn = getattr(ctx, trigger_name)

        def _make_wrapper(name: str, fn: Any) -> Any:
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                ctx._prev_state = ctx.state
                return fn(*args, **kwargs)
            wrapper.__name__ = name
            return wrapper

        setattr(ctx, trigger_name, _make_wrapper(trigger_name, orig_fn))

    ctx._prev_state = initial_state
    return ctx

"""FSM state and transition definitions.

Six states tracking ontological maturity, matching KGF_DESIGN.md Section 14.1.
"""

from __future__ import annotations


class GraphState:
    """Constants for FSM state names."""

    EMPTY = "empty"
    INITIALIZING = "initializing"
    CURING = "curing"
    STABLE = "stable"
    RECURING = "recuring"
    FAILED = "failed"

    ALL = frozenset({EMPTY, INITIALIZING, CURING, STABLE, RECURING, FAILED})


STATES = [
    {"name": GraphState.EMPTY},
    {"name": GraphState.INITIALIZING, "on_enter": ["_on_enter_initializing"]},
    {"name": GraphState.CURING, "on_enter": ["_on_enter_curing"]},
    {"name": GraphState.STABLE, "on_enter": ["_on_enter_stable"]},
    {"name": GraphState.RECURING, "on_enter": ["_on_enter_recuring"]},
    {"name": GraphState.FAILED, "on_enter": ["_on_enter_failed"]},
]

TRANSITIONS = [
    {
        "trigger": "start_run",
        "source": [GraphState.EMPTY, GraphState.STABLE],
        "dest": GraphState.INITIALIZING,
    },
    {
        "trigger": "begin_curing",
        "source": GraphState.INITIALIZING,
        "dest": GraphState.CURING,
        "conditions": ["_needs_calibration"],
    },
    {
        "trigger": "begin_stable",
        "source": GraphState.INITIALIZING,
        "dest": GraphState.STABLE,
        "conditions": ["_already_calibrated"],
    },
    {
        "trigger": "stabilize",
        "source": GraphState.CURING,
        "dest": GraphState.STABLE,
    },
    {
        "trigger": "detect_drift",
        "source": GraphState.STABLE,
        "dest": GraphState.RECURING,
        "conditions": ["_drift_exceeds_threshold"],
    },
    {
        "trigger": "authorize_revision",
        "source": GraphState.RECURING,
        "dest": GraphState.CURING,
    },
    {
        "trigger": "dismiss_drift",
        "source": GraphState.RECURING,
        "dest": GraphState.STABLE,
    },
    {
        "trigger": "fail",
        "source": "*",
        "dest": GraphState.FAILED,
    },
]

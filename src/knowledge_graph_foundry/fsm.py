"""Lifecycle FSM for the foundry.

States: EMPTY -> INITIALIZING -> CURING -> STABLE <-> RECURING, plus FAILED.
The current state persists in the graph control metanode (graph/metanode.py);
this module owns only the machine and its legal transitions.
"""

from __future__ import annotations

from transitions import Machine, MachineError

from knowledge_graph_foundry.events import emit

STATES = ["EMPTY", "INITIALIZING", "CURING", "STABLE", "RECURING", "FAILED"]

TRANSITIONS = [
    {"trigger": "initialize", "source": "EMPTY", "dest": "INITIALIZING"},
    {"trigger": "start_curing", "source": "INITIALIZING", "dest": "CURING"},
    {"trigger": "cure", "source": ["CURING", "RECURING"], "dest": "STABLE"},
    {"trigger": "recure", "source": "STABLE", "dest": "RECURING"},
    {"trigger": "fail", "source": "*", "dest": "FAILED"},
    {"trigger": "recover", "source": "FAILED", "dest": "STABLE"},
]


class Lifecycle:
    """The foundry lifecycle machine. State restored via `restore(state)`."""

    def __init__(self, state: str = "EMPTY"):
        if state not in STATES:
            raise ValueError(f"unknown lifecycle state: {state}")
        self.machine = Machine(
            model=self,
            states=STATES,
            transitions=TRANSITIONS,
            initial=state,
            after_state_change=self._on_transition,
        )

    def _on_transition(self, *args: object, **kwargs: object) -> None:
        emit("fsm.transition", state=self.state)

    def can(self, trigger: str) -> bool:
        try:
            return bool(
                self.machine.get_triggers(self.state)
            ) and trigger in self.machine.get_triggers(self.state)
        except MachineError:
            return False

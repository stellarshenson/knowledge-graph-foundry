"""Tests for the lifecycle FSM."""

import pytest
from transitions import MachineError

from knowledge_graph_foundry.fsm import STATES, Lifecycle


class TestLifecycle:
    def test_happy_path(self):
        fsm = Lifecycle()
        assert fsm.state == "EMPTY"
        fsm.initialize()
        fsm.start_curing()
        fsm.cure()
        assert fsm.state == "STABLE"
        fsm.recure()
        assert fsm.state == "RECURING"
        fsm.cure()
        assert fsm.state == "STABLE"

    def test_illegal_transition_rejected(self):
        fsm = Lifecycle()
        with pytest.raises(MachineError):
            fsm.cure()

    def test_fail_from_any_state(self):
        for start in ("EMPTY", "CURING", "STABLE"):
            fsm = Lifecycle(start)
            fsm.fail()
            assert fsm.state == "FAILED"

    def test_restore_from_state(self):
        fsm = Lifecycle("STABLE")
        assert fsm.state == "STABLE"
        fsm.recure()
        assert fsm.state == "RECURING"

    def test_unknown_state_rejected(self):
        with pytest.raises(ValueError):
            Lifecycle("LIMBO")

    def test_all_states_declared(self):
        assert set(STATES) == {"EMPTY", "INITIALIZING", "CURING", "STABLE", "RECURING", "FAILED"}

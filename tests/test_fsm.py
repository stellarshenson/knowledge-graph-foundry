"""Tests for the pipeline lifecycle FSM."""

import pytest
from transitions import MachineError

from knowledge_graph_foundry.fsm.context import create_fsm
from knowledge_graph_foundry.fsm.states import GraphState


class TestFSMStateTransitions:
    """Test all legal state transitions from the 6-state model."""

    def test_initial_state_empty(self):
        ctx = create_fsm()
        assert ctx.state == GraphState.EMPTY

    def test_initial_state_stable(self):
        ctx = create_fsm(initial_state=GraphState.STABLE)
        assert ctx.state == GraphState.STABLE

    def test_empty_to_initializing(self):
        ctx = create_fsm()
        ctx.start_run()
        assert ctx.state == GraphState.INITIALIZING

    def test_stable_to_initializing(self):
        ctx = create_fsm(initial_state=GraphState.STABLE)
        ctx.start_run()
        assert ctx.state == GraphState.INITIALIZING

    def test_initializing_to_curing(self):
        ctx = create_fsm()
        ctx.needs_calibration = True
        ctx.start_run()
        ctx.begin_curing()
        assert ctx.state == GraphState.CURING

    def test_initializing_to_stable(self):
        ctx = create_fsm()
        ctx.needs_calibration = False
        ctx.start_run()
        ctx.begin_stable()
        assert ctx.state == GraphState.STABLE

    def test_curing_to_stable(self):
        ctx = create_fsm()
        ctx.needs_calibration = True
        ctx.start_run()
        ctx.begin_curing()
        ctx.stabilize()
        assert ctx.state == GraphState.STABLE

    def test_stable_to_recuring(self):
        ctx = create_fsm(initial_state=GraphState.STABLE)
        ctx.drift_confirmed = True
        ctx.detect_drift()
        assert ctx.state == GraphState.RECURING

    def test_recuring_to_curing(self):
        ctx = create_fsm(initial_state=GraphState.STABLE)
        ctx.drift_confirmed = True
        ctx.detect_drift()
        ctx.authorize_revision()
        assert ctx.state == GraphState.CURING

    def test_recuring_to_stable(self):
        ctx = create_fsm(initial_state=GraphState.STABLE)
        ctx.drift_confirmed = True
        ctx.detect_drift()
        ctx.dismiss_drift()
        assert ctx.state == GraphState.STABLE

    def test_fail_from_any_state(self):
        for initial in [GraphState.EMPTY, GraphState.INITIALIZING, GraphState.CURING, GraphState.STABLE]:
            if initial == GraphState.INITIALIZING:
                ctx = create_fsm()
                ctx.start_run()
            elif initial == GraphState.CURING:
                ctx = create_fsm()
                ctx.needs_calibration = True
                ctx.start_run()
                ctx.begin_curing()
            else:
                ctx = create_fsm(initial_state=initial)
            ctx.last_error = "test error"
            ctx.fail()
            assert ctx.state == GraphState.FAILED, f"fail from {initial}"


class TestFSMGuards:
    """Test guard conditions block transitions (state unchanged)."""

    def test_begin_curing_blocked_when_already_calibrated(self):
        ctx = create_fsm()
        ctx.needs_calibration = False
        ctx.start_run()
        ctx.begin_curing()  # guard returns False, no-op
        assert ctx.state == GraphState.INITIALIZING  # state unchanged

    def test_begin_stable_blocked_when_needs_calibration(self):
        ctx = create_fsm()
        ctx.needs_calibration = True
        ctx.start_run()
        ctx.begin_stable()  # guard returns False, no-op
        assert ctx.state == GraphState.INITIALIZING  # state unchanged

    def test_detect_drift_blocked_when_no_drift(self):
        ctx = create_fsm(initial_state=GraphState.STABLE)
        ctx.drift_confirmed = False
        ctx.detect_drift()  # guard returns False, no-op
        assert ctx.state == GraphState.STABLE  # state unchanged


class TestFSMIllegalTransitions:
    """Test that illegal transitions raise MachineError."""

    def test_empty_cannot_stabilize(self):
        ctx = create_fsm()
        with pytest.raises(MachineError):
            ctx.stabilize()

    def test_empty_cannot_detect_drift(self):
        ctx = create_fsm()
        ctx.drift_confirmed = True
        with pytest.raises(MachineError):
            ctx.detect_drift()

    def test_curing_cannot_start_run(self):
        ctx = create_fsm()
        ctx.needs_calibration = True
        ctx.start_run()
        ctx.begin_curing()
        with pytest.raises(MachineError):
            ctx.start_run()

    def test_recuring_cannot_stabilize(self):
        ctx = create_fsm(initial_state=GraphState.STABLE)
        ctx.drift_confirmed = True
        ctx.detect_drift()
        with pytest.raises(MachineError):
            ctx.stabilize()


class TestFSMFullLifecycle:
    """Test complete lifecycle scenarios matching the simulations."""

    def test_first_run_fluid_discovery(self):
        """sim-first-run-fluid-discovery: EMPTY -> INIT -> CURING -> STABLE"""
        ctx = create_fsm()
        ctx.needs_calibration = True
        ctx.extraction_mechanism = "fluid"

        ctx.start_run()
        assert ctx.state == GraphState.INITIALIZING

        ctx.begin_curing()
        assert ctx.state == GraphState.CURING

        ctx.stabilize()
        assert ctx.state == GraphState.STABLE

    def test_multi_run_drift_recuring(self):
        """sim-multi-run-drift-recuring: three runs with drift cycle."""
        # Run 1: EMPTY -> INIT -> CURING -> STABLE
        ctx = create_fsm()
        ctx.needs_calibration = True
        ctx.start_run()
        ctx.begin_curing()
        ctx.stabilize()
        ctx.complete_run()
        assert ctx.state == GraphState.STABLE
        assert ctx.run_count == 1

        # Run 2: STABLE -> INIT -> STABLE (already calibrated)
        ctx.needs_calibration = False
        ctx.start_run()
        ctx.begin_stable()
        ctx.complete_run()
        assert ctx.state == GraphState.STABLE
        assert ctx.run_count == 2

        # Run 3: STABLE -> INIT -> STABLE -> RECURING -> CURING -> STABLE
        ctx.needs_calibration = False
        ctx.start_run()
        ctx.begin_stable()
        # Drift detected mid-run
        ctx.drift_confirmed = True
        ctx.detect_drift()
        assert ctx.state == GraphState.RECURING
        ctx.authorize_revision()
        assert ctx.state == GraphState.CURING
        ctx.stabilize()
        assert ctx.state == GraphState.STABLE
        ctx.complete_run()
        assert ctx.run_count == 3

    def test_strict_seed_direct_curing(self):
        """sim-strict-seed: strict seed still goes through CURING."""
        ctx = create_fsm()
        ctx.needs_calibration = True
        ctx.extraction_mechanism = "direct"
        ctx.ontology_source = "seed"

        ctx.start_run()
        ctx.begin_curing()
        assert ctx.state == GraphState.CURING

        ctx.stabilize()
        assert ctx.state == GraphState.STABLE
        assert ctx.extraction_mechanism == "direct"
        assert ctx.ontology_source == "seed"

    def test_drift_dismissed(self):
        """Drift detected but evaluated as synonyms - dismiss back to STABLE."""
        ctx = create_fsm(initial_state=GraphState.STABLE)
        ctx.drift_confirmed = True
        ctx.detect_drift()
        assert ctx.state == GraphState.RECURING

        ctx.dismiss_drift()
        assert ctx.state == GraphState.STABLE


class TestPipelineContextHelpers:
    """Test context helper methods."""

    def test_begin_run(self):
        ctx = create_fsm()
        ctx.begin_run()
        assert ctx.run_id is not None
        assert ctx.created_at is not None

    def test_complete_run(self):
        ctx = create_fsm()
        ctx.begin_run()
        ctx.complete_run()
        assert ctx.run_id is None
        assert ctx.run_count == 1
        assert ctx.last_completed_at is not None

    def test_consolidation_markers(self):
        ctx = create_fsm()
        assert ctx.consolidation_started_at is None
        ctx.mark_consolidation_start()
        assert ctx.consolidation_started_at is not None
        ctx.mark_consolidation_end()
        assert ctx.consolidation_started_at is None

    def test_is_active_run(self):
        ctx = create_fsm()
        assert not ctx.is_active_run()
        ctx.begin_run()
        assert ctx.is_active_run()
        ctx.complete_run()
        assert not ctx.is_active_run()

    def test_state_predicates(self):
        ctx = create_fsm()
        ctx.needs_calibration = True
        assert not ctx.in_curing()
        assert not ctx.in_stable()

        ctx.start_run()
        ctx.begin_curing()
        assert ctx.in_curing()
        assert not ctx.in_stable()

        ctx.stabilize()
        assert not ctx.in_curing()
        assert ctx.in_stable()

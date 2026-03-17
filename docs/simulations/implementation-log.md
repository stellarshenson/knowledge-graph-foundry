# FSM Implementation Log

## Checklist

### Phase 1: FSM Core Module
- [x] Create `kg_builder_cli/fsm/` package
- [x] `kg_builder_cli/fsm/states.py` - state and transition definitions (6 states, 8 transitions)
- [x] `kg_builder_cli/fsm/context.py` - PipelineContext model with guards and callbacks
- [x] `kg_builder_cli/fsm/metanode.py` - KGFControl Neo4j CRUD operations
- [x] `kg_builder_cli/fsm/__init__.py` - public API
- [x] Unit tests for FSM state transitions (22 tests)
- [x] Unit tests for guard conditions (3 tests)
- [x] Unit tests for metanode operations (12 tests, mocked Neo4j)

### Phase 2: CLI Integration
- [x] Modify `cli.py` to instantiate FSM at ingestion start (`_init_fsm`)
- [x] Graph state detection during INITIALIZING (query KGFControl metanode via `detect_graph_state`)
- [x] Wire curing triggers to FSM `stabilize` transition
- [x] Consolidation crash recovery markers (`consolidation_started_at`)
- [x] Run lifecycle: create KGFRun node at start, complete at end
- [x] Phase transition events emitted by FSM `on_enter_*` callbacks
- [x] Metanode updates at each transition point (`_update_metanode_safe`)
- [ ] Wire drift detection to FSM `detect_drift` / `authorize_revision` / `dismiss_drift`
- [ ] KGFTransition audit trail nodes written on each transition

### Phase 3: Testing and Verification
- [x] All existing tests pass (420/420, 2.94s)
- [x] Lint clean (ruff)
- [ ] Manual verification: first run on empty graph creates KGFControl metanode
- [ ] Manual verification: subsequent run detects existing graph state
- [ ] Benchmark run (v27) with standard CPAP corpus
- [ ] Benchmark score >= v26 baseline (87%)

### Phase 4: Iteration
- [ ] Fix any test failures
- [ ] Fix any benchmark regressions
- [ ] Re-run and verify

## Implementation Log

### Entry 1: Planning

**Strategy**: incremental integration. Build the FSM module as a standalone package first, then wire it into cli.py with minimal disruption to existing logic. The FSM wraps the existing boolean `cured` flag and phase tracking - it does not replace the underlying curing/accumulator/detector logic.

**Key design decisions**:
- FSM is opt-in: if Neo4j connection fails at startup, fall back to existing behavior (fsm_ctx=None)
- KGFControl metanode created/updated via `_update_metanode_safe()` which swallows errors
- The `transitions` library Machine attaches to a PipelineContext dataclass via mixin
- Guards are simple boolean properties set by the pipeline (not reading detector state directly)
- `on_enter_*` callbacks emit existing `phase_transition` blinker signals

### Entry 2: Phase 1 Complete - FSM Core Module

Created `kg_builder_cli/fsm/` package with 4 files:

- `states.py`: 6 states (EMPTY, INITIALIZING, CURING, STABLE, RECURING, FAILED), 8 transitions matching KGF_DESIGN.md Section 14.2. `GraphState` constants class for type-safe state references.
- `context.py`: `PipelineContext` dataclass with all metanode properties, guard methods (`_needs_calibration`, `_already_calibrated`, `_drift_exceeds_threshold`), state entry callbacks that emit blinker signals, and helper methods (`begin_run`, `complete_run`, `mark_consolidation_start/end`). `create_fsm()` factory attaches the `transitions` Machine and wraps triggers to capture `_prev_state`.
- `metanode.py`: Full CRUD for `(:KGFControl)` metanode plus `(:KGFRun)` and `(:KGFTransition)` nodes. `detect_graph_state()` implements the Section 14.3 detection algorithm (check metanode, then entity count, then empty).
- `__init__.py`: Clean public API surface.

37 tests pass (22 state transitions, 3 guards, 4 illegal transitions, 4 full lifecycle scenarios matching the 3 simulation documents, 4 helper method tests, plus 12 metanode tests with mocked Neo4j).

Key finding: `transitions` library returns False on guard failure instead of raising MachineError. Tests adapted to verify state unchanged rather than expecting exception.

Naming collision: `is_curing()`/`is_stable()` conflict with auto-generated `transitions` methods. Renamed to `in_curing()`/`in_stable()`.

### Entry 3: Phase 2 - CLI Integration

Added FSM integration to `cli.py` with minimal disruption:

- `_init_fsm(config, curing_enabled, has_seed)`: detects graph state, creates FSM context, transitions through EMPTY/STABLE -> INITIALIZING -> CURING/STABLE. Returns None on failure (pipeline proceeds without FSM).
- `_update_metanode_safe(config, ctx)`: writes FSM context to KGFControl metanode. Swallows exceptions - non-critical.
- Added `fsm_ctx` parameter to `_ingest_fluid()` (keyword-only, default None).
- Wired FSM hooks at 3 points:
  1. **Ingestion start**: `_init_fsm()` creates context, detects graph state, writes metanode and KGFRun node
  2. **Consolidation**: `mark_consolidation_start()` before type clustering, `mark_consolidation_end()` + `stabilize()` after flush
  3. **Run completion**: `complete_run()` sets run_id=null, increments run_count

All 420 tests pass, lint clean. The FSM is backward-compatible - if Neo4j is unavailable at detection time, `_init_fsm` returns None and the pipeline runs exactly as before.

**Remaining Phase 2 work**: drift detection FSM hooks and KGFTransition audit trail nodes. These are lower priority - the core lifecycle (EMPTY -> CURING -> STABLE across runs) is functional.

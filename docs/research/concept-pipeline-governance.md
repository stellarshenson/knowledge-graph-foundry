# Pipeline Governance: FSM Lifecycle and Graph Control Plane

## Finite State Machine

The KGF pipeline is inherently stateful - it transitions through discovery, stabilization, drift monitoring, and recovery phases. Without an explicit finite state machine, this lifecycle logic leaks into conditionals, handlers, escalation code, and event subscribers, creating hidden complexity.

The FSM formalizes what the system already does implicitly. A lean state set for v1:

- **INITIALIZING** - setup, configuration loading, Neo4j connectivity
- **FLUID** - ontology discovery phase, types emerging from data
- **CURING** - ontology stabilization triggered by convergence metrics
- **CURED** - stable extraction with drift monitoring active
- **RECURING** - re-stabilization triggered by sustained drift
- **FAILED** - unrecoverable error requiring operator attention
- **COMPLETED** - pipeline finished successfully

Each state defines entry conditions, allowed outgoing transitions, key actions, and emitted events. This prevents illegal transitions (INITIALIZING cannot jump to RECURING) and anchors the event architecture to concrete state changes rather than ad-hoc signals.

Events should report transitions or facts around state, not invent state. With an FSM, events like `curing_triggered`, `phase_transition`, `recuring_requested`, and `recuring_completed` all reference defined states and transitions rather than existing in isolation. Recuring is not a normal mutation - it is a phase change in graph governance. The FSM makes this explicit by modeling recuring as a distinct state with its own entry conditions, allowed exits, and emitted events.

Most KG builders have no concept of pipeline lifecycle governance. They run extraction and stop. The FSM enables resume, recovery, and multi-process coordination.

## Graph Metanode Control Plane

The authoritative runtime state should live in the graph itself as a control metanode, not on the local filesystem. The graph is the governed resource, so the governance state belongs with it.

A `(:KGFControl)` metanode stores: `graph_id`, `fsm_state`, `run_id`, `phase_started_at`, `phase_updated_at`, `pending_transition`, `lock_owner`, `lock_acquired_at`, `lock_expires_at`, `status`, `last_error`, `last_completed_run_id`. Related nodes for history: `(:KGFRun)` per ingestion run, `(:KGFTransition)` for state change audit trail. The control node stays small and current while history is append-only.

Filesystem state can be stale, belong to a different machine, go missing, or drift out of sync. With the metanode, any KGF process can inspect current phase, lock owner, pending transition, and recovery state through a single Cypher query. This enables multi-process coordination without shared filesystem assumptions.

**Lease-style locking**: The lock must not be eternal. Dead processes must not freeze the system. Lock acquisition is one atomic graph write that succeeds only if no active lock exists or the existing lock has expired. Long-running operations extend the lease via heartbeat renewal. Clear recovery rules let the next process inspect stale locks and decide whether to resume, roll back, or re-enter recuring.

**Split responsibility**: Graph metanode holds authoritative control-plane state (FSM, lock, active run, recovery). Local filesystem holds non-authoritative artifacts (logs, benchmark outputs, event dumps, debug snapshots). This transforms KGF from a pipeline into a self-governing graph construction system where the graph becomes its own control plane.

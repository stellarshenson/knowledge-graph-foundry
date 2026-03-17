# Simulation: Strict Seed with Crash Recovery

## Scenario

Two sub-scenarios in one run. First, a strict ontology seed is provided on an empty graph - testing the CURING state with direct extraction mechanism. Second, the process crashes mid-consolidation and a new process recovers from the metanode.

## Initial Conditions

- Graph: empty
- Ontology seed: `ontology.yml` with 8 prescribed types (Patient, Provider, Device, Medication, Procedure, Diagnosis, Facility, InsurancePlan)
- Config: `ontology.strict: true`
- Corpus: 15 healthcare administration documents

## Part 1: Strict Seed on Empty Graph

### EMPTY -> INITIALIZING

Trigger: `start_run`.

Detection algorithm: no `(:KGFControl)` metanode, no entity nodes. Graph is EMPTY. Metanode created.

### INITIALIZING -> CURING (not STABLE)

Trigger: `begin_curing` (guard `_needs_calibration` returns true - first run, no prior calibration).

This is the key design decision being validated. Even though 8 types are prescribed and `strict: true` prevents discovery, the system enters CURING because the graph needs calibration. The types exist on paper but the system has never seen real entities of these types. Bayesian posteriors are at their uninformed priors. Resolution guides are empty. Cross-type evidence is zero.

The extraction mechanism is set to `direct` - the LLM will enforce the 8 prescribed types, no new types can emerge. But within CURING, the system is calibrating:
- How often do Patient and Provider entities co-occur? (co-occurrence prior for resolution)
- What does a typical Medication entity look like vs a Procedure? (description similarity baselines)
- Which type pairs are commonly ambiguous? (resolution guide seeds)
- What is the embedding distribution for each type? (exemplar index foundations)

### CURING (documents 1-8)

**Documents 1-3**: extracted with strict type enforcement. All entities assigned to one of the 8 prescribed types. No new types (direct mechanism prevents it). But calibration is happening silently:
- Bayesian posteriors for Patient/Provider resolution: prior was 0.5 (uninformed), now adjusting based on description similarity evidence
- Resolution guide for Device/Medication: 3 ambiguous pairs encountered (e.g., "insulin pump" - Device or Medication delivery system?)
- Exemplar index: 45 entities providing type-specific embedding centroids

**Documents 4-6**: calibration metrics converging. Posterior variance dropping (the system is becoming more confident in its type assignments). Resolution guide has accumulated enough encounters to produce stable rules for the Device/Medication and Procedure/Diagnosis pairs.

**Documents 7-8**: calibration thresholds met. Posterior variance below stability threshold for 2 consecutive documents. Resolution guide coverage > 80% of observed type pairs. The ontology is not just prescribed - it is empirically grounded.

### CURING -> STABLE

Trigger: `stabilize`.

Consolidation runs: type clustering is a no-op (types were prescribed, no merging needed), but the ontology snapshot is frozen with calibrated posteriors, resolution guides are persisted, and exemplar index is built. Batch flush writes 8 documents of entities to Neo4j.

Metanode updates: `fsm_state: stable`, `ontology_source: seed`, `extraction_mechanism: direct`, `ontology_type_count: 8`.

### STABLE (documents 9-12)

Type-enforced extraction with calibrated posteriors. Drift monitored. Remap rate stays low (3-5%). Documents load cleanly.

## Part 2: Crash During Consolidation

### Setup for crash scenario

Imagine the process crashes at a different point in the timeline. Rewind to document 8, where calibration converges and consolidation begins.

### Crash During CURING Consolidation

The system is in CURING state. Convergence is detected. Consolidation begins:

1. `consolidation_started_at` is set on the metanode (**written to Neo4j**)
2. Type clustering LLM call succeeds (no-op for strict seed)
3. Ontology snapshot frozen in memory
4. Batch flush begins writing entities to Neo4j
5. **CRASH** - process killed mid-flush (e.g., OOM, network partition, pod eviction)

The metanode in Neo4j reads:
```
fsm_state: curing
run_id: run-003
consolidation_started_at: 2026-03-17T11:45:22Z
last_error: null
```

The graph has partial data: some entities from the batch flush were written, others were not. The ontology snapshot exists in the metanode's `consolidation_started_at` but was never completed (no `stabilize` transition fired).

### Recovery: New Process Connects

A new KGF process starts. It connects to Neo4j and reads the `(:KGFControl)` metanode.

**Detection**: `fsm_state: curing`, `consolidation_started_at: 2026-03-17T11:45:22Z` (non-null). This tells the recovery process:
- The graph was mid-consolidation when the previous process died
- The graph is in a partially-flushed state
- The system should NOT continue fluid extraction (CURING does not mean "still discovering")
- The system should NOT enter STABLE (consolidation did not complete)

**Recovery options** (presented to operator or decided by config):

1. **Retry consolidation**: roll back the partial flush (delete entities written after `consolidation_started_at`), re-run consolidation from the FluidAccumulator snapshot. This requires the accumulator state to be recoverable - which it is, from the graph's existing entities minus the partial flush
2. **Force-stabilize**: accept the partial flush as-is, mark the run as degraded, transition to STABLE. Some entities may be missing but the ontology is intact
3. **Fail**: transition to FAILED, require manual intervention

The key point: **the metanode told the recovery process exactly what happened.** Without `consolidation_started_at`, the recovery process would see `fsm_state: curing` and not know whether the system was still discovering types (safe to continue) or mid-consolidation (graph is corrupted). This is why `consolidation_started_at` exists as a metanode property - it disambiguates within the CURING state without requiring a separate CONSOLIDATING FSM state.

### Recovery Transition Log

| # | From | To | Trigger | Detail |
|---|------|-----|---------|--------|
| 1 | CURING | STABLE | `stabilize` | recovery: retry consolidation succeeded |

Or, if recovery fails:

| # | From | To | Trigger | Detail |
|---|------|-----|---------|--------|
| 1 | CURING | FAILED | `fail` | recovery: consolidation retry failed, manual intervention |

## Combined Transition Log (Happy Path)

| # | From | To | Trigger | Detail |
|---|------|-----|---------|--------|
| 1 | EMPTY | INITIALIZING | `start_run` | strict seed, 8 prescribed types |
| 2 | INITIALIZING | CURING | `begin_curing` | mechanism=direct, seed=ontology.yml |
| 3 | CURING | STABLE | `stabilize` | calibration converged at doc 8, 8 types |

## Final Metanode State (Happy Path)

```
graph_id: c4d5e6f7
fsm_state: stable
run_id: null
run_count: 1
ontology_source: seed
extraction_mechanism: direct
consolidation_started_at: null
ontology_type_count: 8
ontology_hash: 9a8b7c6d
last_completed_at: 2026-03-17T12:00:00Z
last_error: null
```

## Observations

1. **Strict seed still goes through CURING.** This validates the design decision that CURING means "ontology calibration" not "type discovery." The 8 types were known from the start, but the graph needed 8 documents of real entities to calibrate posteriors, build resolution guides, and establish embedding baselines. A graph with prescribed types but zero evidence is not stable
2. **Direct mechanism within CURING worked cleanly.** No FluidAccumulator type discovery, no convergence metrics based on type emergence. Instead, calibration metrics (posterior variance, guide coverage) drove the CURING -> STABLE transition. The FSM state was the same (CURING) but the internal behavior adapted to the mechanism
3. **`consolidation_started_at` provided crash recovery without a separate state.** The alternative (a CONSOLIDATING FSM state between CURING and STABLE) would add a 7th state for a condition that lasts seconds and exists purely for failure recovery. The metanode property achieves the same visibility at lower FSM complexity. The recovery process reads `fsm_state: curing` + `consolidation_started_at: <timestamp>` and knows "this was mid-consolidation, not mid-discovery"
4. **STABLE absorbed the idle state correctly.** After run completion, the graph sits in STABLE with `run_id: null`. A subsequent `kgf ingest` would trigger `start_run` from STABLE, read the metanode, see `ontology_source: seed` and `ontology_type_count: 8`, and enter STABLE directly (guard `_already_calibrated` = true). The strict seed ontology persists across runs via the graph
5. **The 6-state model handled a scenario that previous iterations needed 10 states for.** The original plan had EMPTY -> INITIALIZING -> DIRECT -> COMPLETED -> READY for this scenario (5 states touched). The current model uses EMPTY -> INITIALIZING -> CURING -> STABLE (4 states touched), and the CURING state is richer because it acknowledges that calibration matters even with prescribed types
6. **Crash recovery is the strongest validation of graph-as-control-plane.** The crashed process left no local state. No `.kgf/` files needed. The new process connected to Neo4j, read one metanode, and knew the full situation. This is the core design principle: recovery requires only `config.yml` + graph connection

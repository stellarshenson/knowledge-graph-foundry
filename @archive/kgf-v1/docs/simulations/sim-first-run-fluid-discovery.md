# Simulation: First Run - Fluid Ontology Discovery

## Scenario

A 10-document medical device corpus (CPAP machines, masks, humidifiers) is ingested for the first time into an empty Neo4j database. No ontology seed is provided. The pipeline runs with `kgf ingest data/raw/ --batch --fluid`.

## Initial Conditions

- Graph: empty, no `(:KGFControl)` metanode
- Ontology seed: none
- Config: `curing.enabled: true`, `curing.min_documents: 3`, `curing.max_fluid_documents: 20`
- Resolution intent: "compare medical devices across manufacturers"

## State Trace

### EMPTY

The graph database contains no nodes, no relationships, no control plane. This is the starting condition for any fresh Neo4j instance.

### EMPTY -> INITIALIZING

Trigger: `start_run` (user invokes `kgf ingest`).

The pipeline loads `config.yml`, verifies Neo4j connectivity, and runs the detection algorithm from Section 14.3. No `(:KGFControl)` metanode exists. No entity nodes found. Conclusion: graph is EMPTY. A new `(:KGFControl)` metanode is created with `graph_id`, `fsm_state: initializing`, `run_id: <uuid>`, `run_count: 0`.

### INITIALIZING -> CURING

Trigger: `begin_curing` (guard `_needs_calibration` returns true - first run, no existing ontology).

No ontology seed was provided, so `extraction_mechanism` is set to `fluid`. The FluidAccumulator is initialized. The ontology buffer starts empty with only the resolution intent loaded. The metanode updates to `fsm_state: curing`, `extraction_mechanism: fluid`.

### CURING (documents 1-4)

**Document 1** (ResMed AirSense 11 datasheet): LLM extracts freely against the resolution intent. Types emerge: Device, Manufacturer, Specification, Standard, Component. 47 entities, 82 relationships accumulated in FluidAccumulator. Convergence check: JSD undefined (first document), Chao1 = 0.42 (low coverage estimate). No curing - too early.

**Document 2** (Fisher & Paykel SleepStyle manual): 2 new types emerge: Material, Certification. Running total: 7 types, 89 entities, 156 relationships. JSD = 0.31 (high divergence from doc 1 distribution). Chao1 = 0.58. Still discovering.

**Document 3** (ResMed mask accessories brochure): 0 new types. All entities map to existing types. 112 entities cumulative. JSD drops to 0.04. Entropy delta = 0.02. Chao1 = 0.78. Convergence metrics improving but `min_documents` = 3 just met, stability window not yet satisfied.

**Document 4** (Philips DreamStation spec sheet): 0 new types for 2 consecutive documents. JSD = 0.008 (below 0.01 threshold for 2 docs). Entropy delta = 0.01. Type accumulation rate = 0. Chao1 = 0.82. **Convergence detected** via `is_converged()` - strictest path.

### CURING -> STABLE

Trigger: `stabilize` (convergence detected).

Consolidation runs within CURING as the exit action:

1. `consolidation_started_at` set on the metanode
2. LLM-assisted type clustering call: Material merges into Component (semantic overlap in this domain), leaving 6 canonical types
3. Ontology snapshot frozen: Device, Manufacturer, Specification, Standard, Component, Certification
4. FluidAccumulator consolidates 4 documents of results: deduplication, entity resolution, type enforcement via Levenshtein mapping
5. Batch flush: 98 merged entities and 203 relationships written to Neo4j
6. Exemplar index built for Bayesian cross-type resolution
7. `consolidation_started_at` cleared

Metanode updates: `fsm_state: stable`, `ontology_source: discovered`, `ontology_type_count: 6`, `ontology_hash: <sha256>`.

### STABLE (documents 5-10)

Documents are now extracted with type enforcement against the frozen 6-type ontology. Each document loads directly to Neo4j per-document (no accumulation).

**Documents 5-8**: clean extraction. Entities map to existing types. Remap rate stays below 5%. Drift monitoring sees no anomalies. Bayesian posteriors calibrate further with each document - resolution guides for Device/Component and Specification/Standard pairs build up encounter evidence.

**Document 9**: a mask compatibility guide introduces "Mode" entities (CPAP, BiPAP, AutoSet). These get remapped to the closest existing type (Specification) with remap rate spiking to 12%. Below the 30% drift threshold. Drift check passes.

**Document 10**: similar remap patterns. Remap rate = 8%. Below threshold. Drift dismissed implicitly (no RECURING entered).

Run completes: `run_id` set to null, `run_count` incremented to 1, `last_completed_at` recorded. Graph remains in STABLE (idle).

## Final Metanode State

```
graph_id: f8a2c3d1
fsm_state: stable
run_id: null
run_count: 1
ontology_source: discovered
extraction_mechanism: fluid
consolidation_started_at: null
ontology_type_count: 6
ontology_hash: 7b3e91a4
last_completed_at: 2026-03-17T10:05:00Z
last_error: null
```

## Transition Log

| # | From | To | Trigger | Detail |
|---|------|-----|---------|--------|
| 1 | EMPTY | INITIALIZING | `start_run` | first kgf ingest, run_id assigned |
| 2 | INITIALIZING | CURING | `begin_curing` | mechanism=fluid, no seed |
| 3 | CURING | STABLE | `stabilize` | convergence at doc 4, 6 types frozen |

## Observations

1. **3 transitions for a complete first run.** The FSM is minimal - it captures the ontology lifecycle without cluttering the audit trail with per-document noise. Per-document events go to the blinker event log, not the FSM
2. **CURING encompassed both discovery and consolidation.** Documents 1-4 were all within CURING state. The convergence check and consolidation flush happened as activities within CURING, not as separate states. The `consolidation_started_at` metanode property provided crash recovery visibility without needing a CONSOLIDATING state
3. **STABLE absorbed both active extraction and run completion.** Documents 5-10 processed in STABLE, and the run finalized in STABLE (setting `run_id` to null). No separate COMPLETED or READY state needed
4. **Drift monitoring was passive in STABLE.** Remap rate spikes (doc 9: 12%) were evaluated but below threshold. No RECURING entered. The FSM stayed in STABLE throughout. If we had a separate DIRECT state, it would have been indistinguishable from STABLE here
5. **The resolution intent drove extraction quality from document 1.** Without it, the LLM would have invented ad-hoc types. The intent constrained the hypothesis space so even the first document produced domain-appropriate types (Device, Manufacturer, Specification rather than Thing, Object, Property)

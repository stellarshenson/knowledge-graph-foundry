# Simulation: Multi-Run with Drift and Recuring

## Scenario

Three ingestion runs against the same Neo4j graph. Run 1 establishes the ontology from medical device documents. Run 2 adds more documents from the same domain (no drift). Run 3 introduces documents from an adjacent domain (home care equipment) that triggers drift detection and the RECURING deliberation.

## Initial Conditions (Run 1 already completed)

The graph is in STABLE state after Run 1 (see `sim-first-run-fluid-discovery.md`). The ontology has 6 types: Device, Manufacturer, Specification, Standard, Component, Certification. Run count = 1.

```
fsm_state: stable
run_id: null
run_count: 1
ontology_source: discovered
ontology_type_count: 6
```

## Run 2: Same Domain, No Drift

### STABLE -> INITIALIZING

Trigger: `start_run` (user invokes `kgf ingest data/batch2/ --batch`).

The pipeline loads config, connects to Neo4j, queries the `(:KGFControl)` metanode. Reads `fsm_state: stable`, `run_count: 1`, `ontology_type_count: 6`. Graph is not empty and has a calibrated ontology. `run_id` set to new uuid.

### INITIALIZING -> STABLE

Trigger: `begin_stable` (guard `_already_calibrated` returns true - graph has existing ontology, no new seed provided).

The existing ontology is loaded from the graph's `(:OntologyType)` nodes. No FluidAccumulator initialized. The system enters STABLE directly and begins processing documents with type enforcement.

### STABLE (documents 1-5)

All 5 documents are from the same medical device domain. Entities map cleanly to the existing 6 types. Remap rate stays at 2-4%. Bayesian posteriors strengthen further. Resolution guides add more encounter evidence for common type pairs. No drift detected.

Run completes: `run_id` set to null, `run_count` = 2.

### Run 2 Transition Log

| # | From | To | Trigger | Detail |
|---|------|-----|---------|--------|
| 1 | STABLE | INITIALIZING | `start_run` | run 2, same domain |
| 2 | INITIALIZING | STABLE | `begin_stable` | graph calibrated, 6 types loaded |

**2 transitions.** The most efficient path - the graph was already calibrated, no curing needed.

## Run 3: Adjacent Domain with Drift

### STABLE -> INITIALIZING

Trigger: `start_run` (user invokes `kgf ingest data/homecare/ --batch`).

Same detection: metanode exists, `fsm_state: stable`, `run_count: 2`. No new seed. Guard `_already_calibrated` = true.

### INITIALIZING -> STABLE

Trigger: `begin_stable`. System enters STABLE with existing 6-type ontology.

### STABLE (documents 1-2)

**Document 1** (wheelchair mobility aid spec): mostly fits existing types. Device, Manufacturer, Specification work. Some entities get remapped - "Mobility Aid" forced to Device, "Safety Rating" forced to Certification. Remap rate = 15%. Below 30% threshold but notable.

**Document 2** (home oxygen concentrator manual): similar remapping. "Flow Rate Setting" forced to Specification, "Therapy Mode" forced to Specification. Remap rate = 18%. Still below threshold. Drift check passes.

### STABLE (document 3) -> RECURING

**Document 3** (home care product comparison guide): this document spans multiple product categories. The LLM encounters types that genuinely do not fit the existing ontology: "Therapy" (a treatment protocol, not a device or spec), "Condition" (a medical condition the device treats), "Accessory" (distinct from Component - an optional add-on vs integral part). Remap rate spikes to 35%. Three distinct type gaps identified.

Trigger: `detect_drift` (guard `_drift_exceeds_threshold` returns true - remap rate 0.35 >= 0.30).

The system enters RECURING. The current ontology state is snapshot for comparison. The metanode updates to `fsm_state: recuring`.

### RECURING Deliberation

The system evaluates whether the drift represents genuine ontology gaps or surface-level synonyms.

**Evidence gathered**:
- 3 distinct unmapped type clusters: Therapy (8 entities across 2 docs), Condition (5 entities), Accessory (12 entities)
- Remap rate sustained above 30% for 1 document (threshold is sustained, not spike)
- The unmapped types are semantically distinct from existing types - "Therapy" is not a Device or Specification, it is a treatment protocol
- Resolution guides show no prior evidence for Therapy/Device or Condition/Specification pairs

**LLM advisory** (if generative curing enabled): receives the remap history, the 3 candidate types with entity examples, and the existing ontology. Decision: **authorize revision** - these are genuine ontology gaps, not synonyms. "Therapy" and "Condition" represent new domain facets from the adjacent home care domain. "Accessory" disambiguates from "Component" which has established semantics in the graph.

### RECURING -> CURING

Trigger: `authorize_revision`.

The FluidAccumulator is reset. The existing 6 types are pre-loaded as priors (they are established and should persist). The extraction mechanism is set to `fluid` because the system needs to discover how many new types the adjacent domain introduces. The metanode updates to `fsm_state: curing`, `extraction_mechanism: fluid`.

### CURING (documents 3-5, re-processed)

Document 3 is re-extracted in fluid mode. The LLM now produces Therapy, Condition, and Accessory alongside the existing types. Documents 4-5 confirm these types without introducing more. Convergence is fast because 6 types are already established as strong priors.

Consolidation: the 3 new types are added to the ontology (total: 9 types). Type clustering confirms they are distinct. Batch flush writes the re-extracted entities from docs 3-5 to Neo4j.

### CURING -> STABLE

Trigger: `stabilize`.

Metanode updates: `ontology_type_count: 9`, `ontology_hash: <new hash>`, `ontology_source: discovered` (re-cured).

Run completes: `run_id` set to null, `run_count` = 3.

### Run 3 Transition Log

| # | From | To | Trigger | Detail |
|---|------|-----|---------|--------|
| 1 | STABLE | INITIALIZING | `start_run` | run 3, home care domain |
| 2 | INITIALIZING | STABLE | `begin_stable` | graph calibrated, 6 types loaded |
| 3 | STABLE | RECURING | `detect_drift` | remap_rate=0.35, 3 type gaps |
| 4 | RECURING | CURING | `authorize_revision` | genuine gaps confirmed |
| 5 | CURING | STABLE | `stabilize` | ontology expanded to 9 types |

**5 transitions.** The full STABLE -> RECURING -> CURING -> STABLE cycle exercised.

## Combined Audit Trail (All 3 Runs)

| Run | # | From | To | Trigger | Detail |
|-----|---|------|-----|---------|--------|
| 1 | 1 | EMPTY | INITIALIZING | `start_run` | first run |
| 1 | 2 | INITIALIZING | CURING | `begin_curing` | fluid discovery |
| 1 | 3 | CURING | STABLE | `stabilize` | 6 types frozen |
| 2 | 4 | STABLE | INITIALIZING | `start_run` | same domain |
| 2 | 5 | INITIALIZING | STABLE | `begin_stable` | already calibrated |
| 3 | 6 | STABLE | INITIALIZING | `start_run` | adjacent domain |
| 3 | 7 | INITIALIZING | STABLE | `begin_stable` | calibrated |
| 3 | 8 | STABLE | RECURING | `detect_drift` | remap 35% |
| 3 | 9 | RECURING | CURING | `authorize_revision` | 3 new types |
| 3 | 10 | CURING | STABLE | `stabilize` | 9 types frozen |

## Final Metanode State

```
graph_id: f8a2c3d1
fsm_state: stable
run_id: null
run_count: 3
ontology_source: discovered
extraction_mechanism: fluid
consolidation_started_at: null
ontology_type_count: 9
ontology_hash: e5f6a7b8
last_completed_at: 2026-03-17T14:30:00Z
last_error: null
```

## Observations

1. **RECURING served its purpose as a deliberation state.** The system paused in RECURING to evaluate whether drift was genuine. If the LLM had said "these are synonyms" (e.g., "Accessory" is just "Component"), the path would have been RECURING -> STABLE (dismiss), and the audit trail would show drift was evaluated and rejected. Without RECURING as a state, this dismiss path would be invisible
2. **STABLE -> INITIALIZING -> STABLE was the efficient path for Run 2.** When the graph is already calibrated and no new seed is provided, the system skips CURING entirely. The FSM correctly models this as "already calibrated, nothing to cure"
3. **The graph's ontology evolved across runs.** Run 1 established 6 types. Run 3 expanded to 9. The FSM tracked this evolution through the STABLE -> RECURING -> CURING -> STABLE cycle. The metanode's `ontology_type_count` and `ontology_hash` provide a diff signal between runs
4. **Re-curing preserved existing types as priors.** When RECURING -> CURING fired, the existing 6 types were pre-loaded into the FluidAccumulator. This prevented the system from "forgetting" established types while discovering new ones. The curing cycle is additive, not destructive
5. **10 transitions across 3 runs.** The audit trail tells the complete story of graph evolution without drowning in per-document detail. An operator reading the `(:KGFTransition)` nodes can reconstruct the graph's ontological history: initial discovery (6 types), stable operation, drift detection, ontology expansion (9 types)
6. **DIRECT state would have been confusing here.** Run 2 and the start of Run 3 both entered STABLE directly - they used the existing ontology for type-enforced extraction. A separate DIRECT state would have required distinguishing "DIRECT because strict seed" from "DIRECT because existing graph" from "CURED because just cured" - three states doing the same thing. STABLE unifies them

# FSM State Considerations for Graph Lifecycle Maintenance

The graph must exist as a long-lived, evolving artifact that matures across ingestion runs. Once cured and in STABLE state, its ontology becomes the authoritative prior - any subsequent seed ontology is merged as an additive signal, never a replacement. The `(:KGFControl:KGFState)` metanode anchors this continuity: a new process connects, reads the metanode, and knows exactly where the graph stands without local filesystem state.

## FSC-1: Control Plane Node Naming Convention

| | |
|---|---|
| **Raised** | 2026-03-17 |
| **Status** | Done |
| **Last Update** | 2026-03-18 |
| **Design Comments** | `:KGFControl` shared label pattern chosen over single-label `KGF` prefix to avoid collision with domain data. Current code uses single-label `(:KGFControl)` for metanode - needs migration to `(:KGFControl:KGFState)` dual-label. Migration scope: `fsm/metanode.py` MERGE/CREATE queries, `validate_graph()` needs `WHERE NOT n:KGFControl` exclusion |
| **Implementation Notes** | Migrated all 7 Cypher queries in `metanode.py` to dual labels (`:KGFControl:KGFState`, `:KGFControl:KGFRun`, `:KGFControl:KGFTransition`). Added `WHERE NOT n:KGFControl` exclusions to all domain queries across `validation.py` (5 queries), `graph_query.py` (4 queries), `loader.py` (1 query), and `metanode.py` (1 query). Updated 3 test assertions to verify dual labels. Updated `context.py` comment. 429 tests pass, lint clean. |

All control plane nodes carry `:KGFControl` as a shared secondary label. This provides collision-safe namespace isolation - the `KGF` prefix alone could collide with domain data extracted from sources that happen to mention "KGF". The shared label enables clean wipe, exclusion from domain queries, and future index optimization without substring matching on label names.

```cypher
-- wipe entire control plane
MATCH (n:KGFControl) DETACH DELETE n

-- exclude control plane from domain queries
MATCH (n) WHERE NOT n:KGFControl RETURN count(n)

-- validation that ignores control plane
MATCH (n:Entity) WHERE NOT n:KGFControl RETURN count(n)
```

Each node has a primary label for its specific type and `:KGFControl` as the shared namespace label:

| Node | Labels | Purpose |
|------|--------|---------|
| Metanode | `:KGFControl:KGFState` | FSM state, run history, ontology hash |
| Run | `:KGFControl:KGFRun` | Per-ingestion run record |
| Transition | `:KGFControl:KGFTransition` | State change audit trail |
| Consumed prior | `:KGFControl:KGFConsumedPrior` | Previously imported seed ontology record |
| Ontology type | `:KGFControl:KGFOntologyType` | Ontology type definition with hierarchy |
| Resolution guide | `:KGFControl:KGFResolutionGuide` | Type pair resolution rules |
| Type calibration | `:KGFControl:KGFTypeCalibration` | Per-type Bayesian calibration state |
| Type metrics | `:KGFControl:KGFTypeMetrics` | Per-type monitoring metrics |

Domain nodes (`(:Entity)`, `(:Document)`, `(:Chunk)`) never carry `:KGFControl` - they are user data, not control plane.

## FSC-2: Ontology as Prior in STABLE

| | |
|---|---|
| **Raised** | 2026-03-17 |
| **Status** | Done |
| **Last Update** | 2026-03-18 |
| **Design Comments** | `ontology.yml` becomes an internal artifact - no longer user-facing or filesystem-authoritative. The system generates and maintains it internally as a cache; the graph is the sole source of truth for schema state |
| **Implementation Notes** | Implemented full graph-authoritative schema: (A) `compute_hash()` on `OntologyBuffer` produces deterministic 16-char SHA256 hash of sorted confirmed types, computed at both stabilize points and stored on metanode as `ontology_hash`. (B) `OntologyBuffer.from_graph()` classmethod reconstructs buffer from 7 graph queries (entity frequencies, rel types, KGFOntologyType defs, IS_A hierarchy, KGFResolutionGuide, entity exemplars, KGFTypeCalibration). (C) `write_ontology_types()`, `write_resolution_guide()`, `write_type_calibration()` in `metanode.py` persist schema at each stabilize. (D) Seed dedup: compares seed hash against metanode's `ontology_hash`, skips if identical, merges if different. Cache-first pattern: loads `ontology.yml` if hash matches, falls back to `from_graph()` on mismatch. `_persist_schema_safe()` helper in `cli.py` orchestrates writes. 3 new test classes (7 tests) for write functions, 3 new tests for `compute_hash()`. 429 tests pass, lint clean. |

In STABLE state the graph's evolved ontology carries calibrated Bayesian posteriors for every type assignment. New documents are extracted against this established schema with type enforcement. A seed ontology provided on a subsequent run merges with the graph's existing types as elevated priors in the ontology buffer - it informs but does not constrain. In strict mode, the graph ontology wins outright (KGF_DESIGN.md Section 14.4).

When KGF is re-launched against an existing graph, the system must solve two problems: recognizing which ontology priors have already been consumed (to avoid re-importing them), and reconstructing the full schema state with its accumulated statistical context.

**Prior deduplication**: any seed ontology provided on a subsequent run must be checked against the graph's internal schema representation. Types already present in the evolved ontology should not be re-imported as fresh signals - they are already reflected in the posteriors, frequencies, and resolution guides. The `ontology_hash` on the metanode provides a coarse conflict check, but type-level deduplication requires comparing individual type names and definitions. A previously consumed seed should be recorded (hash or source path) on the metanode so that identical seeds are recognized and skipped on re-launch. New types in the seed that do not exist in the graph schema are the only ones that should enter the buffer as additive priors.

**Schema state persistence**: the graph's internal schema representation must be fully recoverable from the graph itself. This means persisting type frequencies (how many entities per type), resolution guide rules (which type pairs require special handling and how), type hierarchy relationships (parent-child, sibling groupings), and statistical calibration metrics (posterior means, observation counts, remap rates per type). The `ontology.yml` file transitions from a user-facing artifact to an internal cache managed entirely by the system - it may still exist on disk as a performance optimization (avoiding graph round-trips on startup), but the graph is the authoritative source and `ontology.yml` is regenerable from it at any time. Users no longer provide or edit this file; ontology input comes exclusively through seed files (via `--ontology` flag) or through fluid discovery.

**Current implementation**: the ontology buffer loads from the flushed `ontology.yml` at run start. The buffer's type frequencies and resolution guides carry forward between runs via this file. The `ontology_hash` on the metanode enables coarse conflict detection when a seed diverges from the evolved schema. No record of previously consumed seeds exists. The `ontology.yml` is currently treated as semi-authoritative - this must change to graph-authoritative with `ontology.yml` as disposable cache.

**Open**: three capabilities are needed for full graph-as-control-plane schema persistence.

- **Consumed prior registry**: a list of seed ontology hashes (or source identifiers) stored on the metanode or as `(:KGFControl:KGFConsumedPrior)` nodes, enabling the system to recognize and skip previously imported seeds. Each entry records the hash, source path, import timestamp, and which types were added versus already present.

- **Graph-reconstructable schema**: type frequencies derivable from `MATCH (n:Entity) RETURN n.type, count(n)`, resolution guides from `(:KGFControl:KGFResolutionGuide)` nodes storing type pair rules, type hierarchy from existing `(:KGFControl:KGFOntologyType)` nodes with `[:IS_A]` relationships. The buffer's `from_graph()` class method would reconstruct a full `OntologyBuffer` from these graph structures without reading `ontology.yml`.

- **Statistical calibration state**: per-type metrics persisted to `(:KGFTypeCalibration)` nodes linked to `(:KGFControl)` - entity count, mean posterior, observation count, remap frequency, prior strength. These enable the Bayesian resolver to resume with calibrated priors rather than rebuilding from scratch on each run. The exemplar index (FAISS vectors for type resolution) is ephemeral and rebuilt from graph entities, but the statistical parameters that inform its decision thresholds should persist.

## FSC-3: Evidence Collection in STABLE

| | |
|---|---|
| **Raised** | 2026-03-17 |
| **Status** | Open |
| **Last Update** | 2026-03-17 |
| **Design Comments** | - |
| **Implementation Notes** | - |

STABLE is not idle - during active extraction it continues accumulating evidence for type assignments, deduplication, and cross-type resolution. Each document processed in the cured phase contributes to remap rate tracking (via `CuringDetector.check_drift()`), stability metrics (JSD, entropy delta), and type frequency distributions.

**Current implementation**: the detector tracks remap rates in a sliding window (`drift_window=3`, `drift_remap_threshold=0.3`). When all recent documents exceed the threshold, drift is detected. The FSM transitions STABLE -> RECURING, and the LLM advisory (or heuristic fallback) decides whether to authorize revision (RECURING -> CURING) or dismiss (RECURING -> STABLE). Per-type calibration state (mean posterior, observation count, remap count, prior strength) is now persisted to `(:KGFControl:KGFTypeCalibration)` nodes at each stabilize point, and `OntologyBuffer.from_graph()` reconstructs this state on resume. Isotonic calibration curves are persisted as `(:KGFControl:KGFCalibrationCurve)` nodes and loaded when `run_count >= 1`.

**Partially resolved**: cross-run posterior continuity exists at the aggregate level - per-type mean posteriors and observation counts survive between runs via KGFTypeCalibration nodes. The gap is per-entity posterior provenance: the system knows that "Component" has a mean posterior of 0.87 across 181 entities, but cannot trace which individual entity assignments were high-confidence versus marginal. This limits the ability to selectively re-evaluate low-confidence assignments when the ontology evolves during RECURING.

## FSC-4: Rebuild Cost and the Scale Problem

| | |
|---|---|
| **Raised** | 2026-03-17 |
| **Status** | Open |
| **Last Update** | 2026-03-17 |
| **Design Comments** | - |
| **Implementation Notes** | - |

STABLE graphs range from hundreds to millions of entities. The cost of ontology rework scales with graph size - a type rename affecting 10 entities is trivial, but re-typing 50,000 entities requires careful orchestration. This asymmetry means the system must distinguish between ontology extension (additive, low cost) and ontology revision (restructuring, high cost).

**Extension** adds new types or relationships without modifying existing entities. A new document introduces "Humidifier Chamber" as a subtype of Component - existing Component entities are unaffected, new ones get the refined type. This is the common case in STABLE and requires no rebuild.

**Revision** changes type boundaries, merges types, or splits types in ways that invalidate existing entity assignments. Merging "Accessory" and "Component" into a single type requires re-labeling every affected entity and potentially re-resolving cross-type duplicates. This is expensive and should only proceed with explicit justification.

**Current implementation**: RECURING is the deliberation state where this decision happens. The LLM advisory (`llm_should_recure()`) evaluates whether remapped types represent genuine ontology gaps or synonyms/variants. Two exit paths: `authorize_revision` (proceed to CURING for re-calibration) or `dismiss_drift` (return to STABLE). Both paths are logged as `(:KGFControl:KGFTransition)` audit trail nodes.

**Open**: there is no cost estimation or rebuild impact analysis before authorizing revision. The system could query the graph for affected entity counts per type before deciding - "merging Accessory into Component would re-type 92 entities and invalidate 34 cross-type resolution decisions." This cost signal would inform both the LLM advisory and interactive-mode user prompts. A rebuild from RECURING should also support rollback - snapshot the current ontology state before entering CURING so the system can revert if revision produces worse results.

## FSC-5: RECURING Mechanics

| | |
|---|---|
| **Raised** | 2026-03-17 |
| **Status** | Partial |
| **Last Update** | 2026-03-17 |
| **Design Comments** | Three-step sequence (detect, deliberate, resolve) is wired into FSM and cli.py. Graduated drift severity and interactive confirmation are open enhancements (P4 from research decomposition) |
| **Implementation Notes** | - |

RECURING is triggered when sustained drift is detected during STABLE-phase extraction. The mechanics follow a three-step sequence.

**Detection**: `CuringDetector.check_drift()` fires when all documents in the sliding window exceed the remap rate threshold. The FSM transitions STABLE -> RECURING via `detect_drift` (guarded by `drift_confirmed=True`).

**Deliberation**: in RECURING, the system evaluates whether ontology revision is warranted. With `generative_curing` enabled, `llm_should_recure()` examines the cured ontology types, remap history, and stability metrics. Without it, the `re_cure_on_drift` config flag serves as a heuristic fallback.

**Resolution**: two exits. `authorize_revision` resets the accumulator, detector, and metrics tracker, re-enters fluid accumulation from the current document, and transitions to CURING. The subsequent curing event will re-consolidate with the revised ontology. `dismiss_drift` returns to STABLE with the current ontology intact, treating the remapped types as acceptable variance.

**Open**: RECURING currently makes a binary decision per drift event. A graduated approach could track drift severity across multiple windows - minor drift dismissed automatically, moderate drift flagged for LLM evaluation, severe drift requiring interactive confirmation. The buffer is not used during RECURING deliberation itself, only after `authorize_revision` when fluid accumulation restarts.

**Open**: control plane cleanup on `authorize_revision`. When RECURING transitions to CURING, stale control plane nodes (calibration state, type metrics, resolution guides) may reflect the pre-revision ontology and should be selectively pruned or invalidated. A controller + model pair will track the provenance state of each control plane node class - whether it was written by the current run or inherited from a previous one - so the system knows on any transition whether it is starting clean or carrying forward stale state. This eliminates the current implicit assumption that control plane nodes are always consistent with the active ontology.

## FSC-6: State Recovery Across Interrupted Runs

| | |
|---|---|
| **Raised** | 2026-03-17 |
| **Status** | Done |
| **Last Update** | 2026-03-18 |
| **Design Comments** | P1 priority from research decomposition (SQ3). Crash detection exists (`consolidation_started_at` marker on metanode, `detect_graph_state()` reads it), recovery action does not. Mid-consolidation is hardest - depends on `ingestion_run_id` tagging completeness for safe entity wipe. Post-consolidation is simplest - `(:Document)` nodes identify loaded docs, resume from next |
| **Implementation Notes** | Implemented all three crash recovery scenarios in `_init_fsm()`. (1) Pre-consolidation: detects `fsm_state=curing` + null `consolidation_started_at`, forces re-cure. (2) Mid-consolidation: detects non-null `consolidation_started_at`, wipes entities by stale `run_id` (`MATCH (n:Entity {run_id: \$run_id}) DETACH DELETE n`), forces re-cure, logs wipe count. (3) Post-consolidation: detects `fsm_state=stable` + non-null `run_id`, queries `(:Document)` nodes for loaded names, stores in `ctx.loaded_doc_names`, skips already-loaded docs in both `_ingest_fluid()` and `_ingest_direct()`. Document/entity `run_id` tagging: `_create_document_node()` and `_create_entity_nodes()` in `loader.py` accept and persist `run_id` parameter. All `load_extraction()` and `load_doc_chunks()` calls in `cli.py` threaded with `run_id` from FSM context. `PipelineContext.loaded_doc_names: set[str]` field added. Stale consolidation marker and run_id cleared after detection. 429 tests pass, lint clean. |

A run may be interrupted mid-curing (process killed, rate limit exhaustion, network failure). The graph may contain partial data - some documents loaded, others still in the accumulator.

**Current implementation**: the `consolidation_started_at` timestamp on the metanode serves as a crash recovery marker. If a new process finds a metanode with this field set, it knows the previous run was interrupted during consolidation. The FSM state (`curing`) and run count enable the new process to determine where the previous run left off.

**Open**: recovery from interrupted curing is detected but not yet acted upon. The detection algorithm (KGF_DESIGN.md Section 14.3) identifies the state, but the recovery strategy is not implemented. Three scenarios need distinct handling.

- **Interrupted during fluid accumulation** (no consolidation marker): accumulated results exist only in memory and are lost. The graph has no partial entities from this run. Recovery: restart curing from scratch, re-processing all documents.

- **Interrupted during consolidation** (marker set): type clustering may have completed but the batch flush to Neo4j was partial. Some entities are in the graph, others are not. Recovery: wipe entities from the interrupted run (identifiable by `ingestion_run_id`) and re-consolidate, or detect which documents were successfully loaded and resume from there.

- **Interrupted during cured phase** (consolidation complete, processing remaining docs): the ontology is established and some cured-phase documents are loaded. Recovery: identify the last successfully loaded document (via `(:Document)` nodes) and resume from the next one. This is the simplest case - no ontology state to reconstruct.

## FSC-7: Per-Type Monitoring and Metrics

| | |
|---|---|
| **Raised** | 2026-03-17 |
| **Status** | Open |
| **Last Update** | 2026-03-17 |
| **Design Comments** | - |
| **Implementation Notes** | - |

Each ontology type should carry observable metrics that persist across runs - entity count, posterior mean, assignment confidence distribution, remap frequency, and growth rate. These metrics serve two purposes: drift detection (type-level anomalies are more precise than corpus-level remap rates) and calibration continuity (knowing that "Component" has 181 entities with mean posterior 0.87 across 3 runs is more informative than a single-run snapshot).

**Current implementation**: type frequencies are tracked in the ontology buffer and flushed to `ontology.yml`. The benchmark reports type distribution from the graph (`MATCH (n:Entity) RETURN n.type, count(n)`). No per-type posterior statistics are persisted.

**Open**: a `(:KGFControl:KGFTypeMetrics)` node per ontology type, linked to `(:KGFControl:KGFState)` via `[:HAS_TYPE_METRICS]`, could store `entity_count`, `mean_posterior`, `remap_count`, `first_seen_run`, `last_updated_run`. Updated at each run completion, these nodes would enable type-level drift detection ("Component remap rate jumped from 5% to 25% in the last 3 runs") and provide the cost estimation data needed for informed rebuild decisions.

## FSC-8: Cross-Run Fluid Phase Persistence

| | |
|---|---|
| **Raised** | 2026-03-18 |
| **Status** | Implemented |
| **Last Update** | 2026-03-18 |
| **Design Comments** | Option B (control plane extraction cache) chosen over domain-layer provisional entities |
| **Implementation Notes** | `metanode.py` (write/read/delete for KGFFluidResult + KGFFluidState), `cli.py` (per-doc cache writes, resume logic, cleanup), serialization methods on CuringDetector, StabilityMetrics, DeferredDedupBuffer |

The fluid phase accumulates extraction results in memory across documents until a curing event triggers consolidation. If the process exits mid-fluid (crash, intentional stop, batch boundary), all accumulated data is lost and the next run forces re-extraction from scratch, wasting LLM API costs.

**Solution**: after each fluid-phase document extraction, persist the `ExtractionResult` as a `(:KGFControl:KGFFluidResult)` node and detector/metrics state as a `(:KGFControl:KGFFluidState)` node. On resume, deserialize and rebuild the accumulator identically. Payloads use versioned envelopes with zlib + base64 compression. Embeddings are excluded from the cache (regenerated at curing time). Document + chunk nodes are written to Neo4j per-document during fluid phase rather than deferred to consolidation, so chunk text is already in the graph and excluded from cache payload.

**Cleanup triggers**: fluid cache nodes are deleted whenever the accumulator is reset or consumed - after curing, after end-of-corpus flush, on drift re-entry, during mid-consolidation crash recovery, and as a safety net at run completion. Version mismatch on resume discards the cache and falls back to re-extraction.

## FSC-9: CURING Semantic Breadth - Beyond Type Discovery

| | |
|---|---|
| **Raised** | 2026-03-18 |
| **Status** | Partial |
| **Last Update** | 2026-03-18 |
| **Design Comments** | Core insight: fluid and direct are extraction mechanisms, not lifecycle states. CURING encompasses all ontology calibration, not just type emergence. This is structurally realized in the FSM but the cure trigger still relies primarily on type-distribution signals |
| **Implementation Notes** | FSM correctly routes both fluid and direct extraction through CURING. `extraction_mechanism` is a metanode property, not a state. `needs_calibration` guard ensures strict-seed runs enter CURING. Cure trigger uses CuringDetector (JSD, Chao1, type accumulation rate, Heaps beta). Calibration infrastructure (observation collector, isotonic calibrator, 19-metric multi-channel prior) runs during CURING but does not feed back into the cure decision |

Fluid and direct are extraction mechanisms that control how the LLM extracts entities - fluid lets types emerge freely, direct enforces types from a known schema. Both are configuration parameters within the CURING state, not lifecycle states themselves. The FSM is structurally correct on this: `extraction_mechanism` is recorded on the metanode as metadata, and both mechanisms transit through CURING before reaching STABLE.

The deeper insight is that curing is broader than type discovery. Even with a strict seed where all types are known upfront, the graph is still curing: calibrating Bayesian posteriors with real entity evidence, building resolution guides for ambiguous type pairs, accumulating cross-type dedup evidence, stabilizing entity resolution thresholds, and resolving ontology assignment ambiguities. A graph with a strict seed doesn't skip curing - it cures with types already known but everything else still calibrating. "Cured" means the graph's ontology is robust and well-evidenced, not just that types stopped emerging.

**Current implementation**: the `CuringDetector` decides when to cure based on type-distribution convergence signals - JSD below 0.05 for consecutive documents, Chao1 coverage above 0.7, type accumulation rate declining. These are all type-emergence signals. The broader calibration infrastructure (observation collector recording cross-type and type-assignment decisions, isotonic calibration fitting posterior curves, 19-metric multi-channel prior) runs during CURING and produces artifacts that persist to the control plane, but none of these feed back into the cure decision itself. The system cures when types stabilize, then calibration state persists as a side-effect.

**Gap**: the cure trigger should incorporate calibration convergence alongside type-distribution convergence. Possible signals:

- **Posterior convergence**: mean posterior variance across types dropping below a threshold (types are being assigned with consistent confidence)
- **Resolution guide saturation**: the number of new resolution rules added per document approaching zero (ambiguous pairs are resolved)
- **Deferred dedup resolution rate**: the fraction of deferred cross-type pairs that have accumulated enough evidence to resolve (the system is no longer deferring decisions)
- **Remap rate during CURING**: even in fluid mode, remaps occur when the type assigner overrides an LLM-proposed type. A declining remap rate within CURING signals that the LLM and the Bayesian resolver are converging

A composite cure readiness score combining type stability (current signals) with calibration maturity (new signals) would make the cure decision more robust, particularly for strict-seed runs where type distribution converges immediately but calibration may lag. The generative curing advisory (`llm_should_cure`) already receives the full metrics timeline and could evaluate calibration signals if they were included in the prompt context.

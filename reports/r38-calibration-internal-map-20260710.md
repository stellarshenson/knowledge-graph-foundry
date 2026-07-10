# R38 Internal Map - Self-Calibrating Escalation Gate (H382 → engine)

Cartographer brief, 2026-07-10. Read-only survey of everything the per-corpus self-calibration mechanism for the H382 escalation threshold would touch or reuse. Every claim carries a file:line anchor; absences are marked NOT PRESENT. Paths are relative to the repo root (`/home/lab/workspace/learning/projects/knowledge-graph-foundry`).

Context: H382 CONFIRMED (docs/sota-promotions.md:75, reports/r37-h382-ladder-arm1-20260710T173529Z.json) - the free top-seed similarity signal at a fitted threshold ~0.765 (out-of-fold cuts 0.7650/0.7644) escalates 25% of queries and buys the composed frontier (0.9583, 23/24) at +6.9% context. The shipped `miss_threshold=0.668` is a different operating point on the same signal and escalates nothing. H157 (transfer ECE 5.18x) forbids shipping the fitted cut as a constant.

---

## 1. Existing calibration machinery (H142/H157 lineage)

The engine carries TWO calibration families: the resolver's per-corpus posterior calibrator (H142/H157) and the v2 identity stack's baked offline artifact (H129/H158). Both are identity-side; nothing on the retrieval side is calibrated today.

### 1.1 Fitting code

- **Isotonic calibrator** - `PosteriorCalibrator`, src/knowledge_graph_foundry/resolution/calibration.py:21-74. `fit()` (48-66) gates on `min_observations` (default 50, settings.py:70) and wraps `sklearn.isotonic.IsotonicRegression`; below the floor it returns None and the caller keeps a fixed documented threshold (calibration.py:5-8 module doctrine)
- **Temperature scaler** - `TemperatureScaler`, calibration.py:115-172; single parameter, preferred for few labels (R7), gated on `calibration_min_labels` (default 100, settings.py:74). NOT wired into the pipeline anywhere - only `PosteriorCalibrator` is imported by resolver/pipeline (resolver.py:29, pipeline.py:43). The scaler is available machinery, currently unused
- **Per-corpus fit entry point** - `fit_calibration_from_events()`, calibration.py:77-108: joins the JSONL event log (`resolution.*` events carrying `left_id`/`right_id`/`posterior`, lines 100-106) against a ground-truth pairs file `[{left_id, right_id, same}]` (lines 88-90), fits isotonic offline
- **CLI** - `kgf calibrate`, src/knowledge_graph_foundry/cli.py:131-167. Offline-fit, runtime-frozen: writes the JSON artifact to `resolution.calibration_path`

### 1.2 What data feeds it (ground-truth harvesting)

- The `(posterior, label)` observations come from the event log x a MANUAL ground-truth pairs JSON (calibration.py:79, cli.py:133-135). There is NO automatic ground-truth harvesting in the engine - the labels file is produced offline (H101-style adjudication, notebooks). NOT PRESENT: any in-engine label collection loop
- The event-log side IS automatic: `emit(f"resolution.{decision.decision}", **decision.model_dump())` at pipeline.py:804 writes per-pair posterior + ids for every live-graph match decision; the resolver batch path emits the same family (resolution/resolver.py:242-250 region). This is the identity-side label bus the fitter consumes

### 1.3 Where constants are stored

Three storage tiers, with an explicit precedence chain in `Foundry._make_calibrator()` (pipeline.py:120-130):

1. **File artifact** (wins): `resolution.calibration_path` (settings.py:86-88, default None) - a per-corpus frozen JSON on disk, loaded at pipeline.py:126-127. Survives graph wipes; corpus-bound by convention only
2. **Graph state** (fallback): the `calibration` key of the control metanode - loaded at pipeline.py:128-129, persisted after EVERY document at pipeline.py:454 and at corpus-exhausted consolidation pipeline.py:481, initialized to None at pipeline.py:171. Calibration-in-graph is therefore ALREADY SHIPPED, not a new idea
3. **None** → fixed documented threshold (`resolution.merge_threshold=0.6`, settings.py:64)

Separately, the v2 identity stack loads a baked artifact `data/processed/identity-calibration-v2.json` (settings.py:80-82, loader identity_stack.py:90-93) - never refit at runtime (identity_stack.py:8-9).

### 1.4 Versioning per corpus

- The resolver's serialized curve is bare: `{"kind": "isotonic", "x": [...], "y": [...]}` (calibration.py:68-69) - NO corpus id, NO fit metadata, NO version field. The only stamp is the metanode's blanket `updated_at` (graph/metanode.py:47)
- The v2 artifact is the versioning PRECEDENT to copy: top-level keys `version`, `provenance {hypothesis, built_utc, source_graph, benchmark, n_pairs, n_yes, n_no, titan_auc, isotonic_ece, oof_f1, ...}`, `isotonic`, `logistic`, `nli` (inspected in data/processed/identity-calibration-v2.json)
- **ECE**: computed only offline (notebooks/calibration_family_h102-h129.ipynb, notebooks/corpus_transfer_h157.ipynb); the string "ece" appears in the engine only as a docstring citation (identity_stack.py:5). NOT PRESENT as a runtime quantity

---

## 2. The signal path (top-seed similarity)

### 2.1 Where the signal is computed

- `vector_query()` - src/knowledge_graph_foundry/graph/graphrag.py:118-131: `db.index.vector.queryNodes` over the entity index (`kgf_entity_embeddings`, settings.py:116), returns `score` per seed. Unit caveat: the Neo4j cosine index score is `(1 + cos) / 2` - the resolver explicitly inverts it (pipeline.py:789-790). Both `miss_threshold=0.668` and the H382 ~0.765 cut live in INDEX-SCORE units, since scripts/r37_h382_ladder.py builds rung 0 from the same `vector_query` (script lines 46-47, 57-66)
- Seeds fetched via `overfetch_seeds()` (graphrag.py:134-140) at pipeline.py:1039-1045 (`top_k=16`, `overfetch_factor=4`, settings.py:118-119)

### 2.2 Where it is consumed today - three operating points on one signal

| Consumer | Threshold | Where computed | Where read |
|---|---|---|---|
| Miss detector (R19-H181) | `graphrag.miss_threshold = 0.668` (settings.py:122) | `detect_miss()` graphrag.py:165-169 (max seed score < thr) | pipeline.py:1049-1059; emits `query.miss` with `top_score` at 1054, short-circuits to the abstention render |
| Structural abstention (R03-H17) | `graphrag.abstention_min_score = 0.75` (settings.py:136) | coverage `top_score` = max over seed scores AND proposition-hit scores, pipeline.py:1107-1112 | pipeline.py:977-990; emits `query.abstained` at 982 |
| Escalation gate (H382) | ~0.765 fitted | NOT PRESENT | NOT PRESENT - `grep -rn escalat src/` returns nothing |

Note the composite difference: the abstention gate reads seed-OR-proposition max; the miss detector and the H382 signal read the pure top-seed score. A fitted 0.765 threshold sits just above the 0.75 abstention constant - three constants on one signal is itself an argument for one calibrated family.

### 2.3 What changes to add the second threshold

- The natural insertion point is `_retrieve_local()` immediately after the miss-detector block (pipeline.py:1049-1059): compute `top = max(s.score)` once, decide `escalate = top < escalation_threshold`, and let the flag arm the higher rungs for THIS query only. A `detect_escalation()` sibling belongs beside `detect_miss()` in graphrag.py:165-169
- Ordering constraint: miss (< 0.668) fires FIRST and short-circuits; the escalation band is [miss_threshold, escalation_threshold) - the gate never sees the miss class

### 2.4 Rung machinery status

- **Rung 0 (parity render)** - shipped: overfetch + top_k render, pipeline.py:1039-1045 and the block render loop 1150-1219
- **Rung 1 (proposition-seed union, H367-B)** - 80% built, disconnected: proposition hits fetched pipeline.py:1065-1078, their entity ids extend `seed_ids` at 1079-1083, but `nodes = seeds` at pipeline.py:1085 means the extended set feeds ONLY the PPR expansion, which is off by default (`ppr_enabled=False`, settings.py:127). The R34 record calls the fix "one line, pipeline.py:1085" (docs/experiments/kgf-redesign-experiments.md:4077) - route prop-seeded entities into `nodes`
- **Rung 2 (H366 query-anchored span/window render)** - NOT PRESENT in the engine. Chunks are stored as provenance nodes (pipeline.py:621-640) but never embedded and never rendered; the span construction + bge-m3 passage embeddings exist only offline (scripts/r37_h382_ladder.py:61-65, span cache results/r34/h366-span-embs-bgem3.jsonl). Its engine wiring is the pending R34 tranche and rides the acc-crit Embeddings provider abstraction (experiments log 4023, 4077). Until it lands, the gate can only escalate rung 0 → rung 1
- Embedding-space caveat: the engine index is Titan (settings.py:37-38); the offline rung-2 caches are bge-m3. The GATE signal is Titan-index-score in both worlds (safe), but rung-2 wiring imports a second embedding space into the engine

### 2.5 Threshold-fitting algorithm (reusable)

`fit_threshold()` in scripts/r37_h382_ladder.py:70-81 - candidate cuts at midpoints of sorted signal values, objective = catch every needy probe, then minimize escalations; 2-fold cross-calibration harness at 218-221. Small, dependency-free, portable into the engine as-is.

---

## 3. Label harvesting surfaces (query → outcome → signal)

What the gate's self-calibration needs is `(signal value, needed-escalation?)` pairs per query. Survey of what KGF records today:

| Surface | Where | What is stored | query→outcome→signal link? |
|---|---|---|---|
| JSONL event log | events.py:58-98, enabled via `Settings.event_log` (settings.py:168), CLI default `logs/kgf-events.jsonl` (cli.py:30) | every `emit()` with timestamp | carrier exists; content below |
| `query.miss` event | pipeline.py:1054 | `question`, `top_score` | signal YES, outcome NO. Registry drift: `query.miss` is absent from the SIGNALS list (events.py:17-55 lists only `query.abstained` at 48) - blinker creates signals on demand so it works, but the registry is stale |
| `query.abstained` event | pipeline.py:982 | `question`, coverage (`top_score`) | signal YES, outcome NO |
| Query answers | `query()` return, pipeline.py:1012-1016 | returned to caller, NOT persisted anywhere | NOT PRESENT - no `query.answered` event exists (grep confirms) |
| Probe replay | probe set tests/probes/cpap-probe-set.yml (28 probes: question, gold_answer, gold_evidence, sources); harness notebooks/h158_measure.py; reports/probe-eval-*.json | per-probe recall vs gold; r37 script additionally records per-probe signal + rung recalls (r37_h382_ladder.py:84-96, 218-264) | YES - the ONLY surface with the full triple, but 100% offline, never engine-driven |
| Gap ledger | docs/gap-ledger.md | markdown document of priced-out capabilities (4 entries) | NO - it is a project doc, not a per-query queryable store. The H161 "queryable gap-ledger record" remains doctrine: NOT PRESENT in the graph (nearest kin: `document.skipped` events, pipeline.py:341/346/389/401) |
| Answer cache (H274) | notebooks/usage_coupling_gates_r26.ipynb cells 11-14; decision docs/sota-promotions.md:68, deferral h198-wiring-plan.md:52 | design: EXTERNAL store keyed by (query cluster, supporting-subgraph content hash - md5 over {entity}+1-hop ids+content, notebook cell 12); zero graph coupling BY DESIGN | NOT PRESENT in engine; if shipped it would hold query→answer→evidence-fingerprint, i.e. the natural outcome side of a label |
| Demand signals (H271) | notebooks/usage_coupling_gates_r26.ipynb cells 8-10 (probe catalogue replayed as demand ledger); h198-wiring-plan.md:52 | offline: per-document demand counts | NOT PRESENT in engine |
| Judge verdicts (court) | graph/court.py:86-122 | emits `resolution.court` SUMMARY counts only (docket/freebies/judged/demoted, court.py:108-114); per-pair verdicts are not persisted - demotions become soft links, judged-true leaves no trace | identity-side only, no per-pair record |
| Resolution decisions | pipeline.py:804 `emit(f"resolution.{...}", **decision.model_dump())` | per-pair left_id/right_id/posterior/decision | YES for identity - this is exactly what fit_calibration_from_events consumes (calibration.py:100-107). The retrieval side has NO equivalent bus |

**Bottom line**: the retrieval side records the signal without the outcome (query.miss) and computes outcomes without persisting them (probe replays, offline). The cheapest closure is a `query.answered` event carrying `top_score` + answer + supporting entities, replayable against a probe/gold file by a `fit_gate_from_events()` twin of calibration.py:77-108.

---

## 4. Persistence options in the graph

### 4.1 Precedent - singleton metadata node: YES, and calibration already lives there

- `(:KGFControl {id: 'kgf'})` - graph/metanode.py:18-53. One node holds `fsm_state, purpose, ontology, calibration, buffer_cache, metrics_history, drift, processed_documents, documents_processed, purpose_history` (write sites pipeline.py:164-174, 447-460, 474-487, 209-216). Dict/list values are JSON-serialized under `json_`-prefixed property names (metanode.py:32-34, 43-44); `write_control` stamps `updated_at` (47). The resolver calibration curve is persisted here TODAY (pipeline.py:454) - a `CalibrationState` record has direct, shipped precedent
- Other metadata-node patterns: `(:KGFLock {id: 'ingest'})` lease node lock.py:19-27; `(:KGFCommunity {id})` graphrag.py:106-113; `(:KGFDocument)` pipeline.py:625-630; `(:KGFEntityVersion)` snapshots loader.py:76-79; `(:Proposition)` content-hash-keyed propositions.py:60-61, 73-81

### 4.2 Per-corpus config node

NOT PRESENT as a distinct concept - the design is one-corpus-per-graph, so the singleton `CONTROL_ID = "kgf"` (metanode.py:18) IS the per-corpus record. There is no corpus identifier stored anywhere in state (the `processed_documents` fingerprints - `name:sha1(content)[:16]`, pipeline.py:557-572 - are the closest thing to a corpus fingerprint and could hash down to one).

### 4.3 Risks

- **Wipe-on-rebuild** - `wipe()` is `MATCH (n) DETACH DELETE n` (pipeline.py:1250-1253; CLI cli.py:227-237): the control node and any in-graph calibration die with it, and wipe-between-runs is standard campaign practice. This is exactly why `_make_calibrator`'s two-tier precedence (file wins over graph state, pipeline.py:120-130) exists - the file artifact is the wipe-survivor tier. The same two-tier shape should carry the gate threshold
- **Multi-corpus piles** - two corpora in one DB collide on `CONTROL_ID='kgf'`; a mixed pile also makes the single fitted threshold a mixture cut, which H157 (corpus-class-bound constants) says is wrong. The metanode gives no partition mechanism today
- **Stale-state clobber (inference from code structure)** - the ingest loop loads state ONCE (pipeline.py:280) and `_save_state` writes the full dict after every document (447-460); `write_control` merges with `SET c += $props` (metanode.py:50). A calibration key written by another process mid-ingest would be overwritten by the loop's stale copy. Also documented: writing None clears a key (tests/test_graph_integration.py:185)
- **No versioning on the persisted curve** - see 1.4; a gate record must carry its own provenance block (copy the identity-calibration-v2.json shape) because the metanode gives only `updated_at`

---

## 5. Cross-ingestion flow

### 5.1 Incremental ingestion (existing STABLE graph)

`ingest()` → `_ingest_locked()` (pipeline.py:248-277): state restored from the metanode (280), calibrator restored via `_make_calibrator` (293), STABLE/RECURING branch resolves each document against the live graph (`_stable_load`, 430-432, 738-829), and the SAME calibration JSON is re-persisted after every document (454). **Calibration state survives incremental ingestion but is never updated** - there is no refit hook anywhere in the ingest path. `repair()` (574-619) and `repurpose()` (177-222, `state.update` at 209 preserves untouched keys) also round-trip it unchanged.

### 5.2 Rebuild

`wipe()` (1250-1253) deletes everything; `init_project()` re-creates state with `"calibration": None` (pipeline.py:171). Graph-resident calibration is lost by design; only the `calibration_path` file tier survives (pipeline.py:125-127). For the gate this maps cleanly onto the directive: after a rebuild the settings PRIOR applies until per-corpus labels re-accumulate.

### 5.3 FSM placement for a recalibration step

States and transitions: fsm.py:14-23 (EMPTY → INITIALIZING → CURING → STABLE ↔ RECURING, + FAILED). Candidate hooks:

- **At cure (CURING → STABLE)** - `_consolidate` + `lifecycle.cure()` (pipeline.py:425-428, 470-473): the first moment the graph has a full entity population and a vector index worth calibrating against; also where the drift detector is born (735). Right place for the FIRST fit
- **At optimize() (ingest-close maintenance)** - pipeline.py:853-902: already the home of the ingest-close judge court (888-891), proposition backfill, densify, scorecard persist (901-913). The natural update-on-ingestion hook: replay labeled outcomes/probes against the refreshed index, refit if above the label floor, `write_control` the new record
- **At RECURING - warning** - the recure trigger fires (pipeline.py:435-437) but `end_recure` has ZERO production callers (defined drift.py:119-123; only `begin_recure` is called, pipeline.py:437 - grep confirms). RECURING is a dead-end for the drift detector today (the R36 finding, experiments log 4140), so hanging recalibration exclusively on RECURING inherits a dead path. Treat recure as an extra trigger, not the primary one

### 5.4 Survival matrix

| Event | Graph-state calibration | File-artifact calibration | Settings prior |
|---|---|---|---|
| Incremental ingest | survives (re-persisted, pipeline.py:454) | survives | survives |
| repair / repurpose | survives (587; 209) | survives | survives |
| wipe + rebuild | LOST (1250-1253; re-init None at 171) | survives (125-127) | survives |
| New corpus, same config | wrong-corpus risk if file reused (H157) | wrong-corpus risk | correct by design (prior) |

---

## WIRING SKETCH - minimal-change design

**A-priori prior in settings** (src/knowledge_graph_foundry/settings.py, `GraphRAGSettings` 114-141):

- `escalation_gate: bool = False` - the H382 lever, default off until the R34 rung-2 tranche lands
- `escalation_threshold_prior: float = 0.765` - a-priori prior in index-score units; comment it as pile-fitted (H382) and corpus-class-bound (H157), never final
- `escalation_min_labels: int = 12` - refit floor, mirroring the `calibration_min_labels` doctrine (settings.py:74); below it the prior stands

**Per-corpus fitted threshold in the graph** (no new node type needed):

- Add a `gate_calibration` key to the control-node state dict - written through the existing `write_control` (metanode.py:39-53; dicts auto-serialize under `json_gate_calibration`). Record shape copies the identity-calibration-v2.json precedent: `{version, provenance: {hypothesis: "H382", fitted_at, corpus_fingerprint, n_labels, oof_recall, escalation_rate}, signal: "top_seed_index_score", threshold}` - `corpus_fingerprint` = hash over the state's `processed_documents` list (pipeline.py:457), so a mismatched pile is detectable at load
- Loader: a `_make_gate_threshold(state)` sibling of `_make_calibrator` (pipeline.py:120-130) with the same precedence: optional file artifact > `state["gate_calibration"]["threshold"]` > `settings.graphrag.escalation_threshold_prior`

**Gate in the read path** (pipeline.py `_retrieve_local`):

- After the miss-detector block (1049-1059): `top = max(s.score)`; `escalate = top < gate_threshold`; emit a `query.escalated` event with `top_score` + threshold (register it AND the currently unregistered `query.miss` in events.py SIGNALS, 17-55)
- Rung 1 under the flag: route prop-seeded entity ids into `nodes` at pipeline.py:1085 (the H367-B one-liner) only when `escalate`
- Rung 2 under the flag: the H366 span render - lands with the R34 engine tranche; the gate ships rung-0/rung-1 semantics until then and picks up rung 2 for free when the tranche wires it

**Label capture** (the missing outcome side):

- Emit `query.answered` from `query()` (pipeline.py:1012-1016) carrying `question`, `top_score`, `path`, `supporting_entities` - the retrieval twin of the `resolution.*` bus (pipeline.py:804)
- `fit_gate_from_events(events_path, probe_or_gold_path, min_labels)` in a new `graph/gate_calibration.py` (or beside `detect_miss` in graphrag.py): join events to gold outcomes exactly as `fit_calibration_from_events` does for pairs (calibration.py:77-108), fit with the ported `fit_threshold` from scripts/r37_h382_ladder.py:70-81

**Update-on-ingestion hook**:

- `optimize()` (pipeline.py:853-902) gains a recalibration step after the court: if labeled outcomes >= `escalation_min_labels`, refit, and `write_control` the updated `gate_calibration` record (merge-write, preserving the rest of state - read-modify-write the loaded state to avoid the stale-clobber noted in 4.3). Wipe → rebuild resets to the prior automatically because `init_project` state carries no `gate_calibration` key; ingestion then re-accumulates labels and the next `optimize()` refits - update-not-refit across ingestions, exactly the directive
- Optional CLI: extend `kgf calibrate` (cli.py:131-167) with a `--gate` mode reusing the same fitter offline

**Files/functions to touch**: settings.py (GraphRAGSettings), graph/graphrag.py (`detect_escalation` beside detect_miss:165-169), pipeline.py (`_retrieve_local` ~1049-1085, `_make_gate_threshold` ~120-130, `optimize` ~853-902, `query` ~1012), events.py (SIGNALS 17-55), metanode.py (untouched - the JSON-prefix mechanism already handles the record), cli.py (optional).

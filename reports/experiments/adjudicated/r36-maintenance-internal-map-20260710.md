# R36 Input - KGF Internal Maintenance Map (cartographer agent, 2026-07-10)

Recovered verbatim from subagent transcript agent-a9a38595ddc919d71. Input to R36 registration (maintenance of derived objects). Companion: r36-maintenance-literature-brief-20260710.md

---

All reads complete. Deliverable follows.

---

# KGF internal brief: maintenance machinery, R28 fence, DEF-9

Sources: `docs/experiments/kgf-redesign-experiments.md`, `docs/defects.md`, `src/knowledge_graph_foundry/`, `scripts/experiments/r33_h365_repair.py`. All paths below relative to `/home/lab/workspace/learning/projects/knowledge-graph-foundry/`.

## 1. Hypothesis fence

### R28 - graph maintenance and self-healing under the stateless-session kernel (pre-registered 2026-07-09, doc line 3292)

Kernel constraints: Neo4j graph is the ONLY cross-session state; cost is NOT a verdict gate; baseline = shipped passive detector (52 drift.warning / 0 recure / 0 rebuild across 11 logs, even at js=0.5079). First-pass H301-H304 SUPERSEDED (external-store arms killed by the stateless kernel); H309/H310/H312 folded into H320/H321 (ordinals unissued). Free-replay wave executed 2026-07-09 (23 free arms): 14 CONFIRMED, 3 REFUTED, 5 PARTIAL, 1 MEASURED. GPU/Neo4j-write halves queued behind Phase-3 rebuild.

| ID | Lever (one line) | Status |
|----|------------------|--------|
| H293 | active recall@16 gold-battery probe vs passive drift | CONFIRMED (recall drop 0.0625, 0 passive warnings, 0 false alarms) |
| H294 | read-only probe battery leads schema-only detector | CONFIRMED (Spearman(JSD, recall) = -0.147, decoupled) |
| H295 | dead type-burst counter reproduces detector fires free | REFUTED (Jaccard 0.000; 41/46 warnings pure remap noise) |
| H296 | contentless cadence timer as trigger floor | CONFIRMED (timer 96-99% fires on type_emerged==0; counter is the floor) |
| H297 | cure-exit StabilityMetrics panel as early-warning series | PARTIAL (singleton-fraction rho 0.674 PASS; js_divergence_var FAIL) |
| H298 | health panel rank-deficient, JSD a vehicle not cause | REFUTED (top-2 PC var 0.523; JSD partial-corr 0.366) |
| H299 | relationship-type-entropy CUSUM monitor | CONFIRMED (+3.995 nat on the 6.22 build, 0 false alarms) - promoted |
| H300 | temporal ECE drift monitor on resolver posterior stream | CONFIRMED (0.298 ECE-proxy drift, 0 alarms) - promoted; true-label half behind Phase-3 |
| H305 | multivariate PCA (T²/Q-SPE) monitor | MEASURED (rank 3.16; 0 real joint-only outliers; seeded halves need per-doc dicts) |
| H306 | anomaly-detection ceiling is empty on this corpus | CONFIRMED (oracle TP=0, hindsight-optimal = never-fire) |
| H307 | benign warnings = small-doc remap quantization; entity floor 15 | CONFIRMED (removes 45/46 kgf warnings, 0 suppressed escalations) |
| H308 | delete active self-heal; append-only + abstain holds recall | CONFIRMED (deltas 0.0/0.0; 100% self-heal compute removable) |
| H311 | targeted micro-pass menu vs full-rebuild floor per token | CONFIRMED (95.1% of gain at 5.6% tokens, 17x recall-per-token) - promoted |
| H313 | do-nothing is regime-narrow; in_graph=false residue needs micro-pass | CONFIRMED free half (6/8 failed golds in_graph=false); GPU half behind Phase-3 |
| H314 | no query-time signal separates repairable from soft-link failures | PARTIAL (AUC 0.833 on 2 positives, leaky; Phase-3 must widen N) |
| H315 | append-only :MetricSnapshot ledger reconstructs drift window | PARTIAL (parity over 46 windows CONFIRMED; "fires rebuild" sub-claim refuted by DEF-9 AND-gate) |
| H316 | MERGE (doc,epoch) + monotonic seq, exactly-once window under concurrency | UNTESTABLE-FREE - queued behind Phase-3 |
| H317 | CUSUM change-point over reconstructed JSD series | CONFIRMED (fires at the 0.5079 doc + slow-ramp; boolean 0) - THE promoted drift trigger, DEF-9 fix |
| H318 | CAS version-guard on KGFControl vs blind-SET clobber | UNTESTABLE-FREE - queued (blind-SET blob pattern confirmed in `write_control`) |
| H319 | strategy x scenario 2x2 non-collapsible (alias vs rebuild) | registered, queued behind Phase-3 |
| H320 | first-class :Gap nodes, probe→route→repair→re-probe worklist | registered, queued behind Phase-3 |
| H321 | Demand nodes materialize completeness gaps as repair addresses | registered, queued behind Phase-3 |
| H322 | bitemporal repair-provenance ledger stops repeat/oscillation | registered, queued behind Phase-3 |
| H323 | one source-grounded re-derivation primitive beats strategy catalog | registered, queued behind Phase-3 |
| H324 | in-graph MaintenanceLease (heartbeat/TTL) for liveness | registered, queued; head-to-head with H334 |
| H325 | per-assertion extractor stamp (extraction_fingerprint) | registered, queued (loader SET-clause free half authored) |
| H326 | recorded extraction config disambiguates error vs extractor drift | registered, queued |
| H327 | reified per-assertion DERIVED_FROM edge; dangling-provenance detection | registered, queued; head-to-head with H328 |
| H328 | two provenance facts suffice (Chunk.text + extractor stamp); file path banned | registered, queued |
| H329 | provenance_kind routes assertions to the right regenerator | registered, queued |
| H330 | write-ahead OPEN/SEALED ingest-unit sentinel for torn writes | registered, queued (code-read confirms separate transactions today) |
| H331 | drift window = pure fold over bitemporal graph, no snapshot needed | REFUTED (4945 merges make fold lossy; verdict order-dependent) |
| H332 | drift metrics are trajectory functions; snapshot-at-emit necessary | CONFIRMED (permuted order: recompute 0→15 recure; snapshot invariant) - decisive discriminator |
| H333 | reconstruction solvable except cured-ontology reference (OntologySnapshot) | PARTIAL (type-set recovered; reference FREQUENCIES a second unlogged datum) |
| H334 | content-addressed ActionClaim, at-most-once actuation, no liveness assumption | registered, queued; head-to-head with H324 |
| H335 | quiescence barrier for bounded-consistent stateless rebuild | registered, queued (depends on H330 wave-seal; H339 tests the marker) |
| H336 | in-graph answer cache reopens H273-vs-H274 under statelessness | CONFIRMED (0/2479 stale served; inverts R26's external verdict) - promoted |
| H337 | calibration artifact must reconstruct in-graph | CONFIRMED (parity 0.0/2001 pts; isotonic(0.6)=0.085, ~7x overconfident) - RC-critical, fed DEF-10 |
| H338 | demand-ledger round-trip graph-reconstructable | PARTIAL (16.38x non-decorative; ranked round-trip behind Phase-3) |
| H339 | wave-seal marker's own correctness (same-transaction seal) | registered, queued |

Two cross-cutting R28 findings already ledgered: DEF-9 (rebuild gate structurally unreachable) and DEF-10 (uncalibrated default resolver - since CLOSED 2026-07-10 via R29 "court is the effective repair").

### Adjacent rounds (maintenance-relevant IDs)

**R15 maturity (line 1900)**: H157 corpus-class transfer / per-corpus self-calibration - CONFIRMED; H158 identity stack in-engine - DEGRADED (v1 stays default); **H159 idempotent re-ingestion - PENDING (no verdict)**; **H160 shipped compaction (inert-edge pruning as maintenance job) - PENDING (no verdict, no code exists)**; **H161 silent-failure abstention / parse-failure gap ledger - PENDING (no gap-ledger code exists)**; H198 promotion-debt wiring - pending clause (b); H212 clean-conditions rerun - INCONCLUSIVE; H268 soft links - shipped; H290 demotion court - shipped.

**R16 long-horizon operations (line 1966)**: **H162 source retraction - PENDING**; **H163 supersession correctness - PENDING**; **H164 concurrent ingestion parallel==sequential - PENDING**; H165 ingest cost scaling law - REFUTED (no wall); **H166 extraction injection resistance - PENDING**.

**R17 change provenance (line 2021)**: **H167 version capture completeness - PENDING** (claim: name overwrites + property updates captured at 0% - code confirms, see §3); **H168 revision ordering / monotonic revision counter - PENDING**; **H169 change attribution (caused_by_document) - PENDING**; **H170 change history as retrieval surface - PENDING**. All four registered, none executed.

**R18/R19**: instrument/retrieval rounds - no maintenance hypotheses beyond H178 (ANN at 100x scale).

**R26 usage coupling (H271/H274-class, line 3076)**: H271 external demand ledger - CONFIRMED (allocator); **H272 abstention-triggered repair (gap ledger closes its own entries) - registered, NO VERDICT (queued behind LLM tier)**; H273 in-graph derived layer - CONFIRMED but dominated; H274 external answer cache - CONFIRMED and PREFERRED (inverted by R28-H336 under statelessness); H275 recurrence gate - REFUTED; H276 materialized render views - REFUTED; H278 demand decay - PARKED; H279 staleness law - PARTIAL.

**R33/R34/R35 (post-R28, already claim ground)**: R33-H364 stage-localization census - DONE (83.3% of emitted-but-lost mass = resolution stage); R33-H365 fragment merge + provenance-tagged spec hoist - offline prototype VERIFIED (P09 0.0→1.0, P16 0.5→1.0; engine wiring still open); R34-H370 SIMILAR_TO traversal ("three creators, zero consumers") - registered; R34 preamble names DEF-9 "tangentially" (specificity + voting signals could feed the drift gate); R35-H373 questions-as-audit-probes gap-ledger generator - registered.

## 2. DEF-9 verbatim (docs/defects.md:72)

> ### DEF-9: drift rebuild gate is structurally unreachable - anti-phase remap/JSD conjunction never fires
>
> - [ ] MEDIUM the `rebuild` decision in `DriftDetector._evaluate` requires `divergence > rebuild_jsd_threshold AND sustained_remap` where `sustained_remap = all(r > remap_rate_threshold for r in last-window)` (3 consecutive docs), but the two windowed signals are anti-phase on real ingestion, so the conjunction never trips even at js_divergence 0.5079 (3.4x the 0.15 threshold); R28 free-replay proved a continuous stateful oracle itself fires 0 recure / 0 rebuild (kgf: 17/48 post-cure docs breach remap, 0 three-consecutive breaches), so the rebuild path is dead in practice; cause: conjunctive gate over two anti-phase windowed signals with a 3-consecutive requirement on the noisier (remap) arm; fix pending: replace the boolean AND-gate with the R28-H317 CUSUM change-point statistic over the reconstructed JSD series (fires exactly at the 0.5079 doc AND catches a sub-threshold slow-ramp the boolean structurally cannot); LATENT - harmless on the CPAP corpus (R28-H306/H308: do-nothing-dominates, no material maintenance event to catch) but would also miss genuine drift; `src/knowledge_graph_foundry/drift.py`
>   - 2026-07-09 reported: R28 maintenance round free-replay - the drift-recon cluster reconstructed the DriftDetector window verdict-for-verdict and found the 52-warnings/0-actions pathology is only PARTLY a statelessness bug; even a full-memory continuous run fires 0 rebuild because remap breaches and high JSD never co-occur for 3 consecutive docs (see [experiments R28 free-replay results], H315/H317/H331/H332)

Status: OPEN, one dated note, fix direction = H317 CUSUM (CONFIRMED but not wired).

## 3. Machinery inventory (wired vs dormant)

**Drift detection + rebuild decision engine** - `src/knowledge_graph_foundry/drift.py`
- Signals: per-doc remap_rate (fraction of entities typed outside cured ontology, computed `pipeline.py:827-828`) and JSD between cured type frequencies and merged last-`window` doc frequencies (`drift.py:94-98`)
- Thresholds: `remap_rate_threshold=0.3`, `window=3`, `rebuild_jsd_threshold=0.15` (`settings.py:107-111`)
- Verdict ladder (`drift.py:106-114`): rebuild = `jsd>0.15 AND all 3 consecutive remap>0.3`; recure = sustained remap alone; warn = any single breach. The DEF-9 conjunction is line 106
- WIRED into stable-phase ingest: `pipeline.py:433` (`drift.record_document`), restored/persisted through KGFControl state (`pipeline.py:306-310`, `447-460`); detector serialized via `to_dict/from_dict` (`drift.py:125-141`) - so the window DOES persist in-graph between sessions via the control node, but the ACTION gate never fires (DEF-9)
- Consumption of verdicts: `recure` → `lifecycle.recure()` + `drift.begin_recure()` (`pipeline.py:435-437`). **RECURING is a dead-end state**: in the ingest loop RECURING falls into the `_stable_load` branch (`pipeline.py:416/429`), no code path ever consolidates from RECURING, and `end_recure` has zero production callers (only `tests/test_drift.py:60-65`). `rebuild` is recommendation-only: stored as `drift_verdict` in the control node (`pipeline.py:458`) and rendered by `kgf status` (`cli.py:113-114`). Nothing triggers a rebuild anywhere
- `recure_type_burst=3` (`settings.py:101`) is a DEAD knob - referenced nowhere outside settings (H295's "dead counter")

**Fact-drift alarm (R8)** - `drift.py:53-70` `record_contradictions`: windowed mean of invalidated/entities > `contradiction_rate_threshold=0.2` emits `drift.warning action=fact_drift`. Fed from `pipeline.py:434` ← `_reconcile` (`pipeline.py:831-839`) ← `temporal.reconcile_contradictions`. **Dead in the shipped default**: `load.functional_relationship_types` defaults to `[]` (`settings.py:147`), `_reconcile` returns 0 immediately (`pipeline.py:834-836`), so invalidated is always 0 and the alarm can never fire.

**Bitemporal edges + entity versioning (R1)** - `graph/loader.py`, `graph/temporal.py`
- Every relationship gets `created_at/valid_from=timestamp(), valid_to=null, expired_at=null` on creation (`loader.py:62-65`)
- The ONLY code that ever sets `valid_to` is `temporal.py:22-30` `_RECONCILE` (functional-type supersession, called via `reconcile_contradictions` `temporal.py:46-64`) - and with the default `functional_relationship_types=[]`, **nothing ever sets valid_to in practice**. Renders and propositions filter on `valid_to IS NULL` (`pipeline.py:1157,1168`; `propositions.py:103`) but the filter is vacuous by default
- Entity versioning (`entity_versioning=True`, `settings.py:145`): loader snapshots prior state to `:KGFEntityVersion` via HAD_VERSION ONLY when description grows longer OR a new type label arrives (`loader.py:31-35`, `_VERSION_ACTION` 76-79). Name overwrites (`loader.py:36`) and `prop_*` updates (`SET e += row.props`, `loader.py:44`) are NOT versioned - confirming R17-H167's registered claim at 0% capture for those classes

**Event log** - `src/knowledge_graph_foundry/events.py`: 30+ named blinker signals (list at 17-55) written to append-only JSONL when `Settings.event_log` is set (`events.py:58-98`; enabled per-run by CLI `--events`, `cli.py:24-32`). Consumers: NOTHING in-engine reads it back - it exists for offline forensics (the R28 free-replay notebooks reconstruct all verdicts from these logs). In-process `subscribe()` exists (TUI progress).

**Compaction / idempotency (R15-era)** - **neither exists in code**. `grep compact src/` returns nothing (H160 pending, never built). Idempotency exists only as loader MERGE semantics + resume fingerprints; the H159 "same document twice is a no-op" verdict is pending and unverified. The R28 free-replay note confirms `write_control` is a blind `MERGE ... SET c += $props` clobber point (`graph/metanode.py:49-53`), and `_stable_load` + fingerprint write are separate transactions (H330 kill-gate confirmed).

**Ingest lease** - `graph/lock.py`: single `:KGFLock {id:'ingest'}` node, atomic claim via write-lock probe (`lock.py:19-28`), heartbeat per document (`pipeline.py:442-446`), TTL `lease_ttl_seconds=180`. Mutual exclusion of writers only - no snapshot/quiescence semantics (H335 territory).

**Kill-resume / checkpoint caches at ingest**
- Resume contract: `processed_documents` = set of `name:sha1(content)[:16]` fingerprints (whole file, `pipeline.py:567-572`) or `name#rowN:sha1(row)` (text-heavy structured rows, 555-566), persisted to KGFControl after EVERY document (`pipeline.py:447-460`). An EDITED document gets a new fingerprint and is fully re-extracted - **there is no extraction-result cache at all** (`grep cache extraction/extractor.py` is empty), so no stale-extraction reuse risk; the flip side is zero reuse
- Fluid-phase buffer: pre-cure extractions parked in `buffer_cache` (serialized FluidBuffer) in KGFControl (`pipeline.py:295-300, 452`); a resume mid-cure reuses them. An edited-while-fluid doc re-extracts and ADDS to the buffer; the previous version's buffered entities are not removed
- Embedding cache: in-process dict keyed `(provider, model, entity text)`, 16384 cap (`extraction/embeddings.py:30-34, 176-196`). Text-keyed, so a changed description legitimately re-embeds; process-lifetime only, not persisted
- Document/chunk identity: `document_id = sha1(path.name)` (`readers.py:45-46`) - content-independent; `chunk_id = sha1(doc_id:index:text)` (`models.py:95-98`) - content-addressed. Consequence for re-ingest of an edited file: same KGFDocument node, NEW Chunk nodes for changed text, OLD Chunk nodes remain PART_OF the document forever (never deleted), old MENTIONED_IN edges and `source_chunks` arrays keep pointing at them

**Repair primitive** - `Foundry.repair(question, sources)` (`pipeline.py:574-619`): manual, question-focused re-extraction of named source files into STABLE, bypasses resume fingerprints, regenerates propositions after. Wired to CLI `kgf repair` (`cli.py:194`). This is the "shipped Foundry.repair" H323 references. `repurpose()` (`pipeline.py:177-222`) handles purpose changes with `purpose_history`.

**Offline-only repair prototypes**: `scripts/experiments/r33_h365_repair.py` (fragment PART_OF merge simulation with `h365=true` edge property + unanimous child `prop_*` hoist with `h365_hoisted` key-list marker for rollback, lines 14-19, 58) - applied to the live neo4j4 graph, NOT engine-wired. `graph/aliases.py generate_alias_edges` (SAME_AS writer) has **no in-engine caller** - notebook-only; yet `optimize()`'s demotion court consumes whatever SAME_AS docket exists (`pipeline.py:887-891`, `graph/court.py:86-122`).

## 4. Derived-object invalidation matrix (what happens TODAY)

Preliminary: "entity merge" has two forms - (i) batch merge pre-load (`resolver.py:196-283`, id_map redirects THIS batch's writes to the canonical id) and (ii) stable-phase fold-into-live-node (`pipeline.py:805-808`). Neither form ever touches a previously-loaded node carrying the losing id: entity ids are name-hashes (`models.py:91-93`), so a merged-away name's node, if loaded in an earlier document, **stays in the graph with all its derived objects intact**. There is NO entity-deletion path in the engine except `wipe()` (`pipeline.py:1250-1253`); column (d) is therefore only reachable by manual Cypher.

| Derived object | Derived from | (a) entity merges | (b) description/props change | (c) document re-ingested (edited) | (d) entity deleted (manual) |
|---|---|---|---|---|---|
| **Entity embedding** (`Entity.embedding` property + `kgf_entity_embeddings` index) | entity name+description text at extraction time (`embeddings.py`) | Nothing recomputed. Fold-in keeps the LIVE node's embedding unless the incoming mention carries one - then `coalesce(row.embedding, e.embedding)` OVERWRITES with the new mention's vector (`loader.py:40`) even though the node's (longer, kept) description may not match it | Description kept-longer rule (`loader.py:37-39`) means the stored embedding can describe a text that is no longer the node's description; no re-embed trigger exists anywhere | New mention re-embeds (new text = cache miss) and overwrites; the old vector is simply lost, no version | Vector index entry gone with node; nothing else notices |
| **Proposition nodes + embeddings** (`:Proposition`, content-hash id, ABOUT edges; `graph/propositions.py:84-159`) | current graph state at `optimize()`/`repair()` time: one sentence per valid_to-IS-NULL relationship + one per entity's `prop_*` set | **Nothing invalidates them - proven**: `generate_propositions` only MERGEs NEW hashes; the `existing` set (`propositions.py:122,125`) is used solely to SKIP embedding work. A renamed/merged/changed entity mints new propositions while every stale one stays in the vector index and remains retrievable via `proposition_query` (292-306). No DELETE of :Proposition exists anywhere in src | Same - old property-sentence propositions (e.g. "X - pressure: 4-20.") persist verbatim after the prop changes; both old and new are served | Same - stale sentences from the previous document version persist; quote-propositions (content-hashed chunk sentences) likewise | Node's ABOUT edges go with DETACH; the proposition node itself survives with `entity_ids=[]` and is still retrieved (OPTIONAL MATCH, `propositions.py:299-301`) |
| **Community summaries** (`:KGFCommunity`, `graphrag.py:76-115`) | Leiden `communityId` written to entities at `optimize()` (`graphrag.py:31-73`) | Not touched until the NEXT `optimize()`; then `MERGE (c:KGFCommunity {id}) SET title, summary` (107-113) refreshes summaries for community ids that STILL EXIST, but **KGFCommunity nodes whose community id vanished are never deleted** - `global_summaries` (287-293) serves them indefinitely | Same - summaries are point-in-time LLM text over member names/descriptions; nothing marks them stale between optimize runs | Same | Same; a dead entity's contribution stays in the summary text |
| **SIMILAR_TO edges - creator 1: kNN densify** (`densify.py:19-56`, from `optimize()`) | entity embeddings at densify time, cosine ≥ 0.8 | **Never re-scored, never deleted.** `add_similarity_edges` only counts and MERGEs; an embedding overwrite (see row 1) leaves edges built on the old vector in place. No pruning pass exists (R15-H160 pending) | Same - edge persists even if the new embedding would no longer clear the 0.8 gate | Same; new near-duplicates from the edited doc gain additional edges, old ones stay | DETACH removes edges with the node |
| **SIMILAR_TO - creator 2: defer soft links** (`densify.py:59-82` via `pipeline.py:132-147`, called at cure 724-725 and per stable doc 824-825) | resolver defer decisions + posterior at that moment | Endpoints are remapped through the id_map at write time (`pipeline.py:142-144`), but an EXISTING soft link between two entities that later merge into one live node is never removed (only same-id pairs are filtered pre-write). `ON MATCH SET weight` updates only if the SAME pair defers again | Posterior weight goes stale; refreshed only on a re-defer of the identical pair | Same | DETACH |
| **SIMILAR_TO - creator 3: court demotions** (`court.py:74-83`) | judged-false SAME_AS edges; weight = Bayesian posterior at demotion time | Demotion is terminal: SAME_AS deleted, soft link written; no path re-promotes or re-judges | Weight never recomputed | Same | DETACH |
| **SAME_AS / alias edges** (`aliases.py:159-206`, notebook-only writer; consumed by render `pipeline.py:1181-1186` and court) | deterministic text evidence (chunk text, names, model codes) at audit time | `MERGE ... ON CREATE SET method, evidence` (`aliases.py:194-196`) - **evidence never refreshed**; a merge that unifies the endpoints leaves a self-referential-cluster edge in place | No re-audit trigger; edges reflect the chunk text of whenever the audit last ran | New chunks are not re-audited automatically (no in-engine caller); old edges persist against old chunk evidence | DETACH; court docket shrinks silently |
| **Hoisted props (`h365_hoisted` markers)** (`scripts/experiments/r33_h365_repair.py:58`, offline) | unanimous child-model `prop_*` values at script run time | Nothing recomputes the hoist if children merge or change; the marker lists hoisted keys for MANUAL rollback only (script docstring lines 14-19) | A child prop value change breaks unanimity retroactively - hoisted copy on the parent is now unverifiable and stays | Same | Hoisted copies survive child deletion with no provenance path back |

Additional stale-surface facts for (c): entity `source_chunks`/`source_documents` arrays are set-unioned forever (`loader.py:41-42`), so they accumulate ids of chunks that no longer correspond to current text; relationship `prop` descriptions keep-longer (`loader.py:66-68`), so a shortened/corrected description in the edited doc loses to the old longer one; entity `prop_*` keys overwrite on collision but orphaned keys from the old version persist (`loader.py:44` is additive `+=`). Bottom line the round should register against: **the only refresh mechanism for ANY derived object is "run optimize() again and hope MERGE-by-stable-id overwrites"; deletion/invalidation of derived objects exists nowhere.**

## 5. Config knobs (settings.py)

| Knob | Default | Line | Governs |
|---|---|---|---|
| `drift.remap_rate_threshold` | 0.3 | 108 | warn/recure remap arm |
| `drift.window` | 3 | 109 | consecutive-doc window (both arms) |
| `drift.rebuild_jsd_threshold` | 0.15 | 110 | DEF-9 rebuild conjunction |
| `drift.contradiction_rate_threshold` | 0.2 | 111 | R8 fact-drift alarm (dead by functional-types default) |
| `curing.recure_type_burst` | 3 | 101 | DEAD - referenced nowhere |
| `curing.missing_mass_threshold` / `missing_mass_z` | 0.05 / 1.64 | 99-100 | Good-Turing cure gate |
| `curing.max_fluid_documents` | 100 | 96 | force-cure backstop |
| `load.entity_versioning` | True | 145 | KGFEntityVersion snapshots (desc/label only) |
| `load.provenance_nodes` | True | 146 | Chunk+Document nodes, MENTIONED_IN |
| `load.functional_relationship_types` | `[]` | 147 | ONLY path to valid_to; empty = bitemporal invalidation dead |
| `lease_ttl_seconds` | 180 | 151 | ingest lease staleness |
| `resolution.soft_links` | True | 84 | defer-zone SIMILAR_TO materialization |
| `resolution.demotion_court` | True | 85 | SAME_AS docket adjudication at optimize |
| `resolution.calibration_path` | None | 86-88 | per-corpus isotonic artifact (None = raw posteriors; DEF-10 context) |
| `resolution.identity_stack` | "v1" | 77-79 | v1/v2 stack (R29 NO-GO keeps v1) |
| `graphrag.similarity_edges_enabled` / `similarity_threshold` / `similarity_top_k` | True / 0.8 / 5 | 138-140 | kNN SIMILAR_TO creator |
| `graphrag.propositions_enabled` / `proposition_index_name` / `proposition_split_max_tokens` | True / kgf_proposition_embeddings / 300 | 130-132, 126 | proposition layer |
| `graphrag.community_min_size` | 3 | 115 | community summaries |
| `extraction.union_k` | 1 | 52 | R31-H349 union passes (refuted; default stands) |
| `extraction.document_concurrency` | 1 | 51 | R30 cross-doc look-ahead |
| `extraction.recipe` | "enumerate" | 58-60 | shipped extraction recipe |
| `event_log` | None | 168 | JSONL event sink path |

## Novel-ground summary for a new maintenance round

Already claimed and must not be re-registered: CUSUM drift trigger (H317), rel-entropy monitor (H299), posterior-calibration drift (H300), MetricSnapshot ledger + trajectory-vs-state (H315/H331/H332/H333), targeted-vs-rebuild economics (H311/H313/H314), lease-vs-CAS actuation (H324/H334), quiescence + wave-seal (H330/H335/H339), provenance stamps/DERIVED_FROM/provenance_kind (H325-H329), Gap/Demand nodes + repair-provenance ledger (H320/H321/H322), single re-derivation primitive (H323), in-graph answer cache + calibration persistence (H336/H337/H338), concurrency exactly-once (H316/H318), plus the pending R15-R17 slate (idempotent re-ingest H159, compaction H160, gap-ledger abstention H161, retraction H162, supersession H163, concurrent ingest H164, injection H166, version capture/order/attribution/history H167-H170) and R26 H271/H272/H274, and R33-H365 fragment-merge/spec-hoist engine wiring. Genuinely open ground the code audit exposes that no hypothesis yet names directly: **derived-object invalidation as a class** (the entire §4 matrix - stale propositions, stale community summaries, never-re-scored SIMILAR_TO, embedding/description divergence after keep-longer merges, stale-chunk accumulation on document re-ingest), **the RECURING dead-end** (recure verdict flips the FSM but no consolidation path exists; `end_recure` has zero production callers), and the **dead-by-default fact-drift alarm** (functional_relationship_types=[]).
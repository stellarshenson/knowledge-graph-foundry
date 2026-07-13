# R36 replay-arm execution summary (H377 / H378 / H379) - 2026-07-12

Executor run of the three outstanding R36 verdicts: the H379 replay arm, the H377
revalidation A/B on H376's dirty set, and the H378 end-to-end induced-drift replay
(DEF-9's workstream). All adjudication is against the registered acceptance bars in
`docs/experiments/kgf-redesign-experiments.md` (R36 section).

## H379 - resurrect the dead fact-drift alarm (replay arm): PARTIAL

Report: `reports/experiments/adjudicated/r36-h379-replay-20260712T104736Z.json` (script `scripts/experiments/r36_h379_replay.py`, log `logs/r36-h379-replay.log`)

- **Clause A mechanics PASS** - with `functional_relationship_types=[MANUFACTURED_BY]`
  (the inference arm's 0.90-tier candidate), a conflicting second value drives the real
  `reconcile_contradictions` end-to-end on marked synthetic nodes: superseded edge gets
  `valid_to` + `expired_at`, the `fact_supersession` event fires, `current_relationships`
  returns only the v2 target, history keeps both versions (invalidate-never-delete holds)
- **Clause A alarm FAIL** - the R8 windowed fact-drift alarm does NOT fire on a faithful
  two-version doc replay: re-versioning the SleepStyle manual with EVERY manufacturer
  changed (acquisition scenario, production `_RECONCILE` Cypher in a rolled-back
  transaction) invalidates 8 edges over 148 doc entities = contradiction rate 0.0541,
  while the alarm form (window-3 mean > 0.2) needs a single-doc rate of 0.6 - an ~11x
  threshold-form mismatch; even a sustained 3-doc re-version series at pile-realistic
  rates stays silent. Same defect anatomy as DEF-9: a windowed threshold alarm
  unreachable at the signal scale the graph actually produces
- **Clause B PASS** - zero false gold invalidation: simulating functional discipline over
  the whole pile would invalidate 70 MANUFACTURED_BY edges (all duplicate-target fanout,
  H107-class identity noise like `AirSense 11 -> Resmed` vs `ResMed`), and OUT-labeling
  all 70 from the render leaves the 24-probe harness bit-identical (mean 0.8958, zero
  per-probe regressions); no gold string names an invalidated target. The registered
  REFUTED trigger (gold edge falsely invalidated → typing stays manual) did NOT fire
- **Verdict PARTIAL** - the invalidation machinery is resurrected and safe with the
  inferred `{MANUFACTURED_BY}` set (supersession event fires per-invalidation), but the
  registered "alarm fires" clause fails as-shipped: `contradiction_rate_threshold=0.2`
  over a 3-doc window is miscalibrated for single-doc supersession events. Defect-class
  finding for the coordinator: the R8 alarm needs either a per-event supersession alarm
  (the `fact_supersession` emission already carries it) or a threshold in
  events-per-window units, not entity-mass share

## H377 - revalidation, not regeneration: PARTIAL

Report: `reports/experiments/adjudicated/r36-h377-revalidation-20260712T110540Z.json` (script
`scripts/experiments/r36_h377_revalidation.py`, log `logs/r36-h377-revalidation.log`)

- Setup: real v2 of the SleepStyle manual (17 spec-value edits across 4 of 8 chunks),
  48 dirty descriptions sampled from H376's E2 dirty set (stratified 27 single-doc /
  21 multi-doc), gate arm (entailment keep/regenerate) vs reference arm
  (regenerate-and-compare with an equivalence judge), all on gpt-oss-120b local
- **Agreement 87.5%** - above the 80% reliability floor (the named REFUTED branch does
  not fire), below the 90% bar. Errors: 5 missed-stale (gate keeps, reference
  regenerates), 1 over-invalidation. 22 keep/keep + 20 regen/regen
- **Rescued 56.25% PASS** (>= 50%) - most dirty objects survive their trigger, the
  semantic-early-cutoff premise holds
- **Cost clause FAIL, and INVERTED** - gate cost is ~1.0x a single description regen
  (prompt tokens dominate both calls: 88,992 vs 88,822 total tokens) and **5.2x MORE
  expensive** than the engine's actual regeneration unit (chunk re-extraction amortized
  over the chunk's dirty objects: 43,698 tokens / 8 chunks covering 28-47 objects each).
  The literature's 10-100x revalidation saving assumes per-object regeneration;
  KGF regenerates per CHUNK, which batches the cost below per-object entailment
- **Verdict PARTIAL** - the gate is reliable enough to not be theater (87.5%) and most
  objects are rescuable, but the registered cost premise is inverted on this engine:
  for chunk-sourced derived objects the honest policy is invalidate-eagerly +
  regenerate-the-dirty-chunk, not per-object revalidation. Per-object revalidation only
  pays for objects with NO cheap batch generator (post-H371 question nodes may be that
  class - their generator is per-object)
- Caveat: source shown to both arms capped at 6,000 chars; 11/48 references were
  "entity not in shown source" (mostly generic component entities). Both arms saw the
  identical truncated source so the A/B is internally consistent, but rescued fraction
  is somewhat truncation-depressed

## H378 - wire the drift trigger + RECURING exit, end-to-end replay (DEF-9): CONFIRMED

Report: `reports/experiments/adjudicated/r36-h378-drift-replay-20260712T110305Z.json` (script
`scripts/experiments/r36_h378_drift_replay.py`, log `logs/r36-h378-drift-replay.log`)

- Engine wiring pre-existed from the 2026-07-10 tranche (CUSUM in
  `DriftDetector._cusum_evaluate` behind `drift.cusum_enabled`, RECURING exit in
  `pipeline.py` - `end_recure`'s first production caller); this run supplied the
  registered end-to-end replay, no new src changes needed
- Replay: real pipeline (`Foundry.ingest` -> `_stable_load` -> detector -> FSM ->
  `adopt_drifted_types` -> `end_recure`) on a throwaway scratch Neo4j
  (kgf-h378-scratch), scripted extraction stream of 12 docs: 4 stationary, 5 drifted
  (anti-phase register: per-doc remap 0.25-0.29 BELOW the 0.3 boolean threshold),
  3 post-exit
- **All registered clauses PASS**: CUSUM fires exactly at drift onset (S 0.311 > h 0.30,
  JSD 0.331, mu0 0.0); FSM walks STABLE -> RECURING -> STABLE; `AlienDevice` adopted
  into the cured ontology; post-exit remap collapses to 0.0 and the same register never
  re-alarms (livelock guard); the control arm (shipped boolean) fires NOTHING on the
  identical stream - the DEF-9 anti-phase anatomy reproduced end-to-end; 24-probe
  harness on the untouched live pile bit-identical before/after (mean 0.8958)
- **REFUTED-as-designed branch did not trigger**: consolidation = 3 window docs +
  0 LLM calls + one ontology adoption write = 0.25 of the 12-doc rebuild (patch tier,
  not rebuild theater)
- **DEF-9 closed** (dated note in `docs/defects/defects.md`); `drift.cusum_enabled`
  stays default-off pending the coordinator's promote decision

## Execution notes

- Live pile (neo4j4, 172.19.0.100) write discipline: only 3 marked synthetic nodes
  created and deleted (H379 micro-replay); the pile-scale reconcile ran in a rolled-back
  transaction; census before/after identical (valid_to count 0, MANUFACTURED_BY 694)
- Scratch container `kgf-h378-scratch` (neo4j:5.26.0 + apoc, hub network) removed after
  the run; to re-run the replay, recreate it (`docker run -d --name kgf-h378-scratch -e
  NEO4J_AUTH=neo4j/kgfoundry -e 'NEO4J_PLUGINS=["apoc"]' -e
  NEO4J_server_memory_heap_max__size=1g -e NEO4J_server_memory_pagecache_size=512m
  neo4j:5.26.0`, attach to the hub network, update `SCRATCH_URI` in the script)
- Test suite: 469 passed, 18 skipped, 1 pre-existing environment flake
  (`test_cli.py::test_query_prints_answer` fails only when rich emits ANSI color codes;
  passes with `NO_COLOR=1`; no src changes in this run)

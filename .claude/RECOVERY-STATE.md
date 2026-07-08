# Recovery State - live board snapshot

**Purpose**: if the session dies (limits, crash), a restored session reads THIS FILE FIRST (after JOURNAL.md) and picks up every stream. The compute layer runs as detached OS processes with disk checkpoints - it survives session death; only the *recording and relaunch* duties need the restored session. Updated 2026-07-08 ~05:05 UTC (post-outage recovery pass).

**Board delta at last update**: H119 COMPLETE and RECORDED (REFUTED, commit 4001772) - stream 1 below is CLOSED. H212 ingest DONE (rc=0, quiet Bedrock); finisher agent measuring against neo4j4. R22 CPU tier respawned (first executor died at limits pre-notebook). R22 LLM gates + H229 executor launched (vLLM free post-H119). H157 at 21/30 papers, accelerating. Pending recording: H212, R22 CPU tier (7 verdicts), H229 + 3 gates, H157.

## Standing rules (binding)

- Verdicts recorded ONLY by the main session in `docs/experiments/kgf-redesign-experiments.md` (append Result/Verdict to the registered section; never rewrite recorded verdicts). Promotions -> `docs/sota-promotions.md`. Journal via `/journal:update` + `journal-tools check` (0 errors bar). Checkpoint commits authorized; push after commits (user directed sync tonight).
- Standing directive: every finding that raises questions -> register a new hypothesis before moving on.
- Corpus framing: technical benchmark document set; technical vocabulary only.
- Executors: Opus agents, primed with full spec, "BUDGET DISCIPLINE: lean tool output". Never re-spawn a dead agent whose detached job still runs - check disk state first.
- Instances: default .env = H157 papers scratch (LIVE, do not touch); neo4j2 172.19.0.9 = READ-ONLY reference; neo4j3 = frozen wave-2 scale artifact (952 docs/4649 entities); neo4j4 172.19.0.4 (container user-konrad.jelen-kgf-neo4j4, auth neo4j/kgfoundry) = H212 scratch.

## Live streams (check in this order)

### 1. H119 extraction determinism - detached nbconvert, self-reporting
- Process `pgrep -f extraction_determinism_h119` (was pid 2789003). Checkpoints `results/h119/` (was 101/150; arms A+B complete, C running).
- DONE when `reports/extraction-determinism-h119-*.json` exists; the notebook computes verdict itself.
- **Preview already computed (main session, frozen metrics): heading for REFUTED** - A JD 0.749, B 0.822 (reduction -9.7% vs >=50% bar), B retention 69.2% exact / 89.7% fuzzy (vs >=95%). Arm C = noise-floor cross-check (expect C ~= A).
- On report: record verdict in ledger section R11-H119 (cite preview + report), promotion entry (the 0.749 baseline nondeterminism finding + refutation consequences: resolver keeps identity burden -> H212 criticality), journal entry, commit+push. Strategic note: six-way convergence on extraction stands as DIAGNOSIS; the in-prompt cure is dead; R22 tests the alternatives.
- If process dead without report: relaunch resumes from checkpoints:
  `.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/extraction_determinism_h119.ipynb --ExecutePreprocessor.timeout=43200 --ExecutePreprocessor.kernel_name=python3 >> logs/h119-nbconvert.log 2>&1`
  (Known crash mode: instructor RegistryError = DEF-6; the notebook already carries the explicit-import fix.)

### 2. H157 corpus transfer - detached retry launcher + resumable ingest
- Launcher `pgrep -f h157_launch.sh`; script at scratchpad `h157_launch.sh` (25 retries). Ingest log `logs/h157-corpus-transfer.log` (INGEST_OK on success); events `logs/h157-events.jsonl` (7+/30 papers done; kill-resume safe).
- If both launcher and ingest dead without INGEST_OK: rerun the launcher script (it resumes processed documents).
- After INGEST_OK: the ANALYSIS phase needs an agent - resume parked agent or spawn fresh with: read R15-H157 registration + notebooks/corpus_transfer_h157.ipynb + scratchpad h157_export.py plan; blind-label ~60 candidate pairs (H101 protocol), compute ECE vs identity-calibration-v2.json reference, lifecycle clause from events log; report reports/corpus-transfer-h157-*.json; then main session records.

### 3. H212 clean-conditions recall - agent running (NOT outage-proof)
- Target neo4j4 172.19.0.4:7687 (empty scratch). Expected artifacts: config-h212-v2.yml, logs/h212-clean-recall.log, notebooks/clean_recall_h212.ipynb, reports/clean-recall-h212-*.json.
- If agent died: check the log/report state; if ingest completed, spawn a finisher agent to measure (H158 harness: notebooks/h158_measure.py); if nothing started, respawn with the R15-H212 registration + fresh-instance details above. Bar: failed chunks <= 76 AND recall@16 >= 0.875 -> H158 lifts to CONFIRMED, v2 default flip approved (feeds H198).
- H213 (defer judge) runs after H212 on the same scratch graph.

### 4. R22 CPU tier (H230/231/234/235/236/237/238) - agent running (NOT outage-proof)
- Expected: notebooks/failure_mechanism_r22.ipynb, reports/failure-mechanism-r22-*.json, logs/r22-cpu-tier.log.
- If agent died: work is pure CPU on frozen artifacts - respawn with the R22 registrations verbatim; no state to lose beyond partial notebook.
- LLM gates queued behind H119 completion (idle vLLM): H232 (1 doc x 3 seeded-serial runs), H233 (1 doc x 3 guided-JSON runs), H239 (1 doc x 3 runs on a second model, GPU 0/2). H229 (serial variance floor) also runs then - same executor can take all four gates.

## Recording queue (verdicts pending executor reports)
- H119 (report imminent) - see stream 1.
- H212 - see stream 3.
- R22 CPU tier - seven verdict recommendations expected in one report.
- H157 - after ingest + analysis.
- R21 next tier (H218 describe-then-extract on GPU 2, H224 decorative filter) - launchable when a slot frees; H219/H220/H221/H222 sequenced behind H218; H223 behind H220; H225 last.

## After the recording queue drains
Critical path: H119 verdict -> R22 cures adjudicated -> H198 wiring sweep (registered; includes DEF-6 fix, v2 default if H212 passed, promoted levers composed) -> full re-ingestion on the fixed engine -> H113-H117 head-to-head on benchmark v2 under the pinned H207 harness.
User-gated only: H202 (deferred), further corpus decisions.

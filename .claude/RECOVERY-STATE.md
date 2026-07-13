# Recovery State - live board snapshot

**Purpose**: if the session dies, a restored session reads THIS FILE FIRST (after JOURNAL.md) and picks up every stream. Detached compute survives session death; only recording/relaunch duties need the restored session. Updated 2026-07-08 ~08:20 UTC.

**Board delta at last update**: RECORDED - H229 package (H229 refuted, H232/H233 closed, H239 GO recall-gated, H249 refuted; vLLM FREE), H157 (CONFIRMED; ECE breaks 5.18x -> self-calibration to H198), R26 full round (H271 CONFIRMED 1.7-16.4x, H274 CONFIRMED+PREFERRED over H273, H275/H276/H277 REFUTED, H278 PARKED; ships H271+H274), R25/R26 first gates (H267 REFUTED 4.5%, H268 CONFIRMED 64.7% -> H198, H269 rejected, H279 staleness 9.5%/2.05x). REGISTERED: R27 agentic escalation (H281-H290); **H286 web arm USER-GATED - exhaust non-web paths to SOTA first**. LLM TIER LAUNCHED.

## Standing rules (binding)

- Verdicts recorded ONLY by the main session in docs/experiments/kgf-redesign-experiments.md (append-only; supersede via post-verdict notes). Promotions -> docs/sota-promotions.md. Journal via /journal:update + journal-tools check (0 errors). Checkpoint commits + push authorized.
- Every finding that raises questions -> register a new hypothesis before moving on.
- Corpus framing: technical benchmark document set; technical vocabulary only.
- Executors: Opus agents, full spec, "BUDGET DISCIPLINE: lean tool output". Never respawn a dead agent whose detached job still runs - check disk first.
- Instances: default .env = papers graph (H157 done, but R26 noted concurrent ingest - treat as live); neo4j2 172.19.0.9 READ-ONLY reference; neo4j3 frozen scale artifact; neo4j4 172.19.0.4 = H241 executor's scratch NOW IN USE (auth neo4j/kgfoundry).
- vLLM localhost:8010 is FREE-shared: H241 + R23/R24 batch executors both use it (concurrent OK, H229 exclusivity ended).
- USER GATE: no web-search arms (H286 and any web tool) until the user re-opens; achieve SOTA on in-corpus paths first.

## Live streams (all Opus executors, NOT outage-proof - respawn from specs if dead without report)

### 1. H241 identity v1/v2 A/B - gates the v2 default flip
- neo4j4 scratch (wipe allowed), vLLM extraction, paired arms. Expected: notebooks/identity_ab_h241.ipynb, reports/experiments/adjudicated/identity-ab-h241-*.json, logs/h241-ab.log. On report: record; if GO flip resolution.identity_stack default in H198; then launch H240(b) union arm on neo4j4.

### 2. R23/R24 LLM gates batch - undersampling remedies
- Order: H246 enumerate, H248 GLiNER-primed pass, H243 complement, H258 mention-emission, H251 n-sampling, H245+H257 logprobs, H260 adjudication, H261 distillation. Checkpoints reports/experiments/r23r24_llm/. Expected: notebooks/undersampling_llm_gates_r23r24.ipynb, reports/experiments/adjudicated/undersampling-llm-gates-r23r24-*.json, logs/r23r24-llm-gates.log. On report: record + launch H250 cost frontier (names the H198 extraction recipe).

### 3. R27 precision arms - H282/H283/H284/H285/H289 re-scoped executor
- H288 RECORDED (REFUTED - merge-over-soft delta 0.0 pts; recall agentics dead) + H281 RECORDED (CONFIRMED - 85.6% cheap-decidable, web class 1.1%). Round re-scoped to identity PRECISION: false-merge removal at zero true-merge loss on the SAME_AS surface (57 type-conflict + 64 code-shared + 3 P10 pairs, enumerated in reports/experiments/adjudicated/agentic-escalation-gates-r27-20260708T082438Z.json).
- Executor running: labels frozen blind first, then single-shot control / tool-agent K=4 / no-tools + fetch-then-judge / effort sweep / Strands tax. Expected: notebooks/agentic_precision_arms_r27.ipynb, reports/experiments/adjudicated/agentic-precision-arms-r27-*.json, logs/r27-precision-arms.log, reports/experiments/r27_precision/. On report: record, then compose H287+H290 (free replay arithmetic).

### 4. R21 image tier - H218 VLM contest + H224 decorative filter
- Running (logs/r21-qwenvl-infer2.log, smolvlm download seen). Expected: notebooks/image_vlm_gates_r21.ipynb, reports/experiments/adjudicated/image-vlm-gates-r21-*.json, logs/r21-vlm-gates.log. H218 extraction clause queued behind LLM tier.

## After the streams drain
1. H240(b) union-of-2 ingest arm on neo4j4 (after H241) -> H250 cost frontier -> H198 extraction recipe named
2. H272 abstention-triggered repair (rides H252 micro-pass machinery), H270 schema-as-graph (scratch after H241), H264 (rides H239 artifacts), H280 composition (needs H272)
3. R27 LLM arms if H288 clears (H282-H285, H287, H289, H290 - web arm stays user-gated)
4. H198 wiring sweep (DEF-6 fix, v2 default if H241 GO, extraction recipe from H250, H238 retention pricing, GLiNER lexicon stage, H268 soft links, H271 demand allocator, H274 external cache, per-corpus self-calibration from H157, truncation-resilient parsing + confidence rubric from R25) -> full re-ingestion -> H113-H117 capstone under pinned H207 harness. User-gated: H202, H286/web, corpus decisions.

## BRACE 2026-07-08 ~12:55Z - credits ran out mid-recovery

**vLLM (port 8010) is DOWN** - external SIGTERM 12:20:29Z (unattributed), then 3 failed relaunch attempts (JIT traps, all root-caused).
FIRST ACTION next session: purge poisoned JIT cache + relaunch via `bash scripts/vllm-serve.sh` (correct CUDA_HOME = vllm venv's own nvidia/cu13; full trap writeup in `~/.claude/skills/my-gpu/issues/2026-07-08-vllm-restart-jit-traps.md`):
  rm -rf ~/.cache/flashinfer/0.6.12/120f/cached_ops/sampling && bash scripts/vllm-serve.sh
Health check: curl -s http://localhost:8010/v1/models (200 = up; engine init ~3-5 min incl JIT).

**Then everything self-heals, already armed detached:**
- `scripts/experiments/h241_v2_rerun.sh` (running, polling health): wipe neo4j4 -> v2 arm -> measure -> touches logs/h241-chain.DONE
- Batch driver run_batch.py PID 3262792 is SIGSTOPped - after vLLM healthy: `kill -CONT 3262792` (finishes H261 + report reports/experiments/adjudicated/undersampling-llm-gates-r23r24-*.json; autorender2.sh then executes the notebook)
- If those PIDs/scripts died: caches in reports/experiments/r23r24_llm/ (h246/h248/h243/h251/h245_257/h258/h260 all cached), only h261+report remain

**Valid results on disk (do NOT recompute):**
- v1 arm VALID: reports/experiments/adjudicated/h241-v1-recall.json + h241-v1-stats.json - recall 0.7708 (17/24), precision 0.083 (11 false merges), 2727 entities, fp bc194b65b08137bf, wall 14439s
- v2 first attempt INVALID (ran against dead server): quarantined in reports/experiments/invalid/ - must NOT be used
- Batch verdicts cached: H246 0.971@1.05x, H258 1.000@1.53x inflation, H248 0.943, H251 0.912@3.05x indep=1.000, H243 comp_new=0, H245 sep=0.0066, H260 adjudicated_cov=0.873
- Confound record for H241 verdict: v1 had 6 timeout losses under batch contention (pre-11:55Z pause); v2 rerun runs post-outage - note conditions in verdict

**Wiring tranche 1 READY** in worktree agent-aea0ebaec7aac3122 (uncommitted, base 0735aac) - merge after chains release tree (see docs/h198-wiring-plan.md).
**Pending recordings**: R23/R24 round close (all verdicts above + H261 + H250 frontier -> SLOT-2), H241 verdict -> SLOT-1, journal entries, promotions.

## BRACE 2026-07-10 ~16:05Z - session horizon unknown

Supersedes the 2026-07-08 section where they conflict. Active /goal: fix DEF-8..DEF-13 fixes-first with measured verdicts. Standing directive (2026-07-10): NO Titan for new bulk embedding compute - local GPU models (bge-m3 on GPU idx 2), configurable providers; spec = docs/acc-crit-kgf.md "Embeddings" section (10 criteria). Entity-channel QUERY embedding stays Titan only because the live entity index is Titan-space (fixed control arm). Executor model for this campaign: Fable ("fable" in agent model opts).

**RUNNING (detached, survives session death):**
- H363 clean GPU ramp: PID 46692 (setsid, sid=46692), `scripts/experiments/r30_gpu_ramp.py`, log `logs/r30-h363-ramp.log`. STEP c=16 done: 1.55 chunks/min, 520.3 tok/s total (309.2 gen), hidden_attempts=0, errors=0, peak run/wait 16/0 (single-attempt regime confirmed). c=24 mid-window; rungs 32/48/64/96 remain; ~20:30-21:00Z finish. Holds GPU 1 (PRO 6000) + vLLM :8010. On completion: record H363, fit H347 knee offline, seed first H362 cache entry, then H343/H345 (task #58 remainder)
- Nothing else runs. H366 COMPLETED (below).

**DONE - PENDING VERDICT RECORDING (first analysis duty of next session):**
- R34-H366 passage-node prototype COMPLETE: `reports/experiments/adjudicated/r34-h366-passages-20260710T154339Z.json` (log `logs/r34-h366-passages.log`). M=0 reproduced baseline EXACTLY (0.8542, 20/24 - control valid). M=1: mean 0.9583, 23/24 fully covered, ctx growth +78%; M=2/M=4 identical recall at +160%/+321% growth. Registered bar was "P21+P22 flip, zero regressions, <=30% ctx growth" - recall part massively exceeded at M=1, ctx-growth clause EXCEEDED (78% > 30%). Verdict must weigh the clause honestly (partial pass / confirmed-with-caveat per per-probe diff in the report). Chunk embedding cache: `results/r34/h366-chunk-embs-bgem3.jsonl` (bge-m3, 247 chunks, reusable for H367/H371+)
- Maintenance research (R36 inputs) BOTH LANDED, persisted to disk:
  - `reports/experiments/adjudicated/r36-maintenance-literature-brief-20260710.md` (external literature: IVM/DRed/TMS, EraRAG, Mem0, A-MEM, sleep-time, Drift-Adapter, Memory-Worth; five proven-novel open slots; 5 new papers archived to references/papers/)
  - `reports/experiments/adjudicated/r36-maintenance-internal-map-20260710.md` (cartographer, recovered verbatim: R28 fence H293-H339, DEF-9 = H317 CUSUM confirmed-not-wired, RECURING dead-end end_recure zero callers, functional_relationship_types=[] -> valid_to never set, derived-object invalidation matrix = nothing invalidates anything)

**Recorded earlier today (already in canonical docs, do NOT redo):** H364 CONFIRMED (resolution_loss 83.3%, ranking zero) + H365 CONFIRMED (prototype repair: 0.7917 -> 0.8542, P09/P16 flipped, 22 flat) in docs/experiments/kgf-redesign-experiments.md; DEF-13 dated notes in docs/defects.md; R34 (H366-H370) + R35 (H371-H375) registered; journal entries 192-194; acc-crit Embeddings section added.

**Graph state neo4j4 (bolt://172.19.0.4:7687, neo4j/kgfoundry):** layered pile 5213 ents/23472 rels WITH H365 repair applied (additive, marker `e.h365_hoisted`, edges `PART_OF {h365:true}`; rollback in scripts/experiments/r33_h365_repair.py docstring). Fresh baseline pair: pre-repair 0.7917 (reports/experiments/adjudicated/h364-fresh-recall-20260710T135437Z.json), post-repair 0.8542 (reports/experiments/adjudicated/h365-repaired-recall-20260710T143152Z.json). The old h212-v2 recall map is STALE - never diff against it.

**FIRST ACTION next session:** read this section, then (1) record the H366 verdict in docs/experiments/kgf-redesign-experiments.md against its registered bar (numbers above, per-probe diff in the report JSON), (2) check `logs/r30-h363-ramp.log` - if finished, record H363 + knee fit, (3) register R36 (maintenance of derived objects) from the two reports/experiments/adjudicated/r36-*.md briefs - fence against R28/R15-R17/R26, claim: derived-object invalidation as a class, RECURING dead-end, dead fact-drift alarm, maintenance of NEW R34/R35 objects; give DEF-9 its workstream (wire H317 CUSUM). Then continue task #70 (H367/H369/H370 prototypes; H370 retro-arm needs temporary H365 rollback) and #71 (R35, generation post-H363). Journal entry for maintenance-research + acc-crit + H366 still owed (via /journal:update only).

**Task list**: cleaned 2026-07-10 (43 completed deleted); live: #70 R34 prototypes (in_progress), #71 R35, #66 H363 ramp, #69 wire H365 into engine, #58/#62/#64/#49-#53/#56/#59.

---

# BRACE 2026-07-11 (session end after docs consolidation; user order: let the GPU finish, pick up on return)

**RUNNING - detached, DO NOT KILL:** H363 ramp, pid 46692 (PPID 1, disowned, 9h21m up), `scripts/experiments/r30_gpu_ramp.py`, log `logs/r30-h363-ramp.log`. Closed rungs: c=16 520.3 / c=24 533.1 / c=32 612.3 tok/s - knee NOT reached, throughput still climbing. c=48 window filling; rungs 48/64/96 remain; the script checkpoints STEP lines to the log and writes its own report on completion. The session-owned watcher (grep loop) dies with this session - irrelevant, just tail the log.

**DOWN / needs restart:** nothing.

**VALID ON DISK (all pushed to origin GitLab, HEAD b8a11f7):**
- `2f6202a` - H365 spec-hoist engine wiring (`graph/hoist.py`, `resolution.spec_hoist` default off) + H378 CUSUM/RECURING exit (`drift.cusum_enabled` default off) + R35/R36 verdicts: H376 CONFIRMED, H380 REFUTED (harness density), H375 REFUTED (contamination caught - pre-repair arm decisive, Hawkins retired), H374 deferred to precision arm. 437 unit + 10 live integration green. Reports `reports/experiments/adjudicated/r35-*`, `reports/experiments/adjudicated/r36-*`
- `b8a11f7` - docs consolidation: `@archive/` gains sota-decision, h198-wiring-plan, DESIGN; `docs/defects/defects.md`, `docs/acceptance-criteria/acc-crit-kgf.md`; `api.md` REMOVED (rewrite post-RC from `scratchpad/api-md-audit-findings-20260710.md`); usage-scenarios PPR fix; gap-ledger audited current
- Journal at entry 207, `journal-tools check` 0 errors

**NOT COMMITTED (deliberate):** `models/qwen2.5-7b/` (4.4G), `results/r34/h366-span-embs-bgem3.jsonl` (145M) + `h367-prop-embs-bgem3.jsonl` (230M) (LFS pending user), `scratchpad/build_r24c*.py`.

**PENDING USER DECISIONS:** GitHub remote 4 commits behind GitLab origin; LFS for the two >100MB caches; #56 enhancements doc plan is v1-stale - re-scope or drop.

**PENDING WORK (post-H363 queue, in order):** H363 verdict + H347 knee fit + H362 cache seed (#64) + H343/H345 (#58); then LLM-gated: H385 answer side + optimize() refit hook (#74), H382 self-report rider (#73), H377 + H378 induced-drift replay (closes DEF-9) + H379 replay arm (#72), H371-H373 generation + H374 precision arm (#71), R31 H349/H352 (closes DEF-11) (#62), DEF-13 cures. Chained: H381 on H373; H387/H368/NV-Embed-v2 parity on the #59 second corpus. Open flag: rung-1 additive-vs-displacement parity needs a proposition index on the pile - engine prop index is Titan space, conflicts with the no-Titan-bulk rule.

**FIRST ACTION next session:** tail `logs/r30-h363-ramp.log` and `ps -p 46692`. If new STEP lines landed (c=48+): collect them; if the ramp finished all rungs or died: record the H363 verdict + H347 knee fit in `docs/experiments/kgf-redesign-experiments.md`, seed the H362 throughput-cache entry, then start the post-H363 LLM queue above. If still running: the user directive stands - wait on the GPU, execute only non-GPU work.

## BRACE 2026-07-12 18:11Z - server restart

**HORIZON: SERVER RESTART** - host going down; EVERY job dies (detached included). Relaunch all from the commands below; do not look for surviving PIDs.

### Running at brace (all WILL be killed; value already on disk)
- **vLLM gpt-oss-120b** pid 5816 (8h19m) - stateless, no data loss. Relaunch: `scripts/vllm-serve.sh` (serves :8010; WSL pin-memory flag inside script). Token ledger banks per instance - snapshot after restart: `.venv/bin/python scripts/token_ledger.py` (NEVER --help)
- **Progressive prober** pid 7778, `scripts/bench_progressive_probe.py` - checkpoints incrementally to `reports/experiments/bench/progressive-probe-trajectory.jsonl` (2,443 rows, last cycle 18:05Z on disk; zero loss). Relaunch AFTER vLLM + neo4j3 are up: `setsid nohup .venv/bin/python scripts/bench_progressive_probe.py 2>&1 | tee -a logs/bench-progressive-probe.log &`
- **Scout throwaway Neo4j** container `user-konrad.jelen-kgf-neo4j-scout` (172.19.0.8) - EMPTY (ingest failed pre-init), safe to lose; recreate per scout brief below

### Down / completed before brace
- **Phase-3 rebuild run 1**: COMPLETE + captured (`reports/experiments/adjudicated/phase3-rebuild1-20260712T175208Z.json`, dump `data/interim/dumps/20260712-kgf-neo4j2-phase3-rebuild1.dump` 1.1G + manifest row); graph intact on neo4j2. x2 stood down, verdict OPEN. Nothing to do
- **Scout-rung smoke executor**: died on credit outage; its ONE finding: `kgf ingest` on a fresh throwaway fails with "project not initialized - run `kgf init` first" - the ingest log `logs/bench-scout-ingest.log` ends EXIT_CODE=1 at 18:04Z. Artifacts kept: `config/experiments/config-bench-scout.yml` (URI 172.19.0.8), `data/interim/bench/2wiki-scout-50.json` (head-50 of pilot-200)

### Valid on disk (headline)
- Commit `fcea637` pushed (H371 wiring + CUSUM + doctrine + Phase-3 capture + verdict batch, 69 files)
- Canonical log through Phase-3 run-1 section; journal entries 231-232; task #50 completed, #83 in_progress
- Neo4j piles: neo4j2 = Phase-3 run-1 graph (KEEP), neo4j3 = bench pile, neo4j4 = read-only CPAP reference; all in Docker volumes, survive reboot. Post-reboot containers may exit(255) with stale network IDs - reattach to recreated `stellars-tech-ai-workbench_hub_network` (Phase-3 executor did exactly this for neo4j2)

### Invalid / quarantined
- none new this brace

### Pending recordings / decisions
- Scout smoke never ran - restart it per FIRST ACTION
- Uncommitted at brace start: journal 232, canonical-log Phase-3 section, kgf-dataset skill scout-path edit, scout config + slice - INCLUDED in the brace checkpoint commit

### FIRST ACTION for next session
1. `docker ps -a` - restart neo4j2/3/4 if exited (reattach network if 255); relaunch vLLM (`scripts/vllm-serve.sh`), wait for :8010
2. Remove stale scout container, re-run the scout smoke with the SAME brief PLUS the fix: run `kgf init` (or `--config`-scoped equivalent) against the throwaway BEFORE ingest - that was the sole failure
3. Relaunch prober (command above); then resume ladder campaign task #83

## BRACE-READY 2026-07-12 19:12Z - credit limits imminent

**HORIZON: SESSION-ONLY** - usage credits may run out any moment; this session + its agents die, DETACHED compute SURVIVES. On resume: reattach/verify, do NOT relaunch what still runs.

### Running detached (survives; verify by command, reattach only)
- **vLLM gpt-oss-120b** pid 5621 (:8010) - `logs/vllm-server.log`; health `curl -s localhost:8010/v1/models`; if dead: `bash scripts/vllm-serve.sh`
- **Scout smoke ingest** pid 8189 - `.venv/bin/kgf ingest data/interim/bench/2wiki-scout-50.json --config config/experiments/config-bench-scout.yml --event-log`; log `logs/bench-scout-ingest.log`, events `logs/bench-scout-events.jsonl` (6/50 docs at 19:08Z, ~33s/passage); completion = "ingested N documents" LINE (DEF-15: process may hang after - kill pid, note it); target = throwaway `user-konrad.jelen-kgf-neo4j-scout` 172.19.0.8 (H371 questions ACTIVE - the smoke's point)
- **Progressive prober** pid 7688 - checkpoints to `reports/experiments/bench/progressive-probe-trajectory.jsonl` (2,488 rows at 19:08Z); if dead: `setsid nohup .venv/bin/python scripts/bench_progressive_probe.py >> logs/bench-progressive-probe.log 2>&1 &`

### Dies with session
- Scout executor agent + its monitors - told to write `reports/experiments/bench-scout-resume-brief.md` (verification steps, dump recipe, teardown, report path); a fresh agent finishes from that brief alone

### After scout ingest completes (from the brief or by hand)
1. Verify on 172.19.0.8: counts (nodes/entities/rels/chunks), KGFQuestion ~8/chunk gated source:'ingest', ANSWERABLE_FROM + ABOUT edges, index kgf_question_embeddings, one probe() with "## Question match:" block
2. Dump to data/interim/dumps/ + sidecar + MANIFEST row (scout-rung smoke); container dump to /data/_dumps then docker cp; then stop+rm the scout container
3. Report reports/experiments/adjudicated/bench-scout-smoke-<ts>.json; record in canonical log; journal via /journal:update; then small rung next (#83)

### Standing state
- Commits fcea637 + 6487666 pushed; uncommitted since: this board section, resume brief when written - LOCAL DISK survives a session death; commit only needed against machine death (user approval required)
- AWAITING USER: commit approval for post-brace changes

## LIVE 2026-07-12 ~20:20Z - overnight autonomous run (user: "continue until 4am, then switch model to Fable and hand over")

**HORIZON: SESSION-ONLY** - fumes; this session + agents may die any moment, DETACHED compute SURVIVES. Supersedes prior BRACE sections where they conflict. Model handover to Fable planned at ~04:00 CEST (~02:00Z): at that mark write a clean handover + pause; the model switch itself is a user/runtime action (I cannot self-switch).

### Running detached (survives session death; verify by command, do NOT relaunch what still runs)
- **vLLM gpt-oss-120b** :8010 - `logs/vllm-server.log`; health `curl -s localhost:8010/v1/models`; if dead `bash scripts/vllm-serve.sh`
- **Small-200 ladder ingest** - process 28860/28861, `.venv/bin/kgf ingest data/interim/bench/2wiki-pilot-200.json --config config/experiments/config-bench-small.yml`; log `logs/bench-small-ingest.log`, events `logs/bench-small-events.jsonl`; target throwaway `user-konrad.jelen-kgf-neo4j-small` 172.19.0.9 (H371 questions ACTIVE); launched 19:58Z, ~45/200 docs at 20:21Z, ETA ~21:45Z; completion = `EXIT_CODE=` in the log (DEF-15: may hang after the `ingested N documents` line - kill 28860 if so)
- **Completion waiter** - harness bg task `b98t9hpja`, blocks on `EXIT_CODE=` in the ingest log, notifies on fire (re-arm with an `until grep -qE "EXIT_CODE=" logs/bench-small-ingest.log; do sleep 30; done` loop if it died)

### Verified this run (no recompute)
- `make test` GREEN: 492 passed, 18 skipped, exit 0 - BUT only in a clean color env. This shell has `FORCE_COLOR=1` which makes `test_cli.py::test_query_prints_answer` fail on a raw-substring assert vs Rich-colorized output. Always run `env -u FORCE_COLOR NO_COLOR=1 make test`. Not a code defect; no edit made.
- Staged (not yet run - needs GPU-free window): `scripts/bench_answer_kgf.py` - #59 QA adapter, emits the bench_score.py answers schema over held-in 2wiki questions; run on the small pile after ingest, then `.venv/bin/python scripts/bench_score.py <answers.jsonl>`. recall@5 is a title-level proxy; the peer HEADLINE needs the large rung (manual)

### Open-round truth (do NOT manufacture verdicts)
- R34/R35/R36/R37/R38 fully verdicted EXCEPT: R34-H368 (PPR at bench scale, gated on substrate+H391), R36-H381 (gap-ledger lifecycle, un-gated but its "inject a doc" step needs an ingest=GPU), R38-H387 (gated on a 2nd corpus class = the bench pile, now exists)
- R39-R44 are REGISTERED + partially executed only: R39-H389 shakedown 64.1%/62.1% coverage; R43-H429/H430 router (routes retriever-side, "provisional" per adversarial review); R44-H448 PARTIAL + H468 REFUTED. Everything else is GATED on the ladder substrate now under construction - a multi-day campaign, NOT closeable tonight

### Pending (in order) after small ingest completes
1. Verify small on 172.19.0.9: `.venv/bin/python scripts/bench_small_verify.py` (counts, KGFQuestion ~8/chunk source:'ingest', ANSWERABLE_FROM+ABOUT, index kgf_question_embeddings, one probe question-match); then dump to `data/interim/dumps/` + sidecar + MANIFEST row (small-rung, question-active); LEAVE container UP for the A/B
2. H499 verdict A/B (retrieval-only, no GPU contention): `.venv/bin/python scripts/experiments/r46_h499_screen.py config/experiments/config-bench-small.yml` (raise/remove MAX_ELIGIBLE for verdict grade); bar ON-OFF >= +0.03 answer-in-context AND regressions=0; record verdict in canonical log R46-H499, then decide H500 un-gate
3. #59 shakedown: run `scripts/bench_answer_kgf.py` on the small pile (LLM), score with bench_score.py; record honestly as slice-scale harness validation (peer headline = large rung)
4. Start MEDIUM rung rebuild (current engine, question channel) on neo4j3 172.19.0.101 per doctrine - runs past the 4am handover for Fable to monitor. LARGE rung stays MANUAL (user timing; multi-day vLLM occupancy)

### AWAITING USER
- Commit approval for all post-6487666 changes (canonical-log records, journal entries, `scripts/bench_answer_kgf.py`, this board section, dumps/reports)
- Large-rung start timing (multi-day GPU occupancy)

## LIVE 2026-07-13 ~00:35 CEST (22:35Z) - small rung DONE, medium ingest running, H274 wired

**HORIZON: SESSION-ONLY** - detached compute survives. Supersedes the ~20:20Z section. Fable handover planned ~04:00 CEST.

### Running detached (survives; verify by command, do NOT relaunch what still runs)
- **vLLM gpt-oss-120b** :8010 - `logs/vllm-server.log`; health `curl -s localhost:8010/v1/models`; if dead `bash scripts/vllm-serve.sh`
- **Medium rung ingest** - nesting `2wiki-medium-rows200-999.json` (rows200-999, 800 docs) onto the small-200 pile on .9 → 1,000-doc medium rung; `.venv/bin/kgf ingest ... --config config/experiments/config-bench-medium.yml --event-log`; log `logs/bench-medium-ingest.log`, events `logs/bench-medium-events.jsonl`; launched ~22:32Z; NO `EXIT_CODE=` wrapper - completion = the `ingested N documents` LINE (DEF-15). ETA ~08:00 CEST. Relaunch if dead: same command detached
- **Medium completion waiter** - harness bg task `bd9uufpv9` (greps the `ingested N documents` line + process-death fallback); notifies on fire

### DONE this session (captured on disk, no recompute)
- **Small-200 rung** = ladder rung 2, LIVE on .9 until the medium increment nested over it. Verify report `reports/experiments/adjudicated/bench-small-verify-20260712T215613Z.json`; 1,287 ents / 200 chunks / 1,551 gated questions / index ONLINE
- **R46-H499 small screen** = underpowered null: OFF 15/22, ON 15/22, delta 0.0, zero regressions (`reports/experiments/bench/r46-h499-screen-20260712T215811Z.jsonl`); recorded in canonical log R46-H499; verdict escalates to medium (powered n)
- **#59 shakedown** = EM 0.136 / F1 0.226 / recall@5 0.773 (`reports/experiments/bench/2wikimultihopqa-answers-20260712T220025Z-fixed.jsonl`); `scripts/bench_answer_kgf.py` retrieved_titles bug fixed (d_ hash-id join via KGFDocument.name)
- **H274 answer-cache WIRED** (default off): `graph/answer_cache.py`, `AnswerCacheSettings`, `Foundry.query()` wrapper; 498 tests green; canonical log R26-H274 + journal 234
- **make test GREEN** 498/18-skipped in a clean color env (`env -u FORCE_COLOR NO_COLOR=1 make test` - FORCE_COLOR=1 breaks the CLI substring test, not a code defect)

### PENDING for Fable (in order, after the medium ingest completes)
1. Verify medium on .9 (counts, KGFQuestion ~8/chunk, index); dump medium to `data/interim/dumps/20260713-neo4j-medium-2wiki-1000.dump` + sidecar + MANIFEST row (stop container / throwaway `--volumes-from` `neo4j-admin database dump` / docker cp / restart; image `neo4j:5.26.0`)
2. **Powered R46-H499 verdict**: `.venv/bin/python scripts/experiments/r46_h499_screen.py config/experiments/config-bench-medium.yml <2wiki json> 0` (uncapped) - many more held-in eligible; bar ON-OFF >= +0.03 AND regressions=0; record verdict, then decide H500 un-gate
3. #59 on medium: `scripts/bench_answer_kgf.py config/experiments/config-bench-medium.yml`, score with `bench_score.py` (still slice-scale; the peer HEADLINE needs the large rung)
4. LARGE rung stays MANUAL (user timing; `2wiki-full-rows1000-6118.json`, multi-day vLLM)

### Deferred (noted, not blocking)
- Small-200 standalone physical dump SKIPPED (nesting reuses .9; ladder is strictly nested so the medium dump contains all small docs; .9 is a reproducible throwaway) - see rationale in the H274/journal record
- DEF-16: `kgf_proposition_embeddings` / KGFPassage absent on the bench pile (optimize() never ran) - proposition rung silently skipped, span coverage 0.0; instruments log/skip gracefully

### AWAITING USER
- **Commit approval** for the whole post-`6487666` batch (canonical log H499+H274, journal 234, `scripts/bench_answer_kgf.py`, `scripts/experiments/r46_h499_screen.py`, `src` H274 trio, `tests/test_answer_cache.py`, `config-bench-medium.yml`, this board, reports/experiments) - nothing pushed without it
- Large-rung start timing

---

## R47 GLiNER sparse graph coding - research round registered (2026-07-13 ~01:15 CEST)

User pivot mid-night: "hypothesise with a wide fanout about sparse graph coding with ner at ingestion ... Research". Delivered as a registered research round; NOT executed (execution is the next phase, needs GLiNER wiring + a bench substrate).

### DONE this session (on disk)
- **R47 registered** H501-H513 (13 hypotheses) in `docs/experiments/kgf-redesign-experiments.md` (line ~4667). Two domains: IDENTITY (strong, vs weak 76.8% incumbent, targets H107, 9/13 FREE offline replays) + RETRIEVAL (contested vs dense@16=0.854, gated behind the FREE H501 ceiling gate; all constructions FUSE inside PPR, never seed-compete)
- **H501 is the cheapest decisive experiment**: partition gold carriers spec vs prose; NULL (retrieval domain dead) if dense already holds >90% of GLiNER's spec carriers; OPEN if dense spec-slice recall <0.85. FREE offline replay - run FIRST
- **18 load-bearing papers** downloaded + digested to `references/papers/` (150 total now, all %PDF-verified). Fanouts: research `wf_69853fe5-c2b` (8 Opus, 680k tok), digests `wf_c15bf3c3-26d` (18 Sonnet, 1.9M tok). Full research harvest cached at `/tmp/claude-1000/.../tasks/wup135zue.output` (948 lines, all 32 candidate hypotheses + ~40 papers)
- **journal 235** (Extended) logged via plugin, journal-tools check 0 errors; task #85 created for R47 execution
- GLiNER NOT engine-wired (H260 notebook-only) - every R47 hypothesis needs at minimum one 7.6s idle-card GLiNER pass over the target slice

### R47 execution (Fable / next session, when greenlit + substrate ready)
1. **H501 ceiling gate FIRST** (FREE) - needs a GLiNER pass over a bench slice + the dense-seed logs + gold carriers; decides whether the retrieval domain (H506-H511,H513) is worth building. No harness written yet
2. IDENTITY domain next (H502/H503/H505 FREE over cached H260 spans + the H107 66-pair set; H504 GPU SAE) - the strong bet, independent of H501
3. RETRIEVAL GPU work (H506/H508/H513) rides the medium/large substrate + a positive H501

### AWAITING USER (updated)
- **Commit approval** now covers the post-`6487666` batch PLUS: `docs/experiments/kgf-redesign-experiments.md` (R47 block), `.claude/JOURNAL.md` (entry 235), 18 new `references/papers/[paper]*.pdf` + `[paper digest]*.md`, this board. Nothing committed/pushed without explicit approval

## R48 + RFM register + R49 plan (2026-07-13 ~09:45 CEST, Fable session)

**DONE (on disk, uncommitted on top of f910a1a):**
- **R48 registered** - H514-H538 (25 hypotheses) in the canonical log: community segmentation/balancing as a context lever. Gates: H514 (residual prunable mass after H382; <15% kills reduction domains) + H515 (partition-masked PPR vs cross-community gold). BALANCE H516-H519 = ONE shared FREE Leiden gamma/size-cap sweep; USER-MANDATED metrics table on every balance verdict: {gamma/cap, count, modularity, Gini, max/median, p95} x {recall@16, answer_in_context, EM/F1, tokens p50/p95/p99}. 17/25 FREE. Fanout wf_874da95f-0a7 (657k tokens); harvest cached at scratchpad/r48-harvest.json
- **Recall failure-mode register** - docs/recall-failure-modes.md, RFM-1..9 (defects formalism, TOC validated). RFM-9 (scale-growth flip) attribution due at medium collection
- **R49 PLANNED (task #2)** - R45-conclusions -> ingestion reconciliation fanout: metric panel + Ricci as ingest instruments, repair-at-ingest, carrier-selection fix, seed-reachability certificate column, certificate noise re-pricing, source-repair primacy. Memory: project_r45_conclusions_ingestion_reconciliation.md
- **Journal 236+237** (0 errors); tasks #1 (R48 execution) + #2 (R49) created
- **Server-restart recovery** (earlier this session): containers survived, ingest resumed at doc 967, vLLM + prober relaunched via scripts/resume_after_restart_20260713.sh

**RUNNING:**
- r48-paper-digests workflow wf_7a06c1ce-28c (21 Sonnet agents) -> references/papers/
- medium ingest (verify by command `kgf ingest`, ~975+/1000 docs), prober, vLLM :8010; waiter task bme3fhu4g greps `ingested N documents`

**EXECUTION ORDER when R48 greenlit:** H514 + H515 gates (FREE) -> H516-H519 balance sweep (FREE, ships the metrics table) -> H524 waste audit -> H528-H530 question-space -> H532 systems calibration (GPU evening) -> gated rest. R47 execution (task #85) still queued ahead per user priority at greenlight time.

**AWAITING USER:** commit approval for the post-f910a1a batch (R48 log block, RFM register, journal 236-237, board, new papers/digests when fanout lands); push approval for f910a1a; R47/R48 execution greenlight + relative priority.

## Medium collected + H499 verdict + bench roster (2026-07-13 ~10:00 CEST)

- **H499 VERDICT RECORDED (REFUTED at bar)** - n=132 paired: OFF 85 / ON 86, delta +0.0076, 0 regressions; H500 stays gated; channel value moves to R48 H528-H531
- **Medium rung final**: 1,000 docs / 6,626 entities / 35,637 rels / 7,534 questions; `kgf_proposition_embeddings` ABSENT on this pile (proposition channel unavailable - known scout-lineage gap, affects H367-dependent replays; note for R48 FREE replays)
- **#59 answer run** over 132 eligible in flight; `redo_dump_medium_20260713.sh` (sid 22235) waits for it, scores via bench_score.py, then dumps with in-container polling (first dump attempt raced the proxy's early `docker wait` return - ops lesson appended to the dumps rule)
- **Benchmark selection section** added to docs/benchmark-recipe-multihop-qa.md (2wiki RUNNING, HotpotQA/MuSiQue WANT, LongMemEval-S WANT-subset-first, LOCOMO/BEIR/code-intel SKIP; judge kappa discipline; refusal-as-answer)
- Journal 238; LOCOMO + LongMemEval papers archived (173 total)
- README rewritten by fork agent (uncommitted, on disk)

## Repo untracking + push (2026-07-13 ~10:05 CEST, user-directed)

- **logs/ results/ scripts/ untracked** (`f4940e2`, pushed): gitignored, 320 files removed from index, ALL KEPT ON DISK; pre-removal content in git history; canonical-log relative links still resolve locally. Corrupted .gitignore line (.pypirc/logs merge) repaired
- **Layout verdict**: project already copier-data-science-generated (.copier-answers.yml); skeleton conforms; config/ stays tracked as a project extension; NO file moves (protects experiments-log links)
- **Push carried the 15-commit backlog** (bfa40e5 -> f4940e2) incl. f910a1a - remote current with main
- **Discipline note for future sessions**: results/, scripts/, logs/ are now INVISIBLE to git status - brace checkpoints must NOT rely on `git status` to enumerate run artifacts; the dirs persist on disk only, dumps rule unchanged (data/interim/dumps/ was always untracked)
- Still uncommitted (awaiting approval): R48 log block + H499 verdict, RFM register, README rewrite, benchmark-selection section, journal 236-238, 23 new papers

## R49 Wave 0 closed + Wave 1 contrarian battery launched (2026-07-13 ~19:55 CEST, post-limit resume)

Sessions since the 10:05 section (see git log): `efdac7f` R48 registration + H499 verdict committed, `9853093` R49 registered (H539-H580, 42 hypotheses), `5c52c0f` R49 Wave 0 (carrier gold + H542 + bakeoff runner). Board sections for those sessions were not written (limit); this section reconciles.

### DONE (on disk; verdicts recorded in canonical log)
- **META H539-H543 all CONFIRMED** - bands published (`reports/experiments/r49/meta-variance-20260713T102430Z.json`); paired frozen-probe gates MANDATED (H541); spread is ~99% query sampling
- **Carrier bakeoff adjudicated** (`carrier-bakeoff-20260713T140353Z.json`, n=11 effective): **H568 CONFIRMED - LLM attacher = the carrier function** (11/11, correct ABSTAIN on 4/4 artifacts); H567 CONFIRMED (abstain gate ships); H569 KILLED (alias rule picks object not subject); H565 REFUTED-as-stated (carriers are prominent-not-hub, degree rank 2-3); H564 INCONCLUSIVE-at-bar; H566 BLOCKED-DEP (no coref lib). Six verdicts + journal 246 + token-ledger snapshot are UNCOMMITTED on top of `5c52c0f`
- H554 UN-GATED (its gate = working audit function = H568)

### RUNNING (launched ~19:50 CEST)
- **vLLM gpt-oss-120b :8010** relaunched (sid 39828, `logs/vllm-server.log`) - UP
- **Wave 1 = contrarian gate battery H544-H548**, five Opus executors (harnesses to `scripts/experiments/r49_h544..h548_*.py`, results to `reports/experiments/r49/h54X-*.json`, logs `logs/r49-h54X*.log`): H544 Ricci-degree ablation (neo4j3 :101 read-only + perturbation/rewiring), H545 panel-vs-H37 (medium .9 + H499 screen labels 20260713T072044Z), H546 RAI class kill (ledger + adjudication + dedup-collision), H547 carrier swap-recheck (pilot pile, in-memory swap, NEVER graph writes), H548 cert SNR (N=10 recomputes, frozen scout). Verdicts recorded ONLY by main session on collection
- Medium ingest COMPLETE (1,000 docs / 6,626 ents / 35,637 rels); no ingest in flight

### NEXT after battery collection
1. Record H544-H548 verdicts in canonical log; gate outcomes re-scope H549-H558 (panel/Ricci domains), H559-H563 (RAI), H570 (render transfer - UNAFFECTED by H547 either way)
2. Then per registered order: surviving domains; H554 audit-not-rebuild now un-gated; reachability H571-H576 (H572 CRUX)
3. R48 execution (task #87) + R47 (task #85) queued - relative priority = user call at greenlight

### AWAITING USER
- **Commit approval**: uncommitted batch on top of `5c52c0f` = six bakeoff verdict recordings in canonical log, journal 246, carrier-gold-12.json corrections, token-ledger snapshot, prober trajectory rows, this board section (+ Wave 1 artifacts as they land)
- R47/R48 execution greenlight + relative priority vs R49 waves

## Wave 1 verdicts + verdict re-audit sweep + construction audit (2026-07-13 ~20:45 CEST)

### Battery verdicts RECORDED in canonical log (4/5; H548 recompute 8/10 in flight, `logs/r49-h548.log`)
- **H544 KILLED** - FR = degree alias (no triangle term; mean-AFRC = 4 - sum-deg^2/E; exact 0% rewiring; R^2 0.9987); H553/H555-H558 re-priced to degree instruments; memory corrected
- **H545 KILLED-panel** - five structural metrics at chance (oriented AUC <= 0.551, n=132); certificate lone survivor at AUC 0.609; H549 re-scoped; R45 panel note added; memory corrected
- **H546 KILLED-RAI** - zero ingest-timing recall advantage (48/48 batch-recoverable, 0/1802 collision losses, 25% vs 100%); H559-H563 latency/cost only
- **H547 INCONCLUSIVE leaning KILLED** - net +2 shipped / +1 full render (SURVIVES bar missed both arms); truncation-of-duplicate artifact + 1 genuine drift case; render_budget=0.6 flagged; H570 UNAFFECTED

### Verdict re-audit sweep (user-directed) - RECORDED as log section "Verdict re-audit sweep (2026-07-13 evening)"
- 13 Opus agents (wf_92466fd9-386, 2.12M tok), 573 hypotheses, 150 flags (21 HIGH adjudicated + recorded; 92 MED / 37 LOW advisory); harvest `reports/experiments/audit/verdict-regrade-sweep-20260713T192500Z.json`
- In-place supersede notes added at H67, H91, H100, H371, R45 panel block
- Headline: H544/H545 were re-derivations of R10's H91/H100 - process rule recorded (instrument-class verdicts promote to doctrine)
- DISCOVERED during sweep: R47-H501 + R48-H514/H515/H528/H529/H530 were EXECUTED pre-limit (commits efdac7f/9853093); tasks #85/#87 corrected

### Construction audit (user-directed) - COMPLETE, 4 auditors + synthesis
- Harvest `reports/experiments/audit/construction-audit-20260713T194500Z.json` (workflow wf_7ee42696-d50 + 2 re-run agents after a stub/failure)
- KILL/GATE-OFF: question channel at ingest (H499; ~25% per-chunk LLM budget), Leiden+82 summaries (H68, no reader), SIMILAR_TO writes (no default query reader - H288 value inert while PPR off), drift self-heal recure (H306/H308; RISKY - noise-triggered ontology mutation), rel-entropy scorecard metric (H545)
- WIRE NOW: H568 attacher + H567 abstain gate into repair(); batch reconciliation tier (H546/H107/H547); paired frozen-probe harness (H541 - exists nowhere as tooling); certificate promoted from script to src (H540 bands)
- QUERY-SIDE HEADLINE: bench query = dense@16 + 1-hop fanout + 0.6 truncation + CPAP-fit gates (0.668/0.75/0.765 unrecalibrated; abstention rides the H17-refuted signal); only live augmentation = the H499-killed question channel; H382 lever default-off AND DEF-16-starved (optimize() never ran on bench) - the composed frontier cannot even replay
- DEFECT flagged: render_budget=0.6 drops answer-carrying blocks under unmerged-duplicate identity defects (H547 mechanism)

### NEXT (in order)
1. H548 verdict on collection -> battery closed
2. Journal entries via /journal:update (battery; sweep+audit) + this board
3. R49 remaining spend re-concentrated: H571-H576 reachability (crux H572) + H577-H580 source-repair; H570 un-gated (H568 attacher)
4. AWAITING USER: engine rewiring greenlight (gate-offs + wire-nows above = shipped-engine surgery); DEF-16 repair (optimize() on bench) decision; commit approval for the whole post-5c52c0f batch

## R49 Wave 2 adjudicated + Wave-1 battery CLOSED (2026-07-13 ~21:40)

### All Wave-2 verdicts RECORDED in canonical log (status lines at each registration)
- **H570 SPLIT** - transfer clause CONFIRMED (H568 scorer +14.5pts over degree at 0.5x budget, one implementation ships to attach AND render); 0.85 oracle bar missed structurally (multi-gold probes cannot fit single-pass 0.5x; oracle 0.909 needs decomposition)
- **H571 CONFIRMED** - reachability column: 27.1pts below coverage, IQR 0.5, isolates REG-2 (carrier Torres Rios unreachable from other-gold-doc seeds); ships as audit/forensics column, NOT fate predictor
- **H572 INCONCLUSIVE leaning KILLED (CRUX)** - kappa 0.268 all aggregations; ingest-time reachability framing does NOT proceed (collapses toward R40). REG-2 REVERSAL: answer target Torre Nilsson reachable (dense #16, PPR 14/15), fails at render trimming
- **H573 KILLED** - seed-rank margin WEAKEST proxy (0.537; H479 falsified); hop-distance 0.681 only signal; 5 hop-unreachable carriers identified
- **H574 KILLED** - membership over-reports (~83% vs PPR ~52%), misses the weak tail; PPR required in audit
- **H575 KILLED** - graded r(f) at chance (0.486 vs binary 0.558); Gini clause HELD (0.103->0.185->0.237 monotone = H468 dilution; scale-health candidate, unregistered)
- **H577 BLOCKED-DEPENDENCY** - signals on disjoint corpora (2wiki/CPAP/CPAP-aggregate), no doc key; proxy rho 0.086 leans killed
- **H578 KILLED** - triage at chance (AUC 0.477); all 17 residue facts source-span-PRESENT = attachment/dedup gap (corroborates H546); NOT-ENTAILED false-abstains = cross-doc REG edges (single-span blind spot)
- **H579 PARTIAL** - narrow ledgered repair 47/48 (97.9%) vs blind 25% at 19.3% exact cost - MECHANISM CONFIRMED; probe-flip 43.3% dead zone (17/47 already surfaced pre-repair; visibility is the render layer's problem)
- **H580 KILLED** - demand VoI +7.7pts over fact-count (<10 bar); H493 generalizes; nuance: top-30% capture 0.769, head polluted by 4 carrier-less ARTIFACT gaps (artifact-gated variant = new hypothesis, noted not registered)
- **H548 SURVIVES (battery CLOSED)** - per-doc SNR 3.75 / corpus 5.4; noise claim refuted, per-doc cert gating stands, H552 does not re-price; empirical median repair delta 0.00 is the VISIBILITY layer, not noise. Detached loop outlived executor; collected via tmp/scripts/r49_h548_analyze.py -> reports/experiments/r49/h548-cert-snr-20260713T193838Z.json
- Wave-1 battery final: H544 KILLED, H545 KILLED-panel, H546 KILLED-RAI, H547 INCONCLUSIVE-lean-KILLED, H548 SURVIVES

### Cross-cutting convergence (three independent results, same culprit)
- H570 budget ceiling + H572 REG-2 re-classification + construction-audit DEFECT flag all indict render_budget=0.6 trimming as where probes die - NOT graph structure

### H576 (Wave 2b, sole graph-write experiment)
- Re-priced per H572 (note in registration): must instrument WHERE flips happen (reachability vs render survival); tail clause targets H573's 5 hop-unreachable carriers, not REG-2's class
- Launch DENIED by permission classifier (writes to shared medium graph need explicit user naming) - PARKED AWAITING USER; primed spec preserved in session transcript; keeper dump 20260713-neo4j-medium-2wiki-1000.dump exists; revert-discipline design (pre-state snapshot + restore + verify) ready

### Journal + board state
- Journal entry 249 appended via /journal:update, journal-tools check exit 0 / 0 errors
- R49 remaining unexecuted: H549-H563 (panel/Ricci/RAI domains - most re-priced to degree/latency instruments by H544/H546 kills), H564/H566 (carrier leftovers: inconclusive-at-bar / coref-blocked), H576 (awaiting user)

### AWAITING USER (unchanged + one new)
1. Commit approval for the whole post-5c52c0f batch; push approval
2. Engine rewiring greenlight (gate-offs + wire-nows per construction audit)
3. DEF-16 repair decision (optimize() on bench pile)
4. **NEW: H576 graph-write approval** (anchor replication on medium; revert-discipline + dump fallback in place)
5. R47/R48 relative priority

## User orders 2026-07-13 ~23:55 + autonomous-mode state (2026-07-14 ~00:05)

### User approvals / directives (verbatim intent)
- **H576 GRAPH-WRITE APPROVAL GRANTED** ("Graph right approval granted") - anchor replication on medium may run; QUEUED behind H582 completion (H582 reads medium entity embeddings; H576 writes them - writer-reader isolation). Launch with the primed spec incl. revert discipline (pre-state snapshot + restore + verify; keeper dump 20260713-neo4j-medium-2wiki-1000.dump fallback)
- **Full autonomy**: "work autonomously up to your best. Concept and prediction." + standing authorization to open new territories via subagent hypothesis fanouts as I see fit
- **Vetting mechanism mandated** -> CREATED: docs/hypothesis-vetting.md (V1 ledger-dedup / V2 power-band / V3 oracle-algebraic kill / V4 cheapest-rung / V5 fence+confound; outcomes VET-PASS/KILL/REPRICE; run as read-only vet subagent, coordinator adjudicates). First applied inside the R50 fanout synthesis stage

### New registrations (recorded in canonical log, end-of-log section)
- **R47-H581** concept vocabulary (LLM-proposed per-chunk concepts as dynamic GLiNER labels, shared ingest/query) - REGISTERED-GATED behind H508/H509 per user "sequence it"
- **R47-H582** retrieval-embedder swap (re-embed same nodes, replay dense@16+PPR; carried arms R07-H40 answer-form + R07-H41 split-channel) - RUNNING (executor launched, pure-offline numpy replay, no containers)

### In flight (2026-07-14 ~00:05)
- H582 embedder-swap executor (medium read-only + idle-GPU embedders; must reproduce Titan 0.598 sanity first)
- R50 fanout workflow wf_3c86a7b4-de6 (7 Opus research vectors + vetting synthesis; two-step meta-matching / speculative-topology concept, user-directed; fences R40/R41/R47/H581/H582/R35 primed)
- QUEUED: H576 (on H582 completion); R50 registration + papers batch (on fanout return)

### Verdicts recorded since last section (all in canonical log)
- H555 CONFIRMED-as-degree-bottleneck (AUC 0.6833, razor over bar; Spearman 0.91 with hop)
- H556 KILLED-retired-redundant-with-hop (honest control: delta-AUC 0.0031 over hop alone; literal registered bar diverges - both readings recorded; registered min-deg control was itself broken)
- H557 CONFIRMED-per-bar, seat NOT awarded (orthogonal to certificate r=-0.343, collapses given hop) -> domain synthesis: {certificate, seed-hop-distance} = the complete cheap-column pair
- H558 GATED-DEAD note added (H556 killed)
- H560 CONFIRMED (100% carrier-bearing repairs have carrier present-at-ingest; zero need later docs)
- H561 INCONCLUSIVE lean-negative (strict same-doc name-match 7/12) with kill-rationale REVERSAL: same-doc recall 12/12 - candidate pool suffices, selection needs H568 attacher

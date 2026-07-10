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
- neo4j4 scratch (wipe allowed), vLLM extraction, paired arms. Expected: notebooks/identity_ab_h241.ipynb, reports/identity-ab-h241-*.json, logs/h241-ab.log. On report: record; if GO flip resolution.identity_stack default in H198; then launch H240(b) union arm on neo4j4.

### 2. R23/R24 LLM gates batch - undersampling remedies
- Order: H246 enumerate, H248 GLiNER-primed pass, H243 complement, H258 mention-emission, H251 n-sampling, H245+H257 logprobs, H260 adjudication, H261 distillation. Checkpoints results/r23r24_llm/. Expected: notebooks/undersampling_llm_gates_r23r24.ipynb, reports/undersampling-llm-gates-r23r24-*.json, logs/r23r24-llm-gates.log. On report: record + launch H250 cost frontier (names the H198 extraction recipe).

### 3. R27 precision arms - H282/H283/H284/H285/H289 re-scoped executor
- H288 RECORDED (REFUTED - merge-over-soft delta 0.0 pts; recall agentics dead) + H281 RECORDED (CONFIRMED - 85.6% cheap-decidable, web class 1.1%). Round re-scoped to identity PRECISION: false-merge removal at zero true-merge loss on the SAME_AS surface (57 type-conflict + 64 code-shared + 3 P10 pairs, enumerated in reports/agentic-escalation-gates-r27-20260708T082438Z.json).
- Executor running: labels frozen blind first, then single-shot control / tool-agent K=4 / no-tools + fetch-then-judge / effort sweep / Strands tax. Expected: notebooks/agentic_precision_arms_r27.ipynb, reports/agentic-precision-arms-r27-*.json, logs/r27-precision-arms.log, results/r27_precision/. On report: record, then compose H287+H290 (free replay arithmetic).

### 4. R21 image tier - H218 VLM contest + H224 decorative filter
- Running (logs/r21-qwenvl-infer2.log, smolvlm download seen). Expected: notebooks/image_vlm_gates_r21.ipynb, reports/image-vlm-gates-r21-*.json, logs/r21-vlm-gates.log. H218 extraction clause queued behind LLM tier.

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
- `scripts/h241_v2_rerun.sh` (running, polling health): wipe neo4j4 -> v2 arm -> measure -> touches logs/h241-chain.DONE
- Batch driver run_batch.py PID 3262792 is SIGSTOPped - after vLLM healthy: `kill -CONT 3262792` (finishes H261 + report reports/undersampling-llm-gates-r23r24-*.json; autorender2.sh then executes the notebook)
- If those PIDs/scripts died: caches in results/r23r24_llm/ (h246/h248/h243/h251/h245_257/h258/h260 all cached), only h261+report remain

**Valid results on disk (do NOT recompute):**
- v1 arm VALID: reports/h241-v1-recall.json + h241-v1-stats.json - recall 0.7708 (17/24), precision 0.083 (11 false merges), 2727 entities, fp bc194b65b08137bf, wall 14439s
- v2 first attempt INVALID (ran against dead server): quarantined in reports/invalid/ - must NOT be used
- Batch verdicts cached: H246 0.971@1.05x, H258 1.000@1.53x inflation, H248 0.943, H251 0.912@3.05x indep=1.000, H243 comp_new=0, H245 sep=0.0066, H260 adjudicated_cov=0.873
- Confound record for H241 verdict: v1 had 6 timeout losses under batch contention (pre-11:55Z pause); v2 rerun runs post-outage - note conditions in verdict

**Wiring tranche 1 READY** in worktree agent-aea0ebaec7aac3122 (uncommitted, base 0735aac) - merge after chains release tree (see docs/h198-wiring-plan.md).
**Pending recordings**: R23/R24 round close (all verdicts above + H261 + H250 frontier -> SLOT-2), H241 verdict -> SLOT-1, journal entries, promotions.

## BRACE 2026-07-10 ~16:05Z - session horizon unknown

Supersedes the 2026-07-08 section where they conflict. Active /goal: fix DEF-8..DEF-13 fixes-first with measured verdicts. Standing directive (2026-07-10): NO Titan for new bulk embedding compute - local GPU models (bge-m3 on GPU idx 2), configurable providers; spec = docs/acc-crit-kgf.md "Embeddings" section (10 criteria). Entity-channel QUERY embedding stays Titan only because the live entity index is Titan-space (fixed control arm). Executor model for this campaign: Fable ("fable" in agent model opts).

**RUNNING (detached, survives session death):**
- H363 clean GPU ramp: PID 46692 (setsid, sid=46692), `scripts/r30_gpu_ramp.py`, log `logs/r30-h363-ramp.log`. STEP c=16 done: 1.55 chunks/min, 520.3 tok/s total (309.2 gen), hidden_attempts=0, errors=0, peak run/wait 16/0 (single-attempt regime confirmed). c=24 mid-window; rungs 32/48/64/96 remain; ~20:30-21:00Z finish. Holds GPU 1 (PRO 6000) + vLLM :8010. On completion: record H363, fit H347 knee offline, seed first H362 cache entry, then H343/H345 (task #58 remainder)
- Nothing else runs. H366 COMPLETED (below).

**DONE - PENDING VERDICT RECORDING (first analysis duty of next session):**
- R34-H366 passage-node prototype COMPLETE: `reports/r34-h366-passages-20260710T154339Z.json` (log `logs/r34-h366-passages.log`). M=0 reproduced baseline EXACTLY (0.8542, 20/24 - control valid). M=1: mean 0.9583, 23/24 fully covered, ctx growth +78%; M=2/M=4 identical recall at +160%/+321% growth. Registered bar was "P21+P22 flip, zero regressions, <=30% ctx growth" - recall part massively exceeded at M=1, ctx-growth clause EXCEEDED (78% > 30%). Verdict must weigh the clause honestly (partial pass / confirmed-with-caveat per per-probe diff in the report). Chunk embedding cache: `results/r34/h366-chunk-embs-bgem3.jsonl` (bge-m3, 247 chunks, reusable for H367/H371+)
- Maintenance research (R36 inputs) BOTH LANDED, persisted to disk:
  - `reports/r36-maintenance-literature-brief-20260710.md` (external literature: IVM/DRed/TMS, EraRAG, Mem0, A-MEM, sleep-time, Drift-Adapter, Memory-Worth; five proven-novel open slots; 5 new papers archived to references/papers/)
  - `reports/r36-maintenance-internal-map-20260710.md` (cartographer, recovered verbatim: R28 fence H293-H339, DEF-9 = H317 CUSUM confirmed-not-wired, RECURING dead-end end_recure zero callers, functional_relationship_types=[] -> valid_to never set, derived-object invalidation matrix = nothing invalidates anything)

**Recorded earlier today (already in canonical docs, do NOT redo):** H364 CONFIRMED (resolution_loss 83.3%, ranking zero) + H365 CONFIRMED (prototype repair: 0.7917 -> 0.8542, P09/P16 flipped, 22 flat) in docs/experiments/kgf-redesign-experiments.md; DEF-13 dated notes in docs/defects.md; R34 (H366-H370) + R35 (H371-H375) registered; journal entries 192-194; acc-crit Embeddings section added.

**Graph state neo4j4 (bolt://172.19.0.4:7687, neo4j/kgfoundry):** layered pile 5213 ents/23472 rels WITH H365 repair applied (additive, marker `e.h365_hoisted`, edges `PART_OF {h365:true}`; rollback in scripts/r33_h365_repair.py docstring). Fresh baseline pair: pre-repair 0.7917 (reports/h364-fresh-recall-20260710T135437Z.json), post-repair 0.8542 (reports/h365-repaired-recall-20260710T143152Z.json). The old h212-v2 recall map is STALE - never diff against it.

**FIRST ACTION next session:** read this section, then (1) record the H366 verdict in docs/experiments/kgf-redesign-experiments.md against its registered bar (numbers above, per-probe diff in the report JSON), (2) check `logs/r30-h363-ramp.log` - if finished, record H363 + knee fit, (3) register R36 (maintenance of derived objects) from the two reports/r36-*.md briefs - fence against R28/R15-R17/R26, claim: derived-object invalidation as a class, RECURING dead-end, dead fact-drift alarm, maintenance of NEW R34/R35 objects; give DEF-9 its workstream (wire H317 CUSUM). Then continue task #70 (H367/H369/H370 prototypes; H370 retro-arm needs temporary H365 rollback) and #71 (R35, generation post-H363). Journal entry for maintenance-research + acc-crit + H366 still owed (via /journal:update only).

**Task list**: cleaned 2026-07-10 (43 completed deleted); live: #70 R34 prototypes (in_progress), #71 R35, #66 H363 ramp, #69 wire H365 into engine, #58/#62/#64/#49-#53/#56/#59.

---

# BRACE 2026-07-11 (session end after docs consolidation; user order: let the GPU finish, pick up on return)

**RUNNING - detached, DO NOT KILL:** H363 ramp, pid 46692 (PPID 1, disowned, 9h21m up), `scripts/r30_gpu_ramp.py`, log `logs/r30-h363-ramp.log`. Closed rungs: c=16 520.3 / c=24 533.1 / c=32 612.3 tok/s - knee NOT reached, throughput still climbing. c=48 window filling; rungs 48/64/96 remain; the script checkpoints STEP lines to the log and writes its own report on completion. The session-owned watcher (grep loop) dies with this session - irrelevant, just tail the log.

**DOWN / needs restart:** nothing.

**VALID ON DISK (all pushed to origin GitLab, HEAD b8a11f7):**
- `2f6202a` - H365 spec-hoist engine wiring (`graph/hoist.py`, `resolution.spec_hoist` default off) + H378 CUSUM/RECURING exit (`drift.cusum_enabled` default off) + R35/R36 verdicts: H376 CONFIRMED, H380 REFUTED (harness density), H375 REFUTED (contamination caught - pre-repair arm decisive, Hawkins retired), H374 deferred to precision arm. 437 unit + 10 live integration green. Reports `reports/r35-*`, `reports/r36-*`
- `b8a11f7` - docs consolidation: `@archive/` gains sota-decision, h198-wiring-plan, DESIGN; `docs/defects/defects.md`, `docs/acceptance-criteria/acc-crit-kgf.md`; `api.md` REMOVED (rewrite post-RC from `scratchpad/api-md-audit-findings-20260710.md`); usage-scenarios PPR fix; gap-ledger audited current
- Journal at entry 207, `journal-tools check` 0 errors

**NOT COMMITTED (deliberate):** `models/qwen2.5-7b/` (4.4G), `results/r34/h366-span-embs-bgem3.jsonl` (145M) + `h367-prop-embs-bgem3.jsonl` (230M) (LFS pending user), `scratchpad/build_r24c*.py`.

**PENDING USER DECISIONS:** GitHub remote 4 commits behind GitLab origin; LFS for the two >100MB caches; #56 enhancements doc plan is v1-stale - re-scope or drop.

**PENDING WORK (post-H363 queue, in order):** H363 verdict + H347 knee fit + H362 cache seed (#64) + H343/H345 (#58); then LLM-gated: H385 answer side + optimize() refit hook (#74), H382 self-report rider (#73), H377 + H378 induced-drift replay (closes DEF-9) + H379 replay arm (#72), H371-H373 generation + H374 precision arm (#71), R31 H349/H352 (closes DEF-11) (#62), DEF-13 cures. Chained: H381 on H373; H387/H368/NV-Embed-v2 parity on the #59 second corpus. Open flag: rung-1 additive-vs-displacement parity needs a proposition index on the pile - engine prop index is Titan space, conflicts with the no-Titan-bulk rule.

**FIRST ACTION next session:** tail `logs/r30-h363-ramp.log` and `ps -p 46692`. If new STEP lines landed (c=48+): collect them; if the ramp finished all rungs or died: record the H363 verdict + H347 knee fit in `docs/experiments/kgf-redesign-experiments.md`, seed the H362 throughput-cache entry, then start the post-H363 LLM queue above. If still running: the user directive stands - wait on the GPU, execute only non-GPU work.

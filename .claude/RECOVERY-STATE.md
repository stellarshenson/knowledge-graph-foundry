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

# Recovery State - live board snapshot

**Purpose**: if the session dies, a restored session reads THIS FILE FIRST (after JOURNAL.md) and picks up every stream. Detached compute survives session death; only recording/relaunch duties need the restored session. Updated 2026-07-08 ~07:50 UTC.

**Board delta at last update**: RECORDED since 07:00 - R24 graph gates (H252 CONFIRMED 68.6%/5%, H253 REFUTED robustness, H254 ceiling CONFIRMED 62.9%), R25 registered (H266-H270, peer harvest) + H266 superseded by design, R26 registered (H271-H280, usage coupling), R25/R26 first gates (H267 REFUTED 4.5% exact-normalized, H268 gate CONFIRMED 64.7% soft-link recovery -> ships to H198, H269 PARTIAL lever rejected, H279 PARTIAL staleness 9.5%/concentration 2.05x). Pending recording: H229 + R22 gates, H157, R26 remainder executor, R21 VLM executor.

## Standing rules (binding)

- Verdicts recorded ONLY by the main session in docs/experiments/kgf-redesign-experiments.md (append-only; supersede via post-verdict notes). Promotions -> docs/sota-promotions.md. Journal via /journal:update + journal-tools check (0 errors). Checkpoint commits + push authorized.
- Every finding that raises questions -> register a new hypothesis before moving on.
- Corpus framing: technical benchmark document set; technical vocabulary only.
- Executors: Opus agents, full spec, "BUDGET DISCIPLINE: lean tool output". Never respawn a dead agent whose detached job still runs - check disk first.
- Instances: default .env = H157 papers scratch (LIVE); neo4j2 172.19.0.9 READ-ONLY reference; neo4j3 frozen scale artifact; neo4j4 172.19.0.4 = H241/H240 scratch (auth neo4j/kgfoundry).
- vLLM localhost:8010 EXCLUSIVE to H229 until its 15 checkpoints complete - no other requests.

## Live streams

### 1. H229 serial variance + R22 LLM gates - detached nbconvert
- COMPLETE and RECORDED (H229 refuted, H232/H233 closed NO-GO, H239 gate GO recall-gated, H249 refuted) - stream CLOSED; vLLM FREE.
- After 15/15 the SAME notebook runs the gates: H232 seeded (JD<0.3 gate), H233 guided-JSON (>=15% reduction gate), H239 second model (within-1.5x closes; a Qwen server for it was pre-staged detached). Report reports/serving-determinism-h229-*.json expected with H229 verdict + 3 gate recommendations.
- On report: record H229 + gate outcomes (they adjudicate H249's premise and the whole R23/R24 LLM-tier design); then LAUNCH the LLM tier queue (below).
- If dead without report: relaunch resumes from checkpoints: .venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/serving_determinism_h229.ipynb --ExecutePreprocessor.timeout=36000 >> logs/h229-nbconvert.log 2>&1

### 2. H157 corpus transfer - detached launcher + ingest
- COMPLETE and RECORDED (CONFIRMED: lifecycle transfers, ECE breaks 5.18x, self-calibration -> H198) - stream CLOSED.
- After INGEST_OK: spawn analysis agent (R15-H157 registration + notebooks/corpus_transfer_h157.ipynb plan: blind-label ~60 pairs H101 protocol, ECE vs identity-calibration-v2.json, lifecycle clause from events log) -> report -> record.

### 3. R24 graph gates - Opus executor (NOT outage-proof)
- H252 free clause (scanner-audited residue), H253 (severance x attachment linkage), H254 ceiling (graph-as-lexicon vs neo4j2 read-only). Expected: notebooks/remedies_free_gates_r24.ipynb, reports/remedies-free-gates-r24-*.json, logs/r24-free-gates.log.
- If dead without report: respawn with the R24 registrations + the frozen harness spec (r23 notebook) + neo4j2 read-only constraint.

## LLM-tier queue (launch order, after H229 frees the vLLM)
1. R22 gate follow-ups per their outcomes + H249 adjudication (consumes H232 gate artifacts)
2. H241 paired v1/v2 identity A/B on neo4j4 (gates the v2 default flip; registration R15-H241)
3. R23/R24 LLM gates batch: H243 complement (worst-coverage doc), H245+H257 logprob/top-k capture (1 doc x 3), H246 enumerate gate, H248 primed-pass clause (GLiNER lexicon), H251 n-sampling gate, H258 mention-emission clause, H260 adjudication clause, H261 distillation probe (use the frozen demo split)
4. H240 clause (b) union-of-2 ingest arm on neo4j4 (after H241) - merges H250 frontier validation
5. H250 cost frontier -> names the H198 extraction recipe
6. R21 next tier (H218 VLM contest on GPU 2, H224) when a slot frees

## Recording queue
- R24 graph gates (stream 3), H229 + gates (stream 1), H157 (stream 2)

## After the queue drains
H198 wiring sweep (DEF-6 fix, v2 default if H241 passes, winning extraction recipe, H238 retention pricing, GLiNER lexicon stage) -> full re-ingestion -> H113-H117 head-to-head under pinned H207 harness. User-gated: H202, corpus decisions.

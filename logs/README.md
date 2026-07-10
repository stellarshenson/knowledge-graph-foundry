# Logs

Background job logs for Knowledge Graph Foundry.

- `make-install.log` - environment creation and dependency installation
- `neo4j-verify.log` - Neo4j connectivity and plugin verification
- `cpap-ingest-*.log` - end-to-end ingestion runs on the CPAP corpus
- `cpap-rebuild.log` - full R1-R8 engine rebuild of the CPAP graph (R01 measurement)
- `cpap-rebuild-optimize.log` - communities + scorecard for the R01 rebuild
- `proposition-backfill.log` - R02-H11 proposition generation on the R01 graph
- `cpap-rebuild-h10.log` - H10/H12 rebuild against the second Neo4j (values-as-properties + provenance nodes)
- `cpap-rebuild-h10-resume.log` - resumed H10 rebuild on Haiku extraction after Bedrock quota outage
- `h10-optimize.log` - communities + propositions + densification on the rebuilt graph
- `probe-eval-phaseA.log`, `probe-eval-weak.log`, `probe-eval-r03.log` - probe evaluation notebook executions
- `repair-p09.log`, `repair-p19.log` - R04 targeted repair runs against the rebuilt graph
- `vllm-server.log` - local gpt-oss-120b vLLM server (port 8010, 96GB card)
- `r05-wave-*.log` - R05 longevity campaign wave ingestions on the local engine
- `potentials-r10-exec.log` - R10 potentials-family notebook execution (H81/H82/H83/H85/H86 edit-replay)
- `entailment-r18-exec.log` - R18 entailment-instrument notebook execution (H172 NLI sufficiency scorer + H176 graded gradient)
- `instrument-bench-h194-exec.log` - R18-H194 instrument adjudication notebook (value comparator vs NLI vs fuzzy on the 60-pair blind bench)
- `instrument_v2_h195.log` - R19-H195 notebook (retrieval-convention audit + difficulty-engineered wide benchmark v2 construction)
- `instrument_router_h196.log` - R18-H196 + R18-H197 notebook (dropping NLI on the widened prose stratum + graph snapshot fingerprint replay)
- `h158-identity-stack.log` - R15-H158 E2E orchestration: scratch census, wipes, v1/v2 ingest markers, proxy numbers
- `h158-v1-ingest.log` / `h158-v2-ingest.log` - full ingest output of the 26-doc corpus under identity_stack v1 / v2
- `h158-v1-events.jsonl` / `h158-v2-events.jsonl` - JSONL event logs (resolution.merge/defer/block/veto) driving the H158 precision proxy
- `h158-artifact-build.log` - offline fit of data/processed/identity-calibration-v2.json from the H101 benchmark
- `h119-extraction-determinism.log` - R11-H119 per-run extraction progress (3 arms x 5 runs x 10 docs) and verdict line
- `h119-nbconvert.log` - R11-H119 notebook execution output (extraction_determinism_h119.ipynb)
- `h216-h217-image-census.log` - R21-H216/H217 image census + pixel forensics progress (3 extraction arms, montage classification, per-gold adjudication)
- `h216-arm2-docling.log` - R21-H216 Arm 2 (Docling) figure/layout extraction over the 27-doc corpus
- `h226-h227-forensics.log` - R19-H227 probe-pair cross-pairing audit + R19-H226 feature-ownership attachment census (both CPU-only, neo4j2 read-only)
- `h203-h210-scale.log` - R19-H203 exact-k vs HNSW convention A/B + R19-H210 conflict-density census on the wave-2 neo4j3 graph (both CPU-only, read-only)
- `r22-cpu-tier.log` - R22 CPU-tier execution (H230/H231/H234/H235/H236/H237/H238 failure-mechanism analysis on H119 checkpoints, event logs, census, probes; neo4j2 read-only merge sim)
- `h229-gates.log` - R11-H229 serial-vs-concurrent per-run progress + R22 synthetic gates (H232 seed, H233 guided decode, H239 second-model) on the first 3 H119 docs
- `h229-nbconvert.log` - R11-H229 notebook execution output (serving_determinism_h229.ipynb)
- `h239-model-download.log` - Qwen2.5-7B-Instruct Q4_K_M GGUF download for the H239 second-model gate
- `h239-llama-server.log` - llama.cpp server for Qwen2.5-7B on GPU 0 port 8011 (H239)
- `h229-runner.log` - detached script run of the H229/gates harness (same code as the notebook; fills results/h229 checkpoints)

- `r24-free-gates.log` - R24 free-gate tier adjudication (H252 scanner-audited residue, H253 severed-association linkage, H254 graph-as-lexicon ceiling)

- `r26-gates.log` - R26 usage-coupling free-gate adjudication (H271 demand ledger, H273/H274 derived layer vs external cache, H275 recurrence gate, H276 render views, H277 alias harvest, H278 demand decay); nbconvert execution of notebooks/usage_coupling_gates_r26.ipynb

- `r21-vlm-gates.log` - R21 image-tier progress log: H218 describe-then-extract VLM fidelity contest and H224 decorative pre-filter verdicts
- `r21-qwenvl-download.log`, `r21-smolvlm-download.log` - HF snapshot downloads of Qwen2.5-VL-7B-Instruct and SmolVLM-256M-Instruct for the H218 engine contest
- `r21-qwenvl-infer.log`, `r21-qwenvl-infer2.log` - Qwen2.5-VL-7B describe-then-extract inference on the 36 selected images (GPU 0); infer2 is the resumable rerun
- `r21-smolvlm-infer.log` - SmolVLM-256M (Docling picture-description model) inference on the same 36 images

- `h241-ab.log` - R15-H241 paired v1/v2 identity A/B: wipe/init/ingest markers, per-arm wall-clock, measurement lines (both arms on local gpt-oss-120b)
- `h241-v1-driver.log` / `h241-chain.log` - detached driver of the v1 arm and the orchestration chain (wait v1 -> measure -> run v2 -> measure)
- `h241-v1-events.jsonl` / `h241-v2-events.jsonl` - JSONL event logs (resolution.merge/defer/block/veto) driving the H241 precision proxy per arm
- `r27-precision-arms.log` - R27 precision arms (H282-H285/H289) false-merge removal execution

- `r23r24-llm-gates.log` - R23/R24 undersampling LLM-tier gate progress: per-hypothesis compute/verdict markers (H246 enumerate, H248 GLiNER-primed, H243 complement, H258 mention-emission, H251 n-sampling, H245/H257 logprob, H260 adjudication, H261 distillation) against the frozen H119 harness on local gpt-oss-120b
- `r23r24-runbatch.log` - stdout of the resumable batch driver (scratchpad run_batch.py, notebook code as a plain process) populating results/r23r24_llm/ caches and the report JSON
- `r23r24-nbconvert.log`, `r23r24-autorender.log` - nbconvert executions of notebooks/undersampling_llm_gates_r23r24.ipynb (autorender renders the source-of-record notebook from the caches once the batch completes)

- `r24c-llm-gates.log` - R23/R24 LLM-GATE BATCH (R24c) per-gate compute/verdict markers (H243 complement, H246 enumerate, H245/H257 logprob, H251 n-sampling, H248 primed, H258 mention-emission, H260 adjudication, H261 few-shot) on local gpt-oss-120b; source-of-record notebook notebooks/llm_gates_r24c.ipynb, report reports/llm-gates-r24c-*.json
- `r24c-nbconvert.log` - nbconvert execution output of notebooks/llm_gates_r24c.ipynb

- `phase3-rebuild.log` - H198 Phase-3 reproducibility rebuild: TWO clean-state runs of the composed DEFAULT engine (config-phase3.yml, enumerate recipe, v1 identity, concurrency 16) on neo4j4, wipe between; per-run recall + entity-id fingerprint checkpointed to reports/phase3-run{1,2}-{recall,stats}.json for the matching-numbers gate; DONE marker logs/phase3-rebuild.DONE
- `r30-ramp.log` - R30-H341/H342 per-doc concurrency ramp on the real extraction workload (detached; steps checkpoint to results/r30/ramp-steps.jsonl)
- `r31-h353-gate.log` - R31-H353 gold-carrier chunk gate for union-of-K (6 passes/chunk; checkpoints to results/r31/h353-chunks.jsonl)
- `r34-h366-passages.log` - H366 passage-node prototype: bge-m3 chunk embedding + M-sweep recall@16 (report reports/r34-h366-passages-*.json)
- `r34-h366-trunc.log` - H366 budgeted-render arm: head-truncation sweep at M=1 (report reports/r34-h366-trunc-*.json)
- `r34-h366-window.log` - H366 query-anchored window arm: span sweep (900/1200 x k1/k2) for the <=30% budget clause (report reports/r34-h366-window-*.json)
- `r34-h369-specificity.log` - H369 specificity seed re-ranking A/B: base vs linear vs log IDF prior (report reports/r34-h369-specificity-*.json)
- `r34-h367-propseeds.log` - H367 proposition-seeded render A/B: in-memory deterministic propositions, bge-m3, arms A-D (report reports/r34-h367-propseeds-*.json)
- `r34-h370-simexpand.log` - H370 SIMILAR_TO expansion forward arm (report reports/r34-h370-simexpand-*.json)
- `r34-composed-frontier.log` - R34 composed frontier: parity + H367B prop seeds + H366 s900k1 window (report reports/r34-composed-frontier-*.json)
- `r37-h382-ladder.log` - R37-H382 arm 1: H181 top-score sufficiency gate over the 3-rung escalation ladder, 2-fold cross-calibration (report reports/r37-h382-ladder-arm1-*.json)
- `r36-h379-cardinality.log` - R36-H379 inference arm: cardinality profiles per relationship type, functional candidates (report reports/r36-h379-cardinality-*.json)
- `r38-h383-crc.log` - R38-H383 CRC certificate fit on the H382 escalation ledger: alpha sweep, monotonicity check, out-of-fold verification (report reports/r38-h383-crc-*.json)
- `r38-h386-monitor.log` - R38-H386 two-channel drift monitor simulation: mixture-LR sequential test + label-free escalation-rate sketch over bootstrap replays (report reports/r38-h386-monitor-*.json)
- `r38-h385-engine-replay.log` - R38-H385 engine replay (context side): live passage build on the pile + 24-probe three-arm replay through the shipped gated read path (report reports/r38-h385-engine-replay-*.json)
- `r36-h376-justifications.log` - R36-H376 justification reconstruction + dirty-flag flood on the pile (report reports/r36-h376-justifications-*.json)
- `r36-h380-worth.log` - R36-H380 outcome-linked worth counters over 96 replayed probe-episodes (report reports/r36-h380-worth-*.json)
- `r35-h375-sdr.log` - R35-H375 SDR signature overlap vs cosine blocking head-to-head, post- and pre-repair arms (report reports/r35-h375-sdr-*.json)
- `r35-h374-consensus.log` - R35-H374 multi-view consensus voting: entity/prop/span channels, RRF + agreement ranking (report reports/r35-h374-consensus-*.json)

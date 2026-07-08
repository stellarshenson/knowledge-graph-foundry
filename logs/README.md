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

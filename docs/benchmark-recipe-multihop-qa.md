# Open Benchmark Recipe - Multi-hop QA vs Published Peers

KGF enters the HippoRAG-2 comparison table: HotpotQA / MuSiQue / 2WikiMultiHopQA against published GraphRAG, LightRAG and HippoRAG-2 numbers, under their standardized regime so every delta is attributable to KGF architecture. Peers are never re-run; their numbers come from the HippoRAG-2 paper.

## Contents

- [Regime](#regime) - the fixed protocol
- [Benchmark selection](#benchmark-selection) - which benches we run, which we skip, and why
- [Data](#data) - what is on disk, what each file is for
- [Infrastructure](#infrastructure) - models and serving layout
- [Harness](#harness) - what must be built
- [Execution phases](#execution-phases)
- [Checklist](#checklist)
- [Open decisions](#open-decisions)

## Regime

The comparison is valid only if KGF runs the exact protocol behind the peer numbers. Deviations invalidate the headline table.

- **Question sets** - the sealed 1000-question subsets per dataset (IRCoT sampling, reused by HippoRAG v1/v2); one evaluation run each, no repeats-until-good
- **Corpora** - the pooled passage collections shipped with the subsets; KGF ingests the corpus, builds the graph, retrieves, answers
- **Backbone** - Llama-3.3-70B-Instruct served locally, for BOTH graph construction and QA reading (user decision 2026-07-10); gpt-oss-120b optional as an appendix second backbone
- **Metrics** - QA EM and F1 on answers; passage recall@5 on retrieval; exact metric definitions verified against the HippoRAG-2 paper before any scoring code is written
- **Peer numbers** - lifted verbatim from the HippoRAG-2 paper table (their standardized re-runs of GraphRAG and LightRAG included); paper archived under `references/papers/` with digest per the paper rule
- **Split discipline** - sealed sets are never used for tuning, prompt iteration or hypothesis rounds; tuning draws only on full-dev questions outside the sealed 1000s

## Benchmark selection

Which public benchmarks the campaign runs and which it deliberately skips (user decision 2026-07-13). A bench earns a WANT only if its regime matches a KGF claim and its peer numbers are trustworthy or re-runnable under one shared harness.

| Benchmark | Verdict | Regime | Why |
|---|---|---|---|
| 2WikiMultiHopQA | **RUNNING** | multi-hop doc QA | scale-ladder substrate (scout/small/medium live); peer numbers in HippoRAG-2 table |
| HotpotQA | **WANT** | multi-hop doc QA | headline peer table (GraphRAG/LightRAG/HippoRAG-2); sealed 1000-q set on disk |
| MuSiQue | **WANT** | multi-hop doc QA | hardest of the trio (peers ~46-49 F1); sealed set on disk |
| LongMemEval-S (2410.10813) | **WANT - subset first** | long-term chat memory, 5 abilities | abstention is a first-class scored ability - the gap-ledger / structural-refusal (H17 lineage) differentiator no doc-QA bench scores; ~30% commercial-assistant drop = headroom |
| LOCOMO (2402.17753) | **SKIP** | conversational memory | vendor-benchmark theatre (Zep 84 -> 58.4 -> 75.1 corrections); adversarial cat-5 scoring disputes; regime owned by memory-layer products, not doc-graph engines; revisit only as an appendix if LongMemEval lands well |
| BEIR (2104.08663) | **SKIP** | flat IR retrieval | retrieval-only suite; no graph/multi-hop claim to test; dense incumbents saturate it |
| Code-intelligence (graphify ERPNext-style) | **SKIP** | repo QA | not KGF's corpus class; tree-sitter substrate, different engine entirely |

- **LongMemEval-S processing caveat** - each of the 500 questions ships its OWN ~115k-token session haystack, so a graph system ingests per-question; the full set is ~500 ingests. Entry point: the n=50 English subset (the slice graphify used, 76% tied with dense RAG), which prices the regime for one detached batch. Abstention + knowledge-update abilities are the two KGF should differentiate on; information-extraction is dense-RAG-favored
- **Sessions-as-documents mapping** - one chat session = one KGFDocument, session timestamp as document date; temporal-reasoning questions then exercise the bitemporal/versioning direction ([KGF longevity requirements](../.claude/memories/), H157-class)
- **Judge discipline import (from graphify's harness)** - whatever runs, answers are graded by an LLM judge blind-validated against a second judge on a sample (target Cohen's kappa >= 0.8, verbatim-quote grading); single-vendor unvalidated judging is what made LOCOMO numbers worthless
- **Abstention scoring** - on LongMemEval, KGF's `query()` miss/refusal path is scored as an ANSWER (the abstention ability rewards it); the harness must not treat refusal as failure on unanswerable questions

## Data

All benchmark data lives in `data/external/multihop-qa-benchmarks/` (read-only, provenance in `data/external/README.md`).

- **Sealed eval** - `hotpotqa.json` (1000 q), `musique.json` (1000 q), `2wikimultihopqa.json` (1000 q); source: HippoRAG `reproduce/dataset/`
- **Corpora** - `hotpotqa_corpus.json` (9,811 docs), `musique_corpus.json` (11,656 docs), `2wikimultihopqa_corpus.json` (6,119 docs); title + text passages
- **Tuning slice** - `hotpot_dev_distractor_v1.json` (7,405 q, canonical CMU host) minus the sealed 1000; MuSiQue/2Wiki dev files added later only if per-dataset tuning proves necessary
- **Corpus shape** - passages route through the standard unstructured chunk-and-extract path; one passage = one document (title as document id)

## Infrastructure

Two models served concurrently on separate cards; both must be up before any run.

- **LLM** - Llama-3.3-70B-Instruct on the RTX PRO 6000 (96 GB, GPU index 1) via vLLM; fp8 path per my-gpu recipe (~275 tok/s batched); same server drives extraction and QA reading
- **Embedder** - NV-Embed-v2 (~7B, Mistral-based) on the RTX PRO 4000 (24 GB, GPU index 0) if the parity decision lands; otherwise KGF-shipped Titan via Bedrock
- **Graph** - dedicated Neo4j scratch container per dataset run (wipe between runs, DEF-4/DEF-5 discipline)
- **Configs** - one pinned `config-bench-<dataset>.yml` per dataset, committed before the sealed run; throughput settings from the R30/H363 measured knee, never hand-tuned mid-run
- **Detached compute** - every ingest and eval run launched via setsid/nohup, teed to `logs/`, checkpointed to `reports/experiments/bench/`; runs must survive the driver

## Harness

Four build items, each small; no framework.

- **Corpus loader** - `*_corpus.json` -> KGF document stream (title = doc id, text = body); target: `src/knowledge_graph_foundry/ingest/`
- **QA adapter** - benchmark question -> KGF query; captures retrieved passages + final answer per question to `reports/experiments/bench/<dataset>-answers.jsonl`
- **Scorer** - EM/F1 (normalized answer match, the standard HotpotQA normalization) + recall@5 against gold supporting passages; pure offline script over the answers file
- **Reader prompt** - QA answering prompt matched to the HippoRAG-2 setup (verify from their repo/paper); pinned in the bench config, identical across datasets

## Execution phases

1. **Verify regime** - archive HippoRAG-2 paper + digest, extract the exact peer table, metric definitions and reader setup; correct this document where memory was wrong
2. **Serve** - stand up Llama-3.3-70B vLLM + embedder; record tok/s sanity numbers
3. **Build harness** - loader, adapter, scorer, reader prompt; unit-test the scorer against published examples
4. **Smoke** - full pipeline on a 50-question tuning slice; sanity: recall@5 > dense-retrieval floor, wall-clock per question measured
5. **Tune** - iterate KGF settings (typing regime, retrieval depth, reader prompt) on the tuning slice only; register each tuning experiment as a hypothesis in the experiments log
6. **Seal-run** - one run per dataset on the sealed 1000s with the pinned config; no re-runs on bad numbers - the result is the result
7. **Report** - KGF row alongside the peer table, with backbone/embedder parity stated; deviations (if any) listed explicitly

## Checklist

- [ ] HippoRAG-2 paper archived in `references/papers/` + digest; peer table, metrics and reader setup extracted
- [ ] Regime section of this document corrected against the paper
- [ ] Llama-3.3-70B-Instruct weights acquired; vLLM serving on GPU 1; sanity tok/s recorded
- [ ] Embedder decision executed (NV-Embed-v2 on GPU 0, or Titan fallback recorded as deviation)
- [ ] `hotpot_dev_distractor_v1.json` download completed and JSON-verified
- [ ] Tuning slice built: full dev minus sealed 1000 ids, persisted with fixed seed
- [ ] Corpus loader built + loads all 3 corpora (9,811 / 11,656 / 6,119 docs)
- [ ] QA adapter built; answers checkpoint to `reports/experiments/bench/`
- [ ] Scorer built; validated against published EM/F1 worked examples
- [ ] Reader prompt pinned in bench configs
- [ ] Smoke run: 50 tuning questions end-to-end, per-question wall-clock recorded
- [ ] Tuning experiments registered as hypotheses before running; sealed sets untouched
- [ ] Per-dataset `config-bench-*.yml` pinned and frozen
- [ ] Seal-run HotpotQA (1000 q, one shot)
- [ ] Seal-run MuSiQue (1000 q, one shot)
- [ ] Seal-run 2WikiMultiHopQA (1000 q, one shot)
- [ ] Report table: KGF vs GraphRAG / LightRAG / HippoRAG-2, parity and deviations stated

## Open decisions

- **Embedder parity** - NV-Embed-v2 (full parity, proposed headline) vs KGF-shipped Titan (product number); awaiting user word
- **Typed vs schema-free extraction** - whether KGF's cured ontology helps or hurts on open-domain Wikipedia; registered as a hypothesis candidate for the benchmark round, decided on the tuning slice
- **Sequencing** - benchmark rounds begin post-R31 (current fix chain stays on CPAP); harness build can proceed any time, it needs no GPU

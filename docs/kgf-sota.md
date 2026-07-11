# Knowledge Graph Foundry - SOTA Design

**Canonical SOTA Document**

The distilled design of the shipped engine: components that survived hypothesis adjudication, with the measurement system that governs every change. Evidence lives in the canonical experiments log ([kgf-redesign-experiments.md](experiments/kgf-redesign-experiments.md)) and the promotions ledger ([sota-promotions.md](sota-promotions.md)); this document carries only what ships. Design sections are added as campaigns converge - the Metrics section leads because the measurement system is the part every other section is judged by.

## Metrics

Every KGF change is adjudicated by instruments, not impressions - each metric below states what it measures, how, and why it earns its place. A delta counts only when it clears the instrument's measured noise floor (the H351 rule: bands priced off run-to-run variance, never magic tolerances).

### Retrieval and answer quality

- **Evidence recall (probe harness)** - what: share of gold evidence present in the retrieved context, per probe, averaged over the probe set - how: gold strings matched in the normalized joined context (`notebooks/h158_measure.py`), engine-parity retrieval (overfetch stamped in every report, DEF-14) - why: retrieval quality independent of the reader; the primary lever-adjudication metric of every R-round
- **Entailment sufficiency (H172)** - what: whether retrieved context semantically entails each atomic gold unit - how: mDeBERTa NLI cross-encoder, atomic-unit max-entailment, 1.8 ms/pair, 94% human agreement - why: string matching misses paraphrase; this is the benchmark instrument for sufficiency claims, and any conclusion generated with the retired fuzzy matcher is flagged for re-adjudication
- **Probe-set discipline (H186)** - what: a constraint, not a number - how: probe golds must be document-grounded, never graph-derived - why: graph-derived golds saturate at 99.2% and erase the very levers under test
- **Benchmark EM / F1 / recall@5 (#59, incoming)** - what: answer exact-match and token-F1 (HotpotQA normalization), gold-passage recall in the top 5 - how: `scripts/bench_score.py` over the QA adapter's answers JSONL, sealed 1000-question sets, one shot - why: the public comparison surface against GraphRAG / LightRAG / HippoRAG-2 published numbers
- **Tokens per answered query (#59, incoming)** - what: retrieval context tokens + LLM call count per question - how: logged by the QA adapter per question from the first version - why: the peer table prices nothing; single-shot retrieval at a fraction of an agentic walk's bill (PoG: 8,156 tok / 13.3 calls per question) is a headline claim only a cost column can express

### Graph quality and identity

- **Identity precision (H101 benchmark)** - what: SAME_AS decision quality - how: 298 adjudicated pairs with evidence strings; precision proxy on live edges - why: false merges corrupt silently; the adjudicated set is the ground truth the resolver is scored against
- **Calibration ECE** - what: whether the resolver's posterior means what it says - how: isotonic-calibrated Titan cosine on adjudicated labels (ECE 0.050); per-corpus refit mandated by the H157 transfer failure (5.18x ECE cross-corpus) - why: a mis-calibrated confidence poisons every downstream threshold
- **Extraction variance (H107)** - what: run-to-run instability of what the extractor emits - how: repeated single-chunk extraction, Jaccard over emissions - why: measured at 71%, the dominant identity root cause; the metric that adjudicates every determinism lever
- **Coverage certificate (R39-H389, registered)** - what: per-document fact coverage - the fraction of source facts the graph actually holds - plus a named miss list - how: verbatim-grounded fact probes per chunk, graph-support test, KGGen-MINE style adjudication; reproducibility bar +-2% - why: every published extractor silently drops 34-70% of source facts; "does not miss information" is a claim only a certificate can back

### Operations

- **Throughput (gen tok/s + chunks/min)** - what: real document-grinding rate - how: vLLM counter deltas over stability-gated 600s windows with an occupancy guard >= 0.95c (H388 fast rung); total tok/s rejected as the metric - prompt-mix noise ~+-10% at short windows - why: feeds the H362 calibrator; ingest runs at a measured knee (c=56, 3.4x the old default), not a guess
- **Latency envelope (p50/p95/max per chunk)** - what: per-request wall time at the operating point - how: recorded per calibration rung - why: a knee whose latency violates the client timeout is not shippable (H342); sets `llm.timeout`
- **Warm-start band** - what: is the cached calibration still true - how: first real window vs cached mean +-3 sigma (chunks/min) - why: trust-but-verify; a changed setup recalibrates instead of silently underperforming
- **Progressive regression trajectory** - what: whether growing the graph degrades previously-working queries - how: external prober (`scripts/bench_progressive_probe.py`) replays every benchmark question whose gold passages are fully ingested, each cycle, through the public `Foundry.probe()` retrieval-only surface; a pass -> fail transition is a flagged regression - why: scale-induced regressions (identity collisions, ranking dilution) are invisible to end-state evaluation; the trajectory catches them at the document where they begin

### Gate and abstention

- **Escalation gate signal** - what: per-query "is the base render sufficient" - how: top-seed index score against a CRC-fitted threshold (alpha = 0.08 certificate, fitted at optimize-time, checked at query-time for one float comparison) - why: the only sanctioned second retrieval round; alpha bounds the escalation rate so the second hop stays rare and priced
- **Miss / abstention detection** - what: queries the graph cannot answer - how: top-seed similarity short-circuit (86.7% miss detection, 0% false abstention, 95% token cut on the miss class, H181) - why: honest "not in corpus" beats a confident hallucination and costs almost nothing

### Measurement discipline

- **Noise floors before verdicts** - every continuous metric carries a measured run-to-run sigma; a hypothesis delta below its instrument's band is INCONCLUSIVE, never CONFIRMED (H351; DEF-11 is the standing counterexample)
- **Per-attempt counting** - retries mask storms: throughput and throttle instruments count raw request ATTEMPTS at the client, never goodput (H341's contamination is the standing counterexample)
- **Instrument-first sequencing** - rounds that need a new metric build and validate the instrument before the levers (R39 sequences H389 before every coverage hypothesis)
- **Resolution roadmap** - the 24-probe harness is saturated (23/24); gradient-tracking metrics with power analysis at 1000-question scale are under research (R42 brief in flight)

# KGF v1 Lessons - Carry-Forward Report

Review of the archived knowledge-graph-foundry v1 (28 benchmark iterations on a 10-document CPAP corpus, hybrid score 88% → 72% → 90%). The real asset is the empirically validated ontology-evolution machinery and the written post-mortems.

## Proven techniques worth carrying forward

**1. Intent-driven ontology discovery** - a free-text `intent` string ("compare CPAP devices for patients and doctors...") injected into extraction prompts, seed normalization, and type clustering. Fixed the single worst failure (type proliferation: 31-33 ad-hoc types for an 8-12 type domain). Deterministic score jumped 87% → 95% in v18; with intent, doc 1 discovers all final types and 0 new types emerge afterwards. v1 file: `knowledge_graph_foundry/extraction/prompts.py`. Cheapest, highest-leverage idea in the codebase.

**2. Fluid → cured two-phase ingestion ("schema curing")** - graph data held in memory while the schema is fluid; only after the type system stabilizes is it consolidated and flushed to Neo4j; remaining documents load in a cured phase resolved against the live graph. Cured naturally at doc 4/10. v1 files: `curing/accumulator.py`, `curing/detector.py`, `docs/curing_design.md`.

**3. Information-theoretic stability metrics as the curing signal** - 11 metrics from information theory (Shannon entropy delta, KL, JSD), computational linguistics (Heaps' beta, Zipf R²), ecology (Chao1 coverage, ACE). Early signals: JSD < 0.02 from doc 2. Confirmation: Chao1 0.881 → 0.956, entropy delta 0.0568 → 0.0002 at doc 4. Validated composite criterion: `JSD < 0.02 AND Chao1 > 0.95 AND entropy_delta < 0.01`. v1 `curing/metrics.py` is stdlib-math only, decision-free - ideal for the drift-detection layer. Check order: `is_converged() → is_plateau() → is_cured() → force`.

**4. Bayesian cross-type entity resolution** - odds-form posterior `P(same_entity | evidence)`: prior from name identity (0.8 identical / 0.2 fuzzy / 0.95 hierarchy-sibling), times LR_desc (Jaccard on stop-word-filtered words, floored at 0.3 so it never fully vetoes), LR_emb (cosine, neutral 1.0 if absent), LR_cooc (1.5 shared chunk / 0.9 none). Threshold 0.6, three-zone logic (merge / defer 0.4-0.6 / block). Cut cross-type duplicates 56 → 39. v1: `extraction/resolution.py:_cross_type_posterior` - ~40 lines, portable as-is.

**5. Post-cure drift detection** - per-document remap rate (entities force-remapped during type enforcement); rate > 0.3 for 3 consecutive docs signals drift; warning by default, opt-in re-cure. v1: `curing/detector.py:check_drift`. Seed for the continuous-ingestion drift detector, combined with #3's JSD/entropy tracked post-cure.

**6. FSM with graph-persisted control metanode** - six states (EMPTY → INITIALIZING → CURING → STABLE ⇄ RECURING, FAILED); metanode persists the control node, run nodes, transition history, ontology types, calibration curves, and a compressed fluid-cache into Neo4j itself - the graph is the single source of truth for resumability. v1: `fsm/states.py`, `fsm/metanode.py`.

**7. Embeddings provider fallback with single-provider-per-run lock** - Bedrock Titan v2 (1024-dim) with automatic fallback to local sentence-transformers MiniLM (384-dim) on first-call failure; module-level lock prevents mid-run provider switches that would corrupt exemplar index dimensionality. v1: `extraction/embeddings.py` - clean, portable.

**8. Isotonic posterior calibration** - collects (raw_posterior, was_correct) observations, fits IsotonicRegression, persists curve to graph metanode, applies on subsequent runs. v1: `curing/calibration.py`. Mechanism right; needs a bigger ground-truth set than v28's 25 pairs.

**9. Event architecture** - 41 named blinker signals across 10 categories, ~50 Pydantic payload models, JSONL streaming accumulator, decision events carrying actual LR values. v1: `events/signals.py`, `events/types.py`. This made benchmark forensics possible.

**10. LLM cassette test harness** - record/replay client mimicking instructor's `chat.completions.create`, JSON cassettes with response-model registry. ~504 deterministic test functions with no API. v1: `tests/llm_cassette.py`.

**11. Two-layer type normalization** - deterministic always-on (space/underscore/camelCase → PascalCase) plus one LLM clustering call at curing time for semantic synonyms. v1: `extraction/normalization.py`, `curing/type_clustering.py`.

**12. Benchmark judge-context lesson (H8)** - expanding the LLM-judge's query context moved hybrid 84 → 88 with zero pipeline changes. Measure-before-fix: two of the biggest "failures" were benchmark bugs.

Also: deterministic SHA1 chunk IDs with sentence-boundary snapping (`extraction/chunking.py`), APOC native relationship types (not RELATES_TO + property), multi-label nodes via `apoc.create.addLabels`.

## Known failure modes and lessons

- **Cross-type duplicates are ontological, not evidential** - the dominant never-fully-solved failure (56 → ~39-52 residual). The ambiguous 0.4-0.6 zone contains mostly legitimately dual-role entities (humidifier IS both Component and Accessory); evidence accumulation confirms the ambiguity rather than resolving it. Lesson: model multi-type/multi-label entities as first-class graph pattern from day 1
- **Bolted-on type hierarchy was completely inert** (v23, -5 points) - evolution ran only post-ingestion, thresholds counted documents not encounters, auto-merge bypassed the Bayesian model. Fix pattern: evolve per-encounter during ingestion; hierarchy is a prior boost - "evidence, not an override"; never let a heuristic bypass the probabilistic model
- **Double enforcement** - type clustering ran at curing, then enforcement silently overwrote its decisions. Lesson: one owner per decision
- **Dedup key encodes type** - `sha1("{type}:{name}")` entity IDs mean the same entity under two types can never dedup exactly. Derive identity from name/embedding; type is a mutable attribute
- **Within-type synonym proliferation unsolved** - 36 tubing nodes, 38 filter nodes; Levenshtein catches case variants but not "circuit tubing" vs "connecting tubing". Needs embedding clustering within type blocks
- **Extraction variance** - non-deterministic extraction caused duplicate counts to swing (39 → 52 between identical runs). Multi-pass extraction with convergence signal addresses this
- **Design ambition >> delivery** - 3,311-line design doc; Strands agents, TUI, query/update, structured-data pipeline never implemented. Spec incrementally against working code

## Reusable code candidates (near-verbatim ports from @archive/kgf-v1)

- `extraction/embeddings.py` - provider fallback + run lock (239 lines)
- `extraction/resolution.py` - `_cross_type_posterior`, `_description_similarity`, `_compute_lr_values`, `_UnionFind`
- `curing/metrics.py` + `curing/detector.py` - 11 stability metrics (stdlib-only), convergence/plateau/drift checks
- `curing/calibration.py` - isotonic calibrator with JSON persistence (105 lines)
- `extraction/chunking.py` - tiktoken chunker with sentence snapping, deterministic IDs (113 lines)
- `tests/llm_cassette.py` + conftest cassette pattern - the whole test strategy
- `fsm/states.py` + `fsm/metanode.py` - state definitions and graph-persistence
- `events/` - signal catalogue and JSONL accumulator pattern
- `extraction/normalization.py` - deterministic type-name normalization
- `docs/curing_design.md`, `docs/failure-hypothesis.md` - distilled experimental record

## Architecture verdicts

- **Keep: direct litellm+instructor hot path** with strict agent-escalation criteria; pipeline functions pure, importable, framework-independent
- **Keep: graph as single source of truth** (FSM metanode, calibration curves, ontology types, fluid cache in Neo4j) - resume, recovery, multi-session continuity fall out for free
- **Keep: fluid buffer + metric-driven curing** as the core lifecycle, with per-encounter evolution and the probabilistic model owning every merge decision
- **Abandon: single-type entity identity** - identity from name+embedding, types as multi-label attributes, dual roles as expected structure
- **Abandon: spec-first monolithic design** - institutionalize the hypothesis → change → measure → post-mortem loop (hybrid deterministic + LLM-judge benchmark, versioned scorecards, per-hypothesis impact accounting) as the primary development process

# Acceptance Criteria - Engine Rewiring R49/R50

Evidence-driven rewiring package. Package A flips evidence-killed defaults OFF (code + config override retained). Package B wires in proven winners as new modules with unit tests. Defaults for Package B chosen so existing-graph behavior is not silently changed.

Module: `knowledge_graph_foundry` (src layout). Validation: `make test` (via `.venv/bin/pytest`) green, `make lint` (ruff) clean. Neo4j not required - unit tests only.

## Package A - evidence-killed defaults -> gate OFF

- [ ] A1 - `QuestionSettings.enabled` default is `False` (R46-H499: +0.0076 lift at n=132)
- [ ] A1 - config override to `True` still honored; ingest generation + link + read-channel call sites gate on the setting; existing KGFQuestion nodes untouched (no delete path added)
- [ ] A1 - test asserts new default `False` AND the `True` override
- [ ] A2 - community detection + summaries default OFF via new `GraphRAGSettings.communities_enabled = False` (H68/H528: zero query-time readers)
- [ ] A2 - `optimize()` skips `detect_communities`/`summarize_communities` unless `communities_enabled` is True; override restores them
- [ ] A2 - test asserts new default `False` AND the `True` override
- [ ] A3 - `GraphRAGSettings.similarity_edges_enabled` default is `False` (kNN SIMILAR_TO densification for PPR reach; no default reader while `ppr_enabled` off)
- [ ] A3 - `optimize()` call site honors the flag (already gated); test asserts new default `False` AND `True` override
- [ ] A4 - `DriftSettings.cusum_enabled` default is `False` (R28-H306/H308: oracle TP=0; noise-triggered recure mutates cured ontology)
- [ ] A4 - detection path (`_evaluate`) still runs when disabled (warn/rebuild recommendation preserved); the CUSUM recure ACTION path is off by default
- [ ] A4 - test asserts new default `False` AND the `True` override
- [ ] A5 - `GraphRAGSettings.render_budget` default is `1.0` (was 0.6; DEFECT: 0.6 drops answer-carrying blocks - H547/H570/H572/H576)
- [ ] A5 - render call site honors it (1.0 disables truncation); test asserts new default `1.0` AND an explicit sub-1.0 override

## Package B - proven winners -> wire IN

- [ ] B1 - `graph/attacher.py` exposes `attach(fact_span, doc_entities, llm)` (R49-H568 11/11 + H567 gate + H560/H561 candidate pool)
- [ ] B1 - ladder: artifact abstain gate (regex + LLM confirm, H567) -> exact/normalized name-match fast path (H569, tie -> longest) -> LLM attacher with source span (H568 prompt shape)
- [ ] B1 - candidate pool = same-doc entity set (caller-supplied `doc_entities`); LLM is an injected callable; reasoning_content/headroom note documented
- [ ] B1 - unit tests with a fake LLM cover each ladder rung (name-match, artifact abstain, regex-miss skips LLM, LLM pick, LLM abstain)
- [ ] B2 - `stage_fact_on_anchor(driver, anchor_id, fact_text, ...)` appends fact to anchor description + records provenance in a `staged_facts` list property (timestamp + source) (R49-H576)
- [ ] B2 - NO re-embed by default; `reembed=True` optional path re-embeds via an injected embed_fn (H576: re-embed inoperative for the flip)
- [ ] B2 - unit tests: staging appends + provenance recorded; no embedding write when `reembed=False`; embedding written when `reembed=True`
- [ ] B3 - `EmbeddingSettings.provider` gains a local e5 option; Titan default UNCHANGED (`provider="bedrock"`, `amazon.titan-embed-text-v2:0`)
- [ ] B3 - e5 provider honors conventions: `"query: "`/`"passage: "` prefixes (module constants), sentence-transformers mean pooling, bf16 on GPU (guarded)
- [ ] B3 - unit test with a stubbed model asserts passage-prefix applied + embeddings populated; new-graphs-only caveat documented (dimension mismatch)
- [ ] B4 - audit module (`graph/audit.py`) exposes per-doc `document_certificate` returning `{coverage, missing_spans}` + `corpus_summary` (H389/H512, H548 per-doc gate)
- [ ] B4 - deterministic gates (`grounded`, `supported`, `content_terms`, `generate_probes`) live in the module; the script imports them and still runs; `test_h389_audit.py` collects and passes
- [ ] B4 - unit tests on synthetic fixtures for the certificate + corpus summary
- [ ] B5 - same audit module exposes `seed_hop_distance(adjacency, seeds, target)` over an Entity-only, SIMILAR_TO-excluded adjacency (R49-H573, AUC 0.681)
- [ ] B5 - unit tests: seed-is-target 0 hops, one/two-hop reach, unreachable returns None
- [ ] B6 - `ProbeSettings.manifest` setting added and plumbed; `knowledge_graph_foundry/probe.py` exposes `load_manifest` + `select_manifest` (R49-H541 paired frozen probes)
- [ ] B6 - `scripts/bench_progressive_probe.py` gains a `--manifest` flag: when set, the eligible probe set is the fixed manifest ids in manifest order (no resampling)
- [ ] B6 - unit test for manifest loading + ordering determinism (JSON and text forms, dedup preserving order)

## Global

- [ ] `make test` green (no NEW failures vs baseline: 490 passed / 18 skipped; pre-existing `test_cli.py::test_query_prints_answer` Rich-ANSI failure reported, not fixed)
- [ ] `make lint` clean (ruff format check + ruff check)
- [ ] Surgical: every changed line traces to a package item; no drive-by refactors
- [ ] Commits are logical units with conventional messages citing hypothesis IDs
- [ ] No edits to `docs/experiments/*`, `.claude/JOURNAL.md`, `RECOVERY-STATE.md`

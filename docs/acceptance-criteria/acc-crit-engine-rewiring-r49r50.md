# Acceptance Criteria - Engine Rewiring R49/R50

Evidence-driven rewiring package. Package A flips evidence-killed defaults OFF (code + config override retained). Package B wires in proven winners as new modules with unit tests. Defaults for Package B chosen so existing-graph behavior is not silently changed.

Module: `knowledge_graph_foundry` (src layout). Validation: `make test` (via `.venv/bin/pytest`) green, `make lint` (ruff) clean. Neo4j not required - unit tests only.

Validation status recorded after implementation. All criteria PASS. Two lint failures are PRE-EXISTING and out of scope (see Global).

## Package A - evidence-killed defaults -> gate OFF

- [x] A1 - `QuestionSettings.enabled` default is `False` (R46-H499: +0.0076 lift at n=132) - PASS
- [x] A1 - config override to `True` still honored; ingest generation + link + read-channel call sites gate on the setting; existing KGFQuestion nodes untouched (no delete path added) - PASS (pipeline.py:527/584 ingest gates, :1553 read-channel gate; no delete added)
- [x] A1 - test asserts new default `False` AND the `True` override - PASS (test_questions.py)
- [x] A2 - community detection + summaries default OFF via new `GraphRAGSettings.communities_enabled = False` (H68/H528: zero query-time readers) - PASS
- [x] A2 - `optimize()` skips `detect_communities`/`summarize_communities` unless `communities_enabled` is True; override restores them - PASS (pipeline.py optimize())
- [x] A2 - test asserts new default `False` AND the `True` override - PASS (test_retrieval_levers.py)
- [x] A3 - `GraphRAGSettings.similarity_edges_enabled` default is `False` (kNN SIMILAR_TO densification for PPR reach; no default reader while `ppr_enabled` off) - PASS
- [x] A3 - `optimize()` call site honors the flag (already gated); test asserts new default `False` AND `True` override - PASS
- [x] A4 - `DriftSettings.cusum_enabled` default is `False` (R28-H306/H308: oracle TP=0; noise-triggered recure mutates cured ontology) - PASS
- [x] A4 - detection path (`_evaluate`) still runs when disabled (warn/rebuild recommendation preserved); the CUSUM recure ACTION path is off by default - PASS (test_detection_runs_when_disabled)
- [x] A4 - test asserts new default `False` AND the `True` override - PASS (test_drift.py TestCusumDefault)
- [x] A5 - `GraphRAGSettings.render_budget` default is `1.0` (was 0.6; DEFECT: 0.6 drops answer-carrying blocks - H547/H570/H572/H576) - PASS
- [x] A5 - render call site honors it (1.0 disables truncation); test asserts new default `1.0` AND an explicit sub-1.0 override - PASS (pipeline.py:1503; test_retrieval_levers.py)

### A3 scope note (flagged for coordinator)

A3 was scoped to `graphrag.similarity_edges_enabled` - the R02-H13 kNN densification whose sole purpose is "for PPR reach", the canonical no-reader SIMILAR_TO write. Two other SIMILAR_TO producers were deliberately NOT flipped: `resolution.soft_links` (defer-zone SIMILAR_TO, H268) and the `resolution.demotion_court` (H290 demote-don't-delete, which writes soft links directly regardless of the `soft_links` flag). Reason: `test_registered_resolution_defaults` explicitly guards `soft_links is True` as a registered-verdict change requiring "ledger + GAP-1 + DEF-10, re-run the decider, never a silent edit", and the demotion court is a safety mechanism the A-package does not name. If the intent is to zero ALL SIMILAR_TO writes, flipping `soft_links` (and reconciling the demotion court) is a separate registered-verdict decision - not folded in silently here.

## Package B - proven winners -> wire IN

- [x] B1 - `graph/attacher.py` exposes `attach(fact_span, doc_entities, llm)` (R49-H568 11/11 + H567 gate + H560/H561 candidate pool) - PASS
- [x] B1 - ladder: artifact abstain gate (regex + LLM confirm, H567) -> exact/normalized name-match fast path (H569, tie -> longest) -> LLM attacher with source span (H568 prompt shape) - PASS
- [x] B1 - candidate pool = same-doc entity set (caller-supplied `doc_entities`); LLM is an injected callable; reasoning_content/headroom note documented - PASS
- [x] B1 - unit tests with a fake LLM cover each ladder rung (name-match, artifact abstain, regex-miss skips LLM, LLM pick, LLM abstain) - PASS (test_attacher.py)
- [x] B2 - `stage_fact_on_anchor(driver, anchor_id, fact_text, ...)` appends fact to anchor description + records provenance in a `staged_facts` list property (timestamp + source) (R49-H576) - PASS
- [x] B2 - NO re-embed by default; `reembed=True` optional path re-embeds via an injected embed_fn (H576: re-embed inoperative for the flip) - PASS
- [x] B2 - unit tests: staging appends + provenance recorded; no embedding write when `reembed=False`; embedding written when `reembed=True` - PASS
- [x] B3 - `EmbeddingSettings.provider` gains a local e5 option; Titan default UNCHANGED (`provider="bedrock"`, `amazon.titan-embed-text-v2:0`) - PASS
- [x] B3 - e5 provider honors conventions: `"query: "`/`"passage: "` prefixes (module constants), sentence-transformers mean pooling, bf16 on GPU (guarded) - PASS
- [x] B3 - unit test with a stubbed model asserts passage-prefix applied + embeddings populated; new-graphs-only caveat documented (dimension mismatch) - PASS (test_embeddings.py TestE5LocalProvider)
- [x] B4 - audit module (`graph/audit.py`) exposes per-doc `document_certificate` returning `{coverage, missing_spans}` + `corpus_summary` (H389/H512, H548 per-doc gate) - PASS
- [x] B4 - deterministic gates (`grounded`, `supported`, `content_terms`, `generate_probes`) live in the module; the script imports them and still runs; `test_h389_audit.py` collects and passes - PASS (stale migration path corrected)
- [x] B4 - unit tests on synthetic fixtures for the certificate + corpus summary - PASS (test_audit.py)
- [x] B5 - same audit module exposes `seed_hop_distance(adjacency, seeds, target)` over an Entity-only, SIMILAR_TO-excluded adjacency (R49-H573, AUC 0.681) - PASS
- [x] B5 - unit tests: seed-is-target 0 hops, one/two-hop reach, unreachable returns None - PASS
- [x] B6 - `ProbeSettings.manifest` setting added and plumbed; `knowledge_graph_foundry/probe.py` exposes `load_manifest` + `select_manifest` (R49-H541 paired frozen probes) - PASS
- [x] B6 - `scripts/bench_progressive_probe.py` gains a `--manifest` flag: when set, the eligible probe set is the fixed manifest ids in manifest order (no resampling) - PASS (`--help` verified)
- [x] B6 - unit test for manifest loading + ordering determinism (JSON and text forms, dedup preserving order) - PASS (test_probe.py)

## Global

- [x] `make test` green (no NEW failures vs baseline: 490 passed / 18 skipped) - PASS (545 passed / 18 skipped; the single `test_cli.py::test_query_prints_answer` failure is PRE-EXISTING - Rich injects ANSI colour codes into CLI output in this environment, unrelated to these packages - reported, not fixed)
- [~] `make lint` clean (ruff format check + ruff check) - PRE-EXISTING failures only, NO new issues. My 3 new src modules pass check + format; my edits add zero lint issues. Pre-existing (unchanged from baseline, out of scope): ruff check I001 on `pipeline.py:6`; ruff format on `extractor.py`, `throughput.py`, `answer_cache.py`, and the `settings.py` `gate_probe_set` line (untouched by me)
- [x] Surgical: every changed line traces to a package item; no drive-by refactors - PASS
- [x] Commits are logical units with conventional messages citing hypothesis IDs - PASS (6 commits)
- [x] No edits to `docs/experiments/*`, `.claude/JOURNAL.md`, `RECOVERY-STATE.md` - PASS

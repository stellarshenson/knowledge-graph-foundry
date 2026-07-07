# Defects - Knowledge Graph Foundry

`[ ]` open, `[x]` fixed. Dated notes under each track how it evolved.

## Contents

- [DEF-1: Per-mention re-embedding on every document](#def-1-per-mention-re-embedding-on-every-document) - fixed
- [DEF-2: JSONL with text-heavy rows routed to tabular mapping, LLM never reads the text](#def-2-jsonl-with-text-heavy-rows-routed-to-tabular-mapping-llm-never-reads-the-text) - open
- [DEF-3: Curing floors not scale-aware - 481-doc wave cured at document 4](#def-3-curing-floors-not-scale-aware---481-doc-wave-cured-at-document-4) - fixed
- [DEF-4: .env NEO4J_URI silently overrides --config target, wave 2 ingested into the wrong instance](#def-4-env-neo4j_uri-silently-overrides---config-target-wave-2-ingested-into-the-wrong-instance) - fixed
- [DEF-5: benchmark harness seeded from the .env default instance while rendering from neo4j2](#def-5-benchmark-harness-seeded-from-the-env-default-instance-while-rendering-from-neo4j2) - fixed
- [DEF-6: engine LLM client construction depends on instructor's import-order-sensitive mode registry](#def-6-engine-llm-client-construction-depends-on-instructors-import-order-sensitive-mode-registry) - open

### DEF-1: Per-mention re-embedding on every document

- [x] HIGH ingest embeds the full pre-resolution mention set per document (one 9-chunk manual -> 708 Bedrock calls) and recurring entities (manufacturers, shared specs) are re-embedded in every later document; cause: `Foundry._embed` runs before resolution with no cache keyed by entity identity; fix: in-process cache keyed by (provider, model, entity text) in `generate_embeddings` - repeat texts served from cache, changed descriptions legitimately re-embed; `src/knowledge_graph_foundry/extraction/embeddings.py`
  - 2026-07-06 reported: observed during full CPAP rebuild - per-document embedding batches of 700+ for ~80 resolved entities/doc; linear-forever API cost for a months/years deployment
  - 2026-07-06 fixed: (provider, model, text)-keyed cache with 16384-entry cap; 3 tests; suite 258 green; see [experiments R01 results](experiments/kgf-redesign-experiments.md)

### DEF-2: JSONL with text-heavy rows routed to tabular mapping, LLM never reads the text

- [ ] HIGH a .jsonl of 481 articles ingested as one "document" yielding a mechanical 2 entities + 1 relationship per row; cause: `_extract_file` dispatches every structured extension to `structured_mapping`/`apply_mapping` (deterministic column mapping) regardless of content shape, so long free-text columns are never chunk-extracted, and the whole file is one resume fingerprint / one curing document; fix pending: detect text-heavy columns (e.g. median cell length threshold) and route each row's text through the unstructured chunk-and-extract path as its own document; workaround: campaign waves rewritten as one .txt per article; `src/knowledge_graph_foundry/pipeline.py`
  - 2026-07-06 reported: R05 wave 1 first launch - "ingested 1 documents: 962 entities, 481 relationships" with zero LLM reading of article bodies; data/external README already promised the text-column routing but code never implemented it

### DEF-3: Curing floors not scale-aware - 481-doc wave cured at document 4

- [x] HIGH the R05 wave-1 ontology cured (plateau) at document 4 of 481 with 7 types and 16 entities, then the drift detector fired 34 warnings with remap rates up to 0.875 as later documents kept extracting types outside the frozen set; cause: `CuringSettings` defaults (`min_documents=3`, `min_samples_before_cure=3`) encode the 27-doc CPAP corpus scale, and no gate criterion measured evidence sufficiency; fix: Good-Turing missing-mass upper confidence bound gate (n1/N + z*sqrt(n1+1)/N <= threshold) on both converged and plateau paths - scale-free, no count constants, the minimum evidence mass emerges from the bound; validated by the R06-H32 replay (98.55% forward mass coverage at its cure point vs 85.14% for v1); `src/knowledge_graph_foundry/ontology/curing.py`, `src/knowledge_graph_foundry/settings.py`
  - 2026-07-06 reported: R05 wave-1 event log - `curing.cured {reason: plateau, documents: 4}` at 13:41, followed by a sustained drift storm (remap 0.4-0.875) that is the honest symptom of a 4-document ontology governing a 481-document corpus; post-cure emergence grew types 7 -> 19; run left to complete as the measured H24 baseline
  - 2026-07-06 fix direction corrected: backlog-proportional floors rejected (user) - the foundry ingests an unbounded stream, corpus size is unknowable at cure time; gate must be evidence-statistical: at doc 4 the singleton fraction was 6/8, Good-Turing missing mass ~0.75 - would have blocked the cure with zero corpus-size knowledge
  - 2026-07-06 second correction (user): the first patch's `min_type_observations=200` count floor was itself a smuggled scale constant - replaced by the UCB confidence term, which widens automatically at small N
  - 2026-07-06 fixed: adjudicated by hypothesis R06-H32 - stream replay over 208 live wave-1 documents compared four gates; UCB cures at doc 20 AFTER the material doc-13 type block (98.55% forward mass coverage), v1 cured at doc 5 BEFORE it (85.14%); truncation-invariant at 100/200/full; 28 lifecycle+resume tests green; see [experiments R06-H32](experiments/kgf-redesign-experiments.md)

### DEF-4: .env NEO4J_URI silently overrides --config target, wave 2 ingested into the wrong instance

- [x] HIGH the SOTA-chain wave-2 step (`kgf ingest ... --config config-apnea.yml`, uri neo4j3) wrote 77 documents into the default instance, contaminating the freshly rebuilt 26-doc SOTA graph (26 -> 103 docs); cause: `load_settings` applied `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD` env overrides unconditionally AFTER the config file, so the ambient .env always won over an explicit `--config` target; fix: env fills gaps only - a key present in the config file's neo4j block is never overridden; stale test asserting the inverted precedence replaced by two contract tests (explicit-config-beats-env, env-fills-gap); `src/knowledge_graph_foundry/settings.py`
  - 2026-07-07 reported: three-arm benchmark executor noticed the "finished" SOTA graph fingerprint drifting between reads (3661 -> 3693 entities, docs 75 -> 76) while measuring Arm 3; instance audit showed neo4j3 frozen at 481 docs and the default instance growing ~1 doc/min
  - 2026-07-07 fixed: precedence corrected, verified live (config-apnea resolves to neo4j3 with .env present), test_settings 5 green; wave 2 killed at 103 docs and relaunched against neo4j3; contaminated SOTA instance retained for the post-chain scratch queue (three-arm Arm-3 measurements were taken before heavy contamination and reported stable)

### DEF-5: benchmark harness seeded from the .env default instance while rendering from neo4j2

- [x] HIGH the H199 wide census recorded recall@64 0.406 (vs the true 0.762) and an unranked-dominated miss classification that suspended the H193 coverage-ceiling promotion; cause: `wide_census_h199.ipynb` constructed `Foundry(settings)` without pinning `NEO4J_URI`, so vector-query SEEDS came from the .env default instance (concurrently wiped/re-ingested by the H158 run) while RENDERS read neo4j2 - a cross-instance seed/render mismatch; the run-to-run variance (0.376 -> 0.406 -> 0.0) tracked the default instance's live state, not harness non-determinism; fix: H207 canonical harness pins the retrieval driver explicitly and stamps render_fingerprint + graph_fingerprint as a mandatory census preamble; pinned 3-run census reproduces [77, 77, 77] with zero variance; `notebooks/wide_census_h199.ipynb`, `notebooks/render_parity_h207.ipynb`
  - 2026-07-07 reported: H199 executor flagged impossible run variance on a supposedly frozen graph; main-session forensics proved neo4j2 unchanged since 2026-07-06 14:48, leaving the harness as the suspect
  - 2026-07-07 fixed: H207 render-parity forensics attributed the entire divergence (+0.327 instance, +0.030 scorer arm, +0.010 propositions); the DEF-4 lesson generalizes - EVERY graph consumer (engine or notebook) must pin its instance explicitly, never inherit .env

### DEF-6: engine LLM client construction depends on instructor's import-order-sensitive mode registry

- [ ] MEDIUM `LocalGpuEngine.__init__` calls `instructor.from_litellm(litellm.completion, mode=instructor.Mode.JSON)`, which in instructor 1.15.4 dispatches to the v2 path whose mode registry is populated by IMPORT SIDE EFFECTS - `(OPENAI, Mode.JSON)` is registered only when `instructor.v2.providers.openai.handlers` happens to be imported, so the same construction succeeds or raises `RegistryError` depending on what was imported first in the process; cause: registry population via decorator side effects with no explicit dependency from `from_litellm` to the handler module; fix pending: engine imports `instructor.v2.providers.openai.handlers` explicitly (or constructs with an always-registered mode) - route via the H198 wiring sweep; workaround: notebooks add the explicit import before engine construction; `src/knowledge_graph_foundry/engines/local_gpu.py`
  - 2026-07-07 reported: H119 harness - the sequential notebook run extracted fine, the parallelized relaunch of the SAME notebook crashed twice with `RegistryError: Mode Mode.JSON is not registered for provider Provider.OPENAI`; standalone scripts with identical imports succeed in main thread and 10 threads - the differing kernel import order is the trigger, not threading; verified fix: explicit handler import flips `mode_registry.is_registered(OPENAI, JSON)` to True

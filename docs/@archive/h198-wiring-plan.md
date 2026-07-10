# H198 Wiring Sweep - Work Plan

Execution plan for R15-H198: compose every promoted lever into the shipped engine, rebuild the graph, and demonstrate the composition under the pinned harness. This plan is the bridge between the campaign's promotion ledger (docs/sota-promotions.md) and the release-candidate goal. Drafted while the final deciders run; decision slots below are filled as their verdicts land.

## Goal (active)

Composed every promoted lever into the shipped engine and rebuilt the graph on it, demonstrated SOTA end-to-end under the pinned harness (H113-H117 head-to-head), with every known weakness measurably fixed, priced-out with recorded abstention, or registered in the gap ledger; solution left mature: reproducible rebuild twice with matching numbers, per-corpus self-calibration wired and verified, docs/ledger/defects/promotions reconciled, release candidate presented to the user for the tag decision.

## Decision slots (pending verdicts - filled before Phase 2 begins)

- **SLOT-1 (H241)**: RESOLVED 2026-07-08 - **NO-GO, v1 stays default**. The paired A/B landed PARTIAL (2 of 3 clauses): recall tie 0.7708 = 0.7708 PASS, precision proxy 0.611 vs 0.50 bar PASS, false-merge factor 1.57x vs the registered 2x bar FAIL (11 -> 7 raw count). Per the registered branch: v1 stays default, v2 stays behind `resolution.identity_stack`, gap-ledger entry records v2's measured advantages (7.3x precision, 11x bench recall, equal probe recall, per-merge false rate 3.1x lower). The shipped precision repair is the demote-don't-delete court (SLOT-3), whose docket is exactly v1's false-merge surface. A future flip needs a new pre-registered decider - not a renegotiated bar
- **SLOT-2 (H250)**: RESOLVED 2026-07-08 - **H246 enumerate-then-extract ships as the default extraction recipe** (0.971 of union-of-5 at 1.05x cost, only fully-passed operator; frontier table in the H250 ledger entry). Staged upgrade: H258 mention-emission strictly dominates (1.000 at 0.76x, 1.53x mention inflation) but its resolver-precision clause is untestable offline - H240(b)'s scratch arm runs BOTH recipes and the precision clause decides whether mention-emission displaces enumerate as default. Dead: GLiNER-primed extraction, n-sampling (build cannot execute n>1), complement pass, union demos, GLiNER+adjudication; GLiNER stays as audit lexicon stage only
- **SLOT-3 (H292)**: RESOLVED - type-blind confirmed at the bars but NOT shipped: under demote-don't-delete, over-splits are costless while missed false merges persist as SAME_AS poison; the court ships as H282 baseline judge + demotion (98.0% detection), type labels stay in the judge context
- **SLOT-4 (H240b)**: RESOLVED 2026-07-09 - **PASS on ingest survival; H246 enumerate CONFIRMED default, H258 mention-emission REFUTED as displacement**. Two-arm scratch A/B on neo4j4, both recipes with the v2 resolver, matched corpus (27 kgf docs, 247 chunks). Enum: recall 0.7292, SAME_AS precision 0.5517, 17/24 fully covered, 4363 entities, 13 false merges. Mention: recall 0.6667, precision 0.48, 14/24 covered, 5124 entities (+17% inflation), 13 false merges. The composed ingest path survives E2E (both arms cured and produced coherent graphs; v2 resolver held false merges at 13 in both - H158 band, no drowning). The H258 precision clause FAILS: mention loses 7.2 pt precision (0.48 vs 0.5517, exceeds the 5-pt tolerance) AND 6.25 pt recall - the offline "strictly dominates 1.000 at 0.76x" did NOT survive composition; mention's extra 17% entities fragmented identity rather than lifting recall. Per-probe: mention wins P01/P03/P23 (absent-class help is real) but loses P20/P22/P24 and half-loses P11/P14/P18 - net negative. **H246 enumerate stays the shipped default; no flip.** Confounds: both arms are v2-resolver while the shipped default is v1 (SLOT-1), so absolute recall/precision are v2-arm figures - the enum-vs-mention DELTA is clean but the comparison to the H241-v2 reference (recall 0.7708) carries the v1/v2 confound plus tranche-1 levers active in arms; enum arm lost ~16 chunks to a client-timeout burst on the 8.4 MB catalog, so enum recall is under-counted and its win over mention is conservative; Evox 0-char parse cancels across arms

## Phase 1 - inventory (COMPLETE 2026-07-08)

H198 clause (a) met: 66 promotion entries classified, zero unaccounted - 15 LEVER / 22 DOCTRINE / 18 INSTRUMENT / 9 NEGATIVE / 2 SUPERSEDED. Full machine-readable inventory: `reports/h198-wiring-inventory-20260708T102631Z.json`. Headline: no promoted lever is live in the engine default path - 2 config-only at the wrong default (top_k=8 in `settings.py`, identity_stack=v1), 3 notebook-only, 9-10 not-implemented.

**Wiring constraint (binding until the experiment chains finish)**: the H241 chain and the R23/R24 batch execute from this working tree - NO engine code or default-config edits until both report, or the running arms are contaminated mid-experiment. Wiring order below starts the moment the tree is free.

**DEF-6 minimal fix (first wiring commit)**: `engines/local_gpu.py:28` - add the explicit `instructor.v2.providers.openai.handlers` import before `from_litellm` (instructor 1.15.4 populates its mode registry by import side effect; notebooks carry the workaround today).

## Phase 2 - wiring (the sweep)

**Tranche 1 READY (2026-07-08, worktree `agent-aea0ebaec7aac3122`, uncommitted, base `0735aac`)**: DEF-6 import fix (+regression test in fresh interpreter), top_k 16 default, H190 glyph normalization (`extraction.glyph_normalization`, comparison-time resolver key - entity IDs untouched), H153 header carryover (`extraction.header_carryover`), H146-151 pypdf parser union (`extraction.parser_union`), H173 proposition splitter (`graphrag.proposition_split_max_tokens: 300`). 325 tests pass (+16 new), zero new lint failures. **Merge blocked until H241 chain + R23/R24 batch release the main tree.** Merge watch-items: (1) H195a over-fetch NOT wired into engine `vector_query` - the generous-fetch factor lives in the harness notebooks; decide at merge whether the engine needs it; (2) pre-existing repo-wide ruff format drift (8 files, `uvx` unpinned ruff) - separate `make format` housekeeping, not part of this tranche; (3) chunk ids change under glyph+carryover (content-hashed) - expected on fresh rebuild, both config-reversible for ablation.

Wire by subsystem, cheapest-risk first; every lever behind a config key so the capstone can ablate it. Known members (inventory completes this list):

**Config-only flips** (implemented, wrong default - one-line changes)
- top_k 8 -> 16 in `settings.py` GraphRAGSettings (H53; consumed pipeline.py:850); generous-top_k truncation convention (H195a)
- identity_stack stays v1 (SLOT-1 resolved NO-GO); v2 remains available behind `resolution.identity_stack` for ablation

**New retrieval/render defaults** (not-implemented - target `pipeline._render` + graphrag)
- R19 trio: fanout cap k=5 query-ranked, miss detector ~0.668 + abstention render, adaptive render budget B=60% (note: compose with ppr_enabled default per the H37 optional-removal flag)
- H205 foreign-device exclusion as optional layer; H211 prop-val linkage rule (notebook-only today)

**Ingest operators**
- Parser union: pypdf partner alongside pymupdf4llm (H51/H146-151); Docling table-structure stage where promoted (H152/H153 scope)
- H153 header carryover; H190 glyph normalization (parser post-process + resolver detector); H173 proposition splitter (>300 tok)
- Truncation-resilient JSONL parsing; discrete 5-value confidence rubric (R25 engineering items)
- GLiNER lexicon stage (H260): per-document residue scalar to the gap ledger; priming/audit lexicon for SLOT-2's recipe
- Extraction recipe per SLOT-2

**Identity**
- SLOT-1 resolved: v1 default + demote-don't-delete court as the shipped precision repair; per-corpus self-calibration path (H157 requirement, H142 lineage) - offline-fit, runtime-frozen per corpus
- H268 soft SIMILAR_TO edges for the defer zone (posterior-weighted, render-traversable)
- Demote-don't-delete court (R27): single-shot judge over the SAME_AS docket at ingest-close, judged-false edges demoted to soft links; K=3 effort constant; escalation caps as standing constants; SLOT-3 inside the judge context
- H267 freebie: exact-normalized defers skip the judge queue

**Usage coupling**
- H271 demand-ledger repair allocator (signals outside the graph); H274 external fingerprint-keyed answer cache (no graph coupling)

**Ops/health**
- DEF-6 fix (instructor import-order mode registry)
- Fingerprint discipline: every consumer pins instance + stamps graph/render fingerprints (DEF-4/DEF-5 law, H197 precondition)
- Drift detector unchanged (H59/H120 doctrine); dangling-relationship policy unchanged (H238)

**Excluded from this rebuild (recorded abstentions)**
- Image ingestion: stands on new-capability value only (H217); photo class blocked pending H291; ships later behind H224 filter as optional stage - gap-ledger entry
- Web escalation (H286): user-gated
- PPR, materialized views, community summaries on the quality path: closed avenues (H37/H86/H276)

## Phase 3 - rebuild and reproduce

1. H240(b) union-ingest validation on scratch (SLOT-4) - the composed ingest path proves itself before production
2. Full clean-state rebuild of the benchmark graph on the composed engine - TWICE; benchmark numbers must match within the measured variance floor (H229's model-inherent variance is the known noise source; the harness fingerprints guard the rest)
3. Per-corpus self-calibration run on the rebuilt graph; ECE within the H129 held-out reference band
4. Live continuation check (DEF-7 semantics, user requirement 2026-07-08): after the rebuilds are measured, a NEW ingestion session adds a small held-back document set to the rebuilt graph - must stable-load incrementally (no re-cure, no reprocessing), graph queryable throughout; benchmark re-run after to confirm no regression from the continuation path

## Phase 4 - capstone (H113-H117)

Head-to-head under the pinned H207 harness (frozen render spec, graph + render fingerprints stamped): composed engine vs baseline vs best-prior arm. H198 clause (b) rides here: each promoted lever's effect reproduced within its measured CI under composition - any lever that silently degrades gets its own hypothesis before ship (the three-arm lesson).

## Phase 5 - maturity closure

- Gap ledger finalized: every priced-out capability recorded as deliberate abstention with its pricing evidence
- docs/ledger/defects/promotions reconciled; defects closed or re-registered; journal current
- Release candidate presented to the user (no tag, no version change without explicit approval)

## Post-RC follow-on (user-directed 2026-07-08)

Public-benchmark campaign: take the released engine to the published GraphRAG evaluation surfaces (HotpotQA / MuSiQue / 2WikiMultiHopQA-class multi-hop QA slices with published peer numbers, extending H114's external-validity design). Campaign design delegated to the AI; requires the web/external gate the user opens post-RC (benchmark downloads, peer-framework installs, published-number verification). Success = KGF's numbers on public slices beside GraphRAG/LightRAG/HippoRAG-2 published results under matched conditions, reproducible from a pinned harness.

## Acceptance criteria

- [ ] Inventory complete: zero promotions unaccounted (H198 clause a)
- [ ] All four decision slots resolved by recorded verdicts, not judgment
- [ ] Every wired lever behind a config key; shipped default config = the promoted composition
- [ ] DEF-6 closed; no open defects without a re-registration
- [ ] Two clean-state rebuilds with matching benchmark numbers (within variance floor)
- [ ] Self-calibration verified on the rebuilt graph (ECE within reference band)
- [ ] H113-H117 capstone recorded under pinned harness; per-lever CI reproduction (clause b) - any regression spawns a hypothesis
- [ ] Gap ledger + docs reconciled; release candidate presented for the tag decision

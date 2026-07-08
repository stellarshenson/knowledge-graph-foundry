# H198 Wiring Sweep - Work Plan

Execution plan for R15-H198: compose every promoted lever into the shipped engine, rebuild the graph, and demonstrate the composition under the pinned harness. This plan is the bridge between the campaign's promotion ledger (docs/sota-promotions.md) and the release-candidate goal. Drafted while the final deciders run; decision slots below are filled as their verdicts land.

## Goal (active)

Composed every promoted lever into the shipped engine and rebuilt the graph on it, demonstrated SOTA end-to-end under the pinned harness (H113-H117 head-to-head), with every known weakness measurably fixed, priced-out with recorded abstention, or registered in the gap ledger; solution left mature: reproducible rebuild twice with matching numbers, per-corpus self-calibration wired and verified, docs/ledger/defects/promotions reconciled, release candidate presented to the user for the tag decision.

## Decision slots (pending verdicts - filled before Phase 2 begins)

- **SLOT-1 (H241)**: v2 identity stack becomes default? GO -> `resolution.identity_stack: v2` in shipped config; NO-GO -> v1 stays, v2 remains flagged, gap-ledger entry
- **SLOT-2 (H250)**: the extraction recipe - which remedy composition (union-K / enumerate / GLiNER-primed / n-sampling / complement) ships as the default extraction path, at what K and cost point; fed by the running R23/R24 batch
- **SLOT-3 (H292)**: RESOLVED - type-blind confirmed at the bars but NOT shipped: under demote-don't-delete, over-splits are costless while missed false merges persist as SAME_AS poison; the court ships as H282 baseline judge + demotion (98.0% detection), type labels stay in the judge context
- **SLOT-4 (H240b)**: union-ingest E2E validation on scratch - confirms SLOT-2's recipe survives the full pipeline before the production rebuild

## Phase 1 - inventory (running)

H198 clause (a): complete promotion-vs-code audit - every promotions entry classified (lever / doctrine / instrument / negative / superseded), every lever mapped to wiring status (shipped-default / config-only / notebook-only / not-implemented) with integration point and acceptance check. Executor running; inventory lands in `reports/h198-wiring-inventory-*.json` and is folded into this plan as the Phase 2 checklist.

## Phase 2 - wiring (the sweep)

Wire by subsystem, cheapest-risk first; every lever behind a config key so the capstone can ablate it. Known members (inventory completes this list):

**Config-only flips**
- top_k 8 -> 16 (H53); generous-top_k truncation convention (H195a)
- R19 trio defaults: fanout cap k=5 query-ranked, miss detector ~0.668 + abstention render, adaptive render budget B=60%
- H205 foreign-device exclusion as optional layer

**Ingest operators**
- Parser union: pypdf partner alongside pymupdf4llm (H51/H146-151); Docling table-structure stage where promoted (H152/H153 scope)
- H153 header carryover; H190 glyph normalization (parser post-process + resolver detector); H173 proposition splitter (>300 tok)
- Truncation-resilient JSONL parsing; discrete 5-value confidence rubric (R25 engineering items)
- GLiNER lexicon stage (H260): per-document residue scalar to the gap ledger; priming/audit lexicon for SLOT-2's recipe
- Extraction recipe per SLOT-2

**Identity**
- SLOT-1 default; per-corpus self-calibration path (H157 requirement, H142 lineage) - offline-fit, runtime-frozen per corpus
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

## Phase 4 - capstone (H113-H117)

Head-to-head under the pinned H207 harness (frozen render spec, graph + render fingerprints stamped): composed engine vs baseline vs best-prior arm. H198 clause (b) rides here: each promoted lever's effect reproduced within its measured CI under composition - any lever that silently degrades gets its own hypothesis before ship (the three-arm lesson).

## Phase 5 - maturity closure

- Gap ledger finalized: every priced-out capability recorded as deliberate abstention with its pricing evidence
- docs/ledger/defects/promotions reconciled; defects closed or re-registered; journal current
- Release candidate presented to the user (no tag, no version change without explicit approval)

## Acceptance criteria

- [ ] Inventory complete: zero promotions unaccounted (H198 clause a)
- [ ] All four decision slots resolved by recorded verdicts, not judgment
- [ ] Every wired lever behind a config key; shipped default config = the promoted composition
- [ ] DEF-6 closed; no open defects without a re-registration
- [ ] Two clean-state rebuilds with matching benchmark numbers (within variance floor)
- [ ] Self-calibration verified on the rebuilt graph (ECE within reference band)
- [ ] H113-H117 capstone recorded under pinned harness; per-lever CI reproduction (clause b) - any regression spawns a hypothesis
- [ ] Gap ledger + docs reconciled; release candidate presented for the tag decision

# Recall Failure Modes - Knowledge Graph Foundry

Standing register of detected, evidenced ways KGF fails to recall - not code defects, but tracked with the same formalism. `[ ]` open (unmitigated or under active work), `[x]` mitigated/retired (doctrine, shipped lever, or superseded). Each mode carries its evidence (hypothesis/probe IDs, result files) and the lever or round that owns the fix. IDs `RFM-N`, monotonic, never reused. Dated notes under each track how the mode evolved.

## Contents

- [RFM-1: Retrieval-hop break after complete coverage repair](#rfm-1-retrieval-hop-break-after-complete-coverage-repair) - open
- [RFM-2: Seed dilution by fixed-budget hybrid union](#rfm-2-seed-dilution-by-fixed-budget-hybrid-union) - mitigated
- [RFM-3: Single-pass extraction variance drops gold carriers](#rfm-3-single-pass-extraction-variance-drops-gold-carriers) - open
- [RFM-4: ABSENT-class omissions unrecoverable by re-extraction](#rfm-4-absent-class-omissions-unrecoverable-by-re-extraction) - open
- [RFM-5: ELSEWHERE-class misses - fact present on a different carrier](#rfm-5-elsewhere-class-misses---fact-present-on-a-different-carrier) - open
- [RFM-6: ARTIFACT-class misses - probe/harness artifacts read as coverage gaps](#rfm-6-artifact-class-misses---probeharness-artifacts-read-as-coverage-gaps) - open
- [RFM-7: Reader parse loss (P08 class)](#rfm-7-reader-parse-loss-p08-class) - open
- [RFM-8: Coverage certificate blind to retrieval-class failures](#rfm-8-coverage-certificate-blind-to-retrieval-class-failures) - open
- [RFM-9: Scale-growth probe regression](#rfm-9-scale-growth-probe-regression) - open

### RFM-1: Retrieval-hop break after complete coverage repair

- [ ] HIGH - probe fails although the gold fact exists in the graph and would render; cause: retrieval seeds a neighbouring node (the film, which renders DIRECTED_BY) and PPR never reaches the carrier (the director) - the 2-hop chain breaks at the retrieval hop, not at coverage; lever: seed-side expansion / second-hop routing (R40), reachability-at-ingest audit (R49 planned); evidence: REG-2 `(Leopoldo Torres Rios)-[:CHILD]->(Leopoldo Torre Nilsson)`, R45 repair loop, `docs/experiments/kgf-redesign-experiments.md` R45 section
  - 2026-07-12 detected: R45 repair loop - REG-3 recovered by the same edit class, REG-2 did not; reclassified coverage-repairable -> RETRIEVAL lever, feeds R40
  - 2026-07-13 registered here; R48-H515 (partition-masked PPR) will quantify how segmentation would worsen this class; R49 vector (a) plans the ingest-time reachability audit

### RFM-2: Seed dilution by fixed-budget hybrid union

- [x] adding sparse seeds into a fixed top-k budget displaces dense hits and lowers recall; cause: union/RRF compete for seed slots instead of fusing evidence - dense@16 = 0.854 > union@16 = 0.750 > rrf@8 = 0.646; fix: DOCTRINE - new channels fuse inside PPR (reset-vector mass) or by learned convex combination, never compete for a seed slot; evidence: H53, reaffirmed by R47 registration (every retrieval construction fuses, none seeds)
  - 2026-07-05 detected (H53); promoted to standing doctrine
  - 2026-07-13 doctrine carried into R47 (H506-H513) and R48 (H528-H531) registrations by construction

### RFM-3: Single-pass extraction variance drops gold carriers

- [ ] HIGH - the dominant identity/coverage root cause; cause: single open-vocab LLM extraction pass averages 76.8% carrier recall with high run-to-run variance (H107); 71% of same-type duplicate pairs trace to extraction variance, not resolution; levers: H119 canonicalization, R47 identity domain (GLiNER deterministic 95.2% substrate, H502-H505), speculative ingest context (pins entities to existing identities); evidence: H107 forensics (66 same-type pairs), H260 GLiNER census
  - 2026-07-06 root-caused (H107 CONFIRMED) - primary lever moved from resolver to extraction
  - 2026-07-13 R47 registered the deterministic-substrate attack (H502 blocking key, H505 miss-healing); execution pending

### RFM-4: ABSENT-class omissions unrecoverable by re-extraction

- [ ] facts truly absent from the graph stay absent through extractor re-rolls; cause: extraction omission is not sampling noise - a targeted second pass through production `extract_chunk` recovered only 12/48 = 25.0% of unique ABSENT facts (bar was 30%, H450 REFUTED); fix direction: repair-from-source (gap ledger -> source-grounded repair) has primacy over re-extraction; evidence: `reports/experiments/r45/pass2-20260712T102327Z.jsonl`, R45 pass-2 differential
  - 2026-07-12 H450 REFUTED - pass-2 is a real but insufficient lever (quarter of true omissions)
  - 2026-07-13 registered; R49 vector (c) plans repair-from-source primacy at ingest; bonus datum: resolution absorbed ~85% of re-emissions (healthy-resolver signal)

### RFM-5: ELSEWHERE-class misses - fact present on a different carrier

- [ ] probe targets entity A but the fact landed on entity B (a sibling, series node, or duplicate); cause: carrier placement at extraction/resolution time diverges from where probes look; dominated the R45 terminal residue (8 of 17 final misses); levers: H365 series-fragment merge + spec hoist (shipped, partial), carrier-selection fix (the H394 automation weak link: 12/47 repairs fell back to largest-carrier heuristic); evidence: R45 final decomposition, `reports/experiments/r45/adjudication-20260712T101552Z.md`
  - 2026-07-12 detected as the largest terminal miss class of the repair loop
  - 2026-07-13 registered; carrier selection named the weak link for repair automation (R49 scope)

### RFM-6: ARTIFACT-class misses - probe/harness artifacts read as coverage gaps

- [ ] probes fail for reasons that are not graph deficiencies (malformed probe, gold-string formatting, criterion mismatch); 3 of 17 R45 terminal misses; cause: probe generation + answer_in_context string matching produce false negatives the repair loop cannot touch; lever: harness-side - probe regeneration discipline (H188: document-grounded, never graph-derived), certificate criterion audit; evidence: R45 final decomposition
  - 2026-07-12 detected in the R45 terminal residue
  - 2026-07-13 registered; couples to RFM-8 (instrument trust) and the certificate-noise re-pricing (R49 vector b)

### RFM-7: Reader parse loss (P08 class)

- [ ] the gold string is IN the rendered context but the reader/parser fails to extract it; cause: reader-side parse loss, unreachable by any retrieval-side lever; the single non-full probe of the 23/24 composed frontier; lever: awaits the parser class (registered in R34 close-out); evidence: P08, `reports/experiments/adjudicated/r34-composed-frontier-20260710T162930Z.json`
  - 2026-07-10 isolated at the composed-frontier close - every retrieval lever exhausted against it
  - 2026-07-13 registered; also surfaced answer-side in R38-H385 (LLM paraphrase breaks verbatim gold-substring grading - 17/19 probes read uncovered at BOTH rungs)

### RFM-8: Coverage certificate blind to retrieval-class failures

- [ ] MEDIUM - the certificate adjudicates entity-column coverage and cannot see a probe that fails at the retrieval hop (RFM-1) or reader hop (RFM-7) - a "covered" graph can still miss; cause: certificate criterion = answer_in_context over rendered coverage, no seed-reachability column; compounded by instrument noise: same-graph certificate spread 84.3 vs 88.9 at 25-doc probe scale understates the +-2% reproducibility bar (gated the H484 pass-2 verdict INCONCLUSIVE); levers: seed-reachability certificate column (R49 vector a), probe-scale-dependent reproducibility bands (R49 vector b), H389 registered-corpus adjudication; evidence: R45 instrument anomaly + pass-2 differential; DEF-16 (dead span column) is the code-defect sibling
  - 2026-07-12 noise quantified during the repair loop; span column death registered as DEF-16
  - 2026-07-13 registered as a failure-mode class distinct from the code defect; R49 plans both columns

### RFM-9: Scale-growth probe regression

- [ ] a probe that passed at smaller graph scale flips to fail as the pile grows; 1 regression recorded across the 1,173-doc progressive trajectory (10 pass / 5 fail at last cycle); cause: unattributed - candidate mechanisms: seed-rank displacement by new entities, resolution merges shifting carriers, context dilution; lever: progressive prober attribution pass on the flipped probe (owns: bench ladder campaign #83); evidence: `reports/experiments/bench/progressive-probe-trajectory.jsonl`, `logs/bench-progressive-probe.log` PROBE CYCLE lines
  - 2026-07-13 detected during the medium ingest watch (cycle 05:47Z); pass-count also drifted 10/5 -> 9/6 -> 10/5 across cycles - flip attribution pending at medium collection

# Gap Ledger - KGF v2

Deliberate known-gaps: capabilities measured, priced, and consciously NOT shipped in the default engine. Every entry carries its pricing evidence and the recorded verdict that closed it. Finalized in H198 Phase 5; entries append as slots resolve.

## GAP-1: v2 identity stack not default (SLOT-1, H241)

The calibrated v2 stack (isotonic cosine + NLI veto + logistic) measured strictly better than v1 on the paired A/B - 7.3x SAME_AS precision (0.611 vs 0.083), 11x bench-pair recall (0.212 vs 0.019), per-merge false rate 3.1x lower, at exactly equal probe recall (0.7708 both arms) - but the registered false-merge clause missed (1.57x fewer vs the 2x bar, 11 -> 7 raw count), so the flip was not approved.

- **Ships instead** - v1 default + demote-don't-delete court (H290/H282, 98.0% false-merge detection at ingest-close); the court's docket is exactly v1's false-merge surface
- **Remains available** - `resolution.identity_stack: v2` config key, fully wired
- **Reopen condition** - a new pre-registered decider (rate-normalized clause or multi-run counts with variance accounting); the H241 bar is not renegotiated post-hoc
- **Evidence** - [identity-ab-h241-20260708T160009Z.json](../reports/experiments/adjudicated/identity-ab-h241-20260708T160009Z.json), ledger R15-H241

## GAP-2: image ingestion (R21, H216/H217/H218)

Pixel forensics adjudicated all 32 absent benchmark golds: 0 pixel-only - image ingestion claims no slice of the existing coverage ceiling and stands on new-capability value only.

- **Measured** - 81.5% of captured images information-bearing, but only 26% of documents carry image text absent from the text layer
- **Per-class status** - diagrams + rendered tables GO (Qwen2.5-VL 0.98/0.92 and 0.94/1.00 vs 80/90 bars); product photos BLOCKED on brand hallucination pending H291 brand guard
- **Ships later** - optional describe-then-extract stage behind the H224 filter; not in the default rebuild
- **Evidence** - ledger R21-H216/H217/H218, [pixel-forensics-h217](../reports/experiments/adjudicated/pixel-forensics-h217-20260707T200833Z.json)

## GAP-3: web escalation (H286, user-gated)

The web-search arm is gated by explicit user direction ("achieve SOTA without web search first") and measured as small territory anyway: H281 put world-knowledge-dependent failures at 1.1%.

- **Reopen condition** - user re-opens the gate; the H286 registration stands ready
- **Evidence** - ledger R26-H281, H286 registration

## GAP-4: unranked retrieval residue (H211, priced-out)

Full recovery of the unranked residue (5/8 golds) costs 51.6x the H171 token knee - priced out as abstention territory per the H161 doctrine.

- **Ships instead** - miss detector + short-circuit abstention render (R19 trio: 86.7% miss detection, 0% false abstention, 95% token cut on the miss class)
- **Evidence** - ledger R18-H211, sota-promotions 2026-07-07

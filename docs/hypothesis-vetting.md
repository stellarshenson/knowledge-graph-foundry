# Hypothesis Vetting Protocol - fast-kill triage before registration spend

Every new hypothesis passes a five-gate triage BEFORE it earns registration and execution budget; each gate is a cheap test with a kill outcome. Born from the 2026-07-13 verdict re-audit: R49-H544/H545 re-derived R10's own settled H91/H100 verdicts at full experiment price because nothing checked the ledger at registration time.

## The gates

- **V1 Ledger dedup** - grep the canonical log (`docs/experiments/kgf-redesign-experiments.md`) and the re-audit harvest (`reports/experiments/audit/verdict-regrade-sweep-*.json`) for the MECHANISM, not just the name; a settled instrument-class verdict kills on the spot (sweep process rule: instrument-class verdicts promote to doctrine, checked at registration). Test = targeted grep + read of matched sections
- **V2 Power** - predicted effect vs the H540 binomial band at the available paired n (H541 pairing mandate; bands: n=15 +-24.9pp, n=132 ~+-8.5pp, n=200 +-6.8pp; +-2pp unpaired needs n~9,500). A bar inside the noise band at feasible n = re-price or kill before spend. Test = band lookup, no compute
- **V3 Oracle / algebraic kill** - can a gold-side oracle arm or an algebraic identity decide it FREE before machinery is built? Precedents: H530's oracle-decomposed 0.909 priced the whole decomposition axis in one arm; H544's algebra (mean-AFRC = 4 - sum-deg^2/E) killed the Ricci channel without a sweep. If the oracle ceiling sits below the bar, kill
- **V4 Cheapest rung** - route to the cheapest kill: artifact replay > scout > medium; FREE > GPU > LLM (scale-ladder doctrine). A hypothesis with no FREE or scout kill-path runs a scout smoke FIRST; full-rung spend only after the smoke survives
- **V5 Fence + confound** - name the owning round (collision = fold or fence, never duplicate); check the scoring surface against known confounds: render_budget=0.6 defect (score retrieval-level, never end-to-end probe pass - H570/H572 convergence), query-sampling spread (frozen probe manifests only - H539), attribution controls (an honest baseline per H556's broken-control lesson: control = the CHEAPEST feature that could carry the signal, alone)

## Outcomes

- **VET-PASS** - register with a V2-priced bar and a V4-priced experiment line
- **VET-KILL** - one line in the ledger round intro: vetted-out, gate, reason (kills are recorded, not discarded - they are the cheapest verdicts the program produces)
- **VET-REPRICE** - registered with the bar or target re-derived from the gate that fired

## Mechanism

Run as a primed READ-ONLY vet subagent per candidate batch: input = draft hypotheses; output = per-hypothesis gate table (gate, evidence, verdict) + proposed outcome. The coordinator adjudicates and records; the vet agent never writes canonical docs. For fanout rounds the synthesis stage runs the gates on every proposal before the slate reaches the coordinator (first applied: R50).

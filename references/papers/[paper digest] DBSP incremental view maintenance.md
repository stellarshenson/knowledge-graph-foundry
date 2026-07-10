**DBSP: Automatic Incremental View Maintenance for Rich Query Languages, Budiu, Chajed, McSherry, Ryzhyk, Tannen, PVLDB 16(7) 2023 (best paper)**

The modern formal foundation of incremental view maintenance - the theory template for "derived object X depends on base facts Y; when Y changes by ΔY, compute ΔX instead of recomputing X". DBSP is a stream-algebra language with **four operators** (lifting, delay, differentiation, integration) and a mechanical incrementalization algorithm: any query Q built from DBSP operators is rewritten into Q^Δ that consumes input deltas and emits output deltas, covering full relational algebra, aggregation, nested relations, and monotonic AND non-monotonic recursion (subsuming DRed-style delete/rederive). Deltas are Z-sets (tuples with signed multiplicities), so insert/delete/update are one uniform algebra; for linear operators the incremental version processes work proportional to **|ΔY|, not |Y|**. Implemented in the Feldera engine; the paper is theory-first - no headline speedup number is claimed in the abstract (UNVERIFIED beyond asymptotics; benchmark numbers live in the Feldera engineering literature).

**Key mechanism**
- Z-sets: relations as functions tuple → integer weight; a delta is just a Z-set with positive (insert) and negative (delete) weights
- Incrementalization: Q^Δ = D ∘ Q ∘ I (differentiate output of Q applied to integrated input); chain rules push the ^Δ inward so each operator is replaced by its incremental form
- Linear operators (filter, map, flatmap) are their own incremental versions - cost O(|Δ|); bilinear ones (join) need one integral per side - cost O(|Δ| x |state index|)
- Recursion handled by nested streams; deletion from recursive views falls out of the algebra - no special-case DRed pass

**Main findings**
- Incremental maintenance is compositional: incrementalize every operator locally and the whole pipeline is incremental - no per-query hand derivation
- Deletions are not a special case if derived state carries signed multiplicities/counts
- The cost hierarchy (linear ops free, joins pay state-proportional lookups, recursion pays fixpoint-local work) predicts which derived objects are cheap vs expensive to maintain

**Key takeaways**
- The transferable discipline for LLM-derived objects: record dependencies at derivation time, define a delta type per object class, and write the repair rule as a function of the delta - even when "recompute" is an LLM call, the SCOPING of what to recompute follows the view-maintenance algebra
- Support counts (how many independent derivations support this derived fact) are the cheap trick that makes deletion propagation local - directly applicable to synonym edges and hoisted properties supported by multiple sources
- What does NOT transfer: determinism and cheap recompute; an LLM "operator" is expensive and non-deterministic, so eager per-delta maintenance must be replaced by batched, thresholded, or lazy variants

**Tags**: #DBSP #IncrementalViewMaintenance #ZSets #DeltaProcessing #DatabaseTheory

**Source**: https://arxiv.org/abs/2203.16684. Local: [paper] DBSP incremental view maintenance, 2023.pdf

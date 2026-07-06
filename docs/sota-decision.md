# SOTA Decision - Knowledge Graph Foundry

Grounded evaluation of every core KGF design choice against current literature (2023-2026), not against the archived v1. Five independent research passes covered KG construction, ontology/schema induction, entity resolution, incremental/temporal KG maintenance, and GraphRAG retrieval. Each verdict is keep / change / throw-away with a cited basis. Willing to discard working mechanisms where they are not state of the art.

## Verdict table

| Choice | Verdict | Basis |
|--------|---------|-------|
| Two-phase curing (buffer → stability metrics → commit) | Keep + harden | Chao1/coverage as a stopping criterion is SOTA in adjacent LLM tasks; no KG system does it, so the transfer is novel not inherited |
| Single-pass extraction | Change | Behind even 2024 GraphRAG; gleaning and entity/relation split exist because one pass under-extracts |
| Purpose-guided extraction and typing | Keep + ablate | It is instruction-based IE; benefit is inferred, not measured on type induction - prove with an A/B |
| Identity decoupled from type + multi-label nodes | Keep | Textbook LPG / fine-grained-typing SOTA; add embedding to the identity key to stop name-collision merges |
| One-shot, cure-once, flat type clustering | Change | SOTA canonicalizes by embed → block → LLM-verify and re-consolidates continuously |
| Bayesian multi-signal resolution skeleton | Keep | Structural collapse → embedding candidates → Fellegi-Sunter three-zone → transitive merge already beats GraphRAG/LightRAG dedup |
| Hand-set likelihood ratios | Change | FS's whole value is that LRs are estimated; hand constants double-count correlated description+embedding signals |
| Brute-force within-type cosine blocking | Change | O(n^2) per type; breaks past a few thousand entities - use FAISS ANN top-k |
| Isotonic calibration on collected pairs | Change | Temperature scaling beats isotonic; calibrating on non-held-out pairs overfits; 25 pairs is fitting noise |
| Union-find transitive merge | Keep + guard | Correct but snowballs (A~B, B~C ⇒ A≡C); add a correlation-clustering split pass |
| Accumulate-only facts (no temporal validity) | Throw away | Disqualifying for "runs for months"; puts KGF at LightRAG tier, a whole dimension behind Graphiti/Zep |
| Drift = remap-rate + type JSD | Keep + demote | It monitors schema drift (secondary); it is not the SOTA framing, which is fact-level invalidation |
| Leiden communities + LLM summaries as the retrieval path | Change | No longer SOTA for entity/multi-hop QA; PPR and dual-level match or beat it at a fraction of cost |
| Vector top-k + fixed 1-hop retrieval | Change | Structurally capped below SOTA on multi-hop; a bridging entity two hops out is never retrieved |
| Full on-demand community recompute | Change | A real liability for a growing graph; append-only or incremental-Leiden is SOTA |

## The one disqualifying gap - fact drift and temporal validity

The largest finding: KGF as first built is accumulate-only. It MERGEs and unions provenance, keeps no validity intervals, and has no contradiction handling. Against the actual "runs for months, data drifts" problem this is the failure mode bi-temporality exists to prevent - after month three, "CEO = Alice" and "CEO = Bob" coexist as equally live edges with no way to answer who holds the role now versus in March. Provenance records that both were said; it does not record that one replaced the other.

The reference system is Graphiti/Zep ([arXiv:2501.13956](https://arxiv.org/abs/2501.13956)): every edge carries valid-time (true in the world) and transaction-time (when learned); a superseding fact invalidates the prior edge by setting its end-timestamp rather than deleting it; nothing is ever lost. This is exactly the entity-versioning and evolution-record requirement raised during review - the literature makes it non-negotiable for longevity, not an enhancement.

KGF built a good detector for schema drift (the drift a cured ontology already minimizes) and nothing for fact drift (the drift that unavoidably accumulates). It armored the stable axis and left the lethal one bare.

## What survives as genuinely SOTA

- **Identity decoupled from type, multi-label nodes** - the mainstream labeled-property-graph and fine-grained-typing stance; the dual-role humidifier is exactly the case multi-label exists for
- **The resolution skeleton** - structural collapse, embedding candidates, three-zone Fellegi-Sunter, transitive merge; already ahead of GraphRAG (identical title+type only) and LightRAG (string match)
- **Curing's statistical foundation** - Chao1 and coverage estimators as a saturation-based stopping criterion, transferred from ecology and technology-assisted review
- **Rebuild as recommendation only** - SOTA never auto-rebuilds; incremental-with-invalidation is the norm

## Priority-ordered change plan

Ordered by leverage against the "production-grade, runs for months, SOTA" goal.

1. **Bitemporal edges + contradiction reconciliation** (non-negotiable for longevity). Add valid_from/valid_to and created_at/expired_at to every edge; on ingest, hybrid-search existing edges between the same entity pair, LLM-check for contradiction, and on temporal overlap invalidate the old edge. Make default retrieval "currently valid". Entity versioning falls out of the same machinery. Grounded in Graphiti/Zep, TOKI ([arXiv:2606.06240](https://arxiv.org/pdf/2606.06240))
2. **PPR retrieval seeded from vector top-k** (highest retrieval leverage). Keep the Neo4j vector index as the seeder; replace fixed 1-hop with GDS Personalized PageRank from the top-k entities; take top-N PPR nodes plus their source chunks. Directly targets the multi-hop gap. GDS already ships PageRank, so it is a query-layer change. Grounded in HippoRAG 2 ([arXiv:2502.14802](https://arxiv.org/abs/2502.14802)), NodeRAG ([arXiv:2504.11544](https://arxiv.org/html/2504.11544))
3. **Gleaning + entity/relation split in extraction** (highest quality leverage). After the first instructor pass, re-prompt "what entities/relations are present but not yet extracted", bounded to 1-2 rounds on a cheap model; run entity and relation extraction as separate calls. Attacks extraction-variance failures. Grounded in GraphRAG gleanings, iText2KG ([arXiv:2409.03284](https://arxiv.org/html/2409.03284v1))
4. **ANN blocking + LLM-judged defer zone** in resolution. Replace brute-force within-type cosine with FAISS HNSW top-k per type (faiss-cpu is already a dependency); route only the 0.4-0.6 defer band to an LLM judge (GPT-4o, or local Jellyfish/ANYMATCH). Grounded in DeepBlocker ([PVLDB](https://vldb.org/pvldb/vol14/p2459-thirumuruganathan.pdf)), Peeters and Bizer LLM entity matching ([arXiv:2310.11244](https://arxiv.org/abs/2310.11244))
5. **Re-runnable, hybrid type consolidation.** Replace the one-shot flat LLM pass with embed-definition → block → LLM-verify (EDC, [arXiv:2404.03868](https://arxiv.org/html/2404.03868v1)); allow bounded re-cure on a post-cure type burst so late synonyms still merge; keep a light isa layer instead of a lossy flat collapse
6. **Demote community summaries to a global-only path**; route entity/multi-hop queries to PPR; if no global sensemaking queries are served, drop the community layer and reclaim the LLM cost
7. **Harden curing and calibration.** Add a Chao1 minimum-sample floor before the gate can fire; learn resolution LRs (Splink-style EM or logistic regression) and decorrelate description+embedding into one signal; drop isotonic-on-collected-pairs for temperature scaling on a held-out set, or a fixed documented threshold below ~100 labels
8. **Guard transitivity** with a correlation-clustering split pass after union-find; add contradiction-rate per window as the real fact-drift alarm, demoting remap+JSD to the schema-recure trigger it already is

## Honest note on method

The initial rewrite anchored on v1 and defended curing with v1's own benchmarks - an internal reference, not the state of the art. Going wide confirmed curing was a defensible call for a reason I had not established (its statistical basis is SOTA in adjacent fields), and it caught defects the v1-anchored view would have shipped: accumulate-only facts, single-pass extraction, and Leiden-only retrieval. The lesson stands - ground core decisions in external SOTA, and be willing to discard.

---

# R02 - Retrieval-First Redesign (2026-07-06 research round)

Second research round, six independent passes: graph shape for retrieval, traversal and context assembly, faithfulness and weak-reader serialization, maintenance for retrieval quality, topology balance and agent navigation (contrarian mandate), and millions-of-nodes operation under drift. Guiding directive: the graph must yield perfect context in one or two precise hops even for weak reader models - massive traversals are the bane; work shifts from query time to ingest time. Cited papers are archived with digests under `../references/papers/`.

## R02 verdict table (on the R01 architecture)

| Choice | Verdict | Basis |
|--------|---------|-------|
| Trusting LLM-proposed types (spec values become types) | Throw away | No SOTA system promotes measured values to types; GraphRAG models them as claims/covariates on the entity; the 66-vs-7 proliferation is the measured symptom |
| Homogeneous Entity nodes, entities are the embedded unit | Change | NodeRAG: embed content nodes (propositions, summaries, text); entity names are string-match entry points, not vector targets; MuSiQue 46.3% at 5.9k tokens vs GraphRAG 41.7% at 6.6k |
| No proposition/semantic-unit layer | Change | NodeRAG semantic units drive its multi-hop lead (retrieval ratio 94.9% vs 86.3%); RAPTOR-style ingest-time synthesis +20pt; the single biggest weak-reader lever |
| Entity-only PPR projection, chunks attached after | Change | HippoRAG 2: passage nodes inside PPR worth +11 recall@5 on MuSiQue; reset weights passage 0.05 vs phrase 1.0 |
| Query-to-entity vector seeding only | Change | HippoRAG 2 query-to-triple linking: +12.5% recall@5 average, +21 on MuSiQue |
| One-shot retrieval for comparison queries | Change | Decomposition of "A vs B on X" into per-entity sub-retrievals: +7% F1 / +6% EM, ~10x context efficiency |
| Sparse graph (avg_degree 2.49) | Change | Best-evidenced topology lever: kNN/synonym similarity edges +6.4% entity recall (p=0.000043); winning systems avg_degree ~8.75, failing ~1.48; densify toward coherent local clusters, not global density |
| Context = concatenated descriptions + chunks | Change | Reasoning-ordered structured blocks beat flat triples and prose; PPR-ordered with head+tail placement (lost-in-the-middle >30% degradation); per-claim citations suppress unsupported content in the 8-35B reader band |
| Free-form answering with no abstention | Change | Structural coverage signals reach 76% correct-refusal vs 0% for confidence-based; empty neighborhood / no connecting path / low community overlap route to abstain |
| Eager community summaries for every community | Change | LazyGraphRAG: defer summarization to first thematic hit at ~0.1% cost; dirty-set refresh only touched communities (56x measured cost swing) |
| Destructive hard merges | Change | Mention/entity two-layer with append-only merge log; splits become min-cut data operations; transitivity inconsistency is the measured breaking point at scale |
| FluidBuffer staging as serialized blob outside the graph | Change | In-graph staged tier (Graphiti episode subgraph + MDM mention layer converged): raw mentions/propositions land as staged nodes, promotion attaches canonical labels; buys reversibility, idempotent resume, provenance, concurrent-writer safety in one mechanism |
| Per-query `valid_to IS NULL` Cypher projection | Change | Materialize a current-edge label at write time; native label-filtered projections are the fast path; history in a historical partition |
| Uniform PPR seeding, no hub management | Change | CatRAG query-time hub damping: super-hub mass 45.7% to 42.5%, Recall@5 +2.5-5.6; damp at query time, never delete hubs |
| Per-mention re-embedding, no cache (DEF-1) | Fix | Universal production practice: cache keyed by (text, model_id); Drift-Adapter for model upgrades (97-99% recall at >100x less compute) |
| Structural metrics as quality targets | Demote to diagnostics | Orphan_rate is retrieval-inert (correlational only); community balance benefits asserted not measured; outcome metrics gate, structure diagnoses |
| Global drift metrics only | Change | Per-community drift baselines from day one - selective subgraph rebuild at scale is impossible without accumulated per-subdomain history |

## What survives R02 scrutiny unchanged

- **Bitemporal invalidation + entity versioning** - exactly the Graphiti/Zep production model; validated, not novel risk
- **Bayesian resolution skeleton + FAISS ANN blocking** - ANN-as-blocker is the formalized SOTA (BlockingPy); blocking is what must scale, not the scorer
- **PPR retrieval core at damping 0.85** - the 2025 delta is in seeding richness and node topology, not the diffusion mechanics
- **Curing's statistical basis** - once spec values stop polluting the type space, JSD/Chao1 gates operate on a legitimate inventory
- **Purpose-guided extraction** - still to be ablated, no evidence against
- **Leiden + community summaries for global queries** - well-validated (Microsoft, Zep); do not tune resolution or chase partition balance (asserted, unmeasured)

## Target graph shape (retrieval-first)

Node roles, replacing the homogeneous entity graph. Entities route; content nodes carry what retrieval returns; values are properties, never types.

- **Entity** - identity + multi-label types + name; string-match and vector entry point; NOT the primary retrieval payload
- **Proposition (semantic unit)** - self-contained fact sentence generated at ingest ("SleepStyle 234 supports CPAP and auto-adjusting modes"), embedded, carries source chunk id and per-claim citation; first-class PPR node; the unit weak readers consume
- **Chunk (passage)** - verbatim text, embedded, inside the PPR projection with low reset weight; spill-over context when a proposition is insufficient
- **Spec values** - properties or claim reifications on the parent entity (with provenance and validity when contested), never entity types
- **Community summary** - lazy, generated on first thematic hit, dirty-set refreshed
- **Staged tier** - extraction lands as staged mentions/propositions in-graph; resolution and curing promote by labeling; retrieval projections see only the promoted, currently-valid layer
- **Similarity edges** - kNN/synonym edges (cosine gated) densifying coherent local clusters; the residual resolution defer band gets alias edges instead of forced merges

## Measurement doctrine

Metrics are tracked only where they gate a decision. Hierarchy: outcome metrics gate, retrieval metrics diagnose, structural metrics explain.

- **Gate (probe set per corpus)** - answer accuracy, evidence recall (gold facts present in context), faithfulness (verifiable/total statements), abstention correctness
- **Diagnose** - recall@k of seeds, PPR hit distribution, context token cost per query
- **Explain (never targets)** - avg_degree, clustering coefficient, orphan_rate, modularity, community sizes
- **Maintain** - query-failure rate as a first-class maintenance trigger flagging graph regions for re-extraction; per-community drift baselines stored as community properties

## Priority-ordered change plan (R02/R03 batches)

Retrieval-first structural batch (R02):

1. **Values-as-properties extraction constraint** - extraction schema forbids unit/measure/range strings as entity types; they become properties or claims on the parent entity; cure-time value-likeness demotion guard as backstop (kills the 66-type bug at source)
2. **Proposition nodes** - ingest-time semantic-unit generation per entity neighborhood, embedded, citation-carrying, in PPR
3. **Passage nodes in the PPR projection** with reset-weight tiering (~0.05 passages, 1.0 entities/propositions)
4. **Query-to-triple seeding** - embed relation sentences; seed PPR from matched triples plus entities
5. **Comparison-query decomposition** - split "A vs B on X" into per-entity retrievals, union contexts
6. **Similarity-edge densification** - kNN semantic edges (cosine gated) + alias edges for the resolution defer band
7. **Context serialization** - per-entity blocks (name, propositions, native relationship facts, source snippet), PPR-ordered head+tail, per-claim citation ids, capped budget
8. **Structural abstention** - coverage verdict from seed neighborhood, path connectivity, community overlap; abstain/clarify instead of generating

Operational longevity batch (R03):

9. **In-graph staged tier + mention layer + append-only merge log** (reversible resolution)
10. **Embedding cache** keyed by (text, model_id) - closes DEF-1
11. **Current-edge label materialization** - native projections, historical partition
12. **Lazy + dirty-set community summaries**
13. **Query-time hub damping** (anchored reset mass, degree-aware edge down-weighting)
14. **Per-community drift metrics + query-failure maintenance trigger**
15. **Pruned schema card + cheap query router** (query-scoped schema beats full dump; SVM/heuristic router at 0.928 F1, 28% token savings)

Explicitly rejected after contrarian review: ToG-style agentic beam search as default (5.4x call cost, justified only on measured one-shot failure), build-time master-graph pruning (no production evidence, risks bridges), Leiden resolution tuning for partition balance (asserted, unmeasured), forced JSON answer schemas at query time (-10-15% reasoning accuracy), external vector index at current scale (native fine to ~10M vectors), synonym-edges-everywhere instead of hard merges (redundancy and added hops; merge-primary with alias edges on the defer band wins).

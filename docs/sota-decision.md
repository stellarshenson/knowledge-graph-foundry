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

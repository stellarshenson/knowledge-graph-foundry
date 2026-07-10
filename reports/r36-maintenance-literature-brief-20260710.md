# R36 Input - Maintenance of Derived Retrieval Objects: Literature Brief (research agent, 2026-07-10)

Deliverable of the external-literature research agent (task a8381a8cfc3c3b022), persisted verbatim. Input to R36 registration (maintenance of derived objects). Companion: r36-maintenance-internal-map-20260710.md. New papers archived to references/papers/ (EraRAG, Sleep-time Compute, Mem0, A-MEM, DBSP - PDF+digest pairs, %PDF verified).

---

## STEP 1 - WHAT THE LOCAL ARCHIVE ALREADY ESTABLISHES

All files under `references/papers/`.

| Digest | What it already establishes for maintenance |
|---|---|
| **Zep Graphiti** | The operational invalidate-don't-delete pattern: bitemporal edges (valid-time + transaction-time), contradiction -> mark old edge invalid with end time, never delete; incremental per-entity resolution at ingest (P95 ~300ms); dynamic label propagation instead of periodic full Leiden re-clustering. DMR 94.8%, LongMemEval +18.5% at ~90% lower latency |
| **Drift-Adapter** | Embedding-model swap without corpus re-embed: small transform maps new-model queries into legacy space; 95-99% recall retention, ~0.5 GPU-h vs ~100 GPU-h (~200x cheaper), <10us query overhead. Verified against arXiv 2509.23471 (below) |
| **TCR-QF** | Failed/underserved queries as maintenance trigger; query-relevant missing knowledge incorporated back into the KG; training-free. Verified numbers added below (29.1% EM / 15.5% F1 improvement, IJCAI 2025) |
| **EvoRAG** | Response-level feedback backpropagated to triplet-level graph edits (correct/remove/reweight). Boundary of published work: repairs stop at editing triples IN the graph - no published system closes probe-failure -> re-ingestion from named sources. That loop is KGF's open territory |
| **LightRAG** | Claims incremental update = process new docs with the same pipeline, union node/edge sets; no rebuild. What it does NOT cover in the paper: deletion, edits, description staleness (verified below - deletions were bolted on later in the repo and have documented cache-staleness bugs) |
| **Microsoft GraphRAG** | Hierarchical Leiden communities + LLM summaries per community; index reusable across queries. The paper has NO update story - that arrived in GraphRAG 1.0's `update` command (verified below) |
| **RAPTOR** | The canonical NON-incremental derived structure: global UMAP+GMM clustering means any insert can reshuffle every cluster - the negative example that motivates EraRAG |
| **KET-RAG** | Budgeted derivation: spend expensive LLM extraction only on a PageRank-selected core (~10x indexing cost cut) - transfers directly to "which derived objects deserve eager maintenance" |
| **RPQ materialized view selection** | Workload-aware view benefit is monotone + submodular -> greedy selection with (1-1/e) guarantee; 9.73x speedup on Wikidata. The formal template for CHOOSING which derived objects to materialize under budget |
| **Evidence Units** | Neo4j-stored construction rules with completeness invariants - a working pattern for machine-checkable invariants over derived structures |
| **Trust but Verify** | Verifier-based selection beats unverified generation, gap widens with compute - the argument that maintenance loops need a verifier component distinct from the generator |
| **QuOTE / doc2query / Doc2Query--** | The derived-question object class itself: ~16x one-time indexing cost (QuOTE), questions-per-chunk as budget dial, and Doc2Query--'s quality gate (filtering hallucinated queries: +16% effectiveness, -33% index, -23% query time). None of the three says one word about keeping generated questions in sync with edited corpora |
| **Query-time Entity Resolution (Bhattacharya & Getoor)** | Defer resolution to read time; geometric decay of collective-resolution benefit with neighborhood depth - the theoretical basis for lazy, query-scoped repair |
| **GenIC** | Gap prediction (what SHOULD this entity have) as stage 1 of completeness maintenance; KGF replaces parametric fill with repair-from-source |
| **Knowledge Persistence** | Persistent-homology fingerprint as a cheap global drift/over-merge monitor per snapshot (18h -> 27s evaluation) - a candidate periodic-audit primitive |
| **A-MEM** | Was NOT in the archive - now added (see Step 3) |

---

## STEP 2 - MECHANISM CARDS

### Area (a) - Incremental View Maintenance (database theory)

**CARD a1: Delta-propagation IVM / counting algorithm**
- **Source**: Gupta, Mumick & Subrahmanian, "Maintaining Views Incrementally", SIGMOD 1993
- **Mechanism**: for view V = Q(R), compute dV from dR using delta rules; maintain a support COUNT per derived tuple (number of distinct derivations); deletion decrements the count, tuple dies only at count 0
- **Verified numbers**: none claimed (algorithmic paper)
- **Cost profile**: work proportional to |delta| for linear operators; joins pay per-delta index lookups against materialized state
- **Failure modes**: counting breaks under recursion (a tuple can support its own derivation) - hence DRed
- **Transfer**: support counts are the single cheapest idea to steal - a synonym edge or hoisted property supported by 3 documents survives deletion of 1

**CARD a2: DRed (Delete-and-Rederive)**
- **Source**: same paper; still SOTA for Datalog materialization maintenance (Motik et al., "Maintenance of Datalog Materialisations Revisited", and B/F algorithm)
- **Mechanism**: on deletion, (1) over-delete everything transitively derivable from the deleted facts, (2) re-derive the subset that has alternative derivations from surviving facts, (3) insert new consequences
- **Verified numbers**: none headline; the over-delete phase is the known cost problem (can touch far more than the true change)
- **Cost profile**: worst case proportional to the derivation closure of the deletion, then a partial re-derivation pass
- **Failure modes**: over-deletion explosion on hub facts (delete a hub entity -> giant closure); exactly the risk when a KGF entity with many derived questions/props is merged away
- **Transfer**: the two-phase shape (pessimistically invalidate, then cheaply re-validate what still holds) is the correct template for entity-merge fallout: mark all derived objects of both entities dirty, re-validate against the merged node, regenerate only true losses

**CARD a3: Self-maintainability**
- **Source**: Gupta, Jagadish & Mumick, "Data Integration Using Self-Maintainable Views", EDBT 1996
- **Mechanism**: a view is self-maintainable w.r.t. an update class if it can be maintained from the view contents + the delta ALONE, without querying base relations; the paper derives tight conditions for SPJ views
- **Verified numbers**: none (theory)
- **Cost profile**: self-maintainable updates are near-free; non-self-maintainable ones force base access
- **Failure modes**: most joins are not self-maintainable under insertions - auxiliary data must be stored
- **Transfer**: the design question per KGF object class: what auxiliary provenance must a derived object CARRY so staleness can be decided without re-reading source documents? (e.g., a question node storing the hash of the description span it was generated from is self-maintainable w.r.t. "did my source change" checks)

**CARD a4: DBSP (mechanical incrementalization)**
- **Source**: Budiu et al., PVLDB 16(7) 2023, best paper; arXiv 2203.16684 - archived this session
- **Mechanism**: Z-sets (signed multiplicities) unify insert/delete/update; any query composed of DBSP operators is mechanically rewritten to a delta-in/delta-out version; recursion (and thus DRed) falls out of the algebra
- **Verified numbers**: theory-first; no headline speedup in paper (implementation = Feldera). UNVERIFIED beyond asymptotics
- **Cost profile**: linear ops O(|delta|); bilinear (join) O(|delta| x index probe); recursion pays fixpoint-local work
- **Failure modes**: assumes deterministic, cheap operators - the exact assumptions LLM derivation violates
- **Transfer**: what transfers is the SCOPING discipline (dependencies recorded at derivation time, repair as a function of delta), not eager per-delta execution. For expensive non-deterministic LLM operators, the incremental plan must be batched/thresholded/lazy - which is precisely where the literature goes quiet (open slot)

**CARD a5: Immediate vs deferred maintenance**
- **Source**: classic warehouse literature (Gupta & Mumick 1995 survey; Colby et al. deferred maintenance, SIGMOD 1996)
- **Mechanism**: immediate = maintain in the update transaction (queries always fresh, writes pay); deferred = queue deltas, maintain at query time or on schedule (writes cheap, first query pays or periodic job pays); lazy variants maintain only views a query actually touches
- **Verified numbers**: workload-dependent; no universal figure
- **Failure modes**: deferred + rare queries = unbounded staleness windows; immediate + hot writes = write amplification
- **Transfer**: this is THE policy axis for every KGF derived object; LLM recompute cost pushes strongly toward deferred/lazy, query-correctness risk pushes selected classes (gap ledger, hoisted spec props feeding answers) toward immediate

**CARD a6: Salsa red-green / demand-driven incremental computation**
- **Source**: Salsa framework (rust-analyzer, rustc query system) - salsa-rs.github.io/salsa/reference/algorithm.html; rustc dev guide
- **Mechanism**: memoized query DAG with per-result revision stamps; on input change, walk dependencies backward; EARLY CUTOFF - if a recomputed intermediate value is byte-identical to the old one, downstream consumers are marked green without recomputation
- **Verified numbers**: none published as benchmarks (engineering system)
- **Failure modes**: needs deterministic, comparable outputs for cutoff - LLM outputs are neither, so cutoff must be redefined semantically (e.g., embedding-similarity or entailment-preserving "same enough")
- **Transfer**: early cutoff is the key idea for LLM pipelines: a document re-version that leaves an entity's description SEMANTICALLY unchanged should stop the invalidation flood at that node. Semantic early-cutoff predicates are unpublished territory (open slot)

**CARD a7: Build Systems a la Carte (rebuilder taxonomy)**
- **Source**: Mokhov, Mitchell, Peyton Jones, ICFP 2018 / JFP 2020
- **Mechanism**: every build/derivation system = scheduler (topological / restarting / suspending) x rebuilder (dirty bit / verifying traces / constructive traces / deep constructive traces)
- **Transfer**: gives KGF the exact vocabulary for its maintenance registry: dirty bit = "doc version changed, all derived objects of that doc stale"; verifying trace = "question node stores hash of source span + generator prompt version; verify before reuse"; constructive trace = LLM-output cache keyed by (input-hash, prompt, model) - which is literally what LightRAG's LLM cache does, and what its issue #2442 shows going wrong when the cache key ignores upstream state

### Area (b) - Incremental / streaming GraphRAG

**CARD b1: LightRAG incremental update - verified against paper**
- **Source**: arXiv 2410.05779 (EMNLP 2025 Findings); repo HKUDS/LightRAG
- **Mechanism (paper)**: new documents run through the identical extraction pipeline; the resulting subgraph is combined with the existing one by taking the UNION of node sets and edge sets. That is the entire published mechanism - what it avoids recomputing is re-extraction of old documents and (because LightRAG has no community layer) any re-clustering/re-summarization
- **What the paper does NOT handle**: deletions, document edits, refresh of merged entity descriptions when the union creates duplicates/conflicts (repo issue #2528 asks exactly this)
- **Repo reality (post-paper)**: deletion support added later - removes doc-exclusive entities/relations, REBUILDS descriptions of shared entities from remaining documents using the LLM cache; issue #2442 documents the failure: stale LLM cache entries from a failed ingest get reused instead of fresh extraction, and orphaned chunks persist -> re-ingestion failures
- **Verified numbers**: none published for update cost
- **Failure modes**: append-only union accumulates description drift and duplicate entities; cache-keyed rebuilds inherit corrupted cache state
- **Transfer**: negative lesson - union-merge without a description-refresh policy and without cache invalidation keyed to upstream state is how derived text rots silently

**CARD b2: Microsoft GraphRAG `update` command (v1.0+, standard-update / fast-update)**
- **Source**: microsoft.github.io/graphrag CLI docs; MSR blog "Moving to GraphRAG 1.0"; GitHub issues #741, discussion #511
- **Mechanism**: computes deltas between existing index and new content; merges entities/relationships; tries to minimize community recomputation so community summaries are not regenerated - but if thresholds on community-structure change are exceeded, recompute triggers, worst case degrading to full re-index cost. Scope explicitly limited to APPEND - no removal, no manual edits, no delta-tagged queries. LLM response cache makes re-runs "significantly faster and cheaper" (no published percentage - UNVERIFIED)
- **Cost profile**: bounded below by delta extraction, above by full Leiden re-cluster + full re-summarization; community summaries are the expensive derived object (one LLM call per community per level)
- **Failure modes**: community drift - incremental merges without re-clustering slowly degrade community coherence; the design deliberately makes `index` always recompute communities "so users don't have to worry about model drift" (their words)
- **Transfer**: threshold-triggered escalation (patch -> partial recompute -> full rebuild) is a sane three-tier repair policy; also the honest admission that some derived objects (global clusterings) fundamentally resist local maintenance

**CARD b3: EraRAG - localized maintenance of hierarchical summaries**
- **Source**: arXiv 2506.20963 - archived this session
- **Mechanism**: frozen hyperplane-LSH bucketing makes each insert's dependency footprint computable (one bucket); split/merge thresholds S_max/S_min bound per-update work; re-summarize affected buckets only, propagate upward through ancestor summaries
- **Verified numbers**: up to 57.6% token reduction vs RAPTOR (PopQA insertions); up to 77.5% rebuild-time reduction (QuALITY); ~20s single-doc insert - ~10x faster than RAPTOR/HippoRAG, ~100x vs GraphRAG; accuracy 60.25% vs RAPTOR 55.48% on QuALITY (Llama-3.1-8B); best on 8/10 multi-hop metrics
- **Failure modes**: frozen hyperplanes cannot adapt if corpus distribution shifts massively (the price of determinism); bucket-boundary questions may straddle summaries
- **Transfer**: the strongest published existence proof that a hierarchical LLM-derived structure can be maintained with locality; the frozen-partition trick applies to KGF's community summaries and any clustering-derived object

**CARD b4: iText2KG / ATOM - incremental & dynamic KG construction**
- **Source**: iText2KG arXiv 2409.03284 (WISE 2024); ATOM arXiv 2510.22590 (EACL 2026 Findings), same lab
- **Mechanism**: iText2KG - four-module pipeline (distiller -> incremental entity extractor -> incremental relation extractor -> integrator) that resolves each new document's entities/relations against the growing graph, zero-shot, no post-hoc dedup pass. ATOM extends to dynamic TEMPORAL KGs: atomic-fact decomposition, parallel extraction, 5-tuple merges with temporal metadata, targeting exhaustivity + stability + update latency for continuously arriving text
- **Verified numbers**: qualitative superiority claims across three scenarios (papers/websites/CVs); no maintenance-cost figures. UNVERIFIED beyond that
- **Failure modes**: both address construction-time merging, not derived-object refresh after the fact
- **Transfer**: confirms incremental ER-at-ingest is the 2024-2026 consensus; nobody in this line touches downstream derived-object invalidation

**CARD b5: Incremental entity resolution / record linkage (pre-LLM formal line)**
- **Source**: Gruenheid, Dong, Srivastava, "Incremental Record Linkage", PVLDB 7(9) 2014
- **Mechanism**: maintain the similarity graph + clustering under record inserts/updates/deletes; general framework with merge/split/move-record repair operators applied to the affected subgraph only; greedy correction algorithms
- **Verified numbers**: incremental algorithms run orders of magnitude faster than batch re-linkage with similar quality (per-experiment; PARTLY VERIFIED)
- **Failure modes**: error accumulation - repeated local greedy repairs drift from the global optimum; periodic full re-clustering still recommended
- **Transfer**: merge/split/move as the repair vocabulary for entity clusters is exactly what KGF entity merge/split events need; also the honest pattern of "incremental daily, batch weekly" to cap drift

### Area (c) - Embedding staleness

**CARD c1: Drift-Adapter**
- **Source**: arXiv 2509.23471 (EMNLP 2025 industry track) - already archived
- **Mechanism**: train a small transform (Orthogonal Procrustes / low-rank affine / small residual MLP) on ~5-20k paired (old,new) embeddings of the same items; map NEW-model query vectors into the LEGACY index space; corpus vectors untouched
- **Verified numbers (confirmed against paper)**: recovers 95-99% of full re-embed Recall@10/MRR on MTEB text corpora + a CLIP image upgrade (1M items); <10us added query latency; ~0.5 GPU-h adapter training vs ~100 GPU-h full re-embed (~200x)
- **Failure modes**: degrades when old/new spaces differ radically (cross-architecture, cross-modality jumps); residual 1-5% recall loss compounds if you chain adapters across multiple upgrades
- **Transfer**: KGF's answer to "embeddings regenerated" invalidation events: pin the corpus space, adapt queries, schedule true re-embeds lazily

**CARD c2: Backward-Compatible Training (BCT) and successors**
- **Source**: Shen, Xiong, Xia, Soatto, CVPR 2020 (arXiv 2003.11942); successors: FCT (forward-compatible), Darwinian model upgrades, online-backfill metric training (arXiv 2301.03767)
- **Mechanism**: train the NEW encoder with an influence loss anchoring it to the old model's classifier/space, so new query embeddings are directly comparable to old gallery embeddings -> "backfill-free" upgrade
- **Verified numbers**: UNVERIFIED at number level
- **Failure modes**: constrains the new model's representational freedom (caps upgrade gains); requires controlling the training of the new model - not applicable when consuming third-party embedding APIs (where Drift-Adapter wins)
- **Transfer**: relevant only if KGF ever fine-tunes its own embedders; the "compatibility by construction" end of the spectrum

**CARD c3: Industry re-embedding operations (lazy vs eager, version pinning)**
- **Source**: vendor/practitioner guidance (Zilliz FAQ, aboutvectordatabase.com, engineering posts, OpenViking issue #1066) - INDUSTRY PRACTICE, NO PEER-REVIEWED NUMBERS
- **Mechanism**: (1) pin exact model name+version in config, identical for ingest and query - never "latest"; (2) eager = blue-green: new collection/column, background backfill, dual-write during transition, atomic cutover, drop old; (3) lazy = mixed-state index re-embedded on touch/schedule - generally warned against because old/new vectors are geometrically incomparable within one index; (4) content-edit re-embeds are driven by CDC (change data capture) on the source record
- **Failure modes**: mixed-space corruption (the cardinal sin); silent model drift when a provider updates behind an alias; forgetting derived-of-derived (question-node embeddings must re-embed when question text regenerates, independent of passage embeddings)
- **Transfer**: KGF needs an `embedding_version` property on every vector-bearing node + a registry mapping version -> model hash; a query-time guard refusing to compare across versions unless an adapter is registered (Drift-Adapter slot)

**CARD c4: Query Drift Compensation (continual-learning variant)**
- **Source**: arXiv 2506.00037
- **Mechanism**: when the embedding model itself is continually fine-tuned, estimate and compensate query-side drift so old document embeddings remain usable across model generations
- **Verified numbers**: not extracted - UNVERIFIED
- **Transfer**: marginal for KGF now; confirms the "compensate at query side, leave corpus pinned" pattern generalizes

### Area (d) - Agentic memory maintenance

**CARD d1: Zep/Graphiti temporal edge invalidation**
- **Source**: arXiv 2501.13956 - already archived
- **Mechanism**: bi-temporal bounds on every edge (fact valid-from/valid-to in world time; created/expired in system time); new contradicting information -> LLM identifies the conflict -> old edge gets invalid/expired stamps, stays queryable historically; communities updated by label propagation, not periodic re-clustering
- **Verified numbers**: DMR 94.8%; LongMemEval +18.5% accuracy at ~90% latency reduction vs full-context; ER P95 ~300ms
- **Cost profile**: invalidation is O(conflicting neighborhood) LLM calls at ingest; storage grows monotonically (nothing deleted)
- **Failure modes**: monotone growth needs eventual archival; LLM contradiction detection misses subtle conflicts (paraphrase-level)
- **Transfer**: the append-and-invalidate provenance-preserving pole of the rewrite-vs-append axis; directly applicable to synonym edges and gap-ledger entries (a closed gap is invalidated, not erased - the closure event is itself signal)

**CARD d2: Mem0 ADD/UPDATE/DELETE/NOOP routing**
- **Source**: arXiv 2504.19413 - archived this session
- **Mechanism**: per write, retrieve top-k similar memories, one LLM call classifies the operation; UPDATE rewrites in place (no history)
- **Verified numbers**: +26% relative accuracy over OpenAI memory on LOCOMO (paper's own eval; Zep publicly disputed the Zep-baseline configuration - treat cross-system comparisons with care); ~91% p95 latency and ~90% token reduction vs full-context; ~7k vs ~26k tokens per conversation
- **Cost profile**: one routing LLM call per write batch regardless of novelty - write-cost scales with ingest volume (later work adds novelty gates, e.g. SAGE arXiv 2605.30711)
- **Failure modes**: destroys provenance on UPDATE; routing errors are silent and uncorrectable (no justification retained)
- **Transfer**: the minimal maintenance op-set + similarity-triggered review; KGF should adopt the op vocabulary but reject in-place rewrite for anything feeding answers

**CARD d3: A-MEM memory evolution (neighborhood ripple updates)**
- **Source**: arXiv 2502.12110 - archived this session
- **Mechanism**: every new note links to top-k similar historical notes; linked neighbors' derived attributes (contextual description, tags) may be LLM-REWRITTEN in light of the new note - stale derived metadata repaired opportunistically on-write, bounded by k
- **Verified numbers**: beats MemGPT/MemoryBank/ReadAgent baselines across six foundation models on LOCOMO, biggest gains on multi-hop; no single headline delta (varies by backbone)
- **Cost profile**: maintenance cost scales with write rate x k, not store size
- **Failure modes**: no record of WHY a description changed (no justifications); rewrite cascades can oscillate; correctness of the rewrite is unverified
- **Transfer**: the published pattern nearest to KGF's "descriptions get rewritten -> dependent question nodes stale" problem, solved in the OPPOSITE direction (new data refreshes old derived text). Combine with a verifier gate (Trust-but-Verify) and provenance (Zep) to make it foundry-grade

**CARD d4: Sleep-time compute (offline maintenance budget)**
- **Source**: arXiv 2504.13171 - archived this session
- **Verified numbers**: ~5x test-time compute reduction at iso-accuracy (Stateful GSM-Symbolic, Stateful AIME); accuracy +13% / +18% by scaling sleep-time budget; 2.5x per-query cost cut amortized across related queries
- **Mechanism / transfer**: formalizes "maintenance runs while idle" with a measured exchange rate between offline and online compute; the economic justification for KGF's idle-cycle audit/refresh loops, and the eligibility rule (pre-compute only where queries are predictable) maps to which question nodes to generate eagerly

**CARD d5: Decay and TTL scoring**
- **Sources**: Generative Agents (Park et al. 2023, arXiv 2304.03442): retrieval score = recency + importance + relevance, equal weights, recency = 0.995^(hours since last access), importance LLM-scored 1-10. MemoryBank (AAAI 2024, arXiv 2305.10250): Ebbinghaus curve R = e^(-t/S), strength S incremented on each recall - use-strengthens, disuse-decays. When-to-Forget / Memory Worth (arXiv 2604.12007): two counters per memory (co-occurrence with successful vs failed outcomes) -> converges to conditional success probability; Spearman rho=0.89+-0.02 vs 0.00 for static importance after 10k episodes; stale memories fall to MW=0.17 while good specialists hold 0.77 over 3k episodes
- **Cost profile**: near-zero - counters and exponentials, no LLM calls
- **Failure modes**: decay conflates unused with wrong; outcome-co-occurrence is associational, not causal; cold-start for new derived objects
- **Transfer**: outcome-linked worth (did retrieving this question node lead to a correct answer?) is a far better staleness signal for KGF's generated questions than age-based TTL - and it is nearly free if the benchmark/judge loop already records outcomes

### Area (e) - Generated-query / document-expansion staleness

**Finding: the direct literature is EMPTY - confirmed.** Targeted searches for maintenance/regeneration of doc2query/docTTTTTquery/QuOTE-style generated questions under corpus edits return nothing: doc2query line (1904.08375, docTTTTTquery, Doc2Query-- 2301.03266, Doc2Query++ 2510.09557) treats the corpus as frozen; QuOTE (2502.10976) prices generation as "one-time." No published system tracks generated-question <-> source-span dependencies, no invalidation policy, no drift measurement of question quality as documents are re-versioned. This entire slot is open.

What exists adjacent:
- **Doc2Query-- quality gate** (verified: +16% effectiveness, -33% index size, -23% query time by filtering ungrounded queries) - a groundedness filter that could be RE-RUN as a staleness detector: "can the current source still answer this stored question?" is an entailment check, exactly the filter they run at generation time. Nobody has published using it for revalidation
- **Cache-invalidation framing** (cards a6/a7): a question node is a memoized derivation keyed by (source span hash, prompt version, model version) - verifying traces give the revalidate-before-use recipe; semantic early cutoff (source changed but meaning didn't -> keep questions) is unpublished
- **LightRAG issue #2442** as the cautionary tale: derivation caches keyed without upstream state propagate corrupt/stale derived objects on re-ingest

### Area (f) - Truth Maintenance Systems

**CARD f1: JTMS (Doyle 1979)**
- **Source**: Doyle, "A Truth Maintenance System", Artificial Intelligence 12(3), 1979
- **Mechanism**: every belief carries justifications (sets of supporting beliefs/assumptions); beliefs are labeled IN (has at least one valid justification) or OUT; when a justification's support falls, labels propagate - retraction is automatic and exact; dependency-directed backtracking (Stallman & Sussman 1977) uses the recorded dependencies to backtrack precisely to the responsible assumption
- **Cost profile**: label propagation proportional to the affected justification subgraph; the graph itself is extra storage on every belief
- **Failure modes**: cyclic justifications need care; keeping justifications complete is the burden - an underspecified justification means over- or under-retraction
- **Transfer**: the exact template KGF needs: derived object X carries justification J = {source doc version, entity node(s), description version, generator prompt+model, embedding version}. Entity merge/split, doc re-version, or description rewrite invalidates a member of J -> X's label flips to OUT (retrieval-invisible) pending re-derivation. IN/OUT labeling is precisely "tombstone but keep" - identical in spirit to Zep's edge invalidation, discovered 45 years earlier

**CARD f2: ATMS (de Kleer 1986)**
- **Source**: de Kleer, "An Assumption-based TMS", Artificial Intelligence 28(2), 1986
- **Mechanism**: instead of one current belief state, every belief is labeled with the minimal ASSUMPTION SETS (environments) under which it holds; context switching is free; retraction largely disappears because nothing is ever globally IN - validity is always relative to an environment
- **Failure modes**: label sets can grow exponentially; overkill when only one world-state matters
- **Transfer**: the multi-context view maps to KGF's versioned graph: a derived object labeled with the graph-state interval it is valid for ("valid for entity E as of merge-epoch 12") - the bitemporal generalization of IN/OUT. Practical use: keep derived objects from BEFORE an entity merge alive but scoped, instead of mass-invalidating - answer old-version queries, lazily migrate

**What transfers overall from TMS**: (1) justifications = mandatory provenance schema for every derived object; (2) label propagation = the dirty-flag flood, with the graph as the propagation medium; (3) retraction != deletion - OUT objects are kept for cheap re-IN when support returns (an entity split restoring an old entity can re-validate its old question nodes for free); (4) what does NOT transfer: TMS assumed logical derivations - crisp, cheap to re-check; LLM derivations need a semantic verifier (entailment gate) to decide whether a justification "still holds", and re-derivation is expensive, so label-OUT must decouple from regenerate (invalidate eagerly, regenerate lazily/budgeted)

---

## STEP 3 - PAPERS ARCHIVED THIS SESSION

All downloaded to `references/papers/`, `%PDF` magic bytes verified, digests written in house style:

1. `[paper] EraRAG, 2025-06.pdf` + `[paper digest] EraRAG.md` - localized maintenance of hierarchical derived summaries (arXiv 2506.20963)
2. `[paper] Sleep-time Compute, 2025-04.pdf` + `[paper digest] Sleep-time Compute.md` - offline maintenance economics (arXiv 2504.13171)
3. `[paper] Mem0, 2025-04.pdf` + `[paper digest] Mem0.md` - ADD/UPDATE/DELETE/NOOP consolidation routing (arXiv 2504.19413)
4. `[paper] A-MEM, 2025-02.pdf` + `[paper digest] A-MEM.md` - neighborhood ripple updates of derived metadata (arXiv 2502.12110)
5. `[paper] DBSP incremental view maintenance, 2023.pdf` + `[paper digest] DBSP incremental view maintenance.md` - formal IVM template (arXiv 2203.16684)

Already archived, not re-downloaded: Zep Graphiti, Drift-Adapter, TCR-QF, EvoRAG, LightRAG, Microsoft GraphRAG, RAPTOR, KET-RAG, RPQ views, Evidence Units, Trust but Verify, QuOTE, doc2query, Doc2Query--.

---

## STEP 4 - MAINTENANCE DESIGN SPACE FOR KGF's DERIVED OBJECTS

Cross-cutting frame from the literature: every derived object needs (1) a **justification record** (TMS) = its dependency set with version stamps; (2) an **invalidation channel** (dependency flood / periodic audit / query feedback / outcome decay - not mutually exclusive); (3) a **repair policy** on the eager-lazy-decay-tombstone spectrum, chosen by recompute cost x query-correctness risk; (4) a **verifier gate** before any regenerated object re-enters the index (Doc2Query--, Trust-but-Verify). The consistent published pattern is **invalidate eagerly, regenerate lazily** - cheap label flips at change time, expensive LLM regeneration deferred, batched, or demand-driven.

### Per-object-class matrix

**1. Ingest-generated question nodes (chunk-scoped, QuOTE-style)**
- *Invalidation detection*: verifying-trace check - store (source-span hash, description version, prompt+model version) per question; doc re-version or description rewrite flips the trace. Plus outcome decay (Memory-Worth counters: question retrieved -> answer judged wrong -> worth drops). Entity merge/split reaches these only via their entity links
- *Repair*: invalidate -> OUT-label (retrieval-invisible) immediately; regenerate lazily in idle cycles (sleep-time economics: ~5x cheaper offline); re-admit only through an entailment gate ("can current source answer this question") - the Doc2Query-- filter reused as revalidator
- *Cost model*: generation ~16x base indexing (QuOTE), so eager per-edit regen is unaffordable at scale; entailment revalidation is ~10-100x cheaper than regeneration and can rescue questions that survived the edit (semantic early cutoff)
- *Open slots (novel for KGF)*: (i) the entailment-check-as-revalidator - nobody has published revalidating stored generated questions against edited sources; (ii) semantic early cutoff thresholds (how different must a description be before its questions die?); (iii) outcome-linked question worth wired to a benchmark judge

**2. Entity-scoped cross-document questions**
- *Invalidation detection*: justification = the SET of entity + participating doc versions -> strictly more fragile than chunk questions; entity merge/split is the primary killer. DRed shape: on merge, over-invalidate both entities' question sets, re-validate cheaply against the merged node, regenerate the true losses
- *Repair*: ATMS-style scoping beats mass deletion - label questions with merge-epoch validity so pre-merge questions stay answerable during lazy migration; support counts (a1) decide survival when one of several supporting docs is deleted
- *Cost model*: highest regeneration cost per object (multi-doc LLM context); mitigate with KET-RAG-style budgeting - eager maintenance only for hub entities (PageRank core), lazy elsewhere
- *Open slots*: cross-document question migration under entity merge is completely unpublished; so is the epoch-scoped validity label on generated retrieval objects

**3. Passage-node embeddings**
- *Invalidation detection*: trivial dirty bit on content hash (content edits) and on embedding_version registry (model swaps). The solved class
- *Repair*: content edit -> eager re-embed (cheap, deterministic); model swap -> Drift-Adapter (95-99% recall retained, ~200x cheaper, verified) with deferred blue-green re-embed; NEVER mix spaces in one index (industry consensus)
- *Cost model*: re-embedding is cents/GB vs LLM regeneration at dollars/GB - embeddings should be the EAGEREST tier
- *Open slots*: only the interaction: when question-node text regenerates, its embedding must follow - a second-order dependency (derived-of-derived) no published system tracks explicitly

**4. Hoisted / mirrored spec properties**
- *Invalidation detection*: these are classic materialized views - the ONE class where database theory applies almost verbatim. Delta rules from source triple to mirrored property; support counts for multiply-witnessed values; self-maintainability test: store source-triple id + doc version on the mirror so staleness is decidable without re-reading documents
- *Repair*: immediate/eager - the recompute is a graph copy, not an LLM call, and a stale spec value feeding an answer is a correctness bug, not a ranking degradation. Conflicting sources -> Zep-style bitemporal versioning of the property value rather than overwrite
- *Cost model*: near-free maintenance; the only cost is the discipline of writing the delta rules
- *Open slots*: none theoretical - the novelty is only in implementation (Cypher delta triggers / ingest-pipeline hooks). Do not spend hypothesis budget on mechanism here; spend it on conflict policy

**5. Synonym-edge expansions**
- *Invalidation detection*: justification = the resolver decision (posterior, evidence) that created the edge; entity merge/split and description rewrites re-open the decision. Similarity-triggered review (Mem0 pattern): new evidence near either endpoint queues the edge for re-scoring. Periodic audit: persistent-homology Betti curves (Knowledge Persistence, 18h->27s) as the cheap global over-merge alarm
- *Repair*: append-and-invalidate, never delete - an invalidated synonym edge is negative knowledge that prevents re-derivation of the same false merge (the gap-ledger principle applied to identity). Incremental-record-linkage vocabulary (merge/split/move) with its known drift caveat: local greedy repairs accumulate error -> scheduled batch re-resolution as backstop
- *Cost model*: re-scoring an edge = one resolver call (cheap-ish); the expensive part is transitive fallout (edges feed question scoping, hoisted props) -> synonym edges sit UPSTREAM in the dependency DAG and must propagate dirty flags downstream
- *Open slots*: dependency-DAG propagation from identity decisions to generated retrieval objects is unpublished; so is using invalidated edges as blocking negative evidence in the resolver prior

**6. Gap ledger (unanswerable questions)**
- *Invalidation detection*: inverted polarity - a gap goes stale when it becomes ANSWERABLE. Triggers: new ingest touching the gap's entity/topic neighborhood (A-MEM ripple, inverted); periodic re-probe of open gaps against the current graph (TCR-QF/EvoRAG loop run in reverse - verified TCR-QF gains: 29.1% EM / 15.5% F1 over GraphRAG baselines, IJCAI 2025)
- *Repair*: on closure, invalidate-don't-delete (Zep): the record "this was unanswerable from doc-set X until event Y" is abstention-calibration signal and audit trail; open gaps get outcome-linked worth (are they still being asked?) with decay for gaps nobody hits
- *Cost model*: re-probing is one retrieval + one judge call per gap per cycle - bounded, batchable, ideal sleep-time work with measured 2.5x amortization economics
- *Open slots*: a gap ledger as a first-class maintained derived object appears NOWHERE in the literature (completeness/negation work - UnCommonSense, completeness-recall line - is static). Gap-closure-on-ingest as a maintenance trigger is fully novel territory

**7. Community summaries (existing KGF layer, for completeness)**
- *Invalidation detection*: threshold on community-membership churn (GraphRAG update's escalation pattern); Graphiti label propagation keeps assignments incremental
- *Repair*: three-tier - patch summary (append new-entity sentence) -> re-summarize affected community and ancestors only (EraRAG's verified locality: up to 77.5% rebuild-time and 57.6% token savings) -> scheduled full re-cluster to cap drift (GraphRAG's honest fallback)
- *Open slots*: EraRAG achieves locality by replacing the clusterer with frozen LSH; whether Leiden-based communities can get comparable locality guarantees without that replacement is open

### The five open slots where KGF hypotheses would be novel

1. **Revalidation-not-regeneration for generated questions** - entailment gate as a staleness detector over stored question nodes (Doc2Query--'s filter, repurposed); semantic early cutoff for LLM-derived text. Nothing published
2. **Justification-carrying derived objects in a KG-RAG index** - TMS-style provenance records + label propagation over a Neo4j dependency DAG spanning identity decisions -> derived retrieval objects. Zep does it for facts only; nobody does it for generated retrieval objects
3. **Entity-merge/split fallout management** - DRed-shaped over-invalidate-then-revalidate for entity-scoped questions, with epoch-scoped (ATMS-style) validity labels. Unpublished
4. **Outcome-linked worth for derived objects** - Memory-Worth two-counter scoring (rho=0.89 vs 0.00 for static importance) attached to question nodes/synonym edges, wired to the answer judge. Published for agent memories, never for retrieval index objects
5. **Gap ledger lifecycle** - answerability re-probing as sleep-time maintenance and gap-closure events as ingest-quality signal. Fully open

Verified-number ledger: all quantitative claims above are tagged inline; the items carrying UNVERIFIED flags are BCT's per-benchmark deltas, DBSP engine speedups, GraphRAG cache-savings percentage, iText2KG/ATOM maintenance costs, Query Drift Compensation numbers, and all industry re-embedding guidance. Everything else was verified against the cited paper or its arXiv abstract/HTML this session.

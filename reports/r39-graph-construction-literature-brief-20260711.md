# R39 literature brief - graph construction: dense+sparse node classes, passages as first-class citizens, coverage guarantees

Prepared 2026-07-11 for the R39 hypothesis fanout. Strategic direction (user): KGF must first build a SOTA graph that is trustworthy and does not miss information - dense and sparse node classes, specific passages as first-class graph citizens, per HippoRAG's published science. The retriever bridge comes later; this brief is about the graph substrate. Sources: local paper library (`references/papers/`) plus 6 papers downloaded for this brief (SiReRAG, KGGen, PropRAG, EDC, GraphJudge, ODKE+).

## 1. HippoRAG 1/2 graph-construction anatomy - exact numbers

HippoRAG builds a schema-free open KG per corpus and retrieves with Personalized PageRank; HippoRAG 2 adds passages into the same graph. All numbers from the archived PDFs (`[paper] HippoRAG, 2024-05.pdf`, `[paper] HippoRAG 2, 2025-02.pdf`).

### Node and edge classes

- **Phrase nodes** (H1 Section 2.3) - noun phrases from two-step OpenIE (1-shot NER first, then triples with the NER list injected; "appropriate balance between generality and bias towards named entities"). Schema-free: no types, no ontology
- **Relation edges** (H1) - the extracted triples' predicates, unconstrained vocabulary
- **Synonym edges E'** (H1 Section 2.3) - added between phrase pairs whose retrieval-encoder cosine similarity > threshold **τ = 0.8** (tuned on 100 MuSiQue training examples; H1 Section 3.4). Same threshold retained in H2 (H2 Appendix: Synonym Threshold 0.8)
- **Passage nodes** (H2 Section 3.2) - every corpus passage becomes a node; H1 had passages OUTSIDE the graph, scored via an |N|x|P| phrase-passage count matrix multiplied by the PPR distribution
- **Context edges** (H2 Section 3.2) - labeled "contains", connecting each passage node to ALL phrase nodes derived from it

### Scale of each class (MuSiQue corpus, 11,656 passages)

| Object | H1 (GPT-3.5) | H2 (Llama-3.3-70B) |
|---|---|---|
| Phrase nodes | 91,729 | 85,288 |
| Passage nodes | 0 (external matrix) | 11,656 |
| Relation (extracted) edges | 21,714 unique (107,448 triples) | 140,830 |
| Synonym edges | 145,990 (Contriever) / 191,636 (ColBERTv2) | ~1.26M (total edges 1,399,367 minus extracted; includes context edges) |

The load-bearing structural fact: **synonym edges outnumber relation edges 7-9x in H1 and dominate H2's edge mass**. The associative substrate is mostly the embedding-derived alias layer, not the extracted triples. (H1 Table 1; H2 Table 10.)

### Dense vs sparse - what it means operationally (H2 Section 3.2)

- **Sparse coding = phrase nodes**: compact concept symbols, "concise and easily generalizable but often entail information loss"
- **Dense coding = passage nodes**: the full context embedded with the same encoder as phrases
- Integration is IN THE GRAPH, not score fusion: H1 ensembled graph scores with dense-retrieval scores; H2 explicitly replaces that with passage nodes + context edges so PPR propagates across both classes in one walk
- **Asymmetric reset weights** (H2 Sections 3.5, 6.2): phrase seed nodes get reset probability from their ranking scores (weight 1.0); ALL passage nodes are also seeded, proportional to query-embedding similarity times factor **0.05** (sweep 0.01/0.05/0.1/0.3/0.5 → MuSiQue R@5 79.9/80.5/79.8/78.4/77.9 - H2 Table 5). Propagation is biased ~20:1 toward conceptual structure; passages surface through it

### Retrieval-side mechanisms that shape construction

- **Query-to-triple linking** (H2 Section 3.3) - query embedded against TRIPLES, not phrases: +12.5 avg R@5 over NER-to-node (87.1 vs 74.6; +20.9 on MuSiQue) - H2 Table 4. Requires triples to exist as embeddable objects
- **Recognition-memory filter** (H2 Section 3.4) - LLM filters top-k retrieved triples to <= 4 facts per query (prompt in H2 Appendix A); worth only +0.7 (87.1 vs 86.4 w/o filter, H2 Table 4) and per R34's research pass it is the paper's worst failure surface (26% of failure samples lose all supporting phrases to it). NOT registered in KGF - stands
- **Node specificity** (H1 Section 2.3) - s_i = |P_i|^-1 (inverse passage count) multiplies each SEED node's reset probability before PPR; a soft prior, not a rank multiplier: +2.0 avg, +4.0 HotpotQA (H1 Table 5)
- **PPR** - damping 0.5 (H1 Section 3.4); removing PPR costs -13.7 to -16.7 avg R@5 (H1 Table 5); removing passage nodes costs -6.1 avg / -11.0 MuSiQue (H2 Table 4); removing synonym edges -2.4 avg (H1 Table 5)
- Headline: H1 multi-hop evidence recall 87.9-90.9% vs 59.8-64.5% single-step dense RAG; H2 MuSiQue R@5 74.7, F1 48.6 vs H1's 35.1; H2 beats NV-Embed-v2 (strongest dense retriever) by +5.0 MuSiQue / +13.9 2Wiki R@5

## 2. KGF-has vs KGF-lacks vs HippoRAG-has

| Construction element | HippoRAG 1/2 | KGF today | Gap class |
|---|---|---|---|
| Concept (sparse) nodes | untyped noun phrases, schema-free | typed Entity nodes under cured ontology (26 types), Bayesian-merged | KGF stronger discipline, unknown recall cost (see slot S4) |
| Passage (dense) nodes | full passages as graph nodes, PPR citizens | `(:KGFPassage)` 900-char spans, bge-m3 1024-dim, engine-wired (H366) - but a PARALLEL VECTOR POOL, no edges to entities, rendered top-1 under escalation only | passages are index citizens, not graph citizens |
| Concept-passage linkage | "contains" context edges passage→every derived phrase | 2-hop indirect only: span-[PART_OF]→Chunk←[MENTIONED_IN]-Entity (`passages.py:127`); no direct entity↔span edge | direct traversal path missing |
| Synonym/alias layer | cosine > 0.8 edges, 7-9x relation-edge mass, PPR substrate | hard merges (Bayesian posterior) + SIMILAR_TO soft edges from 3 creators - zero consumers, render access refuted (R34-H370) | KGF collapses synonyms; HippoRAG traverses them |
| Triples as embeddable objects | yes - query-to-triple linking (+12.5) | deterministic propositions, faithful by construction, embedded, seeding confirmed (R34-H367) | parity, KGF form is trust-superior (no paraphrase) |
| Node specificity prior | s_i = \|P_i\|^-1 soft reset scaling (+2.0) | none; hard rerank transplant refuted (R34-H369); soft form only lives inside PPR | dormant pending H368 |
| Unified graph walk | PPR over phrases+passages, weights 1.0/0.05 | PPR implemented, `ppr_enabled=False` (H37: 0.994 seed+1hop containment at 28 docs); re-ablation gated on benchmark scale (R34-H368) | scale-gated |
| Extraction verification | none (open IE, unjudged) | none (extraction enters graph unjudged; fidelity probed downstream) | BOTH lack admission-time trust - see slot S1/S5 |
| Coverage accounting | none - never measures what extraction missed | none - gap ledger doctrine exists, no extraction-side instrument | open in the entire literature - slot S1-S3 |
| Provenance | none per-edge | source_documents/source_chunks on entities/rels, bitemporal fields | KGF strictly ahead |
| Incremental growth | continual-learning experiment only (H2 Fig 3) | FSM-managed ingest, cure-at-doc-4, calibration state (R38) | KGF ahead; R36 maintenance gaps noted |

## 3. What R34 already adjudicated - the fence

R34 (registered 2026-07-10) transferred HippoRAG's retrieval-side levers onto the live graph and is settled: **H366 CONFIRMED** - query-anchored 900-char spans in a local bge-m3 pool flip P21/P22 at +9.5% context (whole-chunk render and head-truncation both rejected), engine-wired as `graph/passages.py` with `(:KGFIndexSpace)` space pinning; **H367 CONFIRMED** - proposition-hit ABOUT entities join the render seed set (arm D proved fact sentences alone carry nothing, the entities' blocks carry everything), routing landed; **H369 REFUTED** - specificity as a hard seed-rerank craters (0.8958 → 0.4792; the soft PPR-prior form survives only inside H368); **H370 REFUTED** - SIMILAR_TO one-hop expansion is flat and the needed parent-tier bridge edges do not exist (creator gap, not consumer gap); **H368 OPEN, GATED** - PPR re-ablation waits for the benchmark-scale corpus (+3 R@5 at <= 1.5x latency to promote); the recognition-memory filter was explicitly not registered (+0.7 peer, worst failure profile). Composed frontier: 0.9583 / 23-of-24 at +27.8% context. R39 must NOT re-propose: passage rendering, proposition seeding, seed-side specificity, SIMILAR_TO render access, or LLM seed filtering. Also fenced: R35 owns question objects and the question-driven gap ledger (H371-H373), multi-channel voting (H374), SDR identity signatures (H375); R36 owns derived-object invalidation; R37 owns escalation (H382); R38 owns calibration certificates (H383-H388).

## 4. Proven-novel open slots - graph-construction levers nobody has published

Verified against the local library (~80 papers incl. GraphRAG survey, NodeRAG, KET-RAG, LeanRAG, autoschemakg, Zep/Graphiti, completeness-prediction lineage) and this brief's 6 downloads. "Does not miss information" is the emptiest quadrant in the field:

- **S1 - Ingest-time extraction-coverage measurement.** KGGen's MINE benchmark proves ALL published extractors drop facts (KGGen 66.07%, GraphRAG 47.80%, OpenIE 29.84% retention - KGGen Section 5.1) but MINE is an offline benchmark; NO system measures its own per-document fact coverage AT INGEST and treats it as a gate. The completeness lineage (Predicting Completeness in KBs 2017; Completeness/Recall/Negation survey 2023, both archived) models KB-level cardinalities, never extraction recall against a held source. Open
- **S2 - Multi-pass extraction-union economics.** Extraction variance is documented (H107: 71% of KGF identity variance; KGGen's retention ceiling) but nobody publishes coverage-vs-passes curves: marginal new-fact yield of unioning k independent extraction passes, dedup burden, cost frontier. The nearest published thing is EDC's single refinement iteration (EDC+R, Section: refinement improves all benches) - which targets QUALITY, not coverage. Open
- **S3 - Closed-loop coverage repair.** ODKE+ is the only production system whose entry point is a completeness signal (Extraction Initiator detects missing/stale facts → 19M facts at 98.8% precision, +48% third-party-KG overlap - ODKE+ abstract) but it targets KNOWN-schema gaps across a corpus; no system iterates extract → audit-against-source → targeted re-extract on a fresh document until coverage is certified. Open
- **S4 - Typed-ontology dense/sparse integration.** HippoRAG's sparse layer is schema-free noun phrases; every published passage+concept unified graph (HippoRAG 2, SiReRAG, PropRAG) is untyped. Whether a CURED TYPED ontology strengthens (cleaner concept layer) or weakens (recall lost to type constraints; synonym traversal made redundant by merges) the duality is unmeasured. EDC (open-extract → canonicalize into schema, handles thousands of relation types via trained Schema Retriever) is the counter-ordering to KGF's cure-then-constrain, and nobody has measured the recall delta between the two orderings. Open
- **S5 - Admission-gate precision/coverage frontier.** GraphJudge fine-tunes a 7B judge to > 90% per-triple accuracy and gates admission (GraphJudge Sections 3-4); ODKE+'s Grounder validates per-fact against evidence. Both DROP rejections silently - a judge false-rejection IS missed information, and nobody accounts for it. A verification gate whose rejections enter a recoverable ledger, priced against coverage, is unpublished. Open
- Anti-slot (checked and closed): proposition-primary graphs are NOT novel - PropRAG already ships propositions as implicit hyper-edges with beam-search paths (MuSiQue R@5 77.3 > HippoRAG 2's 74.7 - PropRAG abstract). KGF's deterministic faithful-by-construction propositions remain a trust differentiator, not a structural novelty

## 5. Hypothesis candidates for the R39 fanout

Numbering continues from H388. Naive baseline for the round: the post-R34 live graph + composed frontier (0.9583 / 23-of-24); coverage hypotheses additionally define their own instrument-first baselines.

### H389 (conformist) - extraction-coverage certificate: the graph measures what it missed

- **Mechanism** - per-document ingest audit: sample verbatim-grounded fact probes from each chunk (LLM generation, groundedness-gated), test graph support (entity/prop/span match + subgraph entailment), emit per-doc coverage score + miss list into the gap ledger
- **Grounding** - KGGen MINE protocol (15 facts/article, top-k node similarity + LLM adjudication; retention 29.8-66.1% across extractors - KGGen Section 5.1); ODKE+ Grounder as the per-fact check pattern
- **Prediction** - KGF's per-chunk fact coverage on the 10-doc corpus measures BELOW 90% (the literature ceiling says it must); the P08 '9.0W' parse loss surfaces in the miss list blind
- **Bar sketch** - the audit rediscovers >= 2 known failure classes without being told them; coverage score reproducible +-2% across re-runs; audit cost <= 25% of ingest cost. Fence: R35-H373 audits ANSWERABILITY via questions - H389 audits EXTRACTION RECALL via facts; if H373's ledger already surfaces the same misses, record subsumption honestly
- **Composes with** - gap ledger doctrine, provenance fields, H373's generation machinery (shared generator, different gate)

### H390 (conformist) - multi-pass extraction union: coverage-vs-passes curve

- **Mechanism** - k independent extraction passes per chunk (temperature/prompt-perm variation), triples unioned through the existing Bayesian resolver; measure marginal unique-fact yield per pass with H389 as the instrument
- **Grounding** - KGGen retention ceiling (Section 5.1); H107 extraction variance 71% (variance implies non-overlapping pass yields); EDC+R's refinement iteration improving extraction on all benches (EDC Section 5)
- **Prediction** - pass 2 adds >= 8% new true facts; marginal yield decays geometrically (pass 3 < half of pass 2); H389 coverage rises accordingly
- **Bar sketch** - coverage gain per dollar beats the alternative spend (single pass with a larger model, measured head-to-head); identity metrics do not regress (the resolver absorbs pass variance); REFUTED if pass-2 yield < 3% (single-pass extraction is already near its ceiling and S2 closes)
- **Composes with** - H389 instrument, Bayesian cross-type dedup, extraction concurrency tuning (c64/t3600 memory)

### H391 (conformist) - passages become graph citizens: context edges entity→span

- **Mechanism** - materialize HippoRAG-2's "contains" linkage: direct edges between `(:KGFPassage)` spans and the entities extracted from their carrier chunk, making the confirmed passage channel a walk citizen instead of pool-only (today the only path is 2-hop via Chunk, which a PPR walk dilutes through the chunk hub)
- **Grounding** - HippoRAG 2 Section 3.2 (passage nodes + context edges; removing passage nodes -6.1 avg R@5, Table 4; reset weights 1.0/0.05, Table 5); KGF spans reachable by vector query or via span-[PART_OF]→Chunk only (`graph/passages.py:127`)
- **Prediction** - inert on the CPAP graph's 1-hop render (H37 containment) but REQUIRED substrate for H368: at benchmark scale, PPR over the unified entity+span graph beats entity-only PPR on passage recall
- **Bar sketch** - edge build idempotent, zero live-harness regressions, storage growth priced; the recall claim rides H368's registered gate (+3 R@5 at <= 1.5x latency) - H391 ships the substrate, H368 adjudicates it; REFUTED as construction if H368 promotes equally well without context edges (seed-side passage entry suffices)
- **Composes with** - passages.py, H368, GDS PPR, `(:KGFIndexSpace)` discipline

### H392 (conformist) - open-extraction shadow pass: measure what the 26-type ontology drops

- **Mechanism** - schema-free OpenIE pass (HippoRAG-style two-step prompt) on a document sample alongside the production constrained pass; diff the fact sets through H389's support test; quantify typed-extraction leakage
- **Grounding** - EDC's thesis that open-extract-then-canonicalize handles unbounded schema without recall loss (EDC Sections 1, 4; Schema Retriever over thousands of relation types); HippoRAG's schema-free layer as the recall-first extreme (H1 Section 2.3)
- **Prediction** - the open pass yields >= 10% facts with no typed-graph support, concentrated in relation vocabulary outside the cured ontology
- **Bar sketch** - decision rule pre-registered: leakage >= 10% → an EDC-style canonicalize-into-ontology stage enters the R40 design; leakage < 3% → cure-then-constrain is vindicated and S4's recall half closes; between → classify the leaked facts and re-fan. Either outcome is informative; REFUTED only if the diff instrument itself is unreliable (< 80% adjudication agreement on a hand-checked sample)
- **Composes with** - H389 instrument, ontology curing pipeline, FSM CURING state

### H393 (contrarian) - the dense/sparse duality does NOT transfer to a typed-merged graph

- **Mechanism** - claim: HippoRAG's synonym-edge mass (7-9x relation edges) and context-edge substrate are COMPENSATION for having no entity resolution and no typing; KGF's Bayesian merges already collapse the synonym clusters, so importing the remaining substrate (H391 context edges + synonym traversal + soft specificity) adds < 1 point over the confirmed H366+H367 composition
- **Grounding** - H1 Table 5: synonymy edges worth only +2.4 avg WITH no entity resolution present; R34-H370: SIMILAR_TO traversal flat on the merged graph, needed bridges absent; v19 Bayesian dedup collapses exactly the cosine-0.8 pair class that HippoRAG bridges with edges
- **Prediction** - benchmark-scale A/B (merged-typed graph vs same graph + HippoRAG-style synonym edges at 0.8): delta < 1 point passage R@5; corollary: HippoRAG's own ablation ordering (synonymy weakest graph lever) inverts under merging - the edges become pure redundancy
- **Bar sketch** - runs on the H368 benchmark harness; CONTRARIAN CONFIRMED if delta < 1 point (synonym layer permanently retired, construction budget freed); REFUTED if >= 2 points, in which case the alias layer earns first-class status and H370's creator-gap finding (kNN misses parent-tier fragments) defines its build spec
- **Composes with** - H368 harness, Bayesian resolver, H370's creator-gap post-mortem

### H394 (heretical) - coverage-gated ingest: the document is not "ingested" until the graph proves it missed nothing

- **Mechanism** - close the loop nobody closes: H389's miss list drives TARGETED re-extraction (prompt carries the missed fact's source span and the miss statement), iterate extract → audit → re-extract until per-doc coverage >= threshold or marginal yield < epsilon; terminal misses are CERTIFIED (named, spanned, ledgered) rather than silent - ingestion returns a coverage certificate, not a hope
- **Grounding** - ODKE+ Extraction Initiator (gap-driven extraction in production, 19M facts / 98.8% precision, update lag -50 days) proves gap-targeting works at scale but only for known-schema staleness, never intra-document extraction recall; KGGen proves the untargeted ceiling is ~66%
- **Prediction** - 2-3 targeted iterations lift per-doc coverage to >= 97% at <= 1.8x single-pass extraction cost; targeted passes recover misses that BLIND multi-pass union (H390) cannot (the point of aiming); P08-class losses either recovered or certified-unrecoverable at the parser level
- **Bar sketch** - coverage lift per unit cost beats H390's blind union at equal spend; zero fidelity regressions on a judged sample of recovered facts; certified-miss list human-verified once (>= 80% are real source facts). GATED on H389 confirming its instrument
- **Composes with** - H389 + H390, gap ledger, FSM (a RECURING-adjacent state that R36 noted is currently dead code), R38 certificate vocabulary

### H395 (follower) - verified admission with a rejection ledger: precision that cannot silently cost coverage

- **Mechanism** - per-triple admission check (judge/grounder verifies each extracted triple against its source span before graph commit) where rejections are NOT dropped: they persist as quarantined ledger objects with provenance, recoverable and auditable - the S5 frontier instrumented from both sides
- **Grounding** - GraphJudge: fine-tuned 7B judge > 90% triple-judgement accuracy, F1-SOTA on REBEL/GenWiki by beating higher-recall unverified rivals; ODKE+ Grounder: second-LLM validation at 98.8% ingest precision; neither accounts for false rejections
- **Prediction** - on seeded synthetic corruptions the gate catches >= 80% while rejecting <= 2% of true triples; some rejected-true triples correspond to known fidelity classes (model_code SAME_AS false-merge surface, spec-conflict fires) - the quarantine becomes the H101-adjudication queue
- **Bar sketch** - corruption-catch and true-rejection rates measured on a labeled sample; end-to-end recall unchanged (quarantine, never drop); per-triple verification cost <= 15% of extraction cost (small local judge, idle-card economics per H363 pattern); REFUTED if judge accuracy on KGF's technical corpus < 75% (domain transfer fails)
- **Composes with** - fidelity probes, demotion court, gap ledger, local-model serving (my-gpu recipes)

## 6. Source register

Downloaded for this brief (all PDF-verified, digests beside them in `references/papers/`):

1. `[paper] SiReRAG, 2024-12.pdf` - similarity+relatedness dual-tree unified pool, +1.9% avg F1 (arXiv 2412.06206, ICLR 2025)
2. `[paper] KGGen, 2025-02.pdf` - MINE retention benchmark: 66.07/47.80/29.84% (arXiv 2502.09956)
3. `[paper] PropRAG, 2025-04.pdf` - propositions as hyper-edges, LLM-free beam search, MuSiQue R@5 77.3 (arXiv 2504.18070, EMNLP 2025)
4. `[paper] EDC Extract-Define-Canonicalize, 2024-04.pdf` - open extraction → schema canonicalization, trained Schema Retriever (arXiv 2404.03868, EMNLP 2024)
5. `[paper] GraphJudge, 2024-11.pdf` - fine-tuned 7B per-triple judge > 90% accuracy (arXiv 2411.17388)
6. `[paper] ODKE+, 2025-09.pdf` - gap-driven production extraction, 19M facts / 98.8% precision (arXiv 2509.04696)

Load-bearing pre-existing library: `[paper] HippoRAG, 2024-05.pdf` (τ=0.8, damping 0.5, s_i=|P_i|^-1, Tables 1/5), `[paper] HippoRAG 2, 2025-02.pdf` (Tables 4/5/10, Sections 3.2-3.5), completeness lineage (Predicting Completeness 2017, Completeness/Recall/Negation 2023), Dense X Retrieval, NodeRAG, KET-RAG, Microsoft GraphRAG. Internal: `docs/experiments/kgf-redesign-experiments.md` R34 (H366-H370) and fences R35-R38; `src/knowledge_graph_foundry/graph/passages.py`, `graph/propositions.py`.

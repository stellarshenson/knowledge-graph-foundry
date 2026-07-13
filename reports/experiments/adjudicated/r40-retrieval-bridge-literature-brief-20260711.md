# R40 literature brief - the retrieval bridge: single-shot query token economics over the trustworthy graph

Prepared 2026-07-11 for the R40 hypothesis fanout (registration pending R39 substrate). Governing constraint (user, authoritative): the bridge's design goal is QUERY TOKEN ECONOMICS - the best possible retrieval in ONE go, single round trip, with multi-hop/multi-round retrieval as a RARE calibrated exception, never the default. This is the standing retrieval-first doctrine (perfect context in 1-2 hops; work shifts to ingest time) elevated to the bridge's primary axis. Consequence: agentic multi-step walks (ToG/Graph-CoT class) are the ADVERSARY BASELINE reported with their token bills, not the design. Sources: local paper library plus 5 papers downloaded for this brief (ToG, Graph-CoT, IRCoT, CRAG, Plan-on-Graph); Self-RAG, Adaptive-RAG, FLARE, ToG-2, GNN-RAG, SubgraphRAG were already archived.

## 1. The decisive cost comparison - single-shot multi-hop vs iterative retrieval

HippoRAG 1 Appendix G Table 17 is the anchor: online retrieval over **1,000 queries** with GPT-3.5-Turbo - ColBERTv2 \\$0 / 1 min, **IRCoT \\$1-3 / 20-40 min, HippoRAG \\$0.1 / 3 min**. Single-step PPR retrieval is **10-30x cheaper and 6-13x faster** than 2-4-round IRCoT at comparable or better recall (HippoRAG on-par-or-better single-step; MuSiQue F1 19.2/29.8 EM/F1 vs IRCoT 19.1/30.5, 2Wiki 46.6/59.5 vs 35.4/45.1). The mechanism of the saving: the multi-hop work is materialized at ingest (KG + synonym edges + PPR), so query time needs only query-side entity extraction + one graph walk-free PPR pass - "single-step multi-hop". IRCoT's recall gap over one-step dense retrieval is real (+11.3 to +22.6 R points, GPT-3) - HippoRAG closes most of it without the rounds. This is the published proof that the user's constraint is achievable, and the bar every bridge candidate is priced against.

## 2. Anatomy of published query→graph bridges - exact numbers with token bills

### Single-shot pole (the design lineage)

- **HippoRAG 2 retrieval side** (`[paper digest] HippoRAG 2.md`) - query embedded against TRIPLES not phrases (+12.5 avg R@5, +20.9 MuSiQue - Table 4); recognition-memory LLM filter on candidate triples (+0.7 only, worst failure surface - 26% of failure samples lose all supporting phrases; NOT registered in KGF, stands); one PPR pass over phrase+passage graph, reset weights 1.0 phrase / 0.05 passage (Table 5 sweep); MuSiQue R@5 74.7, F1 48.6. Query-time LLM cost: 1 NER/linking call + optional 1 filter call + 1 answer call
- **SubgraphRAG** (archived) - learned MLP + triple scorer selects a subgraph in ONE forward pass, zero LLM calls in retrieval, WebQSP F1 78.2 w/ GPT-4o - single-shot structured retrieval over a curated KG; needs training data KGF lacks
- **GNN-RAG** (archived) - zero LLM retrieval calls, verbalized shortest paths, WebQSP Hit 90.7 vs GPT-4 ToG 82.6 at ~9x fewer KG tokens (median 144-281 input tokens) - the extreme cheap pole; needs thousands of QA training examples

### Agentic walk pole (the adversary baseline - with bills)

- **ToG** (ICLR 2024, downloaded) - LLM beam search on Freebase/Wikidata, N=D=3 → **2ND+D+1 = 22 LLM calls/question**; CWQ 69.5 / WebQSP 82.6 / GrailQA 81.4 (GPT-4), SOTA 6 of 9 training-free. Cheap pruners (BM25/SBERT, D+1 calls) cost -8.4/-15.1 points - no cheap variant keeps the accuracy. Depth plateaus at 3
- **Plan-on-Graph** (NeurIPS 2024, downloaded) - best-tuned walk: guidance + memory + reflection/backtracking; CWQ 75.0 / WebQSP 87.3 / GrailQA 84.7 (GPT-4). Published bill (GPT-3.5, per question): **CWQ 13.3 LLM calls / 8,156 tokens / 23.3 s (vs ToG 22.6 / 9,669 / 96.5 s)**; WebQSP 9.0 calls / 5,518 tokens; GrailQA 6.5 / 3,576. The OPTIMIZED walk still burns ~8k tokens and ~13 calls where a single-shot pipe spends 2 calls
- **Graph-CoT** (ACL-F 2024, downloaded) - 4-function graph API (RetrieveNode/NodeFeature/NeighborCheck/NodeDegree) driven in-context; GRBench (1,740 q / 10 graphs) avg GPT4score 36.29 vs 23.09 one-shot 1-hop subgraph RAG. Structural findings: 2-hop subgraph render scores WORSE than 1-hop (22.12 vs 23.09 - lost in the middle); zero-shot (no demos) collapses to ~0; hard questions 2.5-15 vs easy 53-80 - the walk does not rescue compositional reasoning
- **ToG-2** (archived) - alternating graph+text walk, SOTA 6 of 7 w/ GPT-3.5, +5.51% HotpotQA; bill **~5.4 API calls / 27.3 s per query vs 1 call / 10.2 s naive RAG**

### Adaptive / corrective pole (the calibrated-exception lineage - already fenced to R37/R38)

- **Self-RAG** (archived) - trained reflection tokens decide retrieve/critique per segment; on-demand beats always-retrieve AND never-retrieve - trained-model evidence for escalation-only-where-needed
- **Adaptive-RAG** (archived) - T5-large router picks no/single/iterative retrieval per query from outcome-harvested labels; matches always-iterative F1 (~51 vs ~50) at far lower latency
- **FLARE** (archived) - token-probability threshold triggers mid-generation re-retrieval; free untrained sufficiency signal; each trigger costs a regeneration pass
- **CRAG** (downloaded) - T5-large evaluator grades retrieved docs → Correct/Incorrect/Ambiguous; on Incorrect DISCARDS the corpus result, rewrites the query, and web-searches instead - the route-to-source precedent; PopQA 59.8 vs 52.8 RAG, PubHealth 75.6 vs 39.0. Critically: the evaluator judges retrieved documents only - it GUESSES corpus insufficiency from bad retrievals, it never reads a corpus-side coverage record

### Iterative text pole (the cost-honesty baseline)

- **IRCoT** (ACL 2023, downloaded) - CoT sentence becomes next BM25 query, 2-4 rounds, top-10 passages/step; retrieval +11.3 to +22.6 R points, QA +7.1 to +13.2 F1 over one-step (GPT-3); halves CoT factual errors. Its bill is the Table 17 numbers above - the gap it exposes is what ingest-time materialization must close

## 3. KGF-has vs bridge-needs

Current pipe (`src/knowledge_graph_foundry/pipeline.py` `query()` 1055-1173, `_retrieve_local` 1175-1299): 1 embedding call → vector top-k seeds (overfetch 4x→16) → miss gate (R19-H181 similarity threshold → cheap abstention) → escalation gate (R37-H382, threshold from R38 two-tier loader) → proposition hits as fact lines + seeds → entity render with currently-valid relations, budget-truncated → rung-1 proposition-seeded entities under escalation → 1 LLM answer call with citation discipline → `query.answered` event (R38-H385 label loop). Comparison decomposition only (R03-H15). PPR implemented, disabled (H368 gated). Baseline bill: **2 LLM-class calls per query** (1 embed + 1 answer), rung-2 span append pending tranche #70.

| Surface | KGF today | Bridge needs (negotiation surface) | Published precedent |
|---|---|---|---|
| Entry contract | `query(question) → {answer, supporting_entities, path}` - answer-only, CLI-shaped | structured one-response contract: context + provenance + confidence + coverage verdict + cost, caller decides what to do with it | Graph-CoT's 4-function API is the ANTI-pattern (multi-round conversation); SubgraphRAG's one-pass subgraph is the shape |
| Round-trip count | 1 internally, but the LLM caller gets prose only - a querying AI wanting evidence must re-ask | everything in one response; second round exists only as the calibrated exception | HippoRAG Table 17 (single-step 10-30x cheaper) |
| Sufficiency signalling | internal only (miss gate, escalation gate, abstention score) - swallowed before the caller sees them | calibrated confidence + coverage metadata EXPOSED so the caller can negotiate (accept / request escalation / go elsewhere) | Self-RAG reflection tokens made controllable; CRAG 3-band trigger |
| Negative answers | R19-H181 miss text: "No confident match. Nearest entities: ..." - similarity-based guess | certified negative: "not in corpus" backed by the ingest-time coverage certificate + miss ledger, zero extra rounds | NONE - open slot S1 below |
| Compositional queries | comparisons only (`decompose_comparison`) | general sub-objective decomposition as ONE upfront call, k batched vector lookups, one unioned render, one answer call | PoG guidance ablation (+3.1 as one call); IRCoT gap defines the prize |
| Multi-hop reach | seeds + 1-hop render (H37: 0.994 containment at 28 docs); PPR gated on scale (H368) | ingest-materialized reach (R39 substrate: context edges, passage citizens) consumed in one pass | HippoRAG one-PPR-pass = single-step multi-hop |
| Route-to-source | none - graph-or-nothing | on certified miss or thin coverage: route to source documents / gap-ledger repair queue instead of guessing | CRAG Incorrect→web-search (query-time guess version) |
| Cost accounting | none per query | tokens spent + rungs used in every response - the negotiation currency | PoG Table 4 proves it is measurable |

## 4. Fence - what the bridge composes with and must not re-register

R34 owns the transferred HippoRAG retrieval levers and is settled: H366 span render CONFIRMED, H367 proposition-seeded entities CONFIRMED, H369 hard specificity rerank REFUTED, H370 SIMILAR_TO expansion REFUTED, H368 PPR re-ablation OPEN and GATED on the benchmark harness (+3 R@5 at <= 1.5x latency to promote) - the bridge consumes these levers, it does not re-adjudicate them, and the recognition-memory filter stays unregistered (+0.7 peer, worst failure profile). R37 owns the calibrated escalation ladder (H382: sufficiency gate, rungs, frontier-recall-at-<=10%-mean-growth bar) - the bridge treats escalation as the ONLY sanctioned second round and never invents a parallel trigger. R38 owns gate calibration (H383 CRC certificate fitted at optimize time and checked at query time, H384 two-tier state, H385 label harvesting, H386 drift refit, H387 cross-class transfer) - bridge confidence metadata READS these certificates, never refits them. R39 owns graph construction (H389 extraction-coverage certificate, H390 multi-pass union, H391 passage context edges, H392 open-extraction shadow, H393 typed-graph duality contrarian, H394 coverage-gated ingest, H395 rejection ledger) - every construction lever the bridge needs is R39's to build; bridge hypotheses that depend on coverage certificates are GATED on R39-H389/H394, not substitutes for them. R35 owns question objects and query-to-query matching; R36 owns derived-object invalidation (and will maintain any new bridge-created object class); R03-H15 owns comparison decomposition (shipped); R19-H181 owns the miss detector.

## 5. Proven-novel open slots

Verified 2026-07-11 by web sweep (SABER self-aware abstention 2605.18792; Skill-RAG failure-state routing 2604.15771; SURE-RAG sufficiency verification 2605.03534; CoveR coverage-aware retriever training 2605.28522; claim-selective conformal retrieval certification 2605.21949) plus the local completeness lineage (Razniewski et al. 2023 survey; Predicting Completeness 2017):

- **S1 - Retrieval conditioned on the graph's own coverage certificates. OPEN - proven novel.** Every published "knows what it doesn't know" retriever infers insufficiency from QUERY-TIME signals: retrieval scores (CRAG evaluator), model hidden states (Skill-RAG), self-priors (SABER), evidence sufficiency checks (SURE-RAG), conformalized retrieval quality (claim-selective certification). The database-theory lineage (partial closed-world assumption, per-table completeness statements → query completeness, Razniewski/Nutt line) proves the LOGIC exists but was never wired to a retriever, and no RAG/GraphRAG system consumes an ingest-time per-document coverage certificate or certified-miss ledger at query time. Under the token-economics constraint the slot gets STRONGER: a certified miss lets the bridge answer "not in corpus" in ZERO extra rounds - the alternative (agentic search for absent content) is the walk's worst case, burning the full bill to find nothing. R39-H389/H394 will mint exactly this artifact; nobody has ever had one to consume
- **S2 - Cost-adjusted evaluation of agentic KG walks vs calibrated single-shot. OPEN.** PoG Table 4 publishes the walk's bill and HippoRAG Table 17 the single-shot bill, but on DIFFERENT benchmarks with different substrates - no published head-to-head holds the graph constant and reports recall per token. The comparison everyone implies, nobody runs
- **S3 - Bridge response as a negotiation surface with calibrated cost metadata. PARTIALLY open.** Self-RAG exposes self-assessment as tokens, CRAG as 3 bands - but no published retrieval API returns calibrated confidence + coverage verdict + cost-spent as a structured contract for an external agent caller to act on. MCP-era tool-calling surveys describe retrieval tools, none with calibrated sufficiency semantics
- Anti-slot (checked, closed): adaptive routing per query complexity is NOT novel (Adaptive-RAG trains exactly this router); KGF's version is R37/R38's - already owned, already calibrated

## 6. Hypothesis candidates for the R40 fanout

Numbering starts H396. Naive baseline for the round: the post-R34 composed frontier pipe (0.9583 / 23-of-24 at +27.8% context, 2 LLM-class calls per query) with the R37 gate making the composition escalation-scoped. PRIMARY METRIC for every candidate: tokens per answered query (retrieval context tokens + LLM call count) alongside recall - a candidate without a token-economy clause is incomplete.

### H396 (follower) - one-response bridge contract: the query answered, evidenced, priced in a single round trip

- **Mechanism** - replace the answer-only return with a structured single response: answer + evidence blocks (entity renders, proposition lines, spans) + per-claim provenance + calibrated confidence (R38 certificate read) + coverage verdict + cost ledger (tokens, rungs used); one embed call + one answer call, assembly is free graph reads
- **Grounding** - SubgraphRAG one-pass subgraph shape (WebQSP F1 78.2); HippoRAG Table 17 (single-step 10-30x cheaper than iterative); Graph-CoT as the counter-model (multi-round API, schema-misunderstanding failures)
- **Prediction** - frontier recall (0.9583) carried unchanged; an external LLM caller consuming the structured response answers follow-up evidence questions ("cite the span for claim 2") with ZERO re-queries where the prose-only return forces a second query() round
- **Bar sketch** - tokens per answered query <= composed-frontier bill +5% (metadata overhead clause); zero recall regressions on the 24-probe harness; follow-up-evidence probes answered from the response alone >= 90%; schema versioned and pinned as tests
- **Composes with** - R34 render levers (consumed), R38 certificates (read), R37 gate (rung count reported, not altered)

### H397 (conformist - the constraint made falsifiable) - adversary arm: the agentic walk priced on KGF's own graph

- **Mechanism** - implement a bounded ToG/PoG-style walk (LLM-pruned beam, depth <= 3, PoG-style sub-objective memory) as a benchmark ARM over the live graph; run head-to-head vs the single-shot + calibrated-escalation pipe holding graph and judge constant; report recall AND tokens per answered query - closes slot S2
- **Grounding** - PoG Table 4 (13.3 calls / 8,156 tokens / 23.3 s per question, the optimized walk); ToG 2ND+D+1 = 22 calls at N=D=3; HippoRAG Table 17 (the single-shot bill)
- **Prediction** - single-shot + escalation matches or beats the walk's recall on the probe set at <= 15% of its token bill; the walk wins (if anywhere) only on the compositional class H398 targets
- **Bar sketch** - both arms on the H368 benchmark harness, same corpus, same answer judge; verdict = recall-per-1k-tokens dominance; if the walk wins recall by >= 5 points on any probe class at ANY cost, that class is named and handed to H398's escalation rung rather than adopted as default; walk arm capped at 25 calls/query (runaway clause)
- **Composes with** - H368 harness (substrate, not re-registered), R37 gate (the defended champion), PoG-digest walk spec

### H398 (contrarian) - the single-shot ceiling is real: one bounded retrieval round is irreducible on compositional questions

- **Mechanism** - claim: on truly compositional multi-hop questions (path-finding class, hop-2 vocabulary invisible to the query embedding), NO ingest-time materialization lifts one-shot retrieval to parity - a single targeted second retrieval round (reformulated from the rung-2 render, ONE extra embed + render, no LLM walk) is irreducible and must become the ladder's top rung, escalation-gated
- **Grounding** - IRCoT +11.3 to +22.6 R points over one-step (the gap is real even for GPT-3-class readers); HippoRAG's own path-finding case study (iterative perfect on single-path questions its PPR fumbles); Graph-CoT difficulty cliff (hard 2.5-15 vs easy 53-80 - even the walk fails, but so does one-shot)
- **Prediction** - a probe class exists where rung-0/rung-2 recall plateaus < 0.8 while one reformulated round recovers >= half the remaining gap; total bill <= 2x rung-2 tokens on fired queries only
- **Bar sketch** - fires on <= 15% of queries (R37 gate extended, calibrated per R38 - a new rung, not a new trigger); mean token growth across the probe set <= 10%; REFUTED if the ingest-side R39 substrate (context edges + H368 PPR) closes the same class single-shot - refutation here is the doctrine's strongest possible confirmation and must be recorded as such
- **Composes with** - R37-H382 ladder (adds rung 3), R38-H387 (the new rung earns its own certificate), R39-H391/H368 (the competing single-shot fix)

### H399 (conformist - slot S1, the novelty candidate) - certified-negative retrieval: the bridge knows what the graph provably does not contain

- **Mechanism** - at query time the bridge consults the R39 coverage artifacts (per-document coverage certificates + certified-miss ledger + gap ledger): when the query's target region maps to a certified miss or an uncovered attribute class, return "not in corpus - certified" with the certificate as provenance, optionally routing to the source document or repair queue - in ZERO extra rounds and zero answer-LLM tokens
- **Grounding** - proven-novel slot S1 (web-verified 2026-07-11: CRAG/SABER/Skill-RAG/SURE-RAG all query-time-only; PCWA lineage never wired to a retriever); CRAG Incorrect→route-to-source as the guess-version precedent (PopQA +7.0); KGF's own R04-H23 "graph knows what it doesn't know" doctrine
- **Prediction** - on probes targeting certified-missing content, the certificate route abstains correctly where the R19-H181 similarity gate either false-answers (plausible-neighbor render) or pays full escalation to find nothing; unanswerable-probe token cost drops to the embed call alone
- **Bar sketch** - unanswerable probe set (seeded from the miss ledger + hand-written negatives): certified-negative precision >= 0.9, zero false negatives on the answerable 24 (never certify away an answerable question); tokens per unanswerable query <= 20% of the current miss-path bill; GATED on R39-H389 confirming its instrument (and enriched by H394's certified-miss ledger if it lands)
- **Composes with** - R39-H389/H394 artifacts (consumed), gap ledger doctrine, R19-H181 (the similarity gate stays as the uncertified fallback), H396 coverage-verdict field

### H400 (follower) - compositional decomposition as one upfront call: sub-objectives without the walk

- **Mechanism** - generalize `decompose_comparison` (R03-H15) to PoG-style sub-objective decomposition for compositional multi-hop queries: ONE small-LLM call splits the question, k sub-queries embed and retrieve in parallel (batched), renders union under one budget, ONE answer call - the walk's guidance without its loop
- **Grounding** - PoG ablation: guidance alone worth +3.1 CWQ as an upfront decomposition; IRCoT gap (+12.5 MuSiQue R) as the prize; KGF's shipped comparison decomposition as the wiring precedent (`pipeline.py:1092-1118`)
- **Prediction** - on multi-entity/compositional probes, decomposed-union single-shot recovers >= 3 recall points over the whole-question embedding at +1 small-LLM call (+<= 15% tokens); flat probes unaffected (decomposer returns the question unchanged)
- **Bar sketch** - zero regressions on non-compositional probes; token clause: mean bill growth <= 15%, decomposer on the cheap model tier; decomposition fires on <= 30% of queries (trigger = detectable compositional form, not always-on); REFUTED if union dilution costs any currently-passing probe
- **Composes with** - R03-H15 (generalizes, does not replace), H396 response contract (sub-answers traceable per sub-objective), R37 gate (decomposition is rung-0 machinery, not escalation)

### H401 (follower) - the negotiation surface: calibrated metadata lets the CALLER buy escalation

- **Mechanism** - expose the internal signals (seed_top_score, gate threshold + margin, R38 certificate id + alpha, coverage verdict, gap-ledger hits) in the H396 response, plus an explicit escalation offer ("rung 3 available, est. +N tokens"); the caller - a querying AI - decides whether to pay; one optional follow-up round via a resume token, never an open conversation
- **Grounding** - Self-RAG (self-assessment as controllable tokens), CRAG 3-band action trigger, Adaptive-RAG (outcome-labeled routing is learnable - here the caller's LLM does the routing from exposed evidence); slot S3
- **Prediction** - an external agent given the metadata reproduces the calibrated gate's escalate/accept/abstain decisions at >= 90% agreement WITHOUT access to KGF internals - proving the surface carries the negotiation; disagreement cases concentrate where the caller has context KGF lacks (conversation history), which is the point
- **Bar sketch** - metadata <= 5% of response tokens; resume-token follow-up costs only the delta (no re-retrieval of rung-0 context); agreement >= 90% on the probe replay; no calibration leakage (exposing the threshold must not let a caller game the R38 label loop - `query.answered` labels marked caller-initiated)
- **Composes with** - H396 (the carrier), R38 (certificates read-only), R37 (the gate remains the in-band default when the caller doesn't negotiate)

### H402 (heretical) - zero graph work at query time: the render is a build artifact

- **Mechanism** - dissolve query-time graph traversal entirely: every entity's render block (properties + currently-valid relations + top spans) is materialized at optimize() time and stored as a versioned artifact; query time = 1 embed call + artifact fetch by seed id + 1 answer call - no Cypher walks, no per-query neighborhood assembly; the graph becomes a compiler, the bridge serves its binaries
- **Grounding** - sleep-time compute (archived: ~5x test-time reduction by offline anticipation); retrieval-first doctrine taken to its fixed point; PoG's memory ablation inverted (the walk needs bookkeeping because nothing was precomputed); Anthropic contextual retrieval (-49% failures from ingest-time context, vendor-measured) as the ingest-shift precedent
- **Prediction** - identical recall on the 24-probe harness (the render is deterministic given the graph), query latency drops >= 3x and query-time Cypher load → ~0; the artifact store grows linearly with entities and is priced; staleness is the real cost and it lands on R36's ledger, not on query latency
- **Bar sketch** - recall exactly preserved (bit-level render parity on unchanged graph); tokens per query unchanged (same context, cheaper assembly); latency and per-query DB ops measured before/after; artifacts carry justification records at creation (R36-H376 schema) so invalidation is possible at all; REFUTED if merge/re-ingest churn makes artifact refresh cost exceed 1 week of query-time savings at benchmark query volume - in which case partial materialization (hot entities only) is the fallback re-fan
- **Composes with** - R36 (owns invalidation of the new object class - same pattern as R34/R35 objects), H366 span store, H396 (the artifact IS the response body), FSM optimize() stage

### Round table

| Hypothesis | Persona | One-line mechanism | Peer number | Token-economy clause |
|---|---|---|---|---|
| H396 | follower | one-response structured bridge contract | SubgraphRAG F1 78.2 one-pass | bill <= frontier +5% |
| H397 | conformist | agentic walk priced on KGF graph (adversary arm) | PoG 8,156 tok / 13.3 calls / q | dominance = recall per 1k tokens |
| H398 | contrarian | one bounded second round is irreducible on compositional class | IRCoT +11.3-22.6 R | fires <= 15%, mean growth <= 10% |
| H399 | conformist | certified-negative retrieval from R39 coverage certificates | CRAG +7.0 PopQA (guess version) | unanswerable bill <= 20% of miss path |
| H400 | follower | sub-objective decomposition as ONE upfront call | PoG guidance +3.1 | +1 cheap call, growth <= 15% |
| H401 | follower | calibrated metadata → caller buys escalation | Self-RAG controllable tokens | metadata <= 5% of response |
| H402 | heretical | renders precompiled at optimize(), zero query-time graph work | sleep-time ~5x test-time reduction | tokens unchanged, latency >= 3x down |

Sequencing: H396 first (the contract every other candidate returns through); H397 as soon as the H368 benchmark harness exists (shared substrate); H400/H401 ride H396; H398 after H397 names the losing class; H399 gated on R39-H389; H402 offline-testable immediately (render parity is measurable without LLM spend).

## 7. Source register

Downloaded for this brief (all PDF-verified `%PDF`, digests beside them in `references/papers/`):

1. `[paper] ToG Think-on-Graph, 2023-07.pdf` - beam search on KG, 22 calls/q at N=D=3, SOTA 6/9 (arXiv 2307.07697, ICLR 2024)
2. `[paper] Graph-CoT, 2024-04.pdf` - 4-function graph API, GRBench 1,740 q, 36.29 vs 23.09 one-shot (arXiv 2404.07103, ACL-F 2024)
3. `[paper] IRCoT, 2022-12.pdf` - interleaved retrieval, +11.3-22.6 R points at 2-4 rounds (arXiv 2212.10509, ACL 2023)
4. `[paper] CRAG Corrective RAG, 2024-01.pdf` - retrieval evaluator + route-to-source, PopQA 59.8 vs 52.8 (arXiv 2401.15884)
5. `[paper] Plan-on-Graph, 2024-10.pdf` - self-correcting walk, the published token bill: 8,156 tok / 13.3 calls / 23.3 s per CWQ question (arXiv 2410.23875, NeurIPS 2024)

Load-bearing pre-existing library: `[paper] HippoRAG, 2024-05.pdf` (Table 17 cost anchor: \\$0.1 vs \\$1-3, 3 vs 20-40 min per 1,000 queries), `[paper] HippoRAG 2, 2025-02.pdf` (query-to-triple +12.5, reset weights 1.0/0.05, recognition filter +0.7), `[paper] Self-RAG, 2023-10.pdf`, `[paper] Adaptive-RAG, 2024-03.pdf`, `[paper] FLARE active retrieval, 2023-05.pdf`, `[paper] ToG-2, 2024-07.pdf` (5.4 calls / 27.3 s vs 1 call / 10.2 s), `[paper] gnn-rag graph neural retrieval, 2024.pdf` (~9x fewer KG tokens), `[paper] SubgraphRAG, 2024-10.pdf`, `[paper] Sleep-time Compute.pdf` lineage, completeness lineage (Razniewski et al. 2023 survey - the PCWA frame behind slot S1). Novelty-sweep neighbors (cited, not archived - none consume ingest-time coverage artifacts): SABER (arXiv 2605.18792), Skill-RAG (2604.15771), SURE-RAG (2605.03534), CoveR (2605.28522), claim-selective conformal certification (2605.21949). Internal: `docs/experiments/kgf-redesign-experiments.md` R34/R37/R38/R39 registrations; `reports/experiments/adjudicated/r39-graph-construction-literature-brief-20260711.md`; `src/knowledge_graph_foundry/pipeline.py:1055-1299`.

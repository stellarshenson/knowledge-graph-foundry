# R58 amplification research brief - three user-directed families

Literature grounding for the parked R58 amplification fanout (three families: traversal-success amplification, query-insertion, entity strengthening). Every sketch names its cost tier, the honest incumbent control it must beat, and the OUR-STATE fences it must cite. Ceilings for families 2 and 3 are PRICED by the parallel R57 miss atlas (H648 entity axis, H649 query axis) - a family dies if its atlas separation is absent, no matter how good the mechanism reads on paper.

Incumbent controls (the numbers to beat):
- **H627 one-step score smoothing** over the normalized adjacency, +9.5pt carrier recall - the incumbent of evidence amplification
- **max-gap adaptive-k seeder** reach_all **0.8740** (lexicon-free, reproduces H619's hand-built stop-list exactly)
- **anchor-reset PPR** reach 0.8661 / 131 - single-source reset from linked question anchors, dense region unioned AFTER the walk
- **render_budget=1.0** is required for retrieval gains to convert to answers (H620); levers compose super-additively only there

Standing fences that constrain ALL families:
- **H597** fuse-ADD into seed slots KILLED (-1.6pp) - "merge the harvest, never the seeds"
- **H598** multi-anchor joint diffusion / trilateration KILLED at oracle - intersection-style boosts lose to single-source PPR
- **R50** relation/type LABEL weighting KILLED (0% vocab alignment) - amplification weights must be EMPIRICAL, never label-driven
- **H633/H626** candidate precision and walk reachability are ANTI-ALIGNED; hub anchors are load-bearing reset mass; a pre-cut score penalty flattens the top-of-list and fights the max-gap selector
- **LEAKAGE DISCIPLINE** any mechanism that learns from successful probes trains on a split DISJOINT from evaluation; the frozen 132 cannot both teach and judge

---

## Family 1 - Traversal-success amplification

A succeeding walk should get louder, within-query and across queries. The classical form is pseudo-relevance feedback (PRF): treat top results as relevant, fold them back, re-retrieve. IR has studied its failure - QUERY DRIFT - for two decades, and the findings map almost one-to-one onto our fuse-add kill.

**What the literature says**
- PRF on DENSE retrievers helps ONLY in a narrow envelope: the original query must keep the MAJORITY or equal weight, and the feedback pool must be SHALLOW (few top passages); deep pools and query-diluting weights degrade effectiveness (PRF Deep LMs Dense Retrievers Pitfalls, 2108.11044). This is H597 stated in IR terms - averaging feedback vectors into the query is where dense PRF breaks.
- The robust fix is SUBTRACTION not addition: gate the feedback pool with a relevance judge BEFORE expansion. An LLM filter over the top-k, with RM3 estimated only over accepted documents, beats blind PRF; the gain is the filter, not new terms (LLM-Assisted PRF, 2601.11238). This is HippoRAG-2 recognition-memory seed filtering, proven on PRF - and the answer to "what gates a second round."
- Iterative multi-hop retrieval (IRCoT, FLARE, Self-Ask - all filed) interleaves retrieval with reasoning to trigger a second round on demand; the gate is a reasoning-driven need for more evidence, not a blind re-issue.
- Edge weights CAN be learned from outcomes: Supervised Random Walks (1011.4071) learns an edge-strength function so PPR visits the labelled positive destinations, end-to-end through the walk's fixed point. Each source multiplies into many pairwise constraints - the regime our ~130 probes x several carriers each sits in, but far below the paper's graph scale (overfit/identifiability is the live risk).

**Drift / failure modes the literature warns about (-> R58 KILL clauses)**
- **Vector-averaging drift** - folding feedback vectors into the seed/query with non-dominant weight, or from a deep pool, drifts. KILL: any re-injection of walk-success evidence into the SEED or query vector that does not keep the original signal dominant AND the feedback pool shallow is the documented pitfall; it will replay H597's -1.6pp.
- **Blind second round** - re-issuing without a relevance gate amplifies noise. KILL: an ungated second round that does not beat single-pass anchor-reset 0.8661/131.
- **Label-driven weights** - R50 already killed label weighting; SRW is only admissible because its weights are OUTCOME-derived (empirical), never type/relation labels. KILL: any learned weight traceable to a label rather than a probe outcome.
- **Leakage** - SRW/any learned reset trained on the frozen 132 is invalid.

**Hypothesis sketches**
1. **Gated-second-round PPR (recognition-gate replay)** - after the anchor-reset walk, take the top-m walk-surfaced nodes, screen them with a cheap relevance gate (LLM or dense-margin heuristic), and run ONE more PPR reset adding only accepted nodes' mass; original anchors keep majority reset weight. Cost: FREE replay (heuristic gate) / LLM (judge gate). Control: must beat anchor-reset 0.8661/131 AND H627 smoothing without drifting. Fences: H597, LLM-Assisted-PRF gate, PRF-pitfalls shallow-pool rule, H633 (do not flatten top-of-list).
2. **Supervised edge-strength PPR (outcome-learned reset)** - learn an edge-strength function from probe SUCCESS pairs (positive carriers vs negatives) via the SRW objective, run PPR with learned strengths. Cost: GPU-trivial. Control: H627 +9.5pt and max-gap 0.8740; must clear both to justify training. Fences: R50 (weights empirical not label), LEAKAGE (disjoint train split), H626 (respect hub reset mass).
3. **Within-query walk reinforcement (self-loudening)** - during a single query, upweight edges the walk already traversed to a high-mass node (bounded, one pass) so corroborated regions get louder - the H627 smoothing generalized to an outcome-weighted single step. Cost: FREE replay. Control: H627 one-step smoothing (must beat the flat incumbent, not just match); two-hop is dead flat, so stay one-step. Fences: H627 block-diagonal reach, H598 (no intersection boosts), H626 anti-alignment.

---

## Family 2 - Query-insertion into the graph

The query becomes a graph object contributing connectivity and reset mass. H371 is the existing beachhead (question nodes reach parity 24/24 on a probe instrument; engine wiring pending). The literature splits into index-time question generation and query-as-node propagation.

**What the literature says**
- Queries as first-class graph NODES is a classical, proven idea: the click graph (Craswell & Szummer, SIGIR 2007) propagates from a query node across a bipartite graph and retrieves documents NEVER clicked for that query - it reaches carriers the raw query embedding cannot, via shared structure. Best regime: long walk, HIGH self-transition (keep mass near the source, spread locally) - the same local-spread lesson as H627 and anchor-reset.
- Index-time question generation is the mirror of query-insertion and is strongly evidenced (all filed): doc2query/docTTTTTquery appends predicted queries to documents before indexing (Recall@1000 85.3->89.3); QuOTE ("reverse HyDE") indexes LLM-generated answerable-questions per chunk (+10.5 C@1 SQuAD, MultiHop full@20 +12.5) at ~1/9 HyDE's query latency; QA-Expand generates and REFLECTIVELY FILTERS sub-questions. These move the LLM to ingest and make query-time near-pure question-to-question matching.
- HippoRAG-2 (filed) already inserts passage nodes into the PPR graph (+11 recall) with asymmetric reset weights (passage 0.05, phrase 1.0) - the template for giving an inserted node the RIGHT reset mass, not full mass.

**Drift / failure modes the literature warns about (-> R58 KILL clauses)**
- **Generated-question hallucination** - QuOTE/QA-Expand both need a FILTER step (QA-Expand's reflective agent, QuOTE's dedup); ungated generated questions inject noise nodes. KILL: inserted question nodes that are not filtered/deduped against source before wiring.
- **Wrong reset mass** - an inserted query node given FULL reset mass is the fuse-add failure in graph form: it dominates propagation and drifts (H597; HippoRAG-2 uses 0.05 for passages precisely to avoid this). KILL: query node injected into SEED slots or given seed-equal reset mass - it must ADD connectivity, per "merge the harvest, never the seeds."
- **Self-transition too low** - click-graph shows under-propagation if the walk runs away from the source; a query node with diffuse mass reaches nothing. KILL: mechanism that does not keep mass local (echoes two-hop-smoothing-dead-flat).
- **Ceiling** - H649 PRICES this family: it counts missed carriers reachable within 2 hops of a query node wired to (anchors u seeds). If that count is small, the geometric prize is small regardless of mechanism.

**Hypothesis sketches**
1. **Query-node PPR (H371 wired into the engine)** - materialize the query as a node, wire it to linked anchors + dense seeds, run PPR from it with click-graph-style high self-transition and HippoRAG-2-style low reset mass, union dense region after. Cost: FREE replay. Control: anchor-reset 0.8661/131 (query node must ADD reach over anchor-only). Fences: H371 parity, H597 (add not fuse), HippoRAG-2 asymmetric reset, H649 count (prize is bounded by it).
2. **Ingest-time answerable-question nodes (reverse-HyDE graph)** - per chunk, generate + filter answerable questions (QuOTE/QA-Expand recipe), insert each as a question node linked to its evidence carriers; at query time match query->question-node then propagate to carriers. Cost: LLM (ingest-once). Control: dense@16 anchor-reset; must beat it on carriers that fail dense seeding today. Fences: QA-Expand reflective filter (hallucination gate), H371, leakage (generated questions from eval probes cannot seed eval).
3. **Cross-query associative memory (persisted successful query nodes)** - persist a SUCCEEDING query's node + its confirmed carrier edges so a future similar query reaches those carriers by query-to-query match (click-graph generalization to unclicked pairs). Cost: FREE replay. Control: anchor-reset per-query baseline. Fences: LEAKAGE (a persisted eval-probe query cannot teach another eval probe - persist only on a disjoint split), click-graph generalization, H597.

---

## Family 3 - Entity strengthening

Ingest-side enrichment so a starved entity surfaces in dense retrieval. The hard constraint: self-extracted nodes have NO descriptions - every sketch must state where new text/features come from. The literature offers three enrichment channels: triple verbalization, LLM-explanation text, and structural neighbourhood aggregation.

**What the literature says**
- Triple->text verbalization is proven as a RETRIEVAL lever, not just pre-training: KELM/TEKGEN (2010.12688) verbalizes GROUPED triples (an entity's neighbourhood, not one triple) and augmenting a retrieval corpus with it significantly lifts open-domain QA and LAMA. This is the direct answer to "where does the text come from" - generate a description from the node's triple neighbourhood.
- LLM-explanation text as node features is SOTA on text-attributed graphs: TAPE (2305.19523) attaches an LLM's prediction+explanation to each node, re-encodes, and beats shallow and plain-LM node features - text-space enrichment feeding better vectors, done once at ingest (2.88x faster training than the LM baseline).
- Structural neighbourhood aggregation recovers exactly the LOW-SALIENCE entities coarse embeddings miss: GER (2211.10991) aggregates an entity's local knowledge-unit graph via hierarchical attention, complementary to the sentence embedding, with gains concentrated where attention to the entity is low - i.e. our starved carriers.
- Text-side vs embedding-side: the three papers converge - text enrichment (KELM/TAPE) and structural aggregation (GER) both feed BETTER vectors; H627 (confirmed embedding-space smoothing) is a lightweight version of neighbourhood aggregation. The channels are COMPLEMENTARY, not substitutes - text enrichment improves the vector, smoothing spreads it.

**Drift / failure modes the literature warns about (-> R58 KILL clauses)**
- **No starvation signal = dead family** - H648 PRICES this family: if missed carriers do NOT separate from hits on description-length/degree (AUC < 0.55 both axes), the starved-entity theory is dead and the family deprioritizes regardless of mechanism quality. This is the hard gate - cite it in every family-3 registration.
- **Hallucinated descriptions** - KELM's full-KG verbalization surfaces coverage/coherence failures; ungrounded generated text injects false facts into the node. KILL: enrichment text not grounded in the node's source chunk or triple neighbourhood (must quote/verbalize, not invent - self-auditing foundry doctrine).
- **Over-enrichment homogenization** - if every node gets similar generated text, entities collapse toward each other in embedding space and dense discrimination DROPS. KILL: enrichment that reduces hit/miss embedding separation (measure separation before/after).
- **Wrong channel** - spending LLM cost on text when the win is structural (or vice versa); H648's axis (text vs degree) says which channel has purchase.

**Hypothesis sketches**
1. **Neighbourhood verbalization descriptions (KELM recipe)** - for each description-less node, verbalize its k-hop triple neighbourhood into a short description, re-embed, re-seed dense@16. Cost: LLM (ingest-once). Control: dense@16 anchor-reset 0.8661/131 on carriers that fail dense seeding. Fences: H648 (only if starvation confirmed AUC>=0.65), KELM grounding, source-chunk quote requirement (no invented facts).
2. **Explanation-feature enrichment (TAPE recipe)** - generate an LLM explanation of what each starved node IS from its source chunk, re-encode via a small LM into the node vector. Cost: LLM (ingest-once). Control: H627 smoothing (text enrichment must add over the embedding-space incumbent - they should COMPOSE, test both). Fences: H648, TAPE ingest-once, over-enrichment homogenization check.
3. **Structural neighbourhood aggregation (GER recipe, no LLM)** - build each starved node's representation as a fusion of its neighbours' existing embeddings (hierarchical/attention-weighted), no text generation at all - the pure embedding-side arm. Cost: GPU-trivial. Control: H627 one-step smoothing (this IS a heavier neighbourhood aggregation - must beat the one-step incumbent to justify). Fences: H648, H627 (block-diagonal / one-step-only lesson), H598 (no intersection-style fusion).

---

## Cross-family notes

- **R57 prices the ceilings before R58 registers.** Family 2's prize is literally H649's count (missed carriers within 2 hops of a query node); family 3 is dead if H648 finds no hit/miss separation on entity features. Family 1 has no atlas gate but inherits the H597/PRF-pitfalls drift envelope directly. Do not register a family-2 or family-3 hypothesis before its atlas number lands.
- **The unifying literature lesson** - across all three families the robust move is LOCAL, GATED, ADDITIVE-NOT-DILUTIVE: keep the original signal dominant (PRF query-weight, H597), filter the feedback before amplifying (LLM-Assisted PRF, QA-Expand reflection, HippoRAG-2 recognition), keep propagation mass near the source (click-graph high self-transition, H627 one-step, anchor-reset). Every KILL clause is a variant of "do not dilute the seed."
- **Cost ordering for cheapest-first killing** - FREE replay arms (gated-second-round, query-node PPR, within-query reinforcement, structural aggregation) come before LLM-ingest arms (question-node generation, verbalization, explanation enrichment). Kill on the FREE rung where possible.

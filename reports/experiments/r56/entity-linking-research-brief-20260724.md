# Entity-Linking Research Brief - Query→Graph Linking Layer (R56, 2026-07-24)

Cross-references KGF's measured query→graph entity-linking findings (H620-H632, DEF-19) against the external EL and graph-RAG literature. Purpose: seed a pre-registered R56 hypothesis fanout. Every sketch cites the FENCE it must beat so no hypothesis re-derives a closed result.

Papers cited by local digest filename. New this round: ELQ, neural-EL survey, BLINK. Reused from library: GENRE, ReFinED, Entity Retrieval for Entity-Centric Questions, dual-encoder disambiguation, Microsoft GraphRAG, HippoRAG, HippoRAG 2, LightRAG, 2WikiMultiHopQA dataset, cross-document coref KG, link-kg coref KG, Query-time Entity Resolution.

---

## (A) Candidate generation vs disambiguation split

The literature unanimously separates a HIGH-RECALL candidate-generation stage from a PRECISION disambiguation stage, and it never tries to make the candidate cut itself precise - it retrieves wide and re-ranks. This confirms our H626 finding at the seeding layer.

- **BLINK** (`[paper digest] BLINK zero-shot entity linking.md`): two stages, separately tuned. Stage-1 bi-encoder retrieves top-64/100 for RECALL (Recall@64 = 82-93%, vs BM25 69); stage-2 cross-encoder re-ranks a k=10 window for PRECISION. The objectives are explicitly not co-tuned
- **ELQ** (`[paper digest] ELQ efficient entity linking for questions.md`): enumerates ALL spans up to length 10 as candidate mentions (maximal recall), then a single joint-score threshold filters. Links QUESTIONS specifically - short, noisy, casing-free - the exact KGF regime. WebSQP recall 85.0, and the recall gain (+16.7 over VCG) is the headline
- **ReFinED** (`[paper digest] refined entity linking.md`): candidate generation shortlists top-30 by entity prior before the single-pass scorer runs - generous pool, cheap prior-based generation, precision downstream
- **GENRE** (`[paper digest] GENRE Autoregressive Entity Retrieval.md`): the hard alternative - constrained decoding over a name trie makes the model structurally unable to emit a non-existent name; precision is enforced at generation, no separate re-rank
- **neural-EL survey** (`[paper digest] neural entity linking survey.md`): candidate generation is universally recall-first (surface + alias + prior union); ranking (local context or global coherence) carries precision

Maps to our fences: H626 found candidate precision and walk reachability ANTI-aligned at the margin - max-gap's surplus low-precision anchors (376 vs 322) are useful reset mass. This IS the BLINK wide-pool principle stated at the seeding layer: the field would predict our result. H621 (off-gold exact-match hubs outrank gold inside a correct candidate list) is a ranking failure, exactly the job the literature assigns to stage-2, not to the cut.

**Hypothesis sketches (A)**
- **A1 - Stage-2 cross-encoder re-rank of anchors**: keep the generous max-gap anchor set as stage-1 recall mass; add a question×candidate-node-context cross-encoder to reorder off-gold hubs below gold. Cost: GPU-trivial (frozen encoder, replay the H626 paired set). Control it must beat: the current max-gap anchor ordering feeding the walk (0.8740 vs oracle 0.898). Fence: must cite H626 (do not re-cut; RE-RANK) and H621 (the failure is ranking-in-list, not homonymy)
- **A2 - Degree/popularity prior as tiebreaker**: add an IDF-like node-specificity or inverse-degree prior to demote high-degree exact-match hubs at anchor selection. Cost: FREE replay. Control: current exact-match ordering. Fence: H621 (off-gold hubs are the residual, not name collisions) - must show the prior moves gold above the hub without losing max-gap reset mass (H626)

---

## (B) NIL / unlinkable detection WITHOUT score shape

The EL literature detects NIL by MAGNITUDE or a trained classifier - never by the shape of a candidate-score curve. This is the family KGF has not yet tried after closing the score-shape axis (H623/H624/H626).

- **neural-EL survey** NIL taxonomy (Fig 3): four mechanisms - (1) a THRESHOLD on the top entity score; (2) a dedicated NIL PREDICTOR head; (3) a SEPARATE binary model; (4) "no candidate found" => NIL. All attach to a meaningful magnitude or classifier, none to curve geometry
- **ELQ**: NIL is one tuned scalar gamma on the joint `p(e|mention)·p(mention)` context-entity compatibility score - a mention whose best entity never clears gamma is simply not emitted. An absolute compatibility magnitude, not a same-mention ranking shape
- **HippoRAG 2** (`[paper digest] HippoRAG 2.md`): a recognition-memory LLM screens candidate seed nodes before PPR, suppressing spurious anchors - a trained/prompted binary NIL filter (family 3) operating exactly at our anchor-selection stage
- **ReFinED / neural-EL survey**: entity priors (popularity/anchor-text) are a strong NIL and ambiguity signal, but dataset-dependent (over-popularity bias on rare entities)

Maps to our fences: the H623/H624/H626 score-shape axis is CLOSED - the spline separates ambiguous-vs-clean at AUC 0.849 but cannot place a cut; the signal cannot be conformally certified because gold anchors sit at rank ≥2 behind off-gold exact-match hubs. Every literature NIL signal above is ORTHOGONAL to curve shape, so it clears the fence by construction. The H621 fact - the residual is ranking inside a correct list - reframes our problem: we may not need NIL detection at all, we need a hub-demotion re-ranker (see A). NIL detection matters for the 5 genuinely-absent golds (E) and unlinkable question spans.

**Hypothesis sketches (B)**
- **B1 - Context-entity compatibility threshold (ELQ-style)**: score question-embedding × candidate-node-embedding (from incident-edge context), keep anchors above a tuned magnitude gamma. Cost: GPU-trivial. Control: the closed spline cut (H624) AND the current max-gap keep-set. Fence: H623/H624 (must be a magnitude on compatibility, NOT curve shape) - passes the fence only if the score is context-entity, not curve-geometry
- **B2 - Recognition-memory seed filter (HippoRAG-2-style)**: LLM/cheap-classifier binary screen on each candidate anchor before the walk. Cost: LLM (cheap, one call per candidate set) or GPU-trivial if distilled. Control: max-gap adaptive-k keep-set (0.8740). Fence: H626 (must not strip the useful low-precision reset mass; screen for spurious, not merely low-precision) and H623 (classifier, not shape)
- **B3 - Entity-prior NIL for absent golds**: flag a question span as NIL/absent when no node clears a surface+prior match (survey family 4), routing it to extraction-recall repair (E). Cost: FREE replay. Control: current silent no-anchor behavior. Fence: H621 (distinguish genuine absence from hub-outranks-gold; only the former is NIL)

---

## (C) Surface-form / alias normalization at ingest

Production alias tables are overwhelmingly Wikipedia-derived (redirects, disambiguation pages, anchor-text/CrossWikis dictionaries). A self-extracted graph has none of that backbone, so what transfers is corpus-internal alias mining: coreference-derived aliases, appositive/abbreviation caches, and type-constrained matching. Our H632/DEF-19 ladder is a lightweight instance of exactly the survey's candidate-generation family (2).

- **neural-EL survey**: candidate generation family (2) = alias expansion from Wikipedia redirects, disambiguation pages, WordNet synonyms, web-search fallback for misspelled/multi-word mentions; family (1) = surface-form matching via Levenshtein, n-grams, normalization. Our paren-strip/fold/fuzzy-0.92 ladder is family (1)+(2) with no Wikipedia backbone
- **link-kg coref KG** (`[paper digest] link-kg coref kg construction.md`): builds per-entity-type alias caches during LLM extraction, mapping "the device"/"he"/aliases to canonical names BEFORE extraction - corpus-internal alias mining, the transferable substitute for Wikipedia redirects
- **cross-document coref KG** (`[paper digest] cross-document coref kg.md`): uses the graph-under-construction itself as a coreference signal to tie mentions across documents to existing nodes
- **Query-time Entity Resolution** (`[paper digest] Query-time Entity Resolution.md`): expand-and-resolve only the query-relevant neighbourhood at read time; precision/recall decay geometrically with depth, so bounded local resolution suffices - supports resolving variants at query time rather than merging at ingest
- **Type-constrained matching**: ReFinED's fine-grained entity typing gates disambiguation; the survey lists type as a standard ranking signal. This is precisely our Camille refinement (a Film-typed gold must not match a Person node of the same name)

Maps to our fences: H632/DEF-19 resolved 25/38 name variants with a rung-ordered ladder and ZERO false merges; the identified refinement is a type-consistency check before accepting a paren-strip match. The literature confirms type-constrained candidate matching is standard practice (ReFinED, survey), so the Camille refinement is not a hack but the missing standard gate.

**Hypothesis sketches (C)**
- **C1 - Type-consistency gate on paren-strip matches**: before accepting a `Title (disambiguator)` → `Title` join, require node-type compatibility (Wikipedia disambiguator ⇒ expected type, matched against node type). Cost: FREE replay over the 38 DEF-19 golds. Control: the current paren-strip rung (which mis-joined Camille). Fence: H632/DEF-19 (must resolve the remaining 13/38 or fix the Camille false-positive WITHOUT new false merges) and H621 (must not reintroduce hub collisions)
- **C2 - Corpus-internal alias cache at ingest (link-kg-style)**: mine appositive/abbreviation/coref aliases during extraction into a node alias table, widening exact-match candidate generation at query time. Cost: LLM (extraction-side) or GPU-trivial (coref model). Control: exact normalized-name match coverage (0.9997 forecast at 6x, H621). Fence: H621 (name collisions are NOT the problem - the alias cache must add VARIANT coverage without manufacturing homonymy) and H632 (must beat the paren/fold/fuzzy ladder's 25/38, not duplicate it)
- **C3 - Query-time neighbourhood variant resolution**: instead of a global alias ladder, expand-and-resolve variants only in the query-anchored neighbourhood (Query-time ER). Cost: FREE replay. Control: the global H632 ladder. Fence: H632 (must match 25/38 at lower global cost) - likely a cost-refactor, not a recall win; flag as low-priority

---

## (D) The evaluation-join question

Peers do NOT join gold supporting-fact titles to graph nodes. They evaluate at PASSAGE level (recall@k over retrieved chunks) or ANSWER level (SQuAD-style normalize_answer EM/F1), or by LLM-judged win rate. Our carrier-title→node join is a self-imposed instrument with no peer analogue - which is both why it exposes failures peers never measure and why our numbers are not directly comparable to theirs.

- **HippoRAG / HippoRAG 2** (`[paper digest] HippoRAG.md`, `HippoRAG 2.md`): report multi-hop evidence RECALL over retrieved PASSAGES (recall@2/@5) and downstream QA EM/F1. The KG and PPR are the retrieval MECHANISM; scoring is on passages and answers, never on entity-node identity. Their cosine>0.8 synonym edges heal extraction variance internally, so a missed node degrades passage recall rather than failing a join metric
- **Microsoft GraphRAG** (`[paper digest] Microsoft GraphRAG.md`): LLM-judged win rate on comprehensiveness/diversity/directness for global-sensemaking queries - no node-level ground truth at all
- **LightRAG** (`[paper digest] LightRAG.md`): retrieval cost and LLM-judged answer quality/diversity; no title→node join
- **2WikiMultiHopQA** (`[paper digest] 2WikiMultiHopQA dataset.md`): the benchmark scores answer EM/F1, supporting-SENTENCE EM/F1, and evidence-TRIPLE EM/F1 - all against text spans and Wikidata triples, never against a constructed graph's node set. Supporting facts are (title, sentence-id) pairs matched at the passage level

**eval_join_answer**: No peer system joins gold supporting-fact titles to graph nodes. HippoRAG/HippoRAG 2 evaluate passage recall@k and answer EM/F1; GraphRAG and LightRAG use LLM-judged answer quality; the 2Wiki/HotpotQA/MuSiQue benchmarks score answer EM/F1 plus supporting-SENTENCE and evidence-TRIPLE overlap - all at passage/answer/triple granularity, never node identity. Our carrier-title→node join (H631/H632) is therefore a self-imposed instrument peers do not run, and it is strictly HARDER: a title that fails to join fails our metric outright, whereas in a passage-recall regime the same missed node merely lowers recall@k and is often masked by synonym edges (HippoRAG's cosine>0.8) or by the passage still being retrieved via another anchor. This means our carrier-join failures (H631's 5 genuinely-absent, H632's 38 variants) are diagnostic signals invisible to peers, not deficits relative to them - and our headline numbers are not apples-to-apples with published passage-recall figures.

**Hypothesis sketches (D)**
- **D1 - Passage-recall shadow metric**: alongside the carrier-title→node join, compute HippoRAG-style passage recall@k on the same probes so KGF numbers become comparable to published peers. Cost: FREE replay. Control: none (new instrument) - value is comparability, not a score win. Fence: cite H631/H632 (the join is self-imposed; the shadow metric quantifies how much of our carrier-join failure is masked at passage level) - must report BOTH, not replace the join
- **D2 - Synonym-edge join softening**: adopt HippoRAG's cosine>0.8 synonym edges so a variant title joins via an embedding neighbour rather than exact match. Cost: GPU-trivial. Control: the H632 ladder (25/38). Fence: H621 (must not create cross-component false merges - exactly one duplicated normalized name exists graph-wide, so the 0.8 edge budget is tight) and H632 (must beat or match the ladder without the false merges the ladder avoided)

---

## (E) Extraction recall / coverage for absent entities

The genuinely-absent golds are an ingest-time miss, and the literature's answer is multi-pass "gleaning" re-extraction. GraphRAG's mechanism is directly portable and cheap.

- **Microsoft GraphRAG** gleanings: after a chunk's first extraction, feed the extracted entities back and ask the LLM whether entities were missed (logit-bias-100 forced yes/no); on yes, a "MANY entities were missed" continuation prompts a second pass. Lets larger chunks be used without recall loss - a coverage-targeted re-extraction loop
- **link-kg coref KG**: coreference-resolved extraction raises graph completeness - entities named once then referred to as "the device"/"he" fragment or vanish without continuity handling; several of our 5 absent golds are exactly such low-salience entities (`Beatrice I, Countess of Burgundy`, `John Ernest, Duke of Saxe-Eisenach`)
- **REXEL** (`[paper digest] rexel joint relation extraction entity linking.md`): joint document-level extraction captures long-range dependencies that per-chunk extraction drops - a structural argument for wider extraction context
- **neural-EL survey**: extraction recall against a gold entity set is not a standard EL metric (EL assumes mentions given); our carrier-join IS effectively an extraction-recall probe, another reason it has no peer baseline (ties back to D)

Maps to our fences: H631+H632 isolate 5 golds genuinely never extracted (not join artifacts). This is upstream of every linking hypothesis - no linker resolves a node that does not exist. Gleaning is the targeted fix.

**Hypothesis sketches (E)**
- **E1 - GraphRAG gleaning pass on absent-gold chunks**: re-extract the specific source chunks carrying the 5 absent golds with a forced "were entities missed?" continuation. Cost: LLM (5 chunks, trivial). Control: current single-pass extraction (0/5 recovered). Fence: H631 (the 5 are genuinely absent, not join artifacts - so recovery is the only success criterion; do not re-litigate the 4 join artifacts)
- **E2 - Coreference-guided re-extraction**: run link-kg-style coref caching over the absent-gold documents so once-named low-salience entities survive. Cost: LLM or GPU-trivial. Control: single-pass extraction. Fence: H631 (target the 5 absent; measure recovery against that exact set) and H632 (recovered nodes must then JOIN under the variant ladder, else recall gain does not convert to reach)
- **E3 - Extraction-recall shadow metric**: promote the carrier-join into a standing extraction-recall@gold-entity-set gauge, run every ingest. Cost: FREE replay. Control: none (instrument). Fence: H631 (5 absent is the current denominator baseline) - value is a standing coverage signal, ties to D1

---

## Cross-cutting synthesis

- The score-shape axis is closed and the literature agrees it is a dead end: every peer NIL/ranking signal is a magnitude, a prior, a trained classifier, or a cross-encoder re-rank - never curve geometry. The productive re-frames are (i) re-rank the correct candidate list to demote off-gold hubs (A1/A2, from H621), and (ii) threshold on context-entity compatibility, not curve shape (B1)
- Our carrier-title→node join has NO peer analogue; peers evaluate at passage/answer level and mask node misses with synonym edges. Adding a passage-recall shadow metric (D1) makes KGF comparable and quantifies how self-imposed our hardest failures are
- The variant ladder (H632) and type gate (C1) are lightweight instances of standard candidate-generation family (2) + type-constrained matching - well-supported, low-risk to extend
- Absent golds (E) are upstream of all linking work; gleaning (E1) is the cheapest high-value experiment in the fanout

## Sources

New digests written this round:
- `[paper digest] ELQ efficient entity linking for questions.md`
- `[paper digest] neural entity linking survey.md`
- `[paper digest] BLINK zero-shot entity linking.md`

Reused from `references/papers/`: GENRE, ReFinED, Entity Retrieval for Entity-Centric Questions, dual-encoder disambiguation ablation, Microsoft GraphRAG, HippoRAG, HippoRAG 2, LightRAG, 2WikiMultiHopQA dataset, cross-document coref KG, link-kg coref KG construction, REXEL, Query-time Entity Resolution.

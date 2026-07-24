# Neural Entity Linking: A Survey of Models Based on Deep Learning

**Semantic Web Journal 2022 / arXiv 2006.00575, Sevgili, Shelmanov, Arkhipov, Panchenko, Biemann (Hamburg / Skoltech)**. A **43-page** survey organizing neural EL into a generic architecture - candidate generation, mention-context encoding, entity ranking - plus the cross-cutting problems of joint mention-detection+disambiguation, global linking, zero-shot/domain-independence, and NIL (unlinkable-mention) prediction. The reference map for what signals real EL systems use, and specifically for how they decide a mention has NO valid entity.

**Key mechanism**
- Formalizes disambiguation as `ED: (M,C)^n -> (E union NIL)^n` - NIL is a first-class output, either a special entry added to the candidate set or handled by a separate function
- Candidate generation taxonomy (three families): (1) surface-form matching - Levenshtein, n-grams, normalization heuristics over mention strings; (2) alias expansion - dictionaries from Wikipedia redirects, disambiguation pages, the Wikipedia search engine, WordNet synonyms, and even web-search fallback for misspelled/multi-word mentions; (3) prior matching probability - corpus-frequency `P(e|m)` from anchor-text counts
- Entity ranking splits into LOCAL models (mention-context vs entity compatibility) and GLOBAL models (joint coherence of all entity decisions in a document)
- NIL-prediction taxonomy (the reference map, Fig 3): a NIL mention is detected by one of - a THRESHOLD on the top entity score [84,139], a dedicated NIL PREDICTOR head [82], a SEPARATE binary model [107,114], or "no candidate found" => NIL [164,176]

**Main findings**
- No single global-vs-local architecture dominates; global coherence helps documents with many entities, less so short/entity-sparse inputs
- Entity priors (popularity/anchor-text) are a strong but dataset-dependent signal - powerful on common entities, a liability on rare ones (an over-popularity bias)
- Zero-shot linking relies on entity DESCRIPTIONS rather than trained entity embeddings, so entities unseen at train time remain linkable
- NIL is explicitly called out as an open challenge; every listed method attaches the decision to a MEANINGFUL magnitude (top score, a trained head, a prior), none to the shape of the candidate-score curve

**Key takeaways**
- The four NIL mechanisms are all magnitude/classifier-based - a calibrated threshold, a trained head, or "no candidate matched" - which is exactly the family KGF has NOT yet tried after closing the score-shape axis
- Candidate generation is universally recall-first (surface + alias + prior union), precision deferred to the ranker - the classic split
- Alias tables are overwhelmingly Wikipedia-derived (redirects, disambiguation pages, anchor text); a self-extracted graph must synthesize this from the corpus instead

**Relevance to KGF**
- The NIL-prediction taxonomy is the direct catalogue for the (B) sub-problem after the H623/H624/H626 score-shape FENCE closed: the literature's NIL signals are entity-prior magnitude, context-entity compatibility, a trained NIL head, and "no exact match" - candidate hypotheses can draw one from each family and each is orthogonal to the closed shape axis
- Candidate-generation family (2), alias expansion, maps onto the H632/DEF-19 variant ladder (paren-strip / fold / fuzzy) - the survey confirms alias expansion is a first-class candidate-generation stage, not a patch; and family (3), prior probability, motivates the H621 finding that off-gold exact-match HUBS outrank gold (a popularity/degree prior is the missing tiebreaker)
- Confirms the H626 recall-first split: candidate generation stays generous, ranking carries precision - our finding that candidate precision and walk reachability are anti-aligned at the margin is the same lesson stated at the seeding layer

**Tags**
- #EntityLinking #Survey #NILPrediction #CandidateGeneration #AliasExpansion #EntityPrior

**Source**
- Download: https://arxiv.org/abs/2006.00575
- Local: [paper] neural entity linking survey, 2020.pdf

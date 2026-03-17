# Bayesian Entity Resolution: Evidence Fusion and Accumulation

## Posterior over Heuristic Scoring

Entity resolution in KGF uses Bayesian posterior probability rather than ad-hoc weighted scoring. Most KG builders combine similarity signals - name similarity, embedding cosine, description overlap, relationship context - using heuristic weighted sums or rule trees. KGF instead treats these signals as evidence contributing to a posterior probability that two entities represent the same real-world thing.

The posterior is computed as: prior (baseline probability of duplication given ontology compatibility and guide rules) multiplied by likelihood ratios from each evidence channel. The posterior naturally supports three-zone decision logic: high posterior triggers automatic merge, low posterior triggers automatic block, and the middle zone triggers adjudication (currently deferred dedup or LLM escalation).

Three properties that heuristic scoring lacks. First, principled uncertainty handling - the output is interpretable as probability, not an arbitrary score. Second, evidence accumulation is mathematically meaningful - new signals update the posterior via multiplication rather than arbitrary re-weighting. Third, the model is extensible - new signal types plug in as additional likelihood terms without restructuring the scoring logic.

The current cross-type merge threshold is set at 0.6 in ExtractConfig. The prior comes from name identity, and four likelihood ratios (description, embedding, co-occurrence, ontology compatibility) update it. The system currently uses fixed likelihood ratio parameters rather than calibrated ones. Bayesian reasoning for entity resolution exists in research but is rarely used in practical KG builders.

## Multi-Channel Evidence Fusion

Each evidence channel captures a different aspect of entity identity, and their combination produces a richer posterior than any individual signal.

**Current channels**:

- **Lexical similarity** (Levenshtein ratio): Captures surface-level name agreement. Fast to compute, effective for typos and minor variants, but blind to semantic equivalence
- **Embedding cosine similarity**: Captures semantic equivalence from dense vector representations. Handles synonyms and paraphrases but can produce false positives for entities in the same domain
- **Description overlap** (Jaccard): Captures factual agreement between entity descriptions. Strong signal when descriptions share specific details, weak when descriptions are generic
- **Co-occurrence**: Whether entities appear in the same chunks or documents. Entities that co-occur are more likely to be related but not necessarily the same
- **Ontology compatibility**: Whether the entity type pair has a known hierarchy relationship in the ontology buffer. Informs whether cross-type merging is even plausible

The key insight is that agreement or disagreement across channels carries more information than any single channel score. Two pairs may both produce posterior 0.85, but one has strong agreement across all channels while the other has one dominant channel contradicted by three weak ones. The structure of evidence matters as much as the summary.

A disagreement measure across channels (variance of normalized channel-level support scores) provides a second axis for decision-making alongside the posterior. High posterior + low conflict is safe to merge. High posterior + high conflict needs reasoning. This replaces the single-dimensional threshold with a two-dimensional decision surface.

Potential future channels include temporal co-occurrence, ontology distance, extraction confidence, and source trust.

## Positive Evidence Accumulation

Entities accumulate evidence through positive observations over time. Every encounter produces structured traces: canonical attributes (name, identifier, type), fuzzy attributes (spelling variants), contextual attributes (associated organization, document section), relational attributes (connections to other entities in the same chunk), and provenance signals (source document, extraction model, confidence score). Nothing negative is stored - only evidence that "this entity was seen with these properties."

An entity initially has only a name. Later extractions add a description, then a relationship to a manufacturer, then a specification value, then a co-occurrence with another known entity. Each new trace makes the entity profile richer and future comparisons more decisive. The posterior probability for merge decisions improves naturally as entities accumulate more observations. The threshold does not need to move - the probability distribution shifts because the evidence supporting or contradicting a merge becomes stronger.

When evidence is insufficient at first encounter, entity pairs enter the deferred dedup buffer. As more documents are ingested, both entities accumulate additional traces. When the deferred pairs are re-evaluated, the richer profiles produce more confident posteriors, resolving cases that were genuinely ambiguous at first sight.

The graph itself generates delayed evidence. A mistaken merge eventually produces contradictions - incompatible attributes, temporal impossibilities, or duplicate identifiers in the merged entity profile. These contradictions are the real learning signal for calibration, not the merge decisions themselves. The system gets better at resolution not by tuning parameters, but by accumulating more evidence per entity.

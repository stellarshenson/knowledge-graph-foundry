# NELL - Toward an Architecture for Never-Ending Language Learning

**AAAI 2010 (CMU, Carlson et al.)**. The canonical two-tier speculative knowledge base: a system that reads the web 24/7, holding every extraction as a CANDIDATE FACT and promoting only the strongly supported ones to BELIEF status. **242,453 beliefs at ~74% estimated precision after 67 days** from a 500M-page / 2B-sentence corpus.

**Key mechanism**: four coupled extractors (pattern learner CPL, wrapper learner CSEAL, morphology classifier CMC, rule learner RL) propose candidates; the Knowledge Integrator promotes a candidate when a single source gives **posterior > 0.9**, or when MULTIPLE independent sources propose it; mutual-exclusion and type constraints VETO promotion (a candidate is not promoted into a category mutually exclusive with one it already holds; relation instances require argument types to be at least candidates). Beliefs feed back as training data for the next iteration - the committed tier bootstraps the speculative tier.

**Main findings**: coupling many weak extractors with constraint vetoes keeps a self-training loop from collapsing for months; the paper's admitted flaw is directional commitment - **once promoted, a belief is never demoted** in that implementation, and precision erodes over iterations (errors compound as promoted noise re-trains extractors).

**Key takeaways for KGF**: the origin design for candidate/committed tiers with explicit promotion rules - multi-source agreement OR high single-source posterior, plus ontology vetoes - maps directly onto a speculative edge tier feeding KGF's Bayesian resolver. NELL's never-demote flaw is the negative lesson KGF already answered elsewhere (demotion court, demote-don't-delete): promotion must be reversible or the speculative tier's errors become permanent truth.

**Tags**: two-tier-kb, candidate-promotion, never-ending-learning, constraint-veto, provisional-knowledge
**Source**: http://rtw.ml.cmu.edu/papers/carlson-aaai10.pdf (PDF: `[paper] NELL Never-Ending Language Learning, 2010-07.pdf`)

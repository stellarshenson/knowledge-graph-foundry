**STAGG: Semantic Parsing via Staged Query Graph Generation - Question Answering with Knowledge Base (2015)**

STAGG reframes KBQA semantic parsing as search over query graphs - tree structures that resemble KB subgraphs and map directly to executable logical forms - rather than search over an abstract logical-form grammar decoupled from the KB. By pulling KB structure into the search process from the first stage (entity linking) instead of only at execution time, STAGG prunes the search space early and simplifies the semantic-matching problem that follows. The system reaches **52.5% F1** on WebQuestions, a **7.2-point absolute gain** over the prior state of the art, and the paper's staged design lets each contributing component be measured in isolation.

**Key mechanism**
- A query graph has one topic-entity root, one answer node (lambda variable) connected by a directed core inferential chain of zero-or-more existential variables, plus optional entity/aggregation branches attached to any chain node as additional constraints
- Generation is a four-stage best-first search over a finite state machine: (1) topic entity linking, (2) core inferential chain construction, (3) constraint attachment, (4) aggregation node attachment - each stage's action set depends only on the current partial graph's state
- A custom entity linker built for short, noisy queries (surface-form lexicon from names, aliases, anchor text, Wikipedia redirects) replaces generic entity-linking APIs and is evaluated as an independent, swappable stage
- The core inferential chain is scored by a deep convolutional neural network that matches the question text against candidate predicate sequences (PatChain), refined by two additional CNN signal sources (QuesEP, ClueWeb)
- A log-linear reward function estimates the likelihood a candidate query graph correctly parses the question; search proceeds with a priority queue under this reward

**Main findings**
- Full system: **52.5% F1** on WebQuestions, a 7.2-point absolute improvement over prior state of the art
- Entity linking component alone: 9,147 candidate entities cover **99.8%** of training questions vs 19,485 candidates from the Freebase Search API covering 98.8% - roughly half the candidate volume for equal-or-better coverage, and 87.8% vs 81.2% coverage of gold topic entities
- Swapping the custom entity linker for the Freebase API drops end-to-end F1 from 52.5% to 48.4% (a **4.1-point** degradation), showing the first stage dominates downstream accuracy
- Core-inferential-chain-only ablation (dropping constraint/aggregation stages): PatChain alone reaches 49.6% F1; adding QuesEP and ClueWeb sequentially reaches **51.8% F1**, within 0.7 points of the full staged system
- 1,888 questions (50.0% of the set with chain-only graphs) are answerable exactly by the chain alone, showing many real questions do not need the full constraint-attachment machinery

**Key takeaways**
- Staging the search so each stage's valid-action set is constrained by the KB (not just the surface grammar) prunes the space early and lets weaker per-stage signals compose into a strong end-to-end result
- Entity linking is not a preprocessing afterthought - it is the single highest-leverage stage, and errors here cannot be recovered downstream
- A chain-first, constraints-second decomposition captures the bulk of real-question structure; full constraint search is needed for a shrinking tail of harder cases, suggesting a cost/accuracy dial rather than an all-or-nothing search
- The finite-state-per-stage design (structurally legal actions only, defined by the KB schema) is the direct ancestor of the "enumerate then score" pattern later formalized in discriminative frameworks like Pangu

**Relevance**
- STAGG's typed, staged query-graph construction is a direct historical precedent for R50's typed/topology retrieval question - the core-inferential-chain-first strategy is a template for a cheap first-pass topology filter before constraint-heavy refinement
- Entity-linking-as-bottleneck finding reinforces that identity resolution quality gates everything downstream in graph retrieval, consistent with KGF's own identity-root-cause findings

**Tags**
- #KBQA
- #SemanticParsing
- #QueryGraph
- #StagedSearch

**Source**
- Download: https://aclanthology.org/P15-1128/
- Local: [paper] STAGG staged query graph generation, 2015.pdf

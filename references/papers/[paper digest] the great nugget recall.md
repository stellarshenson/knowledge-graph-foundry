**The Great Nugget Recall: Automating Fact Extraction and RAG Evaluation with LLMs (2025)**

The paper revives the TREC QA 2003 "nugget" evaluation methodology - scoring answers by which atomic facts they cover, not by surface overlap with a reference answer - and fully automates it with LLMs end to end. AutoNuggetizer both creates the nugget list (the atomic facts a good answer should contain) and assigns system answers against it, replacing the expensive human nugget-authoring and human-assignment steps used in prior TREC RAG tracks. Calibrated against human-created nuggets and manual assignments from the TREC 2024 RAG Track, the fully automatic pipeline shows **strong run-level agreement** with the human-based variants.

**Key mechanism**
- Nugget creation: an LLM reads the reference/qrel material for a topic and extracts a list of atomic, independently-verifiable facts ("nuggets") that a complete answer should cover
- Nugget assignment: a second LLM pass checks each system-generated answer against every nugget in the list, marking it covered / not covered
- Independent-component design - creation and assignment run as separate LLM calls rather than a single cascaded chain, which the paper finds improves agreement with human judgments
- Nugget recall becomes the scoring metric per topic: fraction of nuggets covered by the system's answer, aggregated across topics for a run-level score
- Direct calibration against TREC 2024 RAG Track's human-created nugget lists and human assignment judgments as ground truth

**Main findings**
- Run-level scores from the fully automatic AutoNuggetizer pipeline show strong agreement with scores from human-created nuggets plus human assignment
- Agreement improves when nugget creation and nugget assignment are run as independent LLM calls rather than cascaded (errors in one stage don't compound into the other)
- Per-topic agreement is weaker than run-level agreement - the automatic pipeline is reliable enough to rank systems in aggregate but not yet reliable enough to diagnose a specific topic's failure
- The authors explicitly flag this per-topic gap as unresolved, requiring further work to make nugget recall trustworthy at the single-question level

**Key takeaways**
- Nugget recall is expensive ground truth (per-fact, LLM-adjudicated) but the paper shows an automatable path to it - useful as the "gold" a cheaper proxy metric should validate against, not as a metric to run at scale itself
- Run-level reliability without per-topic reliability is exactly the granularity mismatch a cheap reachability proxy needs to be honest about - aggregate correlation does not certify single-query correctness
- The independent-component (no cascading) design pattern generalizes: chaining LLM judgment stages compounds error, running them independently and reconciling after does not

**Relevance**
- Provides the expensive per-fact ground truth that KGF's cheap reachability proxy (graph-traversal reachability as a stand-in for actual fact coverage) needs to be benchmarked against before trusting it at scale
- The per-topic vs. run-level agreement gap is a direct warning: KGF should not assume a proxy validated in aggregate diagnoses individual query failures

**Tags**
- #RAGEvaluation
- #NuggetRecall
- #LLMAsJudge
- #FactExtraction

**Source**
- Download: https://arxiv.org/pdf/2504.15068
- Local: [paper] the great nugget recall, 2025.pdf

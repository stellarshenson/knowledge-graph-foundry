**Corrective Retrieval Augmented Generation (CRAG), Yan, Gu, Zhu, Ling, 2024 (arXiv 2401.15884)**

The route-to-source precedent: a lightweight retrieval evaluator grades what retrieval returned and, on low confidence, abandons the corpus and searches the web instead. On PopQA accuracy **59.8 vs 52.8** for standard RAG (SelfRAG-LLaMA2-7b generator); Self-CRAG **61.8 vs Self-RAG 54.9**; PubHealth **75.6 vs 39.0**. Plug-and-play, no generator retraining.

**Key mechanism**
- Fine-tuned T5-large evaluator scores each (query, retrieved doc) pair → confidence aggregated into 3 actions: Correct (refine and use), Incorrect (discard ALL retrieved docs, rewrite query, web-search instead), Ambiguous (combine both)
- Decompose-then-recompose refinement: split retrieved docs into strips, score each, drop irrelevant strips, concatenate survivors - context distillation before generation
- Two-action-only ablation is brittle - the Ambiguous middle band absorbs evaluator error; the 3-band design is what makes a mediocre evaluator usable
- Explicit framing: "a system that knows what it doesn't know and what it cannot answer is more intelligent than one that clings to limited knowledge"

**Main findings**
- Corrective actions transfer across generators (LLaMA2-hf-7b, SelfRAG-7b) and pair multiplicatively with Self-RAG
- The evaluator judges RETRIEVED DOCUMENTS ONLY - it infers corpus insufficiency indirectly from bad retrievals, it never consults any corpus-side coverage record
- Web search as the external knowledge extension, with query rewriting into keyword form

**Key takeaways**
- Closest published shape to a coverage-conditioned bridge - and still query-time-only: the corpus's own coverage accounting stays unread; KGF's certified-miss ledger (R39-H389/H394) would give this decision an ingest-time ground truth CRAG has to guess at
- The 3-band trigger maps onto KGF's miss/escalation-band/answer structure (R19-H181 + R37-H382) - the bands exist; what KGF lacks is the route-to-source action
- Strip-level refinement is a render-side idea KGF already approximates with query-anchored spans (R34-H366)

**Tags**: #CRAG #CorrectiveRAG #RetrievalEvaluator #RouteToSource #Abstention #SelfAwareRAG

**Source**: https://arxiv.org/abs/2401.15884. Local: [paper] CRAG Corrective RAG, 2024-01.pdf

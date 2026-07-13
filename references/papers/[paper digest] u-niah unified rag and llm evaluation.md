**U-NIAH: Unified RAG and LLM Evaluation for Long Context Needle-in-a-Haystack (2025)**

The paper argues that classic needle-in-a-haystack (NIAH) tests conflate two different capabilities - whether a fact is *present* in the context window and whether the model can *find* it once retrieval noise is added - and that LLM-only benchmarks systematically overstate real RAG performance because they never test retrieval noise at all. U-NIAH extends NIAH with multi-needle, long-needle, and needle-in-needle configurations plus a synthetic "Starlight Academy" corpus built to eliminate pre-training contamination, then evaluates LLM-alone vs. RAG-augmented answering side by side. Under matched conditions, RAG achieves an **82.58% win-rate** over LLM-alone answering for smaller models, but the advantage erodes as retrieval noise and reasoning demands increase.

**Key mechanism**
- Synthetic fictional corpus (Starlight Academy universe) removes any chance the model already "knows" the needle from pretraining
- Three NIAH variants stacked on top of the classic single-needle test: multi-needle (several facts scattered across context), long-needle (the fact itself spans many tokens), needle-in-needle (a fact nested inside a distractor passage)
- Retrieval-noise injection - irrelevant or semantically similar chunks mixed into RAG context at controlled rates, plus reversed/shuffled chunk ordering to test position sensitivity
- Same question set run twice - full-context LLM vs. retrieval-augmented pipeline - isolating the "presence" effect from the "findability" effect
- Failure-mode taxonomy hand-labeled from transcripts, not just accuracy scoring

**Main findings**
- RAG mitigates the well-known "lost-in-the-middle" effect and improves robustness to long context relative to feeding the full document directly
- RAG win-rate of **82.58%** holds for smaller/weaker LLMs; the gap narrows for stronger reasoning-tuned models
- Advanced reasoning LLMs show reduced RAG compatibility - they are more sensitive to semantic distractors mixed into retrieved context, sometimes performing worse with retrieval than without
- Three dominant RAG failure modes identified: omission errors under noise, hallucination under high-noise conditions, and self-doubt (correct evidence retrieved but the model second-guesses and produces a wrong answer anyway)
- Performance degrades measurably as retrieval noise ratio and chunk-order disruption increase, even when the correct needle remains somewhere in context

**Key takeaways**
- "In context" and "findable" are separable failure axes - a benchmark that only checks presence (can the fact be found anywhere in the prompt) will not predict RAG accuracy under realistic retrieval noise
- Stronger base models are not uniformly better RAG consumers - reasoning capability can increase sensitivity to distractors, an inversion worth checking against KGF's own retriever
- Failure-mode taxonomy (omission / hallucination / self-doubt) is a reusable lens for post-hoc error analysis on KGF's own retrieval traces, independent of the synthetic corpus

**Relevance**
- Directly externalizes the REG-2 lesson: presence-in-graph is not the same as retrievability under noise, and KGF's reachability proxies should be validated against a noise-injected variant, not just a clean-context one

**Tags**
- #RAGEvaluation
- #LongContext
- #NeedleInHaystack
- #RetrievalNoise

**Source**
- Download: https://arxiv.org/pdf/2503.00353
- Local: [paper] u-niah unified rag and llm evaluation, 2025.pdf

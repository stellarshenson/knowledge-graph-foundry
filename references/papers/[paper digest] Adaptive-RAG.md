**Adaptive-RAG: Learning to Adapt Retrieval-Augmented LLMs through Question Complexity, Jeong, Baek, Cho, Hwang, Park, NAACL 2024 (arXiv 2403.14403)**

The external-router pole of adaptive retrieval. A small trained classifier predicts per-query complexity and routes to one of **3** strategies: no retrieval (A), single-step retrieval (B), or iterative multi-step retrieval (C). On open-domain QA spanning single-hop and multi-hop datasets, matches or beats the always-multi-step approach (GPT-3.5 F1 ~51 vs ~50) at substantially lower latency, and beats prior adaptive-retrieval baselines on the accuracy-efficiency frontier.

**Key mechanism**
- Complexity classifier: a smaller LM (T5-large) trained to emit A/B/C labels for incoming queries
- Training labels collected automatically - no human annotation: label = the cheapest strategy that actually answered the query correctly (predicted-outcome supervision), plus dataset inductive biases (single-hop sets lean B, multi-hop sets lean C)
- Router runs BEFORE generation - one cheap forward pass decides the retrieval budget for the whole query
- Escalation is between whole pipelines, not within one generation (contrast FLARE's token-level trigger)

**Main findings**
- Uniform strategies are dominated: always-simple fails complex queries, always-iterative wastes compute on simple ones
- The learned router beats heuristic and self-ask style routing on both accuracy and time per query
- Outcome-labeled supervision (which rung sufficed in practice) is enough to train the router - the need signal is learnable from replay data

**Key takeaways**
- Escalation-need labels can be harvested from measured outcomes - exactly what KGF's probe replay produces (which probes needed which rung)
- A pre-generation router is the cheapest signal placement: decide budget before paying any LLM cost
- For KGF-H382: complements FLARE - route-then-generate (this paper) vs generate-then-check (FLARE) are the two placements of the sufficiency gate

**Tags**: #AdaptiveRAG #QueryComplexity #Routing #RetrievalBudget #NAACL

**Source**: https://arxiv.org/abs/2403.14403. Local: [paper] Adaptive-RAG, 2024-03.pdf

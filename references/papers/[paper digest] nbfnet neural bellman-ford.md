**Neural Bellman-Ford Networks: A General GNN Framework for Link Prediction (2021)**

NBFNet is the path-based GNN that ULTRA builds on. It generalizes the Bellman-Ford algorithm by learning its operators, producing pair-representations between a source and all targets. The path formulation makes it inductive and interpretable - learned path weights expose which relational paths justify a predicted link - and it set SOTA on standard link-prediction splits at publication.

**Key mechanism**
- Generalizes Bellman-Ford by learning three operators: INDICATOR (boundary condition), MESSAGE (edge operator), AGGREGATE (summation)
- Operators are applied over pair-representations between the source and all targets
- Reasons over relation paths, not fixed entity embeddings, making it inductive
- Learned path weights expose which relational paths justify a predicted link

**Main findings**
- SOTA on standard link-prediction splits at publication
- Path formulation is simultaneously inductive, interpretable, and scalable

**Key takeaways**
- Per-prediction evidence paths are a native output, not a bolt-on
- Trained per relation-vocabulary, so not zero-shot transferable on its own
- ULTRA is the deployable, transferable form of this mechanism

**Relevance**
- For self-auditing and the gap ledger, per-prediction evidence paths matter - a plausibility score is more actionable when the relational path supporting or contradicting an edge is exposed, enabling source-grounded repair
- Caveat: trained per relation-vocabulary, not zero-shot transferable; ULTRA is the deployable form

**Tags**
- #LinkPrediction #GNN #PathReasoning #Interpretability

**Source**
- Download: https://arxiv.org/pdf/2106.06935
- Local: [paper] nbfnet neural bellman-ford, 2021.pdf

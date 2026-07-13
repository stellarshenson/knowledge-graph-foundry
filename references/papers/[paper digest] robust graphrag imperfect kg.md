**Toward Robust GraphRAG: Mitigating Retrieval Drift and Hallucination from Imperfect Knowledge Graphs (Ma et al., 2026)**

Introduces **CS-RAG**, a multi-hop GraphRAG retrieval framework tested across **three multi-hop QA benchmarks**, built on the empirical finding that LLM-constructed knowledge graphs are systematically imperfect in two distinct ways: **spurious noise** (extraneous triples that pull retrieval toward unsupported paths) and **incompleteness** (missing triples that starve retrieval of support), each degrading answer quality through a different failure mode.

Key mechanism:
- Plans each query as an ordered sequence of atomic constraints rather than a single dense retrieval pass
- Performs anchor-aware and relation-aware retrieval to keep traversal grounded to query-relevant subgraphs
- Applies a sufficiency check at each step to test whether retrieved evidence actually supports the variable binding required by that constraint
- When structural (graph) support is insufficient, falls back to textual recovery from source passages instead of continuing to hallucinate over an incomplete graph
- Mitigates the impact of KG imperfection at retrieval time, explicitly not by attempting to repair the KG itself

Main findings:
- Noise (spurious triples) and incompleteness (missing triples) produce measurably different degradation patterns - drift toward wrong-but-plausible answers versus hallucinated continuation - and require different mitigations (constraint sufficiency checks versus textual fallback)
- CS-RAG holds up across different KG builder choices and under controlled, injected KG degradation, whereas baseline multi-hop GraphRAG retrieval degrades sharply as injected noise/incompleteness increases

Key takeaways (relevance to KGF): confirms that KG quality defects (noise, incompleteness) causally propagate into retrieval drift and hallucination rather than being absorbed harmlessly downstream - this is the empirical anchor that keeps H547 (KG defects → retrieval drift) genuinely falsifiable rather than assumed. The retrieval-time mitigation stance (sufficiency checks + textual fallback, no KG repair) is also a useful contrast point against KGF's ingest-time repair-first philosophy.

Tags: graphrag, multi-hop-qa, kg-quality, retrieval-drift, hallucination, kg-noise

Source: https://arxiv.org/abs/2603.14828

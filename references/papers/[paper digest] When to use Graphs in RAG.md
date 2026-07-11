**When to use Graphs in RAG: A Comprehensive Analysis for Graph Retrieval-Augmented Generation, Xiang et al., 2025 (arXiv 2506.05690, GraphRAG-Bench)**

The closest published treatment of GRAPH-STRUCTURE metrics as predictors of GraphRAG usefulness: builds GraphRAG-Bench (4,076 questions, novel + medical corpora) explicitly because existing benchmark corpora yield graphs too sparse and fragmented to reward graph methods, and quantifies that sparsity with structure-based graph quality metrics.

**Key mechanism / metrics catalog**
- Per-corpus structural profile: avg entities and relations per 1k tokens, **proportion of non-isolated entities**, average degree, proportion of entities with degree > 1/2/3, geometric-mean connected-component size, clustering coefficient
- Measured baseline profiles: HotpotQA graph - non-isolated proportion **0.41**, avg degree **0.65**, avg component size **2.11**, degree>3 share 0.06; UltraDomain 0.40 / 0.86 / 2.71; the purpose-built GraphRAG-Bench novel corpus reaches 0.66 / 2.27 / 3.99
- Verdict mechanism: on sparse fragmented graphs, graph-based organization cannot support retrieval - GraphRAG only pays when connectivity and component size are high enough; expanding retrieval coverage on noisy graphs raises recall but drops relevance and final accuracy

**Main findings**
- Graph value is CONDITIONAL on measurable structure: low non-isolated share (~40%) and tiny components (~2-3 entities) predict that graph retrieval adds noise, not signal
- Different question classes couple to different structure: multi-hop/complex-reasoning questions need connected components spanning the hop chain; fact-retrieval barely uses the graph

**Key takeaways**
- Publishes the reference values KGF can compare against: the 2wiki 200-doc pile (1,389 entities, 3,433 rels) should be profiled with the same seven metrics per document checkpoint - non-isolated share and component-size trajectories are the retrieval-coupled structural series with published grounding
- Directly relevant to REG-1: a two-film comparison question is the multi-hop class whose answerability depends on BOTH films' components containing their director chains - component-membership tracking of gold entities over ingest is the mechanism-level instrument
- No published system tracks these metrics DURING ingestion or couples them to a live prober - static corpus profiling only; the dynamic version is open

**Tags**: #GraphRAG #GraphQualityMetrics #Connectivity #ComponentSize #RetrievalCoupling

**Source**: https://arxiv.org/abs/2506.05690. Local: [paper] When to use Graphs in RAG, 2025-06.pdf

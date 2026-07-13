**Less Is More: Denoising Knowledge Graphs for Retrieval-Augmented Generation (2025)**

DEG-RAG applies entity resolution and LLM-as-judge triple filtering to LLM-generated knowledge graphs before they feed a Graph-RAG system, and shows the cleaned, **~40% smaller** graph beats the noisy original in most dataset/method/metric combinations across four Graph-RAG systems (LightRAG, HippoRAG, LGraphRAG, GGraphRAG) and four UltraDomain datasets. LightRAG's Diversity-dimension winning rate against the noisy baseline jumps from **41.60% to 58.40% (Agriculture)**, **40.00% to 60.00% (CS)**, and **40.80% to 59.20% (Mix)** after denoising, and on Mix/Legal performance stays comparable to the original graph even at up to 70% entity reduction.

**Key mechanism**
- Entity resolution runs three stages: blocking (semantic k-means over description embeddings, entity-type grouping, or structural blocking by shared-neighbor sets), matching and grouping (KG-embedding or LLM-embedding similarity over ego-node, neighbor-only, type-aware-neighbor, or ego+neighbor representations), and merging and linking (direct merge into one canonical entity, synonym-edge-only linking, or merge-plus-synonym-edge)
- Triple reflection independently filters relations: an LLM-as-judge assigns each (subject, relation, object) triple a reliability score, and triples below a threshold δ_TR (0.2 default) are dropped
- Formal result (Proposition 1, proved in the appendix): without entity resolution, a graph-based RAG system provably degenerates into a union of disconnected per-chunk subgraphs with no cross-document edges, which is functionally equivalent to vanilla passage-level RAG - entity resolution is the sole mechanism that creates the cross-document connectivity graph-RAG depends on for any benefit over vanilla RAG
- Default configuration: 40% entity reduction ratio, δ_TR=0.2, semantic-based blocking, LLM embeddings (Qwen3-Embedding-8B) for matching, ego-based similarity, direct merging

**Main findings**
- Entity type-based blocking outperforms both semantic (k-means) and structural (shared-neighbor) blocking - entity type is a stronger, more natural inductive bias for grouping candidates than embedding proximity or local topology alone
- Traditional KG embeddings (ComplEx) rival or beat LLM embeddings for the matching step, especially on Legal and Agriculture, offering a cheaper substitute when LLM embedding budget is constrained
- Ego-node similarity alone is necessary for good matching; adding neighbor information (ego+neighbor) helps further on Legal and Mix, but neighbor-only similarity underperforms ego-only in most settings
- Direct merging beats synonym-linking-only: synonym edges leave the graph just as redundant and just as many hops deep as before, only adding pointer edges rather than consolidating structure, while direct merging shortens the multi-hop paths retrieval depends on
- Robust across a wide reduction range - winning rate stays at or above 50% up to 60-70% entity reduction on Mix and Legal before degrading, meaning the denoising step tolerates aggressive merging as long as coarse-grained semantics are preserved
- Ablation confirms mechanism over mere size reduction: dropping entity resolution hurts performance more than dropping triple reflection, and random (similarity-blind) merging performs worse than either partial method alone
- HippoRAG shows the weakest gains on Legal and Mix, attributed to its entity nodes carrying only bare names with no textual description, which starves the entity-resolution matching signal

**Key takeaways**
- Entity resolution, not triple filtering, is the primary quality lever for LLM-generated knowledge graphs in Graph-RAG systems
- The strongest configuration found is type-aware blocking, ego(+neighbor) similarity, and direct merging - each choice independently and empirically outperforms its alternatives
- Classical KG embeddings are a legitimate, cheaper substitute for LLM embeddings at the matching step, not merely a fallback

**Relevance**
- This is the most directly on-topic paper of the batch: Proposition 1 formalizes that entity resolution is exactly the mechanism turning a disconnected union of per-chunk extraction subgraphs into a genuinely traversable typed graph - the same thesis underlying KGF's own R49 ingestion-reconciliation round
- The empirical blocking ranking (entity-type > semantic > structural) is a direct, reusable prior for any KGF blocking/candidate-generation step that feeds typed or topology matching
- The direct-merge-beats-synonym-link finding argues against leaving SAME_AS/synonym edges unresolved in the graph when the goal is shorter multi-hop retrieval paths - consolidation, not pointer-linking, is what shortens the graph

**Tags**
- #EntityResolution
- #KnowledgeGraphDenoising
- #GraphRAG
- #TypedBlocking
- #TripleFiltering

**Source**
- Download: https://arxiv.org/pdf/2510.14271
- Local: [paper] DEG-RAG Denoising Knowledge Graphs, 2025.pdf

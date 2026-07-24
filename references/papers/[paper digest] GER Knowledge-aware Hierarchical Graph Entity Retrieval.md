**Modeling Fine-grained Information via Knowledge-aware Hierarchical Graph for Zero-shot Entity Retrieval (GER), Wu, Bai, Guo, Liu, Li, Yang (Tsinghua SIGS / Tencent), WSDM 2023 (arXiv 2211.10991)**

The retrieval-side evidence that coarse entity embeddings under-serve low-salience entities and that fine-grained, neighbourhood-aggregated node features fix it - the entity-surfaceability mechanism for family 3. Standard zero-shot entity retrieval encodes a mention/entity as one sentence embedding; GER argues this washes out entities whose attention scores are low (exactly the "starved entity" case), and instead builds a mention/entity-centred graph of extracted knowledge units aggregated by a hierarchical graph-attention network.

**Key mechanism**
- Extract "knowledge units" from an entity's context and build an entity-centralized graph (the entity's local neighbourhood as explicit nodes)
- Hierarchical Graph Attention Network (HGAN) aggregates unit-level information into a fine-grained entity representation, with a hierarchy to avoid the graph bottleneck at the central node
- Fine-grained features are COMPLEMENTARY to the sentence embedding, not a replacement - concatenated/fused for the final retrieval representation

**Main findings**
- Beats prior SOTA sentence-embedding entity retrievers on standard zero-shot benchmarks
- The gain concentrates where sentence-level attention to the entity is LOW - i.e. exactly the under-represented/starved entities coarse embeddings miss
- Neighbourhood aggregation (not longer text alone) is what recovers those entities; the hierarchy matters (flat aggregation hits a bottleneck)

**Relevance to KGF**
- Direct family-3 mechanism: a starved entity's dense rank improves when its representation aggregates its graph NEIGHBOURHOOD, not just its own (absent) description - the retrieval-side counterpart to KELM/TAPE text generation, and it names the beneficiary population (low-salience entities = our missed carriers)
- Sharpens the text-vs-embedding question: GER enriches on the ENTITY-representation side via structural aggregation; combined with H627 (score/embedding smoothing) it suggests neighbourhood aggregation is the common thread - our confirmed one-step smoothing is a lightweight version of exactly this
- Its "gain concentrates on low-attention entities" claim is the hypothesis R57-H648 tests on our data: if hit/miss carriers do NOT separate on entity features, this mechanism has no purchase here (H648 KILL < 0.55 both axes deprioritizes the whole family)
- Cost tier GPU-trivial-to-LLM: neighbourhood aggregation can be a fusion of existing embeddings (trivial) or re-encoding enriched text (LLM); honest control is anchor-reset 0.8661/131 dense@16 seeding

**Tags**: #GER #EntityRetrieval #NeighbourhoodAggregation #StarvedEntities #EntityStrengthening #AmplificationFamily3

**Source**: https://arxiv.org/abs/2211.10991. Local: [paper] Knowledge-aware Hierarchical Graph Zero-shot Entity Retrieval, 2022.pdf

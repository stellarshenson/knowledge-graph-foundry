**LEC-KG: An LLM-Embedding Collaborative Framework for Domain-Specific Knowledge Graph Construction, Zeng, Piao, Pei, Li, arXiv 2602.02090, 2026**

LEC-KG couples LLM extraction with Knowledge Graph Embeddings (KGE) in a bidirectional loop, evaluated on Chinese Sustainable Development Goal (SDG) reports where it shows the largest gains on **low-frequency (long-tail) relations** - the class of relation domain-specific KGs struggle with most.

**Key mechanism**
- Hierarchical coarse-to-fine relation extraction reduces long-tail relation bias by first classifying a broad relation category, then refining within it
- Evidence-guided Chain-of-Thought feedback grounds every structural suggestion (KGE-proposed edge) back in an exact-match source sentence before it is accepted, giving each candidate triple a deterministic textual carrier rather than a free-floating embedding score
- Semantic initialization lets KGE validate structure for entities unseen during training, using LLM-derived embeddings as a cold-start prior
- The two modules iterate: KGE gives structure-aware feedback that refines LLM extractions, and validated triples progressively improve KGE representations

**Main findings**
- Substantial improvement over LLM-only baselines, concentrated on low-frequency relations where trained extractors and single-pass LLM extraction both degrade
- Iterative refinement reliably converts unstructured policy text into validated triples without a fixed schema
- Structural (KGE) feedback and textual (LLM) feedback are complementary - neither alone matches the combined loop

**Key takeaways**
- The evidence-guided CoT step is the deterministic carrier-choosing mechanism: an entity's candidate relation is only accepted once it resolves to an exact-match sentence, giving H569 a concrete precedent for picking a single grounding sentence over ranking by embedding similarity alone
- Coarse-to-fine relation classification is a reusable pattern for KGF's long-tail relation types, where a first-pass coarse label narrows the candidate schema before fine-grained typing

**Tags**: #KnowledgeGraphConstruction #KGEmbeddings #EntityLinking #LongTailRelations #ChainOfThought

**Source**: https://arxiv.org/abs/2602.02090. Local: [paper] lec-kg llm-embedding collaborative kg, 2026.pdf

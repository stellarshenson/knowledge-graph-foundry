# OntoType: Ontology-Guided and Pre-Trained Language Model Assisted Fine-Grained Entity Typing

- **Authors**: Tanay Komarlu, Minhao Jiang, Xuan Wang, Jiawei Han
- **Venue**: KDD 2024 (30th ACM SIGKDD Conference on Knowledge Discovery and Data Mining)
- **URL**: https://arxiv.org/abs/2305.12307
- **Key contribution**: Coarse-to-fine entity typing using type hierarchy as structural prior. The ontology defines parent-child subsumption relationships between types, and the model resolves entities from coarse (parent) to fine (child) types progressively. Zero-shot approach that leverages type hierarchy structure for disambiguation without requiring labeled training data.
- **Relevance to H5g**: Direct inspiration for hierarchy-based auto-merge in cross-type resolution. When two types share a parent in the hierarchy, the system can confidently merge entities rather than treating them as distinct. The coarse-to-fine resolution strategy maps to our frequency-based type priority selection within sibling groups.

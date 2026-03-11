# Ontology-Grounded Automatic Knowledge Graph Construction by LLM under Wikidata

- **Authors**: Feng et al.
- **Venue**: KDD Workshop 2024
- **URL**: https://arxiv.org/abs/2412.20942
- **Key contribution**: Uses Wikidata ontology as grounding reference for LLM-based knowledge graph construction. Demonstrates that ontology grounding improves type disambiguation accuracy by providing structural context (IS_A hierarchies, property constraints) that guides the LLM toward consistent type assignments.
- **Relevance to H5g**: Validates ontology-grounded type disambiguation as a strategy for reducing cross-type duplicates. The approach of using hierarchy structure to resolve ambiguous type assignments (rather than relying solely on textual similarity) directly informs the hierarchy safety-net in `_resolve_cross_type()`.

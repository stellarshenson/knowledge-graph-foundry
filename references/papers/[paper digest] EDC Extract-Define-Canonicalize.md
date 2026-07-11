# Extract, Define, Canonicalize: An LLM-based Framework for Knowledge Graph Construction (EDC)

**Authors**: Bowen Zhang, Harold Soh (NUS)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2404.03868

**Publication date**: 2024-04-05 (first arXiv version; EMNLP 2024)

## Summary

- Three-phase KG construction decoupling extraction from schema: (1) **Extract** - open (schema-free) triple extraction, (2) **Define** - the LLM writes a natural-language definition for every schema component its own extractions induced, (3) **Canonicalize** - definitions drive standardization so semantically equivalent entities/relations converge to one phrase, either mapped onto a target schema or self-canonicalized when none exists
- Solves the schema-in-prompt bottleneck: prior constrained extraction must stuff the ontology into the prompt; large schemas exceed context - EDC handles schemas with **thousands of relation types** via a trained **Schema Retriever** (embedding model retrieving relevant schema components per input)
- Optional refinement loop (EDC+R): re-extract with previously canonicalized triples and retrieved schema as hints - a second pass measurably improves triple quality on all three benches (WebNLG ~1,165 pairs, REBEL, Wiki-NRE)
- Open extraction FIRST, typing SECOND: recall is captured before the ontology constrains anything; canonicalization then restores type discipline post-hoc
- No parameter tuning of the extractor LLM required; only the Schema Retriever is trained

**Relevance to Knowledge Graph Foundry**: The published counter-ordering to KGF's cure-then-constrain pipeline: KGF discovers an ontology then extracts under it (constrained recall), EDC extracts free then canonicalizes into the schema (post-hoc typing). Directly grounds a testable question - does KGF's 26-type constrained extraction DROP facts an open first pass would catch? EDC's define-then-canonicalize step is also a principled upgrade path for KGF's alias/synonym layer (definitions, not just embeddings, decide equivalence).

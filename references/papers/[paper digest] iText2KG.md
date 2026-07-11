# iText2KG - Incremental KG construction with matched-entity context injection

**arXiv 2409.03284 (2024, WISE)**. Zero-shot incremental KG construction: Document Distiller → Incremental Entity Extractor → Incremental Relation Extractor → Graph Integrator. Each increment resolves newly extracted entities against the EXISTING graph (cosine matching, merge-threshold experiments around **0.6-0.7**) and - the load-bearing experiment for KGF - feeds matched entities back as CONTEXT for relation extraction.

**Key mechanism**: entities extracted per document are matched to global (already-committed) entities by embedding similarity; relation extraction is then conditioned either on GLOBAL matched entities (the graph's canonical set) or only on LOCAL entities (this document's surface forms).

**Main findings**: the global-vs-local context A/B is a measured anchoring cost - triple precision with global-entity context is **~10% LOWER** than with local-entity context (**0.83 vs 0.94** computer-science corpus, **0.81 vs 0.90** music corpus): when shown the graph's entity inventory, the LLM extracts relations that are implied rather than stated, enriching the graph but admitting irrelevant relations. The paper leaves the trade-off to the user. Incremental matching without post-processing beats baseline construction pipelines on resolution consistency across three scenarios (papers, websites, CVs).

**Key takeaways for KGF**: the closest published system to ingestion-time spanning-context injection, and it supplies the contrarian side's number: injected graph context costs ~10 points of triple precision via implied-relation hallucination. The A/B design (global vs local context, precision measured) is directly the shape of the R41 pin-precision experiment; KGF must beat this failure mode with distinguishing-fact injection and pin-audit gates, not inventory dumps.

**Tags**: incremental-kg-construction, context-injection, entity-matching, anchoring-cost, extraction-time-pinning
**Source**: https://arxiv.org/abs/2409.03284 (PDF: `[paper] iText2KG, 2024-09.pdf`)

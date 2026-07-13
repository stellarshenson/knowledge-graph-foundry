**Grounded Knowledge Graph Extraction via LLMs: An Anchor-Constrained Framework with Provenance Tracking (AEVS), Yang, Chen, He, Zhao, MDPI Computers 15(3):178, 2026**

AEVS grounds every extracted triplet element to a character-level position in the source text, cutting hallucination rate to **0.23-20.23%** across model-dataset configurations at a cost of **2.83-4.28 LLM calls per sample** - evaluated on WebNLG, REBEL, and Wiki-NRE against both trained extraction models and LLM-based baselines.

**Key mechanism**
- Stage 1 (anchor discovery): identifies entities, relation phrases, and attribute values with precise character-level spans, forming a closed extraction vocabulary
- Stage 2 (grounded extraction): generates triplets constrained to only reference discovered anchors, so every element carries a source_pointer by construction
- Stage 3 (restoration-based verification): validates triplets via four matching strategies (exact, fuzzy, schema mapping, text search) with a coverage-aware supplement pass to catch anchors left unused

**Main findings**
- Consistent improvement over both trained and LLM-baseline extractors on all three benchmarks
- Ablations confirm anchor-based constraints, not the verification stage alone, are the primary hallucination-reduction mechanism
- Hallucination rate and computational cost both vary substantially by model-dataset pairing, indicating the anchor vocabulary's tightness (not just verification) governs faithfulness

**Key takeaways**
- Character-level span anchoring is a direct operationalization of an ARTIFACT/ELSEWHERE/ABSENT triage: a claim maps to ARTIFACT when its anchor span exists in-source, ELSEWHERE when the anchor exists but at a different location, ABSENT when no anchor is found
- The anchor's character offset is exactly the gap-ledger's source_pointer field - AEVS treats it as a first-class extraction constraint rather than a post-hoc audit annotation
- Coverage-aware supplement gives a concrete pattern for closing missed-anchor gaps at ingest time rather than deferring to query-time repair

**Tags**: #KGExtraction #Provenance #Hallucination #SpanGrounding #LLMExtraction

**Source**: https://www.mdpi.com/2073-431X/15/3/178. Local: [paper] aevs anchor-constrained kg extraction, 2026.pdf

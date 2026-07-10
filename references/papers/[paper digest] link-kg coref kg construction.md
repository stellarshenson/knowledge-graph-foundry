# LINK-KG - coreference-aware LLM knowledge-graph construction

**arXiv 2510.26486 (2025)**. LLM-driven KG construction pipeline that resolves coreferent and deictic mentions ("the defendant", "he", "the device") to canonical entity names BEFORE extraction, using **type-specific prompt caches** that persist alias-to-canonical mappings across chunks of a document.

**Key mechanism**: a coreference-resolution module maintains per-entity-type alias caches; each chunk is rewritten (or its extraction guided) so mentions map to canonical names, preventing the same real-world entity from fragmenting into pronoun-based or alias-based duplicates across chunk boundaries.

**Main findings**: coreference-resolved pipelines yield measurably more complete and less fragmented graphs than direct per-chunk extraction on the studied corpora (case documents on smuggling networks); the authors note that even sparse pronoun references significantly affect knowledge-graph completeness. Related extraction-side evidence: coreference resolution improved educational KG construction (IEEE 2020). Deltas are domain-specific; no technical-manual benchmark exists.

**Key takeaways for KGF**: extraction-side (not retrieval-side) evidence that entity-continuity handling raises graph completeness - directly relevant to the benchmark corpus where a manual names its device once, then says "the device/unit" for pages (the H21 zero-chunk forensic). Positioned as the LLM-pass escalation if deterministic subject/breadcrumb injection leaves residue.

**Tags**: coreference, kg-construction, entity-continuity, extraction
**Source**: https://arxiv.org/abs/2510.26486 (PDF: `[paper] link-kg coref kg construction, 2025.pdf`)

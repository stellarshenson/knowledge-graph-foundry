# KB-Injection - Injecting Knowledge Base Information into End-to-End Joint Entity and Relation Extraction and Coreference Resolution

**arXiv 2107.02286 (ACL Findings 2021, Ghent)**. Injects KB entity representations (learned from Wikipedia hyperlinks and/or Wikidata graph embeddings) into a joint document-level IE model (NER + coreference + RE) via unsupervised entity-linking candidates: EL candidate representations are ADDED to text-span representations before extraction decisions. **Up to +5% F1** across the joint IE tasks on two datasets (DWIE, DocRED).

**Key mechanism**: for each text span, retrieve KB entity-linking candidates; fuse their embeddings into the span representation either by prior-weighted average (link priors from Wikipedia) or by a learned attention over the candidate list. The extractor then makes NER/coref/RE decisions on spans that already carry KB knowledge.

**Main findings**: KB injection helps ALL three tasks jointly; text-derived (Wikipedia) and graph-derived (Wikidata) entity representations are COMPLEMENTARY; attention over candidates beats prior-weighting - the model learns to discount wrong candidates, the key safeguard when the candidate list is speculative.

**Key takeaways for KGF**: direct published precedent that conditioning EXTRACTION on retrieved KB candidates raises extraction quality itself, not just downstream linking - the mechanism the course-corrected R41 sense proposes for LLM prompts. The attention-beats-prior finding maps to prompt design: injected candidates must be presented as evidence with distinguishing facts (lettng the model discount), not as authoritative instructions (forcing wrong pins).

**Tags**: kb-aware-extraction, joint-ie, candidate-injection, coreference, extraction-time-pinning
**Source**: https://arxiv.org/abs/2107.02286 (PDF: `[paper] KB-Injection Joint IE, 2021-07.pdf`)

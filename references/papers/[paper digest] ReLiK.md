# ReLiK - Retrieve and LinK: entity linking and relation extraction with candidates in the prompt

**arXiv 2408.00103 (ACL 2024 Findings)**. Retriever-Reader architecture for entity linking (EL) and relation extraction (RE): a retriever fetches candidate entities/relations from the KB for the input text, and the reader receives text + ALL candidates in a SINGLE input sequence, linking spans to candidates in one forward pass - **up to 40x faster inference** than prior retriever-reader EL at state-of-the-art in-domain AND out-of-domain accuracy, trained on an academic budget.

**Key mechanism**: the input representation concatenates the passage with the retrieved candidate entity identifiers/descriptions; the reader (a standard pretrained encoder) contextualizes text and candidates JOINTLY, so disambiguation is a reading task over an injected candidate list, not a classification over a closed label space. The same architecture runs closed information extraction (cIE = EL + RE) with a shared reader, setting cIE state of the art.

**Main findings**: SOTA or near-SOTA Micro-F1 across in-domain (AIDA) and out-of-domain EL benchmarks; SOTA cIE; the joint text+candidates encoding is what buys both the accuracy (full cross-attention between mention context and candidates) and the speed (one pass for all candidates, versus one pass per candidate in prior readers).

**Key takeaways for KGF**: the strongest published template for ingestion-time entity pinning - retrieve candidate graph entities for the chunk, inject them WITH the chunk into the extraction prompt, let the model align mentions to injected identities. Retrieval quality bounds linking quality (their retriever recall is the ceiling); an entity not in the candidate list cannot be pinned - the fallback path (mention with no candidate = NEW entity) is exactly KGF's speculation-revocation branch.

**Tags**: entity-linking, relation-extraction, retriever-reader, candidate-injection, extraction-time-pinning
**Source**: https://arxiv.org/abs/2408.00103 (PDF: `[paper] ReLiK, 2024-08.pdf`)

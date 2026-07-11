# GENRE - Autoregressive Entity Retrieval: pin entities by generating their canonical names

**arXiv 2010.00904 (ICLR 2021, Facebook AI)**. Retrieves/links entities by GENERATING their unique canonical names token-by-token with constrained beam search over a prefix trie of all valid KB entity names - the output is guaranteed to be an existing KB identity. SOTA or competitive on **20+ datasets** (entity disambiguation avg Micro-F1 **83.7** InKB across in-domain + 4 OOD sets; strong end-to-end EL) with a memory footprint of ~**2GB** versus tens of GB for dense-embedding entity indexes.

**Key mechanism**: entity space = name strings, not atomic labels. A seq2seq model conditioned on the mention context decodes a name; a prefix trie built from the entity vocabulary masks invalid continuations at every decoding step, so generation can only terminate on a canonical name. Cross-encoding of context and name captures fine-grained interactions a bi-encoder dot product misses; no negative sampling needed (exact softmax over the vocabulary).

**Main findings**: generation beats dense retrieval for entity disambiguation especially with structured name spaces; scales with vocabulary size, not entity count; handles unseen mentions of known entities by composing name tokens.

**Key takeaways for KGF**: constrained decoding is the HARD form of entity pinning - the extractor structurally cannot invent a variant surface form if the name inventory is supplied as a constraint. KGF's extraction variance (H107: 71% of duplicate pairs are surface-form variants of known entities) is exactly the failure class GENRE eliminates by construction. Soft version for LLM prompts: inject the canonical-name inventory and instruct reuse; hard version: constrained decoding on a local model. Risk mirror: constraint forces a pin even when the true entity is NEW - the trie needs an escape token (KGF's speculation-revocation branch).

**Tags**: entity-linking, constrained-decoding, canonical-names, extraction-time-pinning
**Source**: https://arxiv.org/abs/2010.00904 (PDF: `[paper] GENRE Autoregressive Entity Retrieval, 2020-10.pdf`)

**Saga: A Platform for Continuous Construction and Serving of Knowledge At Scale (2022) | Ilyas, Rekatsinas, Konda, Pound, Qi, Soliman (Apple)**

Saga is Apple's production knowledge-graph platform, integrating billions of facts about real-world entities to serve multiple downstream applications (Siri, search, entity cards) with a hybrid batch-plus-stream architecture that keeps a slow, curated "Stable Ontology" graph separate from a fast "Live KG" that streams volatile data linked against that stable identity space.

**Key mechanism**
- Batch KG Construction pipeline runs Linking (blocking, pair generation, matching), Object Resolution, and Fusion to produce the canonical, versioned "Stable Ontology" graph - this is the tier where entity identity and provenance are actually adjudicated
- Live Graph Construction is a lightweight, continuously-running path: streaming source events (e.g. sports scores) are linked to stable entity identifiers already minted by the batch tier, but are not themselves subjected to full canonicalization
- A distributed shared log and log sequence numbers (LSN) coordinate multiple storage engines so each derives its view from the same ordered updates, giving every store an explicit "freshness" watermark
- Data model is extended triples (subject, predicate, relationship id/predicate, object, locale, sources, trust) carrying provenance and confidence per fact, enabling non-destructive integration and on-demand deletion

**Main findings**
- Splitting canonicalization (batch) from freshness (streaming) lets the platform serve both slow-changing curated facts and fast-changing volatile predicates (e.g. popularity) from one graph without forcing either workload to compromise
- Provenance and trust scores are first-class per-fact, not per-source, supporting partial trust and licensing-driven view filtering
- KG views scope entity linking to a relevant subgraph per entity type, reducing the search space before blocking/matching

**Key takeaways**
- Direct precedent for the HYBRID repair shape under discussion for KGF: defer expensive canonicalization/dedup to a batch tier, let a streaming tier attach new facts to already-stable identities without re-adjudicating them
- The freshness/accuracy tradeoff is made explicit via LSN watermarks rather than assumed away - a pattern worth mirroring if KGF adopts a similar split
- Confirms that industrial-scale KG platforms treat identity resolution as inherently a batch-time operation, not a per-event one

**Tags**
- #KnowledgeGraphConstruction #EntityResolution #StreamingArchitecture #Provenance

**Source**
- Download: https://arxiv.org/pdf/2204.07309
- Local: [paper] saga knowledge platform, 2022.pdf

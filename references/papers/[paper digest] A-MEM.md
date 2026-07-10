**A-MEM: Agentic Memory for LLM Agents, Xu, Liang, Mei, Gao, Tan, Zhang (Rutgers), 2025-02**

The published pattern for RIPPLE UPDATES: new arrivals trigger rewrites of neighboring derived objects. A-MEM organizes agent memory by Zettelkasten principles - every memory becomes a structured note (content, LLM-generated contextual description, keywords, tags, embedding), new notes are linked to semantically related historical notes, and crucially "memory evolution" lets the arrival of a new note trigger LLM rewrites of its neighbors' contextual descriptions and tags, so old derived metadata is continuously re-contextualized instead of going stale. Reports superior results over SOTA memory baselines (MemGPT, MemoryBank, ReadAgent) across **six foundation models** on LOCOMO long-term dialogue QA, with the largest gains on multi-hop questions. (Per-dataset deltas vary by backbone - see paper tables; no single headline number.)

**Key mechanism**
- Note construction: each ingested memory gets LLM-generated enrichments (context description, keywords, tags) - i.e., every memory carries DERIVED attributes from birth
- Link generation: retrieve top-k similar historical notes, LLM decides which links to create - the dependency graph is built at write time
- Memory evolution: for each newly linked neighbor, the LLM may REWRITE that neighbor's contextual description and tags in light of the new information - staleness is repaired opportunistically, on-write, only in the touched neighborhood
- No global refresh pass: evolution work is bounded by k (the retrieval neighborhood), so maintenance cost scales with write rate, not store size

**Main findings**
- Evolution + linking beat static append-only memory stores across all six backbones
- Ablations show both the link structure and the evolution step contribute; removing evolution degrades multi-hop performance most
- The neighborhood-bounded rewrite is the cost-control: only what the new memory touches gets refreshed

**Key takeaways**
- On-write neighborhood refresh is the lazy middle ground between eager global recompute and pure decay: derived text (descriptions, question nodes, hoisted specs) is revisited exactly when new related evidence lands
- LLM-decided linking at ingest = dependency tracking for unstructured derived objects
- Rewriting neighbor metadata without provenance is A-MEM's gap - it never records WHY a description changed, which a foundry-grade system must

**Tags**: #AMEM #Zettelkasten #MemoryEvolution #NeighborhoodRefresh #AgentMemory

**Source**: https://arxiv.org/abs/2502.12110. Local: [paper] A-MEM, 2025-02.pdf

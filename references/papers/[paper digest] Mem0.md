**Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory, Chhikara, Khant, Aryan, Singh, Yadav (Mem0), 2025-04**

The published rewrite-vs-append decision procedure for LLM-maintained stores. Every incoming fact candidate is routed by an LLM controller that inspects the top-k most similar existing memories and picks one of four operations - **ADD** (new memory), **UPDATE** (rewrite an existing memory in place), **DELETE** (retract a contradicted memory), **NOOP** (redundant, discard). On LOCOMO Mem0 beats six baseline categories (including RAG variants, full-context, and Zep) with **+26% relative LLM-judge accuracy over OpenAI's memory** while cutting p95 latency **~91%** and token usage **~90%** vs full-context (memory footprint ~7k vs ~26k tokens per conversation); the graph variant Mem0g adds relational structure for another ~2% at higher cost. (Note: baseline-comparison figures are the paper's own evaluation; Zep disputed the Zep configuration used.)

**Key mechanism**
- Extraction phase: LLM distills candidate facts from the new exchange using conversation summary + recent context
- Update phase: for each candidate, retrieve top-k similar memories, then one LLM call classifies ADD / UPDATE / DELETE / NOOP - conflict resolution is delegated to the model per-write, not to a schema
- DELETE is soft: contradicted memories are marked invalid rather than physically removed
- Cost profile: one routing LLM call per write batch - write cost scales with ingest volume regardless of novelty (the known weakness; later work adds novelty gates)

**Main findings**
- Selective memory (dense, curated) beats full-context on both accuracy and cost at long horizons - maintenance is what keeps the store small enough to win
- The four-operation vocabulary is sufficient in practice for consolidation; the hard part is the classifier's judgment, a heuristic (prompted) not learned policy
- Rewrite-in-place (UPDATE) trades provenance for compactness - Mem0 keeps no history of overwritten content, the direct opposite of Zep/Graphiti's append-and-invalidate

**Key takeaways**
- ADD/UPDATE/DELETE/NOOP is the minimal maintenance op-set for any LLM-curated derived store (question nodes, gap ledger entries, hoisted props)
- Route-on-similar-neighbors is the standard trigger: new evidence pulls its nearest derived objects into review
- Rewrite-vs-append is a real fork: rewrite wins on token cost, append-and-invalidate wins on audit/provenance - pick per object class

**Tags**: #Mem0 #MemoryConsolidation #RewriteVsAppend #ADD_UPDATE_DELETE #AgentMemory

**Source**: https://arxiv.org/abs/2504.19413. Local: [paper] Mem0, 2025-04.pdf

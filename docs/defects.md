# Defects - Knowledge Graph Foundry

`[ ]` open, `[x]` fixed. Dated notes under each track how it evolved.

## Contents

- [DEF-1: Per-mention re-embedding on every document](#def-1-per-mention-re-embedding-on-every-document) - open

### DEF-1: Per-mention re-embedding on every document

- [ ] HIGH ingest embeds the full pre-resolution mention set per document (one 9-chunk manual -> 708 Bedrock calls) and recurring entities (manufacturers, shared specs) are re-embedded in every later document; cause: `Foundry._embed` runs before resolution with no cache keyed by entity identity; fix: embedding cache keyed by `entity_id` + description hash (in-graph or local), embed only cache misses; `src/knowledge_graph_foundry/pipeline.py`
  - 2026-07-06 reported: observed during full CPAP rebuild - per-document embedding batches of 700+ for ~80 resolved entities/doc; linear-forever API cost for a months/years deployment

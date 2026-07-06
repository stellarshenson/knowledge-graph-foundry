# Defects - Knowledge Graph Foundry

`[ ]` open, `[x]` fixed. Dated notes under each track how it evolved.

## Contents

- [DEF-1: Per-mention re-embedding on every document](#def-1-per-mention-re-embedding-on-every-document) - fixed

### DEF-1: Per-mention re-embedding on every document

- [x] HIGH ingest embeds the full pre-resolution mention set per document (one 9-chunk manual -> 708 Bedrock calls) and recurring entities (manufacturers, shared specs) are re-embedded in every later document; cause: `Foundry._embed` runs before resolution with no cache keyed by entity identity; fix: in-process cache keyed by (provider, model, entity text) in `generate_embeddings` - repeat texts served from cache, changed descriptions legitimately re-embed; `src/knowledge_graph_foundry/extraction/embeddings.py`
  - 2026-07-06 reported: observed during full CPAP rebuild - per-document embedding batches of 700+ for ~80 resolved entities/doc; linear-forever API cost for a months/years deployment
  - 2026-07-06 fixed: (provider, model, text)-keyed cache with 16384-entry cap; 3 tests; suite 258 green; see [experiments R01 results](experiments/kgf-redesign-experiments.md)

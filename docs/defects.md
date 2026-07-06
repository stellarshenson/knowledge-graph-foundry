# Defects - Knowledge Graph Foundry

`[ ]` open, `[x]` fixed. Dated notes under each track how it evolved.

## Contents

- [DEF-1: Per-mention re-embedding on every document](#def-1-per-mention-re-embedding-on-every-document) - fixed
- [DEF-2: JSONL with text-heavy rows routed to tabular mapping, LLM never reads the text](#def-2-jsonl-with-text-heavy-rows-routed-to-tabular-mapping-llm-never-reads-the-text) - open

### DEF-1: Per-mention re-embedding on every document

- [x] HIGH ingest embeds the full pre-resolution mention set per document (one 9-chunk manual -> 708 Bedrock calls) and recurring entities (manufacturers, shared specs) are re-embedded in every later document; cause: `Foundry._embed` runs before resolution with no cache keyed by entity identity; fix: in-process cache keyed by (provider, model, entity text) in `generate_embeddings` - repeat texts served from cache, changed descriptions legitimately re-embed; `src/knowledge_graph_foundry/extraction/embeddings.py`
  - 2026-07-06 reported: observed during full CPAP rebuild - per-document embedding batches of 700+ for ~80 resolved entities/doc; linear-forever API cost for a months/years deployment
  - 2026-07-06 fixed: (provider, model, text)-keyed cache with 16384-entry cap; 3 tests; suite 258 green; see [experiments R01 results](experiments/kgf-redesign-experiments.md)

### DEF-2: JSONL with text-heavy rows routed to tabular mapping, LLM never reads the text

- [ ] HIGH a .jsonl of 481 articles ingested as one "document" yielding a mechanical 2 entities + 1 relationship per row; cause: `_extract_file` dispatches every structured extension to `structured_mapping`/`apply_mapping` (deterministic column mapping) regardless of content shape, so long free-text columns are never chunk-extracted, and the whole file is one resume fingerprint / one curing document; fix pending: detect text-heavy columns (e.g. median cell length threshold) and route each row's text through the unstructured chunk-and-extract path as its own document; workaround: campaign waves rewritten as one .txt per article; `src/knowledge_graph_foundry/pipeline.py`
  - 2026-07-06 reported: R05 wave 1 first launch - "ingested 1 documents: 962 entities, 481 relationships" with zero LLM reading of article bodies; data/external README already promised the text-column routing but code never implemented it

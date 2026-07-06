# Usage Scenarios - Knowledge Graph Foundry

The scenarios KGF is designed to carry, each naming the flow, the capabilities that carry it, and what must hold for it to work. They stress different subsystems - together they define what "production ready" means for this project and drive the acceptance criteria and experiment bars.

## S1 - One-shot corpus to comparison answers

An analyst has a folder of product documentation and needs grounded comparisons the same day.

- **Flow** - `kgf.build("compare CPAP machines", "data/manuals/")` → query comparisons
- **Carried by** - purpose-guided extraction, curing on a small corpus, PPR retrieval, comparison decomposition (R03-H15)
- **Must hold** - zero-config startup (env-only), cure on a 10-30 document corpus, answers cite sources

## S2 - Continuous ingestion over months

A service ingests nightly document drops for months; products get revised, discontinued, renamed.

- **Flow** - scheduled `kgf ingest` on new drops; the graph absorbs, supersedes, never loses history
- **Carried by** - bitemporal edges + contradiction reconciliation, entity versioning, schema/fact drift detection, recure on type burst
- **Must hold** - a superseded spec answers correctly for "now" and for "as of March"; ingest cost stays flat per document (embedding cache, DEF-1); no full rebuild needed for drift short of the rebuild threshold

## S3 - Embedded component in a host application

A product-support platform embeds KGF as its retrieval backend; the host owns the UI and lifecycle.

- **Flow** - `Foundry(settings)` as a library, events subscribed for progress, `query()` behind the host's API
- **Carried by** - full public API surface, typed Settings tree, blinker events, role-based LLM routing
- **Must hold** - no CLI dependency, no stdout side effects the host cannot control, every knob reachable from code

## S4 - Weak reader, strong graph

Deployment answers queries with a small local model (7-14B class); frontier models run only at ingest.

- **Flow** - frontier extraction + proposition generation at ingest; local GPU engine answers from pre-assembled context
- **Carried by** - proposition nodes (R02-H11), reasoning-ordered serialization with citations (R03-H16), engine mixing (frontier ingest / local-gpu reader)
- **Must hold** - weak-reader accuracy on the probe set approaches the frontier reader on the same context; the probe set measures this explicitly

## S5 - Concurrent ingesters

Two pipelines (or a human and a cron job) try to ingest at the same time.

- **Flow** - second ingester blocks or fails fast with a clear owner report; a crashed ingester's lease expires and is taken over
- **Carried by** - graph-resident lease with heartbeat + stale takeover, per-document persistence for resume
- **Must hold** - no interleaved state mutation ever; a killed run resumes without re-ingesting completed documents

## S6 - Audit and provenance

A reviewer asks "why does the graph say the AirSense 11 weighs 1130 g, and since when?"

- **Flow** - trace answer → supporting entities → propositions/chunks → source document; inspect edge validity intervals and entity versions
- **Carried by** - MENTIONED_IN provenance, bitemporal intervals, entity version snapshots, (R03) per-claim citations; append-only merge log when the mention layer lands
- **Must hold** - every fact reachable from a query is traceable to a document and a time; merges are explainable

## S7 - Schema-governed enterprise deployment

An organization seeds the ontology (freeform text or OWL) and wants discovery constrained to it.

- **Flow** - `kgf init --seed ontology.owl`, ingest respects and extends the seeded frame
- **Carried by** - seed parsing (freeform/YAML/JSON/OWL), purpose + seed steering extraction typing
- **Must hold** - seeded types are never demoted or clustered away; discovery adds, never overwrites, governed structure

## S8 - The graph says "I don't know"

A user asks about a device the corpus never mentioned.

- **Flow** - coverage gate detects thin structural support → refuse/clarify instead of hallucinating; the failed query flags the gap
- **Carried by** - structural abstention (R03-H17), query-failure rate as a maintenance trigger
- **Must hold** - correct refusal >= 70% on unanswerables at < 10% false refusal; each refusal records what was missing so ingestion can target it

## S9 - Model migration mid-life

Nine months in, the embedding model or the LLM engine is upgraded.

- **Flow** - swap `EmbeddingSettings.model` / `LLMSettings` config; re-embed or adapt without downtime
- **Carried by** - single-provider-per-run embedding discipline, model-stamped vectors (planned with the cache), Drift-Adapter pattern held as the scale path
- **Must hold** - old and new vectors never mix in one index; retrieval quality measured before cutover

## S10 - Agent memory (episodic)

A host agent streams conversation/transcript episodes into the graph as long-term memory.

- **Flow** - continuous small-document ingestion; temporal queries ("what did we agree in June?"); staged tier absorbs raw episodes
- **Carried by** - bitemporal model (the Graphiti/Zep-validated shape), in-graph staged tier (R04), relationship_history API
- **Must hold** - ingest latency suits interactive use (small batches, no full recompute per episode); history is queryable by time

## Scenario coverage map

| scenario | primary subsystems | measured by |
|---|---|---|
| S1 one-shot corpus | extraction, curing, PPR | probe set accuracy, cure-by-document |
| S2 months of drift | temporal, drift, versioning | supersede probe, per-doc cost trend |
| S3 embedded library | API, settings, events | test_public_api, no-CLI import |
| S4 weak reader | propositions, serialization | weak-reader probe delta (R02-H11, R03-H16) |
| S5 concurrent ingest | lease, resume | lock tests, kill-resume test |
| S6 audit | provenance, bitemporal, versions | trace walk from answer to source |
| S7 seeded schema | seed, ontology governance | seed-protection test |
| S8 abstention | coverage gate, drift trigger | R03-H17 bars |
| S9 model migration | embeddings lifecycle | parallel-index discipline |
| S10 agent memory | temporal, staged tier | ingest latency, history queries |

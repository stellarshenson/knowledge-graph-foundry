# Library API

Knowledge Graph Foundry is usable as a component in any Python application. Everything the CLI does is available programmatically through one entrypoint (`Foundry`) and one fully-typed configuration object (`Settings`). Import from the package top level.

## Quick use

```python
from knowledge_graph_foundry import Foundry, Settings, Neo4jSettings

settings = Settings(
    neo4j=Neo4jSettings(uri="bolt://localhost:7687", user="neo4j", password="pw"),
)

with Foundry(settings) as kgf:          # context manager closes the driver
    kgf.init_project("compare CPAP machines", seed=None)
    summary = kgf.ingest("data/manuals/")          # file, directory or zip; str or Path
    print(kgf.status())
    print(kgf.query("AirSense 11 vs DreamStation pressure range?"))
    kgf.optimize()                                  # communities, summaries, scorecard
```

`Foundry.from_config(path)` builds the same from a `config.yml` with environment overrides (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`).

## Entrypoint - Foundry

- `init_project(purpose, seed=None)` - store the purpose and optional seed (YAML/JSON/OWL path or freeform text), create the control metanode
- `ingest(path)` - run the full lifecycle over a file, directory or zip; returns a summary dict; holds a graph-resident run lease so only one ingester mutates state at a time
- `status()` - lifecycle state, counts, ontology, latest stability metrics, drift
- `query(question)` - answer over the graph; global/thematic questions route to community summaries, entity/multi-hop questions to Personalized PageRank; returns `{answer, supporting_entities, path}`
- `optimize()` - GDS Leiden communities, LLM summaries, quality scorecard (persisted to `reports/`)
- `search(text_or_embedding, top_k=8)` - vector search over entities
- `current_relationships(entity_id)` - currently-valid outgoing edges (time-aware)
- `relationship_history(entity_id, rel_type)` - full ordered edge history (the evolution record)
- `wipe()` - delete all graph content and the metanode
- `close()` / context manager - release the Neo4j driver

## Configuration - Settings

Every knob is a field on `Settings` or one of its typed sub-models; construct directly or load from YAML. Sub-models: `Neo4jSettings`, `LLMSettings`, `EmbeddingSettings`, `ExtractionSettings`, `ResolutionSettings`, `CuringSettings`, `DriftSettings`, `GraphRAGSettings`, `LoadSettings`.

Notable knobs:

- **Neo4j** - `uri`, `user`, `password`
- **LLM** - `engine` (`frontier` | `claude-cli` | `local-gpu`), `model`, `temperature`, `base_url` (local GPU), `region` (Bedrock)
- **Embeddings** - `provider` (`bedrock` | `sentence-transformers`), `model`, `fallback`, `fallback_model`
- **Extraction** - `chunk_size`, `chunk_overlap`, `concurrency`, `gleaning_rounds`, `split_entity_relation`
- **Resolution** - `merge_threshold`, `defer_lower`, `ann_top_k`, `llm_defer_judge`, `split_guard`
- **Curing** - `jsd_threshold`, `chao1_threshold`, `min_samples_before_cure`, `max_fluid_documents`, `recure_type_burst`
- **Drift** - `remap_rate_threshold`, `window`, `contradiction_rate_threshold`
- **GraphRAG** - `ppr_enabled`, `ppr_top_n`, `top_k`, `vector_dimensions`, `community_min_size`
- **Load** - `entity_versioning`, `functional_relationship_types` (edge types where a new target supersedes the old)

### Role-based LLM routing

Extraction is high-volume; orchestration (type clustering, contradiction and defer judging, community summaries, query answering) is low-volume but benefits from a stronger model. Configure them independently:

```python
from knowledge_graph_foundry import Settings, LLMSettings

settings = Settings(
    llm=LLMSettings(model="bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0"),        # orchestrator
    extraction_llm=LLMSettings(model="bedrock/eu.anthropic.claude-haiku-4-5-20251001-v1:0"),  # bulk extractor
)
```

When `extraction_llm` is `None` (default) both roles use `llm`. The `frontier`, `claude-cli` and `local-gpu` engines can be mixed across roles - a local GPU extractor with a frontier orchestrator is a valid configuration.

## Events

Subscribe to the pipeline's blinker signals to drive progress UIs, metrics, or side effects in a host app:

```python
from knowledge_graph_foundry import subscribe, SIGNALS

def on_doc(sender, **payload):
    print("document done", payload)

subscribe("document.completed", on_doc)      # SIGNALS lists every signal name
```

`enable_event_log(path)` also streams every signal to a JSONL file for run forensics.

## Lower-level building blocks

Individual stages are importable for embedding one part of the pipeline: `knowledge_graph_foundry.ingest` (readers, chunking), `knowledge_graph_foundry.extraction` (extraction, embeddings), `knowledge_graph_foundry.resolution` (Bayesian resolver, blocking, calibration), `knowledge_graph_foundry.ontology` (seeds, buffer, metrics, curing, clustering), `knowledge_graph_foundry.graph` (loaders, temporal reads, GraphRAG, metanode). Domain models (`Entity`, `Relationship`, `Ontology`) are at the top level.

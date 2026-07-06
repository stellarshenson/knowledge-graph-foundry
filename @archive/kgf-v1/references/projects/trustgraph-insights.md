# TrustGraph

**Repository**: https://github.com/trustgraph-ai/trustgraph

Graph-native context development platform for building knowledge-aware AI systems. Self-hosted infrastructure combining graph, vector, and document storage with LLM-driven knowledge extraction. Significantly larger scope than KGF - full backend platform vs focused extraction CLI.

## Architecture

Multi-model storage: Cassandra (structured/graph), Qdrant (vectors), Garage S3-compatible (objects). Apache Pulsar for pub/sub messaging between pipeline stages. Prometheus/Grafana/Loki for observability. Docker/Kubernetes deployment.

Three RAG patterns: DocumentRAG (text retrieval), GraphRAG (relationship traversal), OntologyRAG (schema-aligned queries).

Multi-stage extraction pipeline with three parallel extractors: relationship extraction, definition extraction, and ontology-conformant extraction (OntoRAG). Each emits RDF triples with PROV-O provenance.

## Relevant Patterns

### OntoRAG - Dynamic Ontology Selection Per Chunk
- Each ontology element (class, property) gets vector embedding from combined text (ID + labels + descriptions)
- For each text chunk: split into sentences, embed, vector search for top_k=10 similar ontology elements, filter by similarity_threshold=0.3
- Auto-includes dependency resolution: parent classes, domain/range classes, related properties
- LLM receives only the relevant ontology subset per chunk, not the full schema
- **Relevance to KGF**: KGF sends the full ontology to every chunk. OntoRAG's per-chunk ontology subsetting via embeddings would reduce prompt size and improve extraction precision for large ontologies. The dependency resolution pattern (auto-include parent classes and related properties) is directly applicable

### Entity Normalization with Type-Aware URIs
- URI pattern: `https://trustgraph.ai/{ontology_id}/{type}-{name}` where type and name are normalized (lowercase, hyphens)
- Same name + different type = different URI: "John" + PERSON != "John" + PRODUCT
- `EntityRegistry` maintains `(name, type) -> URI` mapping for consistency within extraction runs
- **Relevance to KGF**: KGF uses UUID-based entity IDs. Type-aware deterministic IDs would enable cross-run entity matching without the Bayesian model. The "80% rule" - deterministic resolution handles 80% of cases, complex resolution for the rest - validates KGF's approach

### PROV-O Provenance Model
- Full W3C PROV-O provenance chain: Document -> Page -> Chunk -> extraction Activity -> Triples
- Each extraction Activity records: component name/version, LLM model used, ontology URI, timestamp
- Uses RDF-star quoted triples: `subgraph_uri tg:contains <<s p o>>` to link provenance to specific triples
- Derivation chain: `entity prov:wasDerivedFrom chunk`, `chunk prov:wasDerivedFrom page`, `page prov:wasDerivedFrom document`
- **Relevance to KGF**: KGF has `source_chunks` on entities but no formal provenance model. The Activity/Agent/Entity pattern from PROV-O would formalize KGF's extraction metadata (which LLM, which prompt version, which ontology state produced each entity)

### Context Cores (Versioned Knowledge Bundles)
- Portable, versioned bundles: domain ontology + triples + graph embeddings + provenance manifests + retrieval policies
- Stored in Cassandra with user/collection isolation
- Operations: list, get (stream triples + embeddings in batches), put, load (stream into active stores)
- Each core has metadata: name, version, namespace, created/modified timestamps
- **Relevance to KGF**: the ontology YAML + resolution_guide + type_exemplars we flush is a primitive version. Context Cores formalize what KGF does informally. The serialization pattern (batch streaming of triples + embeddings) is relevant if KGF adds export/import of graph snapshots

### Ontology as JSON Config (Not OWL)
- Classes with `rdfs:subClassOf`, `owl:disjointWith`, multilingual labels
- Object properties with domain/range constraints, `owl:inverseOf`
- Datatype properties with XSD types, `owl:functionalProperty`
- Stored as JSON config items, not OWL files - simpler than full OWL but retains key semantics
- **Relevance to KGF**: validates KGF's YAML ontology format. TrustGraph's JSON is structurally equivalent to KGF's YAML but adds `disjointWith` (KGF has this as advisory), `inverseOf` (KGF doesn't track), and `functionalProperty` (single-valued constraint). The domain/range constraints on properties are the main gap - KGF's relationship types have source_type/target_type but don't enforce them during extraction

### Prompt Structure for Ontology-Constrained Extraction
- Jinja2-templated prompts with ontology elements injected per chunk
- Explicit extraction rules: "Only use classes defined above", "Respect domain and range constraints", "Include rdfs:label for new entities"
- Output format: JSON array of `{subject, predicate, object}` triples with entity URIs
- **Relevance to KGF**: KGF's extraction prompts list entity types but don't inject relationship domain/range constraints. TrustGraph's approach of including property definitions with domain/range in the prompt would improve relationship extraction accuracy

### Multi-Stage Parallel Extraction
- Three parallel extractors per chunk: relationships, definitions, ontology-conformant
- Each produces different output: triples (relationships), EntityContexts with definitions, typed triples (ontology)
- Definition extraction feeds embedding pipeline: entity + context text -> vector
- **Relevance to KGF**: KGF uses a single extraction pass (entity_relationship mode) or hybrid (+ atomic facts). The separate definition extraction pass is interesting - generating entity context text specifically for embedding quality rather than using the raw description

## Applicability to KGF

**Direct code reuse**: minimal - fundamentally different architecture (platform vs CLI tool, RDF vs property graph)

**High conceptual value**:
- OntoRAG per-chunk ontology subsetting via embeddings - reduces prompt bloat, improves precision
- PROV-O provenance chain formalizes KGF's ad-hoc source tracking
- Domain/range constraints in extraction prompts for relationship type enforcement
- Separate definition extraction pass for better entity embeddings
- Type-aware deterministic entity IDs as complement to Bayesian resolution

**Moderate conceptual value**:
- Context Cores as formalization of KGF's ontology flush + graph snapshot
- Ontology dependency resolution (auto-include parent classes when child is selected)
- EntityRegistry for within-run dedup consistency

**Not applicable**:
- Full platform infrastructure (Cassandra, Pulsar, Qdrant) - KGF targets Neo4j directly
- Multi-model storage layer (KGF is graph-first with optional vector indexes)
- RDF triple model (KGF uses labeled property graph)
- Kubernetes deployment model (KGF is CLI-first)
- TypeScript/React UI libraries (KGF uses Textual TUI)

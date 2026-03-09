# Fact Repository - kg-builder-cli DESIGN.md

Verified claims sourced from design document, reference articles, and seed evaluation.
No interpretation - just facts.

## Design document facts

- DESIGN.md is 1800 lines across 20 sections, consolidating 3 source documents (SPEC.md, ingestion-unstructured.md, ingestion-structured.md)
- Three CLI commands: `kg ingest`, `kg query`, `kg update` - each backed by a Strands agent
- Four tools in shared registry: `py-repl`, `neo4j-mcp`, `neo4j-driver`, `file-ops`
- Ontology buffer tracks entity types, relationship types, type hierarchy, type variants, disjoint constraints, coverage scores
- Entity resolution pipeline: exact ID match -> SpaCy+fuzzy -> embedding similarity (0.85 threshold) -> LLM clustering
- Three extraction modes: `entity_relationship`, `graph_reader`, `hybrid`
- Graph Reader pattern: 85% precision, 95% recall on detail-oriented queries (from Akash Goyal reference articles)
- Entity Reader pattern: 95% precision, 70% recall (from reference articles)
- Hybrid extraction: ~2x LLM cost per chunk vs single-track
- Dual indexing: vector (cosine, 1536d) + fulltext (Lucene)
- Batch loading default: 500 entities per transaction, 3 deadlock retries
- SHA1 chunk IDs for idempotent re-processing
- Ontology normalization: LLM converts any-format to canonical YAML via Pydantic validation
- OWL import: programmatic via owlready2, no LLM involvement
- Schema inference: agent samples 20 records, computes field profiles, proposes schema interactively
- Migration plans saved to `.kg-builder/migrations/` with timestamps and rollback instructions
- Agent memory: YAML files in `.kg-builder/memory/`, TTL 90 days, max 100 entries per source
- No functional code exists yet - project is at design stage with copier-data-science template scaffolding

## Reference implementation facts

- Neo4J LLM Graph Builder uses LLMGraphTransformer, token-based chunking with SHA1 chunk IDs, APOC merge-based dedup
- Neo4J LLM Graph Builder has minimal structured data support - treats everything as unstructured
- langchain-neo4j provides Neo4jGraph, Neo4jVector, GraphDocument, Text2Cypher
- Instructor library provides Pydantic model enforcement with auto-retry on LLM validation failure
- Chonkie implements semantic chunking via embedding similarity
- owlready2 HermiT reasoner handles subclass propagation, transitive closure, consistency checking
- NCIt has 170,000+ classes, SNOMED has 350,000+ classes - too large for direct extraction constraints

## Seed evaluation facts

- Overall rating: 8.5/10
- Source: senior engineer review (devils_advocate_seed.md)
- Architecture rated "very strong", ontology system "excellent", structured pipeline "excellent"
- Query pipeline and update pipeline rated "good" (lower than core pipeline ratings)
- Five critiques identified: agent overuse, overengineering, LLM normalization risk, schema inference instability, missing confidence model
- Recommended minimal v1 graph model: Document, Chunk, Entity, FactNode, OntologyType
- Strategic question raised: developer CLI tool vs GraphRAG engine vs general KG framework

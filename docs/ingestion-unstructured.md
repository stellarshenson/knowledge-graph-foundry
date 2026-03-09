# Unstructured Data Ingestion

Strategy for extracting knowledge graph triples from free-form text documents (PDF, TXT, MD, DOCX).

## Pipeline Overview

```
Document -> Parse -> Chunk -> LLM extract -> Deduplicate -> Resolve entities -> Consolidate types -> Load
```

1. Parse document into plain text, preserving page/section metadata where available
2. Split text into overlapping chunks sized for the LLM context window
3. Send each chunk (or batch of chunks) to the LLM with an extraction prompt
4. Collect entities and relationships from all chunks
5. Deduplicate entities across chunks by exact `(type, id)` match
6. Resolve remaining duplicates via LLM-based entity clustering
7. Consolidate type labels (merge "Person"/"Human"/"Individual" into canonical type)
8. Load merged graph into Neo4J

## Document Parsing

Each format requires a different parser to extract clean text.

| Format | Parser | Notes |
|--------|--------|-------|
| PDF | `pymupdf` | Preserves page numbers per text block |
| TXT / MD | built-in | Read as-is |
| DOCX | `python-docx` | Extracts paragraph text, ignores formatting |

The parser outputs a list of text segments with source metadata (file path, page number or line offset). This metadata propagates through chunking into the final extraction output, enabling traceability from any entity back to its source location.

## Chunking Strategy

Token-based splitting using `langchain-text-splitters.TokenTextSplitter`. Character-based splitting risks cutting mid-word or mid-sentence, while token-based splitting aligns with LLM context limits.

**Parameters** (from `.kg-builder/config.yml`):
- `chunk_size`: 2000 tokens (default) - sized to give the LLM enough context per chunk without exceeding practical limits
- `chunk_overlap`: 200 tokens (default) - ensures entities spanning chunk boundaries appear in at least one complete chunk

**Chunk identity**: each chunk gets a deterministic ID derived from SHA1 of its content. This allows idempotent re-processing - re-running extraction on the same document produces the same chunk IDs and can be merged cleanly.

**Chunk linking**: chunks maintain their sequential order via metadata (chunk index within document). This is preserved in the extraction output and optionally in Neo4J as a `NEXT_CHUNK` relationship chain for downstream retrieval tasks.

## LLM Extraction

Each chunk is sent to the LLM with a prompt that instructs it to extract entities and relationships in a structured JSON format.

### Free Extraction (no ontology)

The LLM identifies entity types and relationship types on its own. The prompt instructs:

- Extract all meaningful entities (people, organizations, concepts, locations, events, etc.)
- Extract relationships between entities with typed labels
- Treat dates, numbers, and quantitative values as properties on entities, not as separate nodes
- Return a unique `id` per entity (lowercase, underscore-separated, prefixed by type)
- Include a brief `description` for each entity summarizing what the chunk says about it

### Constrained Extraction (with ontology)

When `.kg-builder/ontology.yml` is provided, the prompt includes the list of allowed entity types and relationship types. The LLM is instructed to only emit entities matching those types and only create relationships of the defined types between the defined source/target type pairs.

Entity type descriptions from the ontology are included in the prompt to guide classification.

### Prompt Structure

```
You are a knowledge graph extraction system. Extract entities and relationships
from the following text.

[If ontology provided:]
Use ONLY these entity types: {entity_types_with_descriptions}
Use ONLY these relationship types: {relationship_types_with_source_target}

[If custom instructions provided:]
Additional instructions: {custom_instructions}

Rules:
- Treat dates, numbers, revenues, and quantitative values as properties on
  entities, not as separate nodes
- Each entity must have a unique id (lowercase, underscores, type-prefixed)
- Each entity must have a name and type
- Include a brief description for each entity based on the text
- Relationships must reference entity ids

Return JSON:
{
  "entities": [{"id": "...", "name": "...", "type": "...", "description": "...", "properties": {}}],
  "relationships": [{"source": "...", "target": "...", "type": "...", "description": "..."}]
}

Text:
{chunk_text}
```

### Chunk Batching

For efficiency, multiple small chunks can be combined into a single LLM call (configurable via `concurrency`). The trade-off: larger batches reduce API calls but may reduce extraction quality as the LLM has more text to process at once. Default is one chunk per call with parallel requests controlled by `concurrency`.

## Entity Deduplication

The same entity often appears across multiple chunks. Deduplication happens at two levels.

### Intra-document Deduplication

After all chunks from a single document are processed, entities are merged by `(type, id)` tuple. When the same entity appears in multiple chunks:
- Properties are merged (later values overwrite earlier ones for the same key)
- Descriptions are concatenated or the longest is kept
- `source_chunks` list accumulates all chunk references
- Relationships are deduplicated by `(source_id, target_id, type)` tuple

### Cross-document Deduplication (at load time)

When loading into Neo4J, `MERGE` operations ensure `(type, id)` uniqueness across the entire graph. If an entity already exists from a previous document, its properties are updated rather than creating a duplicate node.

### Entity Resolution

Beyond exact ID matching, the pipeline supports a post-extraction entity resolution step to catch duplicates the LLM produced under different IDs. This is inspired by the schema-first approach described in the Dynamic Ontology reference (Akash Goyal) and the entity resolution pipeline from Brian Curry's end-to-end guide.

**LLM-based clustering**: after extraction, the full list of entity names is sent to the LLM with a clustering prompt that asks it to group entities referring to the same real-world thing. For example, "Apple", "Apple Inc.", and "the Cupertino giant" would be clustered together. The LLM returns clusters, and a canonical name is chosen (typically the most complete form).

```
Given these entity names, identify which ones refer to the same
real-world entity. Return clusters as JSON arrays.

{entity_names}
```

**Normalization metadata**: when entities are resolved, the original extracted name is preserved alongside normalized fields. Following the Dynamic Ontology pattern, resolved entities store:
- `name`: original extracted value (for traceability)
- `normalized_name`: canonical form after resolution
- `normalized_score`: confidence of the resolution match
- `normalized_method`: how it was resolved (e.g., `llm_cluster`, `exact_match`)

This makes resolution auditable and reversible - downstream consumers can choose their own trust threshold.

**Ontology schema consolidation**: the LLM may also produce type variations (e.g., "Person", "Human", "Individual"). A separate consolidation pass groups similar type labels and renames them to the most representative category. With a constrained ontology this is unnecessary, but for free extraction it prevents type sprawl.

### Limitations

Entity resolution depends on LLM consistency and the clustering prompt's effectiveness. Short entity names (abbreviations, acronyms) are particularly prone to false matches. For domains with highly ambiguous short tokens, consider separating resolution into domain-specific passes with restricted candidate sets, as recommended in the Dynamic Ontology reference for gene symbol normalization.

## Graph Structure in Neo4J

```
(:Document {name, source, processed_at})
  <-[:PART_OF]- (:Chunk {id, text, index, page})
    -[:HAS_ENTITY]-> (:Entity:Person {id, name, description, ...})
    -[:HAS_ENTITY]-> (:Entity:Organization {id, name, description, ...})

(:Entity:Person)-[:WORKS_AT]->(:Entity:Organization)
(:Chunk)-[:NEXT_CHUNK]->(:Chunk)
```

- `Document` node tracks source file metadata
- `Chunk` nodes store the original text and link to their parent document
- Entity nodes carry both the base `Entity` label and their type label (e.g., `Person`, `Organization`)
- Typed relationships connect entities as extracted by the LLM
- `HAS_ENTITY` relationships from chunks to entities enable provenance queries

## Loading Strategy

Entities and relationships are loaded in batches using parameterized Cypher.

**Node creation**:
```cypher
MERGE (n:Entity:{type} {id: $id})
SET n.name = $name, n.description = $description
SET n += $properties
```

**Relationship creation**:
```cypher
MATCH (a:Entity {id: $source_id}), (b:Entity {id: $target_id})
MERGE (a)-[r:{rel_type}]->(b)
SET r.description = $description
```

**Indexing**: auto-create indexes on `Entity.id` and per-type label indexes for efficient MERGE operations. Without indexes, MERGE degrades to full scans as the graph grows.

**Batch size**: configurable (default 500), balancing transaction overhead against memory usage. Deadlock retries (3 attempts with backoff) handle concurrent write conflicts.

# Unstructured Data Ingestion

Strategy for extracting knowledge graph triples from free-form text documents (PDF, TXT, MD, DOCX).

## Pipeline Overview

```
                          +---> extract ---> feed back --->+
                          |                                |
Document -> Parse -> Chunk -> [Ontology Buffer] -> LLM extract -> Deduplicate -> Resolve -> Load
                          |                                |
                          +<--- refine  <--- new types <---+
```

1. Parse document into plain text, preserving page/section metadata where available
2. Split text into overlapping chunks sized for the LLM context window
3. Initialize the ontology buffer (from `ontology.yml` or empty for free extraction)
4. For each document (or batch of documents):
   a. Run schema signal extraction - lightweight LLM pass to detect category/type signals in the text
   b. Estimate coverage - compare detected signals against the ontology buffer
   c. Extract entities and relationships per chunk, constrained by the current ontology buffer
   d. Feed extraction results back into the buffer - accumulate new types, type frequencies, relationship patterns
   e. Periodically trigger ontology refinement - LLM proposes additions or merges to the buffered ontology
5. Deduplicate entities across all chunks by exact `(type, id)` match
6. Resolve remaining duplicates via LLM-based entity clustering
7. Flush the final refined ontology buffer to disk as `ontology.yml`
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

## Ontology Buffer

The ontology buffer is the central mechanism that makes the extraction pipeline adaptive. Rather than treating the ontology as a static input file read once at startup, the buffer holds the evolving ontology in memory throughout the entire ingestion run. Every document processed contributes back to it, so later documents benefit from what earlier documents taught the system.

### Initialization

The buffer is initialized from one of two states:

- **From file** (constrained mode): loads `.kg-builder/ontology.yml` as the starting schema. The buffer begins with a known set of entity types and relationship types. New types discovered during extraction can still be proposed, but require higher confidence to be accepted
- **Empty** (free extraction mode): the buffer starts with no types defined. The first few documents establish the initial ontology, which then stabilizes as more documents are processed

### Buffer Contents

The buffer tracks:

- **Entity types**: name, description, frequency count (how often this type has appeared across chunks)
- **Relationship types**: name, source type, target type, frequency count
- **Type variants**: raw type labels the LLM has produced that map to a canonical type (e.g., "Human" -> "Person", "Corp" -> "Organization")
- **Coverage score**: fraction of recently extracted types that match existing buffer entries, measured per document

### Schema Signal Extraction (pre-flight)

Before full extraction, each document goes through a lightweight first pass that identifies what categories and entity types are likely present in the text. This is a cheaper LLM call that returns only type signals, not full entities.

```
Scan the following text and list the categories of entities and
relationships you would expect to find. Do not extract specific
entities - only list the types.

Text:
{first_N_chunks_concatenated}

Return JSON:
{
  "entity_types": ["Person", "Organization", "Technology", ...],
  "relationship_types": ["WORKS_AT", "FOUNDED", ...]
}
```

The detected signals are compared against the ontology buffer to compute a coverage score. High coverage (> 0.8) means the buffer already knows about most types in this document - extraction can proceed with tight constraints. Low coverage (< 0.5) means the document contains unfamiliar territory - the extraction prompt loosens constraints and the buffer prepares to accept new types.

This coverage score is also a drift detection signal. If coverage drops across a batch of documents, it indicates the source material is shifting away from the ontology's domain.

### Feedback Loop

After each document's chunks are extracted, the results feed back into the buffer:

1. **Type accumulation**: new entity types and relationship types increment their frequency counters. Types that appear only once in a single document are held as candidates. Types that appear across multiple documents are promoted to confirmed
2. **Variant detection**: the LLM is asked to check if any new types are variants of existing buffer types. For example, if the buffer has "Organization" and extraction produces "Company", the LLM evaluates whether these are the same concept. If yes, "Company" is added as a variant mapping to "Organization"
3. **Relationship pattern validation**: new relationship types are checked for consistency - do the source and target types make sense? A relationship "WORKS_AT" from Person to Technology would be flagged as suspicious

### Refinement Trigger

Ontology refinement does not run after every single document - that would be too expensive. Instead, refinement triggers on:

- **Document count threshold**: every N documents (configurable, default 5)
- **Coverage drop**: when coverage falls below a threshold for consecutive documents
- **New type accumulation**: when more than M candidate types are pending promotion

The refinement pass sends the current buffer state and pending candidates to the LLM:

```
You are maintaining a knowledge graph ontology. Here is the current
ontology state:

Entity types: {buffer_entity_types_with_frequencies}
Relationship types: {buffer_relationship_types}
Pending candidates: {candidate_types_with_frequencies}
Type variants detected: {variant_mappings}

Based on the extraction evidence so far, propose refinements:
1. Which candidates should be promoted to confirmed types?
2. Which candidates are variants of existing types?
3. Should any existing types be merged or renamed?
4. Are any relationship type constraints missing?

Return the updated ontology as JSON.
```

### Buffer Flush

At the end of the ingestion run, the final buffer state is written to `.kg-builder/ontology.yml`. This means:

- **Free extraction** produces an ontology as a side effect - the next run can start constrained
- **Constrained extraction** produces a refined ontology that incorporates what the documents actually contained
- The flushed ontology includes frequency data as comments, so the user can see which types were common vs rare

## LLM Extraction

Each chunk is sent to the LLM with a prompt that instructs it to extract entities and relationships in a structured JSON format. The prompt is dynamically constructed from the current ontology buffer state.

### Extraction Modes

The extraction prompt adapts based on buffer state and coverage:

- **High coverage, constrained**: buffer has confirmed types matching the document's signals. Prompt uses strict `ONLY these types` language. This produces the most consistent output
- **Low coverage, constrained**: buffer exists but doesn't cover this document well. Prompt uses the known types but adds `If you encounter entities that don't fit these types, extract them with your best type label and flag them as NEW`
- **Free extraction**: no buffer types yet (early in a free extraction run). Prompt gives the LLM full freedom. Extracted types feed into the buffer for subsequent documents

### Prompt Structure

```
You are a knowledge graph extraction system. Extract entities and relationships
from the following text.

[If buffer has confirmed types:]
Use these entity types: {entity_types_with_descriptions}
Use these relationship types: {relationship_types_with_source_target}
[If coverage is high:] Do NOT create types outside this list.
[If coverage is low:] If entities don't fit these types, use your best
judgment and prefix the type with NEW_ to flag it for review.

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

**Ontology schema consolidation**: with the buffered ontology, most type consolidation happens incrementally during the feedback loop (variant detection). However, a final consolidation pass after all documents are processed catches any remaining type sprawl - particularly from the last few documents whose feedback was never refined. This pass uses the buffer's variant mappings to rename all entities to their canonical types before loading.

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

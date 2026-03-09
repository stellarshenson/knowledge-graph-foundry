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
| PDF | `pymupdf4llm` | Converts to structured Markdown with layout, tables, and image extraction |
| TXT / MD | built-in | Read as-is |
| DOCX | `python-docx` | Extracts paragraph text, ignores formatting |

The parser outputs a list of text segments with source metadata (file path, page number or line offset). This metadata propagates through chunking into the final extraction output, enabling traceability from any entity back to its source location.

### PDF Parsing with pymupdf4llm

PDF parsing uses `pymupdf4llm` rather than raw `pymupdf`. Built on top of PyMuPDF, pymupdf4llm converts complex PDFs into structured Markdown with layout reconstruction, table preservation, and image handling. The key API:

```python
import pymupdf4llm

# Basic text + tables as Markdown
md_text = pymupdf4llm.to_markdown("document.pdf")

# With image extraction to disk
md_text = pymupdf4llm.to_markdown("document.pdf",
                                  write_images=True,
                                  image_path="extracted_images/")

# Per-page chunks for RAG pipelines
chunks = pymupdf4llm.to_markdown("document.pdf", page_chunks=True)
```

The layout model (`pymupdf.layout`) activates ONNX-based block detection for realistic table structures and figure placement. Tables are converted to Markdown table syntax, figure captions are preserved, and images are referenced by path in the output Markdown.

### Image Description Enrichment

PDFs containing charts, plots, diagrams, or photographs lose critical information when only text is extracted. A survival curve, an architecture diagram, or a data visualization may carry the core insight of a document section - yet plain text extraction produces only the figure caption.

The image description pipeline addresses this by running extracted images through a vision model and injecting the resulting descriptions back into the parsed text before chunking:

1. Extract text as Markdown with `write_images=True` (images saved to disk, referenced in Markdown)
2. Parse image references from the Markdown output (both `![alt](path)` and `<img>` formats)
3. Send each image to a vision model with a description prompt
4. Replace image references in the Markdown with the original reference plus a text description block

This produces Markdown that contains both the original text and natural-language descriptions of all visual content. When this enriched text is chunked and sent to the extraction LLM, entities and relationships depicted in charts and diagrams become extractable - a chart showing "Treatment A outperforms Treatment B" yields the same relationship triple that a text sentence would.

The vision model is configurable separately from the extraction LLM. For local processing, smaller vision models (LLaVA 7B) provide adequate descriptions. For production quality, larger multimodal models produce richer descriptions. Image description is optional - configured via `describe_images: true` in the extract section of `config.yml`. When disabled, pymupdf4llm still extracts and references images, but they are not interpreted for text content.

### Tables and Images as Graph Elements

Tables and images extracted from PDFs can be stored as separate element nodes (`TableElement`, `ImageElement`) in Neo4J, linked to their parent Chunk via `HAS_ELEMENT`. Rather than folding all content into the chunk text, this preserves the original structure as a distinct graph element that downstream queries can target directly.

Tables are stored as markdown or HTML text in a node property - this preserves row/column structure for downstream LLM interpretation without requiring the retrieval layer to re-parse PDF layout. Images can be stored as base64 in a node property (convenient but large) or as an external file path (lighter, requires file access at query time).

Both element types can carry their own embeddings for similarity search. Images use multimodal embedding (CLIP) for visual similarity, while tables use text embedding of their markdown representation or a generated description. This enables queries like "find tables showing revenue figures" or "find diagrams of network architecture" to match against element-specific embeddings rather than the parent chunk's general embedding.

This is optional - simpler pipelines can inline table text and image descriptions directly into chunk text during parsing. Element nodes add graph complexity but improve retrieval precision when documents contain many tables or figures that need to be individually addressable.

## Chunking Strategy

Token-based splitting using `langchain-text-splitters.TokenTextSplitter`. Character-based splitting risks cutting mid-word or mid-sentence, while token-based splitting aligns with LLM context limits.

**Parameters** (from `.kg-builder/config.yml`):
- `chunk_size`: 2000 tokens (default) - sized to give the LLM enough context per chunk without exceeding practical limits
- `chunk_overlap`: 200 tokens (default) - ensures entities spanning chunk boundaries appear in at least one complete chunk

**Chunk identity**: each chunk gets a deterministic ID derived from SHA1 of its content. This allows idempotent re-processing - re-running extraction on the same document produces the same chunk IDs and can be merged cleanly.

**Chunk linking**: chunks maintain their sequential order via metadata (chunk index within document). This is preserved in the extraction output and optionally in Neo4J as a `NEXT_CHUNK` relationship chain for downstream retrieval tasks.

### Semantic Chunking

As an alternative to token-based splitting, semantic chunking uses embedding similarity to detect natural topic boundaries within a document. Instead of cutting at fixed token intervals, the chunker generates embeddings for sliding windows of text and splits where cosine similarity between consecutive windows drops below a configurable threshold - indicating a topic shift.

Configured via `chunking_strategy: semantic` in `.kg-builder/config.yml`. The embeddings generated during chunking are retained on the resulting chunk objects, avoiding redundant embedding calls downstream.

Semantic chunking works best for documents with clear topic transitions - research papers, structured reports, policy documents - where fixed-size splits would cut across conceptual boundaries. For homogeneous text or when predictability matters more than boundary quality, token-based splitting remains the default (`chunking_strategy: token`).

### Parent-Child Chunking

Large chunks may contain diverse topics producing noisy embeddings that reduce similarity search accuracy. A single 2000-token chunk covering three different concepts produces an embedding that is a weak match for any one of them individually.

The parent-child model addresses this by splitting each chunk (parent) into smaller sub-chunks (children) and embedding only the children. During retrieval, similarity search matches against child embeddings for precise semantic targeting, then traverses to the parent chunk for full surrounding context. The child provides the match signal, the parent provides the context window.

In Neo4J this is represented as `(:Chunk)-[:HAS_CHILD]->(:Chunk {is_child: true})` with embeddings stored on child nodes only. Parent chunks retain their text but do not carry embeddings - they serve as context containers. Configured via `parent_child_chunking: true` in config, with `child_chunk_size` controlling the sub-chunk token size (default scales relative to the parent `chunk_size`).

### Page and Section Structure

For documents with clear page boundaries (PDFs) or section headers (research papers, manuals), the lexical graph can include Page and Section nodes that capture the document's structural hierarchy.

Page nodes sit between Document and Chunk in the graph: `(:Document)<-[:PART_OF]-(:Page)<-[:PART_OF]-(:Chunk)` with a `NEXT_PAGE` chain linking pages in order. This enables page-level reconstruction - retrieving all chunks from a specific page or page range without scanning the full chunk sequence.

Section and Subsection nodes enable retrieval of complete document sections: `(:Document)<-[:HAS_SECTION]-(:Section)<-[:HAS_SUBSECTION]-(:Subsection)<-[:PART_OF]-(:Chunk)`. This is particularly useful for structured documents where users query by section title ("What does the Methods section say about...").

Page metadata (page number) is always preserved on chunks regardless of whether Page nodes are created - the nodes add navigational structure on top of the existing metadata. Section detection relies on title/header elements identified during parsing - pymupdf4llm's layout model and Unstructured's `by_title` chunking both support this. These are optional enrichments to the core Document -> Chunk model, useful when retrieval needs page-level reconstruction or section-level filtering.

## Ontology Buffer

The ontology buffer is the central mechanism that makes the extraction pipeline adaptive. Rather than treating the ontology as a static input file read once at startup, the buffer holds the evolving ontology in memory throughout the entire ingestion run. Every document processed contributes back to it, so later documents benefit from what earlier documents taught the system.

### Initialization

The buffer is initialized from one of three sources:

- **From seed** (domain-informed mode): an ontology seed file in any format - OWL/RDF, JSON, markdown, plain text, or any other human-readable description of domain knowledge. All non-YAML, non-OWL inputs pass through an LLM normalization step that converts freeform content into the canonical YAML ontology format (see Ontology Normalization in SPEC.md). OWL/RDF files are normalized programmatically via owlready2. The normalized output is validated against Pydantic models before loading into the buffer. **The seed is suggestive, not prescriptive** - it provides initial vocabulary and domain context, but extraction is explicitly allowed to go beyond it. The resulting ontology may contain types, relationships, and connection patterns the seed never defined. The seed file is read-only - never modified
- **From YAML** (constrained mode): loads `.kg-builder/ontology.yml` as the starting schema. The buffer begins with a known set of entity types and relationship types. New types discovered during extraction can still be proposed, but require higher confidence to be accepted
- **Empty** (free extraction mode): the buffer starts with no types defined. The first few documents establish the initial ontology, which then stabilizes as more documents are processed

When both seed and YAML are configured, the YAML takes precedence for overlapping type definitions. The seed fills in types not covered by the YAML - this allows using a broad domain description as background knowledge while maintaining a curated application schema on top. In all cases, the buffer is free to evolve beyond its initial state. Seed-sourced types carry higher initial confidence but discovered types that appear consistently across documents are promoted equally. The final flushed ontology represents what the data actually contains, not what the seed prescribed.

### Buffer Contents

The buffer tracks:

- **Entity types**: name, description, frequency count (how often this type has appeared across chunks), source (`seed`, `seed_normalized`, `yaml`, `discovered`), confidence (`high`, `medium`, `low` - normalized seeds carry confidence from the LLM normalization step)
- **Relationship types**: name, source type, target type, frequency count, transitive flag (from OWL `TransitiveProperty` if OWL seed)
- **Type hierarchy**: parent-child relationships between entity types (from OWL `subClassOf` or inferred by normalizer), used as context in extraction prompts
- **Type variants**: raw type labels the LLM has produced that map to a canonical type (e.g., "Human" -> "Person", "Corp" -> "Organization")
- **Disjoint constraints**: type pairs the seed considers incompatible (from OWL `disjointWith` or normalizer inference), logged as warnings during extraction but not enforced - the data may legitimately contain entities that bridge seed-defined boundaries
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

### DAG Validation

The ontology type hierarchy must be a directed acyclic graph - cycles in IS_A relationships are nonsensical (A is-a B is-a A). The buffer runs a topological sort on the type hierarchy at each refinement checkpoint. Detection is programmatic (no LLM cost), but resolution is LLM-assisted.

When a cycle is detected, the cycle edges and their participating types are passed to the LLM with context about each type's description, frequency, and source origin. The LLM decides which edge to remove or reclassify - it may determine that one IS_A relationship should actually be a HAS_PART or RELATED_TO, or that two types were incorrectly distinguished and should be merged. The LLM's resolution is presented to the user for confirmation in interactive mode, or applied automatically in batch mode with a warning logged.

DAG validation runs:
- After ontology normalization (when a freeform seed is converted to canonical YAML)
- After each buffer refinement pass
- Before the final buffer flush

Relationship type constraints (source/target type pairs) are not required to be acyclic - a `REPORTS_TO` relationship from Person to Person is valid. DAG enforcement applies only to the type hierarchy (IS_A edges between entity types).

### Buffer Flush

At the end of the ingestion run, the final buffer state is written to `.kg-builder/ontology.yml`. This means:

- **Free extraction** produces an ontology as a side effect - the next run can start constrained
- **Constrained extraction** produces a refined ontology that incorporates what the documents actually contained
- The flushed ontology includes frequency data as comments, so the user can see which types were common vs rare

## LLM Extraction

Each chunk is sent to the LLM with a prompt that instructs it to extract entities and relationships in a structured JSON format. The prompt is dynamically constructed from the current ontology buffer state.

### Pydantic Response Models

During extraction, ontology entity types are converted to Pydantic classes that serve as structured response models for the LLM. Each entity type becomes a class with `Field` descriptions drawn from the ontology, `field_validator` functions for property validation (lowercase normalization, pattern matching), and `json_schema_extra` providing few-shot examples that guide the LLM toward correct output structure.

The Instructor library wraps LLM calls and enforces Pydantic models against the response - validation failures trigger automatic retry with the error message, allowing the LLM to self-correct without manual intervention. This produces substantially more reliable structured output than raw JSON parsing with post-hoc validation.

Entity types should use distinct field names per type (e.g., `medication_name` instead of `name`, `condition` instead of `name`) to prevent LLM confusion when multiple types share the same JSON structure. These are mapped back to canonical property names during loading. For large ontologies with many entity and relationship types, a nested `ResponseModel` groups all types into a single structured response rather than a flat union list - each field is a typed list of one entity/relationship model. This reduces extraction failure rate compared to flat lists where the LLM loses track of which schema applies to which item.

When the schema is very large, subgraph splitting extracts entity subgraphs in separate LLM calls per chunk - higher cost but lower failure rate because each call handles a manageable subset of the full ontology. Configured via `subgraph_splitting: true`.

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

### Atomic Facts Extraction

Alongside entity-relationship extraction, the pipeline supports a parallel track that decomposes chunk text into atomic facts - the smallest indivisible statements that can stand alone as true or false claims. Where entity-relationship extraction captures the structural skeleton of the text (who, what, how connected), atomic facts capture the fine-grained detail that structure-only extraction routinely misses: specific dosages, exact dates, measurements, conditions, and qualifications.

Each atomic fact is stored as a `FactNode` in Neo4J, linked to its source chunk via `HAS_FACT`. Every fact node carries an embedding vector, making the full set of extracted statements searchable via semantic similarity - this is the foundation for the Graph Reader retrieval pattern described in the reference literature (85% precision, 95% recall on detail-oriented queries).

Three extraction modes control which tracks run:
- `extraction_mode: entity_relationship` (default) - standard entity and relationship extraction only
- `extraction_mode: graph_reader` - atomic facts only, no entity-relationship extraction
- `extraction_mode: hybrid` - both tracks run per chunk, producing entities, relationships, and atomic facts

Hybrid mode is recommended for production workloads where downstream queries need both structural graph traversal and fine-grained semantic search. The cost is roughly 2x the LLM calls per chunk compared to single-track modes.

### Chunk Batching

For efficiency, multiple small chunks can be combined into a single LLM call (configurable via `concurrency`). The trade-off: larger batches reduce API calls but may reduce extraction quality as the LLM has more text to process at once. Default is one chunk per call with parallel requests controlled by `concurrency`.

### Rolling Context Window

For documents where extraction order matters (instructional manuals, sequential processes, step-by-step guides), later chunks may reference entities introduced in earlier chunks without restating them. Extracting each chunk independently loses these cross-chunk references - a process step mentioning "the solution from Step 3" yields nothing if the extraction prompt has no knowledge of Step 3.

A rolling context window passes the N most recent extraction results as additional context in the prompt, maintaining continuity across chunks. The extraction prompt includes a summary of recently extracted entities and relationships so the LLM can resolve backward references and maintain sequential relationships. This prevents gaps in process chains, chapter references, and instructional sequences that would occur with fully independent chunk extraction.

Configured via `rolling_context_window: N` in config (default 0 = disabled, each chunk extracted independently). Higher values increase prompt token usage but improve extraction completeness for sequential documents.

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

**Resolution pipeline**: entity resolution uses an escalating-cost pipeline where cheaper methods handle easy cases before expensive LLM calls process the remainder:

1. **Exact ID match** - entities sharing the same `(type, id)` tuple are merged directly (zero cost, handled during deduplication)
2. **Embedding similarity** - entity name embeddings are compared pairwise within each type group. Pairs exceeding a configurable cosine similarity threshold (default 0.85) are flagged as candidate matches. This is substantially faster than LLM clustering for large entity sets - O(n) embedding calls plus vectorized similarity vs O(n) LLM calls
3. **LLM-based clustering** - remaining unresolved entities (those below the embedding threshold but above a lower bound) are sent to the LLM with a clustering prompt. This catches semantic equivalences that surface-level similarity misses ("the Cupertino giant" and "Apple Inc.")

A lightweight SpaCy + fuzzy string matching pre-filter runs before step 2 to group obvious lexical variants (case differences, abbreviation expansions, minor typos) without consuming embedding API calls. This pre-filter uses token overlap and Levenshtein ratio, not semantic understanding, so it is conservative - false negatives proceed to embedding comparison.

The LLM clustering prompt for step 3:

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
  <-[:PART_OF]- (:Page {number})                                          # optional
    <-[:PART_OF]- (:Chunk {id, text, index, page})
      -[:HAS_ENTITY]-> (:Entity:Person {id, name, embedding, description, ...})
      -[:HAS_ENTITY]-> (:Entity:Organization {id, name, embedding, description, ...})
      -[:HAS_FACT]-> (:FactNode {id, text, embedding})
      -[:HAS_ELEMENT]-> (:TableElement {markdown, embedding})             # optional
      -[:HAS_ELEMENT]-> (:ImageElement {description, path, embedding})    # optional
      -[:HAS_CHILD]-> (:Chunk {text, embedding, is_child: true})          # optional

(:Page)-[:NEXT_PAGE]->(:Page)
(:Chunk)-[:NEXT_CHUNK]->(:Chunk)
(:Entity:Person)-[:WORKS_AT]->(:Entity:Organization)
(:Entity)-[:INSTANCE_OF]->(:OntologyType {name, description})
(:OntologyType)-[:IS_A]->(:OntologyType)

Vector index: entity_embeddings ON Entity.embedding (cosine, 1536d)
Fulltext index: entity_names ON Entity.name
```

- `Document` node tracks source file metadata
- `Page` nodes (optional) sit between Document and Chunk, linked by `NEXT_PAGE` chain for page-level reconstruction
- `Chunk` nodes store the original text and link to their parent document (or parent page when page nodes are present)
- Entity nodes carry both the base `Entity` label and their type label (e.g., `Person`, `Organization`)
- `FactNode` stores atomic facts extracted from chunks (when using `graph_reader` or `hybrid` extraction mode), each carrying an embedding for semantic search
- `TableElement` and `ImageElement` nodes (optional) store extracted tables and images as separate graph elements linked to their source chunk via `HAS_ELEMENT`
- Child chunks (optional) are sub-chunks of a parent chunk used for parent-child retrieval - embeddings live on child nodes only
- `OntologyType` nodes represent the type hierarchy with `IS_A` edges between types and `INSTANCE_OF` links from entities to their ontology type
- Typed relationships connect entities as extracted by the LLM
- `HAS_ENTITY` relationships from chunks to entities enable provenance queries
- Vector index on `Entity.embedding` supports semantic entity search and embedding-based resolution
- Fulltext index on `Entity.name` supports fast text-based entity lookup and fuzzy matching

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

**Dual indexing** for retrieval: beyond the structural indexes needed for MERGE, the loader creates a vector index and a fulltext index on entity nodes to support downstream search:

```cypher
CREATE VECTOR INDEX entity_embeddings IF NOT EXISTS
FOR (n:Entity) ON (n.embedding)
OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}

CREATE FULLTEXT INDEX entity_names IF NOT EXISTS
FOR (n:Entity) ON EACH [n.name]
```

The vector index enables semantic similarity search across entities (used by the embedding-based entity resolution step and by downstream retrieval queries). The fulltext index supports fast text-based lookup, autocomplete, and fuzzy name matching. Both indexes are created idempotently with `IF NOT EXISTS` so re-runs are safe.

**Batch size**: configurable (default 500), balancing transaction overhead against memory usage. Deadlock retries (3 attempts with backoff) handle concurrent write conflicts.

### Post-Load Validation

After loading, a validation pass checks graph integrity using Cypher queries. This catches structural problems that individual entity or relationship loads would not detect - orphan entities with no relationships, missing expected relationship types per entity type, node counts by label falling outside expected ranges, and relationship type coverage against the ontology.

Validation results are included in the extraction output JSON and logged as warnings. Failures do not block loading - they are advisory, allowing the user to decide whether to investigate or accept the current state. Configured via `validate: true` in the load section of config.

## Post-Load OWL Reasoning

When the ontology buffer was seeded from an OWL file and `post_load_reasoning` is enabled, an inference pass runs after loading the graph into Neo4J. This materializes implicit relationships that the LLM did not explicitly extract but that follow logically from the ontology's formal semantics.

### What the Reasoner Does

The owlready2 HermiT reasoner operates on the OWL ontology augmented with individuals (entities) from the extracted graph. It produces:

- **Subclass propagation**: if an entity is typed as `Dog` and the ontology defines `Dog rdfs:subClassOf Mammal rdfs:subClassOf Animal`, the reasoner infers `INSTANCE_OF` edges to `Mammal` and `Animal`. These are materialized as additional relationships in Neo4J
- **Transitive closure**: for properties marked as `owl:TransitiveProperty` (e.g., `REPORTS_TO`, `PART_OF`), the reasoner computes the full transitive chain. If A `REPORTS_TO` B and B `REPORTS_TO` C, the inferred edge A `REPORTS_TO` C is added
- **Consistency checking**: disjoint class constraints from the OWL ontology flag entities that were incorrectly assigned to incompatible types during extraction. These are logged as warnings rather than silently corrected

### Pipeline

1. Export the loaded Neo4J graph as RDF triples (using n10s or direct serialization)
2. Load the RDF into owlready2 alongside the original OWL ontology
3. Run the HermiT reasoner via `sync_reasoner()`
4. Collect inferred triples that are new (not already in the graph)
5. Import the inferred relationships back into Neo4J

Alternatively, for simpler inference patterns (subclass propagation only), a Cypher-based approach avoids the RDF export round-trip:

```cypher
MATCH (i)-[:INSTANCE_OF]->(c)-[:SUBCLASS_OF*]->(sup)
MERGE (i)-[:INSTANCE_OF]->(sup)
```

For lightweight continuous inference, APOC periodic rules can run inside Neo4J:

```cypher
CALL apoc.periodic.repeat(
  "subclassRule",
  "MATCH (i)-[:INSTANCE_OF]->(c)-[:SUBCLASS_OF]->(sup)
   MERGE (i)-[:INSTANCE_OF]->(sup)",
  60
);
```

### When to Use

Post-load reasoning is most valuable when:
- The domain has deep type hierarchies (biomedical, industrial, organizational)
- Downstream queries need to find entities by ancestor type (e.g., "all Animals" should include Dogs)
- Transitive relationships are important for graph traversal (reporting chains, part-of hierarchies)
- Consistency validation is needed to catch extraction errors

It adds processing time and is not necessary for flat ontologies with no subclass relationships or transitivity. Default is off.

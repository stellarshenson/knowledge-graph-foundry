# Devil's Advocate - kg-builder-cli DESIGN.md

## The Devil

**Role**: Senior backend engineer with 15+ years building production data pipelines, reviewing a design document for implementation readiness
**Cares about**: implementation complexity, runtime predictability, maintenance burden, time-to-first-value
**Style**: data-driven, pragmatic, allergic to speculative architecture
**Default bias**: skeptical of agent-heavy designs, prefers deterministic pipelines, suspicious of LLM-in-the-loop for infrastructure decisions
**Triggers**: overengineering, optional features described as core, missing confidence/provenance on extracted data, vague error handling
**Decision**: approve for implementation, request simplification, or reject sections as premature

---

## Concern Catalogue

### 1. "Agents are overused - most ingestion steps should be deterministic pipelines"

**Likelihood: 5** | **Impact: 4** | **Risk: 20**

**Their take**: Every command spawns an agent. That is three agents for what should mostly be a deterministic pipeline with LLM steps injected at specific points. Agents introduce latency, unpredictability, and debugging difficulty. When extraction fails at chunk 47 of 200, I want a stack trace, not a conversation. The ingest pipeline should be code, not an agent deciding what to do next.

**Reality**: The Strands SDK agent model does provide tool orchestration, but the ingest pipeline's steps (parse -> chunk -> extract -> dedup -> resolve -> load) are sequential and deterministic. The agent adds value only for interactive schema inference and ontology review. For batch ingestion, the agent layer is overhead.

**Response**: The design should clarify that the agent orchestrates the pipeline but individual steps are deterministic functions. The agent's role in `kg ingest` is primarily for interactive initialization and schema inference - batch extraction and loading should be direct function calls, not agent-mediated tool invocations. Consider making the agent optional for non-interactive batch runs.

### 2. "Too many optional features presented as core architecture"

**Likelihood: 5** | **Impact: 3** | **Risk: 15**

**Their take**: Page nodes, Section nodes, TableElement, ImageElement, child chunks, OWL reasoning, semantic chunking, parent-child chunking, image description enrichment - these are all marked "optional" but described with the same depth and prominence as core features. A new contributor reading this document cannot tell what they need to implement for a working v1 versus what is future scope. The design reads like a feature catalogue, not an implementation blueprint.

**Reality**: These features are genuinely optional enrichments. The document does mark them as optional. But the presentation gives them equal weight to core functionality.

**Response**: The design should explicitly define a "Core Model" (Document, Chunk, Entity, FactNode, OntologyType, Source) versus "Extensions" (Page, Section, TableElement, ImageElement, child chunks). Each optional feature should be marked with a visual indicator and the document should include a phased implementation section.

### 3. "LLM normalization of arbitrary ontology formats is a silent corruption risk"

**Likelihood: 4** | **Impact: 4** | **Risk: 16**

**Their take**: You let an LLM convert markdown prose into an ontology schema. That is ontology hallucination. The LLM will invent types, misinterpret relationships, and produce schemas that look plausible but are wrong. JSON should be deterministic mapping, not LLM interpretation. Only truly unstructured formats (markdown, plain text) should use the LLM path. The design treats all non-YAML, non-OWL formats the same way, which hides the risk.

**Reality**: The normalization pipeline does use Pydantic validation and confidence scoring. The output is presented for interactive review. But the design does not distinguish between formats that could be parsed deterministically (JSON with known structure) and formats that genuinely need LLM interpretation.

**Response**: Split normalization into two tiers: deterministic parsing (JSON with recognizable ontology structure -> direct mapping) and LLM interpretation (markdown, plain text, unknown formats). Add a validation step that compares LLM-normalized output against the source to flag potential hallucinations.

### 4. "Schema inference conversation loop will produce unstable schemas"

**Likelihood: 3** | **Impact: 4** | **Risk: 12**

**Their take**: The schema inference loop (sample -> propose -> review -> refine -> confirm) depends on conversation state. If the user asks slightly different questions in two sessions, they get different schemas for the same data. The schema should be a deterministic artefact derived from data profiling, not a conversation outcome. The LLM should propose, the user should edit a YAML file, done. Conversation history should not be a dependency.

**Reality**: The design does save the confirmed schema to `.kg-builder/schemas/` as a static file. But the interactive refinement loop means the same data can produce different schemas depending on conversation flow. Agent memory mitigates this by checking for prior sessions, but memory is advisory.

**Response**: Clarify that the conversation produces a static schema file which becomes the sole authority. Once saved, the schema is configuration, not conversation. Re-inference produces a fresh proposal compared against the existing schema, not a continuation of the previous conversation.

### 5. "Missing confidence model for extracted triples"

**Likelihood: 5** | **Impact: 5** | **Risk: 25**

**Their take**: This is the biggest gap. Entities, relationships, and facts are extracted with no confidence score. The normalization metadata stores `normalized_score` for resolution, but the extraction itself produces no confidence signal. Every triple looks equally trustworthy regardless of whether it came from a clear statement or an LLM inference from ambiguous text. Downstream reasoning, query ranking, and graph pruning all need confidence scores. Without them the graph is a flat assertion layer with no way to distinguish reliable facts from noise.

**Reality**: The design includes `normalized_score` for entity resolution and `confidence` for ontology normalization, but not for extracted entities or relationships. FactNodes store `embedding` but not `confidence`. The extraction output format (Section 19) has no confidence field on entities or relationships.

**Response**: Add `confidence` field to entities, relationships, and facts in the extraction output format. Confidence should reflect extraction certainty - derived from LLM self-assessment, cross-chunk corroboration (entity appears in multiple chunks), and ontology coverage (entity matches a known type vs NEW_ prefix). Store `extraction_model` on all extracted elements for provenance.

### 6. "Entity resolution lacks Levenshtein distance details and similarity matrix"

**Likelihood: 4** | **Impact: 3** | **Risk: 12**

**Their take**: The resolution pipeline mentions "Levenshtein ratio" in passing but does not specify thresholds, distance metrics, or how candidates are selected for pairwise comparison. For large entity sets, pairwise comparison is O(n^2). The design needs a similarity matrix approach with blocking strategies to make this tractable. Without it, resolution will either be too slow (comparing everything) or too lossy (arbitrary cutoffs).

**Reality**: The SpaCy+fuzzy pre-filter step mentions "token overlap and Levenshtein ratio" but provides no thresholds, no blocking strategy, and no description of how the similarity matrix is constructed or pruned. The embedding step says "pairwise within each type group" but does not address the O(n^2) scaling problem.

**Response**: Specify Levenshtein ratio thresholds (e.g., 0.85 for name matching), describe type-based blocking (only compare entities within the same type group), and add a similarity matrix construction step with configurable cutoff. For large entity sets, use approximate nearest neighbor (ANN) indexing on embeddings rather than brute-force pairwise comparison.

### 7. "No concurrency model for LLM calls"

**Likelihood: 3** | **Impact: 3** | **Risk: 9**

**Their take**: The config has `concurrency: 4` but the design never describes how parallel LLM calls are managed. Are chunks extracted in parallel? How are results merged? What about rate limiting across parallel calls? If four extraction calls modify the ontology buffer simultaneously, what is the synchronization model?

**Reality**: The design mentions `concurrency` as a config option and "parallel LLM requests" but does not describe the concurrency model. The ontology buffer is described as an in-memory structure that receives feedback after each document, but the interaction between parallel extraction and sequential buffer updates is not specified.

**Response**: Clarify that concurrency applies to chunk extraction within a single document - multiple chunks are extracted in parallel, but buffer feedback happens after all chunks from a document are collected. Documents are processed sequentially to maintain buffer consistency.

### 8. "Post-load OWL reasoning is a complexity trap"

**Likelihood: 3** | **Impact: 2** | **Risk: 6**

**Their take**: The HermiT reasoner pipeline (export to RDF -> load into owlready2 -> reason -> import inferred triples) is a full round-trip through two different graph representations. This is fragile, slow, and adds a heavy dependency. The Cypher-based alternative is simpler and covers the most common case (subclass propagation). The full reasoning pipeline should be removed from v1 and replaced entirely by the Cypher approach.

**Reality**: The design already presents the Cypher-based approach as an alternative. Post-load reasoning is optional and off by default.

**Response**: Mark the full HermiT pipeline as a future extension. Keep the Cypher-based subclass propagation as the v1 approach. This removes the n10s dependency and the RDF export complexity.

### 9. "No data volume estimates or performance characteristics"

**Likelihood: 4** | **Impact: 3** | **Risk: 12**

**Their take**: The design never states what scale it targets. Is this for 10 documents or 10,000? 1,000 entities or 1,000,000? The batch size of 500 and concurrency of 4 suggest small-to-medium scale, but the entity resolution pipeline with embedding similarity suggests larger ambitions. Without scale targets, I cannot evaluate whether the architecture is appropriate.

**Reality**: No performance targets, scale estimates, or benchmarking strategy are mentioned anywhere in the document.

**Response**: Add a "Scale and Performance" subsection with target ranges (e.g., "designed for 10-10,000 documents, 1,000-100,000 entities per graph") and note where architecture decisions change at different scales.

### 10. "The module structure lists 30+ files but has no interface contracts"

**Likelihood: 3** | **Impact: 3** | **Risk: 9**

**Their take**: Section 16 lists files and describes what each module does, but there are no function signatures, no data flow types, no interface contracts. What does `buffer.py` expose? What data structure does `extraction/unstructured.py` pass to `loading/loader.py`? Without these, the module structure is a file listing, not a design.

**Reality**: The section describes interface boundaries in prose ("loading/ depends only on config/ for connection details, receives entities and relationships as data structures") but does not define the data structures or function signatures.

**Response**: Add key interface types - at minimum the data structures passed between major modules (extraction output -> loader input, buffer state -> prompt constructor, config -> all modules). Pydantic models for these interfaces would make the design implementable.

---

## Scorecard

| # | Concern | Risk | Score | Residual | How addressed |
|---|---------|------|-------|----------|---------------|
| 1 | Agent overuse | 20 | 40% | 12.0 | Section 2 describes agents as command-level orchestrators but does not distinguish interactive vs batch modes. No mention of deterministic pipeline fallback |
| 2 | Optional features as core | 15 | 45% | 8.3 | Individual features marked "optional" in prose but no consolidated core vs extensions distinction |
| 3 | LLM normalization risk | 16 | 55% | 7.2 | Section 5.2 mentions Pydantic validation, confidence scoring, and interactive review. Does not distinguish deterministic vs LLM parsing paths for different formats |
| 4 | Schema inference instability | 12 | 60% | 4.8 | Section 7.3 saves schema to static file, memory checks for prior sessions. Does not explicitly state schema-as-configuration principle |
| 5 | Missing confidence model | 25 | 15% | 21.3 | Only `normalized_score` for resolution. No confidence on extracted entities, relationships, or facts. Extraction output format (Section 19) has no confidence field |
| 6 | Missing Levenshtein/similarity matrix details | 12 | 25% | 9.0 | Section 6.7 mentions "Levenshtein ratio" once. No thresholds, no blocking strategy, no similarity matrix, no ANN for embeddings |
| 7 | No concurrency model | 9 | 20% | 7.2 | `concurrency: 4` in config, "parallel LLM requests" mentioned. No synchronization model for buffer updates during parallel extraction |
| 8 | OWL reasoning complexity | 6 | 70% | 1.8 | Marked optional, off by default, Cypher alternative provided. Still presented with full implementation detail |
| 9 | No scale targets | 12 | 5% | 11.4 | No performance targets, volume estimates, or benchmarking strategy anywhere in the document |
| 10 | Module structure lacks interfaces | 9 | 35% | 5.9 | Prose descriptions of boundaries but no data types, function signatures, or interface contracts |

**Document score (total residual risk)**: 88.9 (lower = better, max 136)

**Top gaps** (highest residual risk):
1. **#5 - Missing confidence model** (residual 21.3) - no extraction confidence on entities/relationships/facts
2. **#1 - Agent overuse** (residual 12.0) - no distinction between interactive and batch pipeline modes
3. **#9 - No scale targets** (residual 11.4) - no performance or volume characteristics
4. **#6 - Missing Levenshtein/similarity matrix** (residual 9.0) - entity resolution lacks implementation detail
5. **#3 - LLM normalization risk** (residual 7.2) - no tiered parsing strategy by format type

---

## Recommended Corrections

### Correction 1: Add confidence model to extraction output (addresses #5)

Add `confidence` and `extraction_model` fields to entities, relationships, and facts in Section 19 extraction output format. Add a paragraph to Section 6.4 explaining confidence derivation (LLM self-assessment, cross-chunk corroboration, ontology match).

**Expected effect**: #5 from 15% to 85% (residual 3.8), net improvement 17.5

### Correction 2: Add Levenshtein thresholds and similarity matrix to entity resolution (addresses #6)

Expand Section 6.7 SpaCy+fuzzy step with specific thresholds, blocking strategy, and similarity matrix construction. Add ANN for embedding comparison at scale.

**Expected effect**: #6 from 25% to 85% (residual 1.8), net improvement 7.2

### Correction 3: Add scale targets section (addresses #9)

Add a "Scale and Performance Targets" subsection to Section 2 or as a new Section 14.5 with target document counts, entity counts, and notes on where architecture decisions change at scale.

**Expected effect**: #9 from 5% to 70% (residual 3.6), net improvement 7.8

### Correction 4: Clarify agent vs deterministic pipeline boundary (addresses #1)

Add a paragraph to Section 2 distinguishing interactive agent mode from deterministic batch mode. The agent orchestrates initialization and interactive operations; batch extraction/loading are direct function calls.

**Expected effect**: #1 from 40% to 75% (residual 5.0), net improvement 7.0

### Correction 5: Add concurrency model (addresses #7)

Add a paragraph to Section 6.4 clarifying that concurrency applies within documents (parallel chunk extraction), buffer feedback is per-document (sequential), and documents are processed sequentially.

**Expected effect**: #7 from 20% to 80% (residual 1.8), net improvement 5.4

### Correction 6: Distinguish core vs extension features (addresses #2)

Add a "Core vs Extensions" note to Section 8 listing the minimal graph model (Document, Chunk, Entity, FactNode, OntologyType, Source) and marking all other node types as extensions.

**Expected effect**: #2 from 45% to 80% (residual 3.0), net improvement 5.3

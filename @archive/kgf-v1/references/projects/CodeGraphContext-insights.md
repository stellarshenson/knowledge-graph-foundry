# CodeGraphContext - Design Insights

Source: [CodeGraphContext](https://github.com/CodeGraphContext/CodeGraphContext)

Code indexing and graph analysis platform that builds knowledge graphs from source code using tree-sitter AST parsing. Supports Neo4j, KuzuDB, and FalkorDB as graph backends. Different domain (code analysis, not document/knowledge extraction) but several architectural patterns transfer well.

## Transferable Patterns

### Two-Pass Graph Construction

CGC builds the graph in two passes rather than a single traversal. Pass 1 creates all nodes (files, functions, classes, variables) and immediate containment relationships. Pass 2 resolves cross-file references (function calls, inheritance) using a pre-built import resolution map. This separation means entity creation never blocks on relationship resolution, and unresolved references degrade gracefully rather than failing the entire index.

Relevant to kg-builder-cli: our extraction pipeline already follows a similar pattern (extract entities, then resolve/deduplicate, then load), but the explicit pre-scan resolution map is worth adopting - building a lookup structure of all extracted entities before attempting cross-document relationship resolution would make the dedup/resolve stage more deterministic.

### Database Abstraction Layer

A single `DatabaseManager` interface supports three graph backends (Neo4j, KuzuDB, FalkorDB) with identical query semantics. KuzuDB is the default - an embedded graph database requiring zero configuration, useful for local development and testing. Neo4j is used for production/shared deployments.

Relevant to kg-builder-cli: we target Neo4j only, but the abstraction pattern is worth noting. KuzuDB as a local dev/test backend would eliminate the Neo4j dependency for development and CI. The interface is thin enough that adding it later would not require architectural changes if we keep our Neo4j interaction behind a clean boundary.

### Background Job Management

Long-running indexing operations run as tracked background jobs with queryable status and job IDs. The CLI returns immediately while indexing continues. Status can be checked via CLI or MCP queries.

Relevant to kg-builder-cli: our `--batch` mode could benefit from a similar pattern - launch ingestion as a tracked job, return a job ID, allow `kg status <job_id>` to check progress. This is lighter than a full TUI for batch workflows.

### MCP Server as Query Interface

CGC exposes 18+ tools via MCP, allowing AI assistants to query the code graph through natural language. The MCP layer translates tool calls into Cypher queries. Tool definitions are data structures, handlers are functional components.

Relevant to kg-builder-cli: our query agent already plans to use Cypher, but exposing the graph via MCP tools would allow external AI assistants to query our knowledge graph directly. Worth considering as a future extension.

### Pre-Scan Import Resolution Map

Before resolving function calls across files, CGC scans all files for imports and builds a `Dict[symbol_name] -> List[file_paths]` lookup. This enables accurate cross-file linking with graceful fallback for ambiguous references.

Relevant to kg-builder-cli: analogous to building an entity index before cross-document resolution. After extracting entities from all documents, build a `Dict[entity_name] -> List[entity_ids]` map before running the resolution pipeline. This pre-scan makes the resolution stage's blocking strategy (only compare within type groups) more efficient.

### Uniqueness Constraints

CGC uses composite uniqueness: `(name, path, line_number)` prevents duplicates while allowing same-named entities in different contexts. Clean MERGE semantics.

Relevant to kg-builder-cli: our entity ID scheme (`type_normalized_name`) serves the same purpose, but the composite constraint pattern is cleaner for structured provenance where the same entity name might appear in different source files with different semantics.

## Not Transferable

- **Tree-sitter parsing** - domain-specific to code analysis, not applicable to document extraction
- **No LLM in core pipeline** - CGC is purely structural analysis, LLM only at the query layer. Our extraction pipeline is fundamentally LLM-driven
- **Language-specific handlers** - 14 language parsers with custom extraction logic per language. Our parser diversity is format-based (PDF, text, JSON), not language-based
- **Live file watching** - watchdog integration for real-time graph updates during active development. Not relevant for document ingestion workflows

## Technology Overlap

| Component | CodeGraphContext | kg-builder-cli |
|-----------|-----------------|----------------|
| CLI framework | typer | typer |
| Logging | loguru | loguru |
| Graph DB | Neo4j, KuzuDB, FalkorDB | Neo4j |
| Agent framework | none (direct Cypher) | Strands SDK |
| Parsing | tree-sitter | pymupdf4llm, python-docx |
| LLM | none in core pipeline | Bedrock (extraction, resolution, ontology) |

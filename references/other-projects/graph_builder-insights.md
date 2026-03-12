# ContextClue Graph Builder

**Repository**: https://github.com/Addepto/graph_builder

Structured data extraction and graph assembly system focused on tabular data from documents (PDFs, CSVs, Excel). Fundamentally different from KGF in scope - extracts table structures rather than semantic entities from free text.

## Architecture

Pipeline: Identifiers -> Instances -> Enrichment Matching -> Enrichment Models -> Hierarchy Detection -> Fuzzy Enrichment

Multi-stage sequential enrichment rather than monolithic extraction. Includes FastAPI REST wrapper for web deployment.

## Relevant Patterns

### Automatic Header Detection from PDFs
- Multi-method system: semantic classifier (rule-based scoring), layout analyzer (font size clustering), pattern recognizer (regex), hybrid scoring (weighted combination)
- Optional LLM refinement layer for merging/canonicalizing header candidates
- Applicable if KGF adds document structure analysis before LLM extraction

### Collection-Aware Entity Management
- All operations accept optional `collection` parameter for namespace isolation
- Name maps refreshed per collection
- Relations and queries filter by collection
- Clean multi-tenant pattern - validates KGF's approach

### Hierarchy Detection via Separator Normalization
- Decomposes identifiers by separators (`-`, `/`, `_`, spaces)
- Finds implicit parent nodes not explicitly present in data
- Creates parent-child edges automatically
- Not directly applicable (KGF derives hierarchy semantically), but pattern for implicit node generation is interesting

### Enrichment via Fuzzy Matching
- Substring/normalized-value matching between entity attributes and table rows
- Confidence assignment: "high" (1 match), "medium" (multiple matches)
- Separation of enrichment logic from graph assembly is clean

### Extraction Configuration Models (Pydantic)
- `TableFromHeaderExtractionConfig` (PDF with manual headers)
- `TableMultilineExtractionConfig` (complex multi-line tables)
- `TableWithContextExtractionConfig` (tables with surrounding context)
- `TableXlsExtractionConfig` (Excel with sheet/row config)
- `TextExtractionConfig` (unstructured text)
- Document-level configs vs KGF's semantic-level configs

### Relation Metadata Pattern
- Relations stored as tuples: `(relation_type, entity_id, r_data)`
- `r_data` dict stores confidence scores and other metadata
- Clean pattern for relation provenance tracking

## Applicability to KGF

**Direct code reuse**: minimal - different extraction paradigm (tabular vs semantic LLM)

**Conceptual value**:
- Multi-stage assembly pipeline validates KGF's fluid-to-cured lifecycle design
- Collection-aware entity management confirms KGF's isolation patterns
- Confidence metadata on relations is useful pattern for relation provenance
- Declarative extraction configs could model document-specific extraction hints

**Not applicable**:
- PDF table extraction via pdfplumber (KGF uses LLM-based semantic extraction)
- Hierarchy from naming conventions (KGF derives hierarchy semantically)
- Simple fuzzy string matching (KGF uses Bayesian multi-signal resolution)
- FastAPI deployment model (KGF is CLI-first)

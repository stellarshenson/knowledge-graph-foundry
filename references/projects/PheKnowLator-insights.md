# PheKnowLator - Phenotype Knowledge Translator

**Repository**: https://github.com/callahantiff/PheKnowLator

Mature Python framework for constructing biomedical knowledge graphs from structured data sources and pre-existing OWL ontologies. Fundamentally different from KGF - it merges pre-defined ontologies (Gene Ontology, HPO, ChEBI) and constructs edge lists from curated biomedical databases (CTD, Reactome, Ensembl), rather than extracting from unstructured text via LLM.

## Architecture

Pipeline: Download Data -> Create Edge Lists -> Merge Ontologies -> Construct Graph -> Decode OWL -> Output KGs

Two construction approaches:
- **Instance-based**: intermediate UUID nodes connecting subject/object via `owl:NamedIndividual`
- **Subclass-based**: direct `rdfs:subClassOf` with OWL Restrictions

Outputs: RDF/XML, N-Triples, integer-mapped triples, NetworkX MultiDiGraph.

## Relevant Patterns

### Entity Mapping & Deduplication
- Pre-computed entity-to-ontology mappings via pickled dictionaries
- Declarative filter criteria DSL for data quality (numeric thresholds, regex, dedup rules)
- Dedup strategy: sort by column, drop duplicates keeping first occurrence
- Identifier mapping via Pandas merge (1:N mapping files)
- **Deterministic** - no probabilistic matching, no multi-signal scoring

### Ontology Validation (Applicable to Curing Heuristics)
- Punning detection: same entity declared as class and individual
- Obsolescence removal: deprecated classes filtered
- Connectivity checks: synonymous classes linked via `rdfs:subClassOf`
- Identifier consistency validation

### Node Metadata Model
- Two-level dictionary: entity type -> entity URI -> {Label, Description, Synonym}
- Pre-built from domain databases, stored as pickled files
- Applied during KG construction as RDFS labels/comments
- Mirrors KGF type clustering + per-entity extraction

### OWL-NETS Semantic Decoding
- Removes OWL-encoded semantic edges to create simplified property graphs
- Decodes `owl:Restriction`, `owl:someValuesFrom`, `owl:onProperty`
- Filters namespace-based edges (ISO, SUMO, BFO removed; RO kept as predicates)
- Not applicable to KGF (no formal OWL semantics), but shows pattern for ontology simplification

## Applicability to KGF

**Direct code reuse**: minimal - different problem domain (structured biomedical vs unstructured documents)

**Conceptual value**:
- Ontology validation checks could inform curing heuristics (punning, connectivity, consistency)
- Two construction approaches (instance vs subclass) could map to different Neo4j loading strategies
- Metadata model validates KGF's approach to storing entity descriptions/synonyms
- Declarative filter criteria pattern could model pre-ingestion quality gates

**Not applicable**:
- Pre-defined biomedical ontologies (KGF discovers schema adaptively)
- File-based identifier mapping (KGF uses Bayesian multi-signal resolution)
- OWL reasoning and RDF triple generation (KGF outputs Neo4j property graphs)
- Domain-specific data sources (KGF is domain-agnostic)

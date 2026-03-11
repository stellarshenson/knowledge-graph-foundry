# Failure Hypothesis Analysis - Benchmark v15 (73%)

Three systemic architectural failures explain the stalled benchmark score. These are not threshold problems - they are structural gaps in the pipeline.

## H1: Double Type Enforcement (CONFIRMED)

**Hypothesis**: Type clustering (LLM-assisted) runs at curing time and decides canonical types, but `_enforce_ontology_types()` runs AGAIN inside `accumulator.consolidate()` and overwrites those decisions.

**Evidence**:
- `cli.py:406-435` - Type clustering produces approved mapping, applied via `apply_type_mapping()`
- `accumulator.py:81-86` - Consolidation calls `_enforce_ontology_types()` on the SAME entities
- Types like Mode, Gas, Software are decided as canonical by clustering, then enforcement doesn't find them in the ontology type list and either remaps them badly (v14) or keeps them as singletons (v15)
- v14 logs: Mode->Role (0.50), Gas->Accessory (0.33) - destructive remaps
- v15 logs: "Type kept: 'Mode' for 'Standby'" - correct but creates 12 singleton types

**Root cause**: Two independent type normalization steps operating on the same entities without coordination. Step 2 doesn't know step 1 already ran.

**Fix**: Skip `_enforce_ontology_types()` during consolidation when type clustering has already run. The clustering output IS the canonical type assignment - enforcement should not second-guess it.

**Impact**: Eliminates 12 singleton types (type_distribution 80% -> 100%) and prevents all absurd remaps.

## H2: Cross-Type Resolution Ignores Embeddings (CONFIRMED)

**Hypothesis**: The system generates 1024-dim Titan v2 embeddings per entity but `_resolve_cross_type()` only uses bag-of-words Jaccard similarity on descriptions. 50 cross-type duplicates persist because Jaccard can't capture semantic similarity.

**Evidence**:
- `resolution.py:157-232` - `_resolve_cross_type()` only calls `_description_similarity()` (Jaccard on word sets)
- `resolution.py:132-154` - Jaccard returns 0.0 when either description is empty, blocks all cross-type merges for sparse entities
- `embeddings.py:42` - Embeddings include type + name + description: `"{type}: {name} - {description[:200]}"`
- `resolution.py:258-266` - `_cosine_similarity()` already exists in the same file but is never called from cross-type resolution
- v15 logs show 60+ blocked cross-type merges, many with desc_sim between 0.0 and 0.15 - entities that describe the same thing in different words

**Concrete failure**: "Humidifier" appears as Component, Accessory, and Setting across documents. Description Jaccard = 0.00 (descriptions use different vocabulary). Embedding cosine similarity would be ~0.75+ because Titan encodes the semantic relationship.

**Fix**: Add embedding cosine similarity as a secondary gate in `_resolve_cross_type()`. When description similarity < 0.3 AND both entities have embeddings AND cosine similarity >= 0.75, allow the merge.

**Impact**: Cross-type duplicates 50 -> ~20-25 (target < 20). Improves cross_doc_resolution generative score.

## H3: Specification Entities Lack Structured Properties (CONFIRMED - FIX REJECTED)

**Hypothesis**: The extraction prompt produces Specification entities but doesn't parse numeric values and units into structured properties. The generative scorer sees "Pressure Range" as an entity name but no `value` or `unit` fields.

**Evidence**:
- Benchmark spec_extraction LLM score: 2/5
- 98 Specification entities exist in the graph but most lack `value` and `unit` properties
- The extraction prompt asks for entities with properties but doesn't specifically instruct parsing "4-20 cmH2O" into `{value: "4-20", unit: "cmH2O"}`
- The generative scorer checks whether specifications have concrete numeric values with units

**Rejected approach**: Regex-based post-extraction parser (`spec_parser.py`) to extract value/unit from entity names and descriptions. Rejected because parsing with fix rules increases model variance and fights against the LLM rather than leveraging it. Extraction should interpret, not parse.

**Correct approach**: Improve the extraction prompt so the LLM interprets and structures specification properties at extraction time. Each chunk is already analyzed in its own context window with the ontology buffer - the prompt should instruct the LLM to produce `value` and `unit` properties for Specification-type entities directly. This keeps interpretation in the LLM where semantic understanding lives, rather than attempting fragile regex post-processing.

**Impact**: spec_extraction generative 2/5 -> 3-4/5. Also improves query_answerability since spec queries return richer data.

## Priority and Expected Impact

| Fix | Complexity | Expected Score Impact |
|-----|-----------|----------------------|
| H1: Skip double enforcement | Low (remove 2 lines) | +3-5% (type_distribution 80->100%) |
| H2: Embedding cross-type gate | Medium (20 lines) | +5-8% (cross_doc + query_answerability) |
| H3: Spec interpretation in prompt | Medium (prompt update) | +3-5% (spec_extraction + query) |

Combined expected impact: 73% -> 84-91% hybrid score.

## Verification Plan

Each hypothesis was verified against code, logs, and benchmark output. No hypothesis relies on speculation - all are traced to specific code paths with line references.

For implementation:
1. H1 first (simplest, removes architectural bug)
2. H2 second (highest impact on the most-failed dimension)
3. H3 third (prompt improvement for spec interpretation - not regex parsing)
4. Benchmark after each fix to measure isolated impact

# Evidence Units: Ontology-Grounded Document Organization for Parser-Independent Retrieval

**Source**: https://arxiv.org/abs/2604.00500
**Authors**: Yeonjee Han, Rock Sakong, Jaemin Na (KT / Korea Telecom)
**Venue/Date**: Preprint, April 2026

## Summary

Evidence Units (EUs) is a parser-independent chunking pipeline that groups visual assets (tables, figures) with their contextual text into semantically complete retrieval units, instead of indexing each parsed element separately. On a 1,340-page OmniDocBench subset (1,551 QA pairs), EU chunking raises retrieval Recall@1 from 15.0% to 51.1% (3.4x) and average LCS from 0.50 to 0.81.

## Method

- Ontology-grounded role normalization extending DoCO/SPAR (a Document Structure Ontology) maps heterogeneous parser labels to canonical roles via pattern matching, a TYPE_MAP, then embedding fallback
- Three-phase EU construction: visual seeds anchor units, structural elements attach by proximity, paragraphs attach by a global paragraph x EU similarity matrix (threshold tau=0.40)
- Graph-based decision layer stores D1 construction rules as Neo4j nodes with NEXT chains; two completeness invariants (anchoring, type consistency)
- "EU spatial footprint convergence": union bbox of a full EU converges across parsers (MinerU, Docling) even when individual element bboxes differ

## Key Findings

- Recall@1 15.0% -> 51.1% (3.4x); Avg LCS 0.50 -> 0.81 (+61%); MinK search depth 2.58 -> 1.72
- Text queries gain most: Recall@1 0.08 -> 0.47
- Cross-parser gain preserved: delta-LCS +0.23 to +0.31 across GT, MinerU, Docling
- EU chunks are 4.7x larger (2,931 vs 623 chars) but self-contained, front-loading evidence into top rank

## Relevance to KGF

- SUPPORTS the retrieval-first principle: self-contained units deliver answer evidence in a single top-ranked hit, shifting work to ingest time and cutting query-time traversal
- SUPPORTS H27 partially: EUs co-locate verbatim source content (table + caption + surrounding text) as provenance rather than paraphrasing it
- Demonstrates a working Neo4j decision/rule layer with invariant checks - a concrete pattern for KGF's self-auditing completeness invariants
- Uses ontology for document structure, not entity typing, so it is orthogonal to H28

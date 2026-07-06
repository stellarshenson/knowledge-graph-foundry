# Query-time Entity Resolution

**Source**: https://arxiv.org/abs/1111.0045
**Authors**: Indrajit Bhattacharya (IBM India Research), Lise Getoor (University of Maryland)
**Venue/Date**: Journal of Artificial Intelligence Research 30, 2007

## Summary

The paper introduces query-time entity resolution: rather than maintaining a fully resolved database, references are reconciled on the fly only for the entities relevant to a query. It shows collective resolution (resolving related references jointly) can be preserved at query time through an "expand and resolve" strategy that stays fast enough for real-time answering on large publication databases (CiteSeer, arXiv).

## Method

- Formal analysis proving that in collective resolution, per-entity precision and recall follow a geometric progression as neighbors at increasing distance are added, so gains fall off exponentially with depth
- Two-stage "expand and resolve": novel expansion operators extract related records for a query, then collective resolution runs only on the extracted set
- Recursive expansion terminated at small depths because returns decay exponentially
- Adaptive strategy resolves only the most informative related references, bounding the number of records considered per query

## Key Findings

- Collective resolution significantly beats attribute-based and naive relational baselines for accuracy (from the authors' prior work, reconfirmed)
- Query-time adaptive processing preserves collective-resolution accuracy while answering in real time
- Unconstrained expansion returns too many records even at small depth, motivating the adaptive, informativeness-ranked selection
- Validated on two large real-world publication databases plus synthetic data across varied structural characteristics

## Relevance to KGF

- SUPPORTS H29 (keep duplicates, resolve at read time): this is the canonical argument for deferring resolution to query time over an unresolved store, resolving only query-relevant entities on demand rather than merging everything at ingest
- Directly informs a read-time alias-resolution design: expand from the query, resolve the local neighborhood, exploit exponential decay to bound cost
- Predates LLMs but provides the theoretical backbone (geometric precision/recall progression) for arguing that perfect ingest-time merging is unnecessary

**AUTOMATING LARGE-SCALE DATA QUALITY VERIFICATION (2018)**

Deequ (Amazon Research) treats data quality checks as "unit tests for data": a declarative API compiles quality constraints into Apache Spark aggregation queries, run either as a full batch pass or incrementally against just the newly arrived delta. On a growing 120-million-record product dataset, incremental verification of non-repartitioning metrics (size, completeness) holds runtime **constant regardless of dataset size**, while batch recomputation grows linearly, reaching roughly **30 seconds** at the full 120M-record scale versus a flat few seconds incrementally.

**Key mechanism**
- Declarative constraint API combining built-in checks (completeness, uniqueness, entropy, distribution) with user-defined validation code, compiled to Spark aggregation queries
- Incremental analyzers maintain per-metric state (e.g., a value-frequency histogram) that is updated by merging the delta's histogram via an outer join, avoiding a full-dataset rescan on every new batch
- Constraint suggestion component uses a learned model (AUC **0.859**) to estimate which columns likely warrant a uniqueness constraint, and profiles a 10% sample to auto-suggest thresholds validated against the remaining 90%
- Anomaly detection layer tracks metric time series across historical verification runs to flag quality regressions, not just single-snapshot constraint violations

**Main findings**
- Non-grouping metrics (size, completeness) scale identically whether computed on 12M or 120M records under the incremental scheme, while batch computation grows linearly from near-zero to ~30 seconds over the same range
- Repartitioning metrics (entropy, uniqueness) on low-cardinality columns (material, brand) show the incremental approach overtaking batch after **3-4 accumulated deltas**, despite a persistence/join overhead per update
- On a high-cardinality column (product id, effectively all-unique values) the incremental approach's histogram-maintenance overhead makes it perform worse than batch - incremental state size scales with cardinality, not row count saved
- Constraint suggestion on the Reddit dataset (50K record sample) achieved 100% of suggested constraints holding on the held-out 90%; the Twitter dataset correctly inferred `isUnique` for actual primary-key columns

**Key takeaways**
- Incremental verification is a genuine win only when the maintained state is small relative to the data scanned - low-cardinality metrics benefit sharply, but near-unique columns get no incremental advantage and should fall back to batch or sampling
- Certificate-style quality assertions can be attached at load time as a first-class step (their "unit tests for data" framing), not deferred to a downstream audit pass, without paying full-rescan cost on every ingest
- Automated constraint suggestion from a sample is reliable enough to bootstrap thresholds, reducing the manual specification burden that gates most production data-quality tooling

**Relevance**
- Supports treating a KGF ingest-time certificate as a streaming incremental assertion rather than a full-corpus batch audit: cheap, low-cardinality checks (completeness of required fields, entity-type distribution) can run per-chunk at near-zero marginal cost, while expensive high-cardinality checks (e.g., near-duplicate entity detection) should stay batched rather than forced into the incremental path

**Tags**
- #DataQuality
- #IncrementalComputation
- #StreamingVerification

**Source**
- Download: http://www.vldb.org/pvldb/vol11/p1781-schelter.pdf
- Local: [paper] deequ, 2018.pdf

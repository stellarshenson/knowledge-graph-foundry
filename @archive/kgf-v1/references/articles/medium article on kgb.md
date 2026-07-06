# Data Science-Informed Knowledge Graph Construction: Moving Beyond Fixed Schemas

**How statistical convergence detection, Bayesian entity resolution, and iterative benchmarking produce better knowledge graphs than the standard extract-and-load approach**

---

The standard approach to knowledge graph generation from unstructured documents follows a well-established pattern: define your entity types upfront, chunk your documents, send each chunk to an LLM with the schema, load the results into Neo4j. Alex Gilmore's article on the Neo4j Developer Blog describes this pattern well using PubMed articles with predefined types like `Medication`, `MedicalCondition`, and `TreatmentArm`. It works when you know your domain intimately before you start.

But this approach has a fundamental assumption baked in: the schema is known. In practice, schema design is itself a discovery problem. You learn what entities matter by looking at the data, not by looking at the domain from the outside. And once extraction begins, you discover that entity boundaries are ambiguous, type assignments are inconsistent across documents, and the resolution decisions that determine graph quality require more than string matching to get right.

This article describes a data science-informed approach to knowledge graph construction that treats schema discovery, entity resolution, and quality measurement as statistical problems rather than engineering problems. The approach is implemented in an open-source Python CLI tool that will be published shortly as a public repository. The benchmark results come from 20 iterations of pipeline refinement against a corpus of 10 CPAP medical device documents.

## Where the Standard Approach Falls Short

The standard pipeline - chunk, extract, load - treats knowledge graph generation as a data engineering task. Chunk sizes are picked from documentation recommendations. Entity types are hand-curated from domain knowledge. Deduplication uses exact or fuzzy string matching. Quality is evaluated by eyeballing the resulting graph.

Each of these decisions is made once, before processing begins, and applied uniformly. But knowledge graph construction is fundamentally a statistical estimation problem. Consider the questions a pipeline must answer:

- **When is the schema stable enough to commit?** The standard approach answers "before the first document" - the schema is fixed. A data science approach monitors type frequency distributions across documents and detects convergence using information-theoretic measures
- **Are these two entities the same?** The standard approach uses Levenshtein distance or exact matching. A data science approach computes a posterior probability from multiple evidence signals - name similarity, embedding cosine distance, description overlap, source co-occurrence - and treats low-confidence decisions as deferred rather than binary
- **Is the graph good?** The standard approach relies on manual inspection. A data science approach uses a hybrid scoring framework combining deterministic Cypher checks with LLM-as-judge evaluation across multiple dimensions, then iterates

The gap between the standard approach and what data science methods offer is not theoretical. Across 20 benchmark iterations, statistical methods consistently outperformed hand-tuned heuristics.

## Schema Discovery as Convergence Detection

The standard approach requires the schema upfront. Our approach treats schema discovery as a statistical convergence problem.

### The Fluid-Cured Architecture

Instead of defining entity types before processing, the system discovers types during a fluid phase and locks them at a curing event when statistical convergence is detected.

During the fluid phase, each document passes through extraction with progressively constrained prompts. The first document uses free extraction guided only by an intent prompt. From the second document onward, an ontology buffer injects discovered types into the extraction prompt. Results accumulate in memory rather than loading into Neo4j immediately.

The curing event triggers when three statistical conditions converge:

- **Coverage stability** - the fraction of extracted types matching known types stops changing (delta below a configurable threshold for N consecutive documents)
- **Type frequency distribution stability** - measured by Jensen-Shannon divergence between consecutive type frequency distributions dropping below threshold
- **No new type emergence** - zero new types discovered for a configurable window of consecutive documents

These conditions are augmented by a Chao1 species richness estimator (borrowed from ecology) that estimates how many undiscovered types likely remain given the observed type frequency distribution. When Chao1 coverage exceeds 0.5, the system has high confidence that the observed types represent the domain adequately.

An optional LLM judge can also evaluate curing readiness, but the statistical signals are the primary triggers. The LLM judge serves as a semantic sanity check ("do these types make sense for the stated intent?") rather than the decision mechanism.

### Why This Matters

Compare what happens with 10 documents about CPAP devices:

**Standard approach**: You define `Product`, `Manufacturer`, `Specification` upfront. Document 3 mentions "therapy modes" - not in your schema. Document 5 discusses "regulatory standards" - also missing. You either miss these concepts or re-run the entire pipeline after expanding the schema.

**Convergence-based approach**: Document 1 discovers 12 types including `Feature`, `Component`, `Standard`. Documents 2-4 reinforce these types with no new additions. Coverage stabilizes. The system cures at document 4, locking the schema. Documents 5-10 process with the stable schema. If document 7 introduces genuinely new concepts (high remap rate), drift detection re-enters the fluid phase automatically.

The convergence approach discovered the same types that manual curation would identify, without requiring domain expertise. Benchmark v08 used 8 hand-curated types and scored 88%. Benchmark v18 used automatic discovery with intent guidance and scored 82%. By v20, automatic discovery matched the hand-curated baseline at 88%.

## Entity Resolution as Bayesian Inference

The standard approach to entity deduplication in knowledge graph pipelines is string matching - Levenshtein distance, exact matching, or at most embedding cosine similarity. These are single-signal decisions applied uniformly.

Entity resolution is fundamentally a classification problem: given two entity mentions, what is the probability they refer to the same real-world concept? Bayesian inference provides a natural framework for combining multiple evidence signals.

### Multi-Signal Posterior

For within-type resolution (entities sharing the same type), we combine three signals into a composite score:

- **Name similarity** (Levenshtein ratio) - surface-level variant detection
- **Embedding similarity** (cosine distance on dense vector embeddings) - semantic variant detection
- **Description overlap** (Jaccard on filtered words) - contextual similarity

For cross-type resolution (entities with different types but possibly the same referent), we compute a full Bayesian posterior:

```
posterior = prior * LR_description * LR_embedding * LR_cooccurrence
```

The prior is 0.8 for identical normalized names - empirically, most same-name entities across types are indeed the same thing. Each likelihood ratio adjusts based on evidence: description word overlap, embedding cosine similarity, and source chunk co-occurrence. Co-occurrence is a negative signal - entities extracted from the same chunk are more likely to be deliberately distinct.

### Three-Zone Decision Theory

A fixed merge threshold forces a binary decision: merge or block. But many entity pairs fall in an ambiguous zone where a single document provides insufficient evidence. Decision theory suggests treating these cases differently.

We partition the posterior space into three zones:

- **Posterior >= 0.6**: merge immediately (high confidence, same entity)
- **0.4 <= posterior < 0.6**: defer judgment, accumulate more evidence
- **Posterior < 0.4**: block (high confidence, different entities)

Deferred pairs enter an evidence accumulation buffer. As more documents are processed, the buffer collects additional signals:

- **Co-occurrence count** - how often the pair's names appear across the corpus
- **Topology signal** - Jaccard similarity of relationship targets (entities that connect to the same neighbors are more likely to be identical)
- **Description convergence** - whether descriptions converge or diverge across documents

At curing time, the posterior is recomputed with accumulated evidence. If still ambiguous, an optional LLM judge makes the final call with the full evidence package.

This approach directly addresses the core weakness of single-pass resolution: genuinely ambiguous pairs (is "humidifier" a Component or an Accessory?) get more evidence before a decision is forced. The standard approach forces that decision on first encounter.

### Empirical Results

Cross-type duplicates are the primary quality bottleneck in our benchmark. The progression:

| Resolution Method | Cross-Type Duplicates | Benchmark Score |
|---|---|---|
| No cross-type resolution | 56 | 72% |
| Description Jaccard gate | 39 | 84% |
| Bayesian posterior (single-pass) | 39 | 84% |
| Bayesian posterior + deferred buffer | Pending v21 | Target 90%+ |

For comparison, Neo4j's graphrag-python uses `SinglePropertyExactMatchResolver` that explicitly does not merge across types. Graphiti (Zep) uses entropy-gated fuzzy matching within same-type pairs. Microsoft GraphRAG uses community detection to cluster entities post-extraction. All accept cross-type duplication as a design tradeoff. The Bayesian approach treats it as a solvable inference problem.

## Intent-Driven Extraction: The Biggest Signal

Across 20 iterations, the single largest quality improvement came not from better algorithms but from a single prompt parameter: the intent.

Benchmark v17 scored 72% with carefully tuned resolution thresholds, clustering prompt hardening, and merge validation. Benchmark v18 added one configuration field:

```yaml
ontology_buffer:
  intent: >-
    Compare CPAP and auto-titrating positive airway pressure therapy devices
    across manufacturers, focusing on product specifications, clinical features,
    therapy modes, regulatory compliance, and component architecture
```

Score jumped to 82%. A 10-point improvement from 30 words.

The intent transforms extraction in three measurable ways:

1. **Type precision** - without intent, document 1 discovers types like `PageNumber`, `Disclaimer`, `TableOfContents`. With intent, document 1 discovers `Product`, `Organization`, `Feature`, `Component`, `Specification` - all domain-relevant
2. **Type stability** - without intent, new types emerge through document 6-7 as the LLM encounters unfamiliar content. With intent, all 12 final types are discovered by document 1, with zero new types from document 2 onward
3. **Relationship specificity** - without intent, relationships are generic (`RELATED_TO`, `HAS`). With intent, relationships are domain-specific (`HAS_SPECIFICATION`, `SUPPORTS_MODE`, `MANUFACTURED_BY`)

The data science framing explains why this works: the intent constrains the hypothesis space. Without it, the LLM samples from a broad prior over all possible entity types. With it, the prior is concentrated on domain-relevant types, producing more consistent extraction across chunks and documents.

## Benchmarking as Experimental Science

The standard approach to knowledge graph quality evaluation is subjective: look at the graph, decide if it seems right. Our approach treats benchmarking as experimental science with reproducible measurements across iterations.

### Hybrid Scoring Framework

We combine 63 deterministic Cypher-based checks with 5 generative LLM-as-judge evaluations into a weighted hybrid score.

**Deterministic checks** are binary pass/fail:
- Schema checks: expected types exist, expected relationship types exist, no orphan nodes
- Cross-document checks: manufacturers linked to multiple products, entities from different documents share connections
- Data quality: no singleton types, entity count within expected range, relationship density reasonable

**Generative scoring** evaluates dimensions that resist deterministic checking. An LLM judge receives Cypher-queried context from the graph and scores on a 1-5 scale:
- Manufacturer coverage, product completeness, cross-document resolution, specification detail, query answerability

The hybrid score weights deterministic at 60% and generative at 40%.

### What 20 Iterations Teach

| Version | Hybrid Score | Key Change | Category |
|---------|-------------|------------|----------|
| v01-v05 | 48-70% | Basic pipeline | Engineering |
| v08 | 88% | Hand-curated types | Cheating |
| v09-v13 | 73-81% | Surface normalization, clustering | Engineering |
| v17 | 72% | Clustering prompt hardening | Engineering |
| v18 | 82% | Intent prompt | Data science |
| v19 | 84% | Bayesian cross-type dedup | Data science |
| v20 | 88% | Expanded judge context | Measurement |

Three patterns emerge:

1. **Engineering improvements plateau at ~76%** - better chunking, normalization, and clustering produce diminishing returns
2. **Data science methods break through** - intent prompts (+10 points) and Bayesian resolution (+2 points) moved the needle where engineering refinements could not
3. **Measurement quality matters** - two iterations (v20, and several earlier) involved no pipeline changes, only benchmark improvements. The v20 jump from 84% to 88% came from fixing how the LLM judge queried the graph for context

The last point deserves emphasis. Two of 20 iterations improved the benchmark, not the pipeline. The implication: if your evaluation methodology is wrong, pipeline improvements are invisible. Invest in measurement as much as in the pipeline.

## The Standard Pipeline vs. Data Science-Informed Pipeline

| Aspect | Standard Approach | Data Science Approach |
|--------|-------------------|----------------------|
| **Schema** | Fixed upfront | Discovered via convergence detection (JSD, Chao1, coverage delta) |
| **Entity resolution** | String matching (Levenshtein) | Bayesian posterior over multiple evidence signals |
| **Ambiguous cases** | Binary merge/block | Three-zone decision theory with evidence accumulation |
| **Type assignment** | Static enum | Dynamic Pydantic model generation from evolving ontology |
| **Quality evaluation** | Manual inspection | Hybrid deterministic + generative scoring framework |
| **Iteration** | Ad-hoc | Versioned benchmark with regression detection |
| **Intent** | Not captured | First-class configuration driving extraction and clustering |
| **Convergence** | Not measured | JSD, Chao1 richness estimator, Shannon entropy delta |
| **Cross-type duplicates** | Accepted | Bayesian posterior + deferred buffer + LLM escalation |

The data science approach is not necessarily more complex to implement. The convergence detection is 200 lines of Python using scipy. The Bayesian posterior is a straightforward product of likelihood ratios. The benchmark framework is Cypher queries plus an LLM call. The difference is in framing: treating extraction quality as a measurable quantity that can be optimized through iteration, rather than a one-shot engineering problem.

## Implementation Details

The approach is implemented in a Python CLI tool built on:

- **LiteLLM** for LLM provider abstraction (Bedrock, OpenAI, Anthropic)
- **Instructor** + **Pydantic** for structured output enforcement with retry
- **pymupdf4llm** for PDF parsing
- **Neo4j** for graph storage with dual indexing (vector + fulltext)
- **Amazon Titan** embeddings for semantic entity resolution
- **FAISS** for exemplar-based type resolution
- **scipy** for statistical convergence measures (JSD, entropy)
- **Levenshtein** for surface-level string similarity

Each pipeline stage (parse, chunk, extract, deduplicate, resolve, load) is an importable, testable function. The project has 272 unit tests at 86% coverage. The architecture deliberately avoids meta-frameworks (LangChain, LlamaIndex) in favor of composable functions that can be tested and benchmarked independently.

The benchmark corpus (10 CPAP documents, 158 chunks) produces approximately 1,000 entities and 3,500 relationships with 0 orphan nodes.

A public repository will be published shortly, along with the benchmark dataset and scoring framework.

## Takeaways

**Treat schema discovery as convergence detection, not upfront design.** Statistical measures (JSD, Chao1, coverage delta) tell you when the schema has stabilized without requiring domain expertise. The fluid-cured architecture automates what domain experts do manually: look at data, form type hypotheses, refine until stable.

**Frame entity resolution as Bayesian inference.** Multiple evidence signals (name, embedding, description, co-occurrence, topology) combined through likelihood ratios produce better merge decisions than any single threshold. Deferred judgment for ambiguous cases outperforms forced binary decisions.

**Intent is the strongest signal.** A one-sentence use case description outperformed months of algorithmic tuning. The intent constrains the LLM's hypothesis space, producing consistent extraction without constraining the schema.

**Invest in measurement.** Two of 20 iterations improved the benchmark, not the pipeline. If your evaluation methodology is broken, pipeline improvements are invisible. Build a reproducible scoring framework early and iterate on both the pipeline and the measurement.

**Cross-type resolution remains open.** After 20 iterations and a Bayesian posterior model, cross-type duplicates are still the primary quality bottleneck. The industry (Neo4j, Zep, Microsoft) accepts this tradeoff. The deferred evidence accumulation buffer is a step toward solving it, but genuine ontological ambiguity may not have a clean algorithmic answer.

---

*The tool is built with Claude Sonnet 4 on Amazon Bedrock and Neo4j. Public repository coming soon.*

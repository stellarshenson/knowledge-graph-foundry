# SMART Research Goal: Graph-Resident FSM for Knowledge Graph Lifecycle Management

## Topic

State persistence patterns for long-lived knowledge graphs that evolve across multiple ingestion runs, with governance embedded in the graph itself rather than external configuration artifacts.

## Novel Angle

LLM-based knowledge graph construction has seen rapid growth in 2024-2026, with systems like Microsoft GraphRAG, LightRAG, Graphusion, and AGENTiGraph demonstrating increasingly sophisticated extraction pipelines. However, nearly all of these systems treat KG construction as a one-shot batch process - extract, resolve, load, done. None address what happens when you run the pipeline again against the same graph with new documents, when ontology drift invalidates previous type assignments, or when a process crashes mid-consolidation.

**What is NOT well-studied**: the intersection of graph-resident control planes and ontology lifecycle governance for LLM-constructed knowledge graphs. Three specific gaps:

1. **Graph-authoritative schema management** - Production KG systems (Wikidata, YAGO, DBpedia) manage schema through external ontology files, version control, or dedicated ontology management tools. For LLM-extracted KGs where the ontology emerges from data, no established pattern exists for persisting the evolved schema state (type frequencies, resolution rules, calibration parameters) inside the graph itself, making the graph self-describing and independent of filesystem artifacts

2. **Cross-run statistical continuity** - Bayesian entity resolution systems accumulate calibrated posteriors during a single run, but these are typically ephemeral. No published work addresses persisting per-type calibration state (prior strength, observation counts, likelihood ratio history) across runs so that resolution quality improves monotonically with corpus growth rather than resetting each time

3. **Crash recovery for multi-phase graph construction** - Traditional ETL crash recovery (checkpointing, write-ahead logs) does not map cleanly to LLM extraction pipelines where consolidation involves type clustering, Bayesian resolution, and batch graph writes as interleaved non-idempotent operations. The partial-consolidation recovery problem (some entities flushed, others not, type clustering complete but resolution incomplete) is specific to this domain and unaddressed

**Why now**: The 2024-2025 wave of LLM KG builders (GraphRAG, nano-graphrag, LightRAG, fast-graphrag) has established that LLM extraction works. The next frontier is operationalizing these systems for continuous ingestion, and the absence of lifecycle governance is the primary barrier. Neo4j's own Graph Builder (2024) added basic incremental ingestion but no schema evolution or state persistence. The timing is right because the extraction problem is increasingly solved while the governance problem remains wide open.

**How this differs from standard approaches**: Traditional ontology evolution research (Stojanovic 2002, Flouris et al. 2008) addresses formal ontology versioning for hand-crafted schemas. This work addresses emergent ontology stabilization for LLM-discovered schemas - the ontology is not authored but learned, and its evolution is governed by statistical signals rather than human editorial decisions. Traditional graph database state management (Neo4j operational guides, JanusGraph management) addresses infrastructure-level concerns. This work addresses application-level lifecycle state embedded as first-class graph citizens.

## Scope

Design, implement, and evaluate a graph-resident control plane for multi-run knowledge graph lifecycle management. The system must demonstrate: (a) ontology state reconstruction from graph structures alone (no filesystem dependencies), (b) measurable resolution quality improvement from cross-run calibration persistence, and (c) correct crash recovery from all three interruption scenarios (pre-consolidation, mid-consolidation, post-consolidation). Evaluation uses a 10-document CPAP medical device corpus processed across 3+ sequential ingestion runs with controlled crash injection.

## SMART Goal

**Specific**: Implement and evaluate three graph-resident persistence mechanisms for the KGF pipeline lifecycle FSM: (1) consumed prior registry with ontology deduplication on re-launch, (2) per-type calibration state persistence via `(:KGFTypeCalibration)` nodes enabling cross-run Bayesian continuity, and (3) crash recovery protocol handling three interruption scenarios with correct state restoration.

**Measurable**: Success is quantified by four metrics:
- Ontology reconstruction accuracy: `OntologyBuffer.from_graph()` output matches `ontology.yml` on 100% of fields after round-trip (persist -> wipe file -> reconstruct)
- Resolution quality delta: entity resolution F1 on run N+1 with persisted calibration vs. fresh calibration (target: +3% F1 improvement)
- Crash recovery correctness: 3/3 interruption scenarios (pre-consolidation, mid-consolidation, post-consolidation) recover to valid FSM state with no orphaned entities
- Rebuild cost estimation accuracy: predicted affected entity counts within 10% of actual counts during RECURING deliberation

**Achievable**: All three mechanisms build on existing KGF infrastructure - the FSM, metanode CRUD, Bayesian resolver, and ontology buffer are implemented. The work extends existing Cypher patterns and Python dataclasses. No new external dependencies required. Evaluation uses the existing 10-document CPAP benchmark corpus and multidoc benchmark specification.

**Relevant**: Addresses the primary gap preventing KGF from operating as a production-grade continuous ingestion system. Without graph-resident state persistence, every run starts from scratch, calibration is lost, and interrupted runs leave the graph in undefined states. This work transforms KGF from a batch pipeline into a self-governing graph construction system.

**Time-bound**: 4 weeks total.
- Week 1: Graph-reconstructable schema (`OntologyBuffer.from_graph()`, consumed prior registry, `(:KGFOntologyType)` and `(:KGFConsumedPrior)` node persistence)
- Week 2: Per-type calibration persistence (`(:KGFTypeCalibration)` nodes, cross-run posterior continuity, resolution quality measurement)
- Week 3: Crash recovery protocol (three-scenario detection, recovery actions, controlled crash injection tests)
- Week 4: Rebuild cost estimation, integration testing across 3+ sequential runs, evaluation and writeup

## Constraints

- **Compute**: Single machine, no GPU required. Neo4j Community Edition (no clustering). LLM calls via existing API (Claude/GPT-4o for extraction, structured calls only)
- **Data**: 10-document CPAP medical device corpus (proprietary but self-contained). No external datasets required
- **Tools**: Python 3.12, Neo4j 5.x, `transitions` library for FSM, existing KGF benchmark harness
- **Scope limitation**: Single-process lifecycle only. Multi-process coordination (lease-style locking, concurrent ingestion) is designed in the control plane but not evaluated in this work
- **No new LLM fine-tuning**: All LLM usage is via structured API calls with existing prompt templates

## Benchmark

**Name**: KGF MultiDoc Benchmark (internal, v27 baseline)

**Source**: 10-document CPAP medical device corpus, `multidoc_benchmark_spec.md` procedure

**Metrics**:
- Hybrid score (weighted deterministic + generative): current baseline 86% (v27)
- Deterministic checks: 63 assertions covering entity counts, relationship types, cross-document resolution, orphan detection
- Generative checks: 5 dimensions scored 1-5 by LLM judge (manufacturer accuracy, product coverage, cross-doc resolution, specification completeness, query answerability)
- Cross-run calibration delta: new metric comparing resolution F1 between fresh-start and persisted-calibration runs
- Crash recovery success rate: new metric (3 scenarios, binary pass/fail each)

**Current SOTA**: v27 baseline at 86% hybrid (60/63 deterministic, 3.8/5.0 generative). The benchmark is internal to this project; no external SOTA exists for this specific evaluation. The closest external comparison point is Neo4j Graph Builder's incremental ingestion, which has no published benchmark for multi-run ontology evolution.

**Evaluation protocol**: Three sequential ingestion runs against the same Neo4j instance. Run 1: full 10-doc corpus from empty graph. Run 2: 5 new documents added to existing graph (measures ontology deduplication and calibration continuity). Run 3: 3 documents after controlled crash injection in Run 2 (measures recovery correctness). Each run produces a full benchmark score. The cross-run comparison measures whether calibration persistence improves resolution quality and whether the graph reaches equivalent quality regardless of whether it was built in one run or three.

## Success Criteria

Results would be publishable if:
1. Graph-reconstructable schema achieves perfect round-trip fidelity (filesystem artifact becomes truly disposable)
2. Cross-run calibration persistence produces measurable resolution improvement (even +1-2% F1 demonstrates the principle)
3. Crash recovery handles all three interruption scenarios without manual intervention
4. The pattern generalizes - the control plane design is transferable to other LLM KG construction systems, not KGF-specific
5. The evaluation demonstrates that multi-run incremental construction achieves equivalent graph quality to single-run batch construction (proving that lifecycle governance does not degrade extraction quality)

## Generated

2026-03-17T00:00:00Z

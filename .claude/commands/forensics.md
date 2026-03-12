# Benchmark Forensics

Run an agentic forensic investigation on the most recent benchmark run. Analyse the JSONL event log, the benchmark markdown report, and the Neo4j graph state to diagnose every failure, trace root causes, and produce an actionable forensic report.

## Inputs

Locate automatically:
- **Event log**: most recent `tmp/v*-events.log` file (by mtime)
- **Benchmark report**: most recent `docs/benchmarks/MULTIDOC_BENCHMARK_v*.md` file (by mtime)
- **Neo4j**: bolt://neo4j:7687 (credentials in .env)

If multiple event logs exist, use the one matching the benchmark version.

## Investigation Protocol

You are a pipeline forensics agent. Your goal is to explain every benchmark failure with evidence, classify each by failure type, and recommend specific fixes.

### Phase 1 - Scope

Read the benchmark report. Extract:
- All failed deterministic checks (name, dimension, actual vs expected)
- All generative scores below 5/5 (dimension, score, judge reasoning)
- Graph stats (entities, relationships, chunks, types)

These are your investigation targets.

### Phase 2 - Event Log Analysis

For each failure, query the JSONL event log using `jq` via bash. The event log contains one JSON object per line with `signal` and `payload` fields.

**Available signals** (not exhaustive - explore the log):
- `cross-type-decision` - individual merge/block/defer decisions with posteriors and likelihood ratios
- `entity-resolution-completed` - per-document resolution summary with cross_type_decisions array
- `merge-blocked` - blocked pairs with entity names, types, posteriors
- `cross-type-pair-deferred` - deferred pairs
- `deferred-resolution-completed` - deferred buffer resolution results
- `curing-triggered` - curing trigger type and metrics
- `curing-condition-blocked` - why curing didn't trigger for a document
- `phase-transition` - fluid to cured transition
- `llm-call-started`, `llm-call-completed`, `llm-call-failed` - LLM call tracking
- `document-extraction-started`, `document-extraction-completed` - per-doc extraction stats
- `hierarchy-evolved`, `guide-rule-generated` - ontology evolution events
- `buffer-snapshot-taken` - ontology state at extraction time
- `graph-load-completed`, `graph-validated` - loading stats
- `ingestion-started`, `ingestion-completed` - pipeline bookends

**Reference jq patterns** (adapt as needed):

```bash
EVENT_LOG=tmp/vNN-events.log

# Cross-type action breakdown
jq -r 'select(.signal == "entity-resolution-completed") | .payload.cross_type_decisions[]? | .action' "$EVENT_LOG" | sort | uniq -c | sort -rn

# Blocked pairs with posteriors
jq -r 'select(.signal == "merge-blocked") | "\(.payload.posterior | tostring | .[0:5]) \(.payload.entity_a) [\(.payload.type_a)] vs [\(.payload.type_b)]"' "$EVENT_LOG" | sort -rn

# Curing timeline
jq -r 'select(.signal | test("curing-triggered|phase-transition|curing-condition-blocked")) | "\(.signal): \(.payload | tostring | .[0:150])"' "$EVENT_LOG"

# LLM stats
jq -r 'select(.signal == "llm-call-completed") | .payload.duration_ms' "$EVENT_LOG" | awk '{s+=$1; n++} END {printf "calls=%d avg=%dms\n", n, s/n}'

# Search for entity by name
jq -r 'select(.payload | tostring | test("SEARCH_TERM"; "i")) | "\(.signal): \(.payload | tostring | .[0:150])"' "$EVENT_LOG"
```

These are starting points. Follow leads - if a blocked pair has a surprising posterior, dig into the likelihood ratios. If an entity is missing, search for it across all signals. If curing triggered early or late, examine the blocked conditions.

### Phase 3 - Graph State (when event log is insufficient)

For failures where the event log provides no evidence (extraction gaps, graph-load merge misses), query Neo4j directly using the MCP neo4j tools (read-cypher).

Examples:
- Count OSA name variants: `MATCH (e) WHERE toLower(e.name) CONTAINS 'osa' OR toLower(e.name) CONTAINS 'obstructive' RETURN e.name, e.type, count(*) ORDER BY count(*) DESC`
- Check iBreeze manufacturer link: `MATCH (p) WHERE toLower(p.name) CONTAINS 'ibreeze' OPTIONAL MATCH (o)-[:MANUFACTURES]->(p) RETURN p.name, p.type, o.name`
- SleepStyle mode entities: `MATCH (p)-[r]->(e) WHERE toLower(p.name) CONTAINS 'sleepstyle' AND toLower(e.name) CONTAINS 'mode' RETURN p.name, type(r), e.name, e.type`

### Phase 4 - Classification and Report

For each failure, classify as one of:

| Class | Evidence Pattern | Fix Domain |
|-------|-----------------|------------|
| **Extraction gap** | Entity/relationship absent from all event signals AND absent from Neo4j. LLM never produced it | Extraction prompt, chunk content, model capability |
| **Resolution miss** | Entity extracted (visible in events) but cross-type decision was `blocked` or `deferred`. Posterior below threshold | Threshold tuning, hierarchy enforcement, deferred dedup LLM escalation |
| **Graph-load merge miss** | Entity extracted and resolved, but name variants survive as separate Neo4j nodes after MERGE | Name normalization in loader, Levenshtein pre-merge |
| **Benchmark measurement** | Data exists in graph (deterministic passes or Cypher confirms) but generative judge scored low | Judge context queries, prompt enrichment |

## Output

Produce a forensic report with these sections:

1. **Summary** - benchmark version, hybrid score, failure count, one-line verdict
2. **Failure Analysis** - per failure: check name, evidence gathered, root cause, classification, recommended fix
3. **Pipeline Health** - curing trigger and timing, LLM stats (calls, avg duration, failures), resolution breakdown (hierarchy_merge, merged, blocked, multi_facet, deferred)
4. **Cross-Type Deep Dive** - all blocked pairs with posteriors, grouped by type pair pattern. Identify which pairs are threshold-fixable vs genuinely ambiguous
5. **Actionable Recommendations** - ordered by expected impact on hybrid score

Append the forensic report to the benchmark markdown file as a `## Forensic Analysis` section.

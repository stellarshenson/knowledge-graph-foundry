# Implementation Instructions

These instructions govern the implementation phase of kg-builder-cli. They override the default approval-seeking behaviour. Re-read this file after every context compaction.

## Execution Mode

Execute autonomously without asking for permission. Make decisions independently using Occam's razor - minimum viable implementation to achieve each result. Do not overengineer, do not add features not described in `docs/KGB_KGB_DESIGN.md`, do not ask "should I proceed?" - just proceed.

## Build Loop

1. Add dependencies to `pyproject.toml` (both dev and runtime)
2. Run `make install` to build
3. Test in the local uv-managed `.venv/`
4. If something breaks, fix it and run `make install` again
5. Keep iterating until the pipeline works end-to-end

Never use direct `pip install` or `uv install` - always `make install`.

## Source of Truth

`docs/KGB_KGB_DESIGN.md` is the canonical design document. All implementation decisions flow from it. The design has been through 6 devil's advocate iterations (residual risk 15.5/136) and covers:

- CLI commands (typer): `kg ingest`, `kg query`, `kg update`, `kg init`
- Agent layer (Strands SDK): one agent per command
- Ontology system: free or constrained, three-tier normalization
- Extraction pipeline: parse -> chunk -> extract -> dedup -> resolve -> load
- Graph structure: 12 node types, all core (no optional features)
- Schema versioning: SchemaVersion nodes, CREATED_UNDER linking
- Module structure: `types/` shared Pydantic contracts, dependency rules per module

## AWS and LLM Configuration

- **AWS profile**: `kolomolo`
- **Region**: `eu-central-1`
- **Model**: `eu.anthropic.claude-sonnet-4-20250514-v1:0` (Claude Sonnet 4, cross-region inference)
- Set `AWS_PROFILE=kolomolo` and `AWS_DEFAULT_REGION=eu-central-1` in `.env`
- The Strands SDK reads AWS credentials from the environment/profile chain

## Neo4j

- **Container**: `kg-builder-neo4j` (Docker)
- **URI**: `bolt://localhost:7687`
- **Credentials**: `neo4j` / `kg-builder-pass`
- **Browser**: `http://localhost:7474`
- Already configured in `.env` and `.mcp.json`
- If container is stopped: `docker start kg-builder-neo4j`
- **Clean between iterations**: Before each new ingestion test run, wipe the graph with `MATCH (n) DETACH DELETE n` via Cypher. Start fresh every time to avoid stale data confusing results

## Test Data

Use PDFs from `data/external/cpap-datasheets-and-manuals.zip` for testing ingestion. Extract one PDF to `data/raw/` for a quick smoke test. The full 23-document set is the benchmark corpus.

Do not modify or delete the zip file. Keep `data/raw/` contents reproducible.

## Testing Strategy

- Write tests, but keep them grouped and reasonable
- Group by module: `tests/test_config.py`, `tests/test_extraction.py`, `tests/test_loading.py`, etc.
- Not thousands of tests - cover the critical paths, edge cases where they matter
- Run with `make test`
- Use fixtures for Neo4j connection, mock LLM calls where appropriate

## Stop Condition

Stop when the multidoc benchmark hybrid score reaches 90+. Until then, keep iterating.

Pipeline prerequisites (must all be working):
1. Parses a PDF from the CPAP dataset
2. Chunks the parsed content
3. Extracts entities and relationships via Claude Sonnet 4
4. Loads the graph into Neo4j
5. The graph is queryable via Cypher

## Task Management

Maintain a global task list in `TASKS.md` at the project root. This is the master plan for the implementation phase - all major work items derived from `docs/KGB_KGB_DESIGN.md`.

**Structure**:
- Major tasks grouped by module/layer (e.g. "Types Module", "Config", "Ingestion Pipeline", "Loading", "CLI")
- Each task has a status: `[ ]` todo, `[x]` done, `[~]` in progress
- Keep it coarse - one line per task, not subtasks within subtasks
- Update after completing each major piece of work

**Execution via subagents**:
- Use the Agent tool to parallelise independent work streams
- Launch multiple subagents for tasks that don't depend on each other (e.g. writing types/ models while writing config/ loader)
- Use foreground agents when results are needed before proceeding
- Use background agents for independent work that can run in parallel
- Each agent gets a clear, self-contained prompt with all context it needs
- Trust agent outputs - review briefly, integrate, move on

**Example workflow**:
1. Read TASKS.md to see what's next
2. Identify 2-3 independent tasks
3. Launch subagents in parallel to implement them
4. Integrate results, run `make install`, fix issues
5. Update TASKS.md
6. Repeat

## Git and Checkpoints

Commit regularly without asking - after completing each major task or group of related tasks. Use conventional commit messages per `.claude/GIT.md`. No co-authoring attribution.

**Always create a checkpoint tag before starting implementation of a new plan.** This ensures a known-good state to revert to if the implementation goes wrong. Use the `/checkpoint` skill with a descriptive name like `BEFORE_V19_IMPLEMENTATION`.

Create checkpoint tags at significant milestones using the version-based format:
- `CHECKPOINT_<NAME>_<version>` (e.g. `CHECKPOINT_TYPES_MODULE_0.1.0`)
- Milestones: foundation complete, extraction working, loading working, end-to-end working, before major implementation

Push after each commit. Keep the remote up to date.

## Improvement Iteration Loop

After each major implementation run, enter a structured improvement cycle. Keep iterating until hybrid score reaches 90+.

**Each iteration**:
1. **Execute** - Implement improvements targeting the weakest benchmark dimensions. Use subagents for parallel work
2. **Build & Test** - Run `make test` && `make lint`. All tests must pass
3. **Wipe & Ingest** - Wipe Neo4j graph (`MATCH (n) DETACH DELETE n`), run fluid ingestion against 10-doc benchmark corpus
4. **Benchmark** - Run `python tests/benchmark_multidoc.py vNN "description"` with deterministic + generative scoring. Save results to `docs/benchmarks/`
5. **Analyze** - Which dimensions improved vs regressed? New failure modes? Did the fixes hit their targets?
6. **Commit & Push** - Commit all changes with descriptive message, push to remote
7. **Update KGB_DESIGN.md** - Document lessons learned, what worked, what didn't
8. **Update JOURNAL.md** - Log iteration number, changes, benchmark delta
9. **Plan next** - Based on analysis, identify next highest-impact change. Repeat from step 1

**Autonomous execution**: Do not ask for permission at any step. Execute the full loop. Commit and push after each iteration. The loop terminates when hybrid score >= 90 or after exhausting feasible improvements.

**Benchmark scorecard** (query-based, not prompt-based):
- Evaluates graph output via Cypher queries against ground truth from source documents
- Multi-dimensional: entity coverage, relationship accuracy, specification completeness, dedup quality, numeric property extraction, query answerability
- Scorecard is completely independent of extraction prompts - no overfitting
- Ground truth is derived from the source PDFs, not from the system prompts

**Neo4j cleanup**: Always wipe the graph with `MATCH (n) DETACH DELETE n` before each benchmark/test ingestion run

**Ontology buffer**: Can be serialized to disk and versioned between iterations

**Entity resolution**: Levenshtein similarity is a pre-filter for candidate identification. LLM makes the final merge/canonicalize decision generatively. Do not use deterministic merge for production - use LLM-assisted canonicalization

## Benchmark Documentation

Each benchmark run produces a versioned document in `docs/benchmarks/`:
- Filename: `BENCHMARK_v<iteration>_<score>.md` (e.g. `BENCHMARK_v01_48.md` for 48% score)
- Contains: conditions (model, config, ontology), test data, dimension scores, per-check results, reasoning about failures, improvement plan
- Previous benchmarks are never deleted - they form the improvement history
- `docs/benchmarks/` directory tracks the complete evolution from v01 onward
- Benchmark results must always be saved as markdown files, not JSON

## Design Feedback Loop

After each benchmark run, update `docs/KGB_KGB_DESIGN.md` with lessons learned:
- What extraction patterns work well vs poorly for the document types
- Which entity types and relationship patterns the LLM captures reliably
- Where the ontology needs tightening (types that get confused, relationships that get missed)
- Specification extraction patterns that need prompt or schema changes
- This creates a feedback cycle: benchmark results -> design updates -> implementation changes -> better benchmark scores

## Reminders

- After every context compaction, re-read this file, `TASKS.md`, and `docs/KGB_KGB_DESIGN.md`
- Do not ask for permission - execute
- Use `make install` for every build cycle
- Occam's razor: simplest working solution first
- Clean Neo4j before every ingestion test run
- Record iteration count in journal entries

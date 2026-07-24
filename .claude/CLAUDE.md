<!-- @import /home/lab/workspace/.claude/CLAUDE.md -->

# Project-Specific Configuration

This file imports workspace-level configuration from `/home/lab/workspace/.claude/CLAUDE.md`.
All workspace rules apply. Project-specific rules below strengthen or extend them.

The workspace `/home/lab/workspace/.claude/` directory contains additional instruction files
(MERMAID.md, NOTEBOOK.md, DATASCIENCE.md, GIT.md, and others) referenced by CLAUDE.md.
Consult workspace CLAUDE.md and the .claude directory to discover all applicable standards.

## Mandatory Bans (Reinforced)

The following workspace rules are STRICTLY ENFORCED for this project:

- **No automatic git tags** - only create tags when user explicitly requests
- **No automatic version changes** - only modify version in package.json/pyproject.toml/etc. when user explicitly requests
- **No automatic publishing** - never run `make publish`, `npm publish`, `twine upload`, or similar without explicit user request
- **No manual package installs if Makefile exists** - use `make install` or equivalent Makefile targets, not direct `pip install`/`uv install`/`npm install`
- **No automatic git commits or pushes** - only when user explicitly requests

## Project Context

Knowledge Graph Builder CLI (`kg-builder-cli`) - a Python CLI tool for building knowledge graphs in Neo4J, inspired by Neo4J Graph Builder. Supports free or constrained ontology with straightforward execution.

**Technology Stack**:
- Python 3.12 with uv package manager
- Neo4J graph database
- Strands Agents SDK for agent orchestration
- typer for CLI entry points
- loguru for logging
- python-dotenv for environment configuration
- ruff for linting/formatting
- pytest for testing

**Environment**:
- Virtual environment managed by uv at `.venv/`
- Jupyter kernel registered as `kg-cli`
- Use `make install` for setup, `make test` for testing

**Module**: `kg_builder_cli` (underscore), package name `kg-builder-cli` (hyphen)

## Dataset Doctrine

**MANDATORY**: Consult the `kgf-dataset` skill (`.claude/skills/kgf-dataset/SKILL.md`) before ANY ingest, A/B, or benchmark run. It defines the benchmark-only rule (CPAP testing abandoned 2026-07-12), the scale ladder (scout/small/medium/large rungs with purposes), corpus asset paths, Neo4j instance roles, and rung-boundary dump discipline. Route every hypothesis to the cheapest rung that can kill it.

## Implementation Phase

**MANDATORY**: Read `/home/lab/workspace/learning/projects/kg-builder-cli/INSTRUCTIONS.md` at the start of every session and after every context compaction. It governs the autonomous execution mode for the implementation phase.

## Planning Workflow

- Every implementation plan must include acceptance criteria before work begins
- Post-implementation must validate against all acceptance criteria and record PASS/FAIL

## Strengthened Rules

- Always use Makefile targets (`make install`, `make test`, `make lint`, `make format`) - never direct uv/pip commands
- Follow copier-data-science template conventions for directory structure
- Keep `data/raw/` immutable - use `data/interim/` for transforms, `data/processed/` for final datasets

## Orchestrator-First Session Policy (Reinforced)

**MANDATORY**: per the global Orchestrator-First Session Policy (`~/.claude/CLAUDE.md`), the main session in this project is the ORCHESTRATOR: it clarifies with the user, registers hypotheses, primes specs, and adjudicates/records verdicts in the canonical docs. Execution (experiment runs, sweeps, research legwork, mechanical file work) is handed off to subagents (via `/claude-handoff` where available, else the Agent tool) after clarifications with the user settle scope and bars. Canonical-doc writes (experiments log, SOTA, defects, journal) stay coordinator-owned.

## Detached Compute Rule (Executor Survival)

**MANDATORY for every executor agent running long computations** (LLM sweeps, ingests, gate batches, experiment chains):

- Launch the computation DETACHED from the agent's own process tree: `nohup`/`setsid`, output teed to a `logs/*.log` file
- Checkpoint results incrementally to `reports/experiments/` (persistent) or `tmp/results/` (throwaway) as they land - never hold results only in agent memory
- The agent watches the LOG FILE, never its own child process
- On resume, check caches before recomputing anything

**Why**: session limits or agent death must never kill the compute. The R23/R24 gates executor died mid-run (2026-07-08) and its in-flight computation died with it; the H241 chain, launched detached, survived multiple agent deaths in the same window. Compute must outlive the driver so a resumed agent or the coordinator can collect results from disk.

**Enforcement**: prime every executor spec with this rule verbatim.

## Repository Layout Doctrine (2026-07-13, migration executed same day)

Copier-data-science template is the skeleton (`.copier-answers.yml` present). Persistence directive: **referenced-anywhere (experiments log, board, MANIFEST, reports, memory) = persistent; hypothesis-naming decides `scripts/` vs `scripts/experiments/` within persistent**. Persistent tiers are TRACKED (hypothesis-skill reproducibility rule: a hypothesis must re-run from its own text); throwaway goes to `tmp/`:

- **`scripts/`** (tracked) - infra harnesses (bench_*, token_ledger.py, vllm-serve.sh, ops one-shots the board cites)
- **`scripts/experiments/`** (tracked) - hypothesis/round-named execution artifacts (`r*`, `h*`, `phase3*`); the experiments log links these paths
- **`reports/experiments/`** (tracked) - all experiment evidence, internally structured: `adjudicated/` (adjudicated verdict reports - JSON + briefs, the experiments log cites these), `invalid/` (quarantined results kept for the record), `<round>/` per-round persistent result groups (bench/, r45/, ...) + planned output paths of registered rounds; `reports/` root holds ONLY `experiments/` and `figures/`
- **`tmp/`** (gitignored, template semantics: never anything you need to keep) - `tmp/scripts/`, `tmp/results/` hold unreferenced throwaways; pure scratch elsewhere
- **`logs/`** (gitignored) - runtime + background-job logs, per template
- **Dumps** - keeper Neo4j dumps + MANIFEST + sidecars in `data/interim/dumps/` (gitignored; sync to S3 via profile `stellars-tech`); a dump that is only a private experiment cache may stay in `tmp/`
- **Notebooks** - project-local naming `<topic>_<hypothesisID>.ipynb` (NOT the template's `NN-initials-` scheme; retro-renaming would break append-only experiments-log links); tracked `.py` files in `notebooks/` are PINNED instruments (e.g. `h158_measure.py`) - never move them
- **config/** - tracked project extension (pinned per-rung experiment configs)
- **Canonical docs** - experiments log `docs/experiments/kgf-redesign-experiments.md`, SOTA `docs/kgf-sota.md`, defects `docs/defects/`, recall failure modes `docs/recall-failure-modes.md`, acc-crit `docs/acceptance-criteria/`
- **History** - pre-migration `results/` and `scripts/` paths in journal entries and git history are historical record, never rewritten; living docs were link-rewritten at migration (2026-07-13)

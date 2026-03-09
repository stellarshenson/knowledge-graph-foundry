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
- typer for CLI interface
- loguru for logging
- python-dotenv for environment configuration
- ruff for linting/formatting
- pytest for testing

**Environment**:
- Virtual environment managed by uv at `.venv/`
- Jupyter kernel registered as `kg-cli`
- Use `make install` for setup, `make test` for testing

**Module**: `kg_builder_cli` (underscore), package name `kg-builder-cli` (hyphen)

## Strengthened Rules

- Always use Makefile targets (`make install`, `make test`, `make lint`, `make format`) - never direct uv/pip commands
- Follow copier-data-science template conventions for directory structure
- Keep `data/raw/` immutable - use `data/interim/` for transforms, `data/processed/` for final datasets

# Claude Code Journal

This journal tracks substantive work on documents, diagrams, and documentation content.

---

1. **Task - CLI specification document** (v0.1.0): Created `docs/SPEC.md` defining the full CLI command structure, configuration, and data formats for kg-builder-cli<br>
    **Result**: Spec covers six typer subcommands (`init`, `extract`, `load`, `pipeline`, `schema`, `status`). The `.kg-builder/` directory is the resource folder for the target project - contains `config.yml` (Neo4J connection, LLM settings, extraction/loading defaults), `ontology.yml`, `schemas/` for structured data descriptions, and `extractions/` for output. Supports both structured (JSON/JSONL with generatively-interpreted schema descriptions) and unstructured (PDF/TXT/MD/DOCX with chunking) data sources. `kg init` has template mode (commented YAML scaffold) and interactive mode (LLM-driven Q&A to generate tailored config). Config resolution: CLI flags > config.yml > built-in defaults. Secrets use `${VAR}` interpolation from `.env`. Added Neo4J LLM Graph Builder as reference implementation in `README.md`.

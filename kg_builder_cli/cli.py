"""CLI entry points for kg-builder-cli."""
from __future__ import annotations

from pathlib import Path

import typer
from loguru import logger

app = typer.Typer(name="kg", help="Knowledge Graph Builder CLI", invoke_without_command=True)


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    """Launch TUI when no subcommand is given."""
    if ctx.invoked_subcommand is None:
        from kg_builder_cli.tui.app import KGBuilderApp
        tui_app = KGBuilderApp()
        tui_app.run()


@app.command()
def ingest(
    source: Path = typer.Argument(..., help="Path to file or directory to ingest"),
    batch: bool = typer.Option(False, "--batch", help="Run in autonomous mode without interactive checkpoints"),
    ontology: Path | None = typer.Option(None, "--ontology", help="Path to ontology seed file"),
    config_path: Path | None = typer.Option(None, "--config", help="Path to config.yml"),
    chunk_size: int | None = typer.Option(None, "--chunk-size", help="Override chunk size"),
    chunk_overlap: int | None = typer.Option(None, "--chunk-overlap", help="Override chunk overlap"),
    concurrency: int | None = typer.Option(None, "--concurrency", help="Override concurrency"),
):
    """Ingest documents into the knowledge graph."""
    from kg_builder_cli.config import load_config
    from kg_builder_cli.extraction.unstructured import ingest_document
    from kg_builder_cli.loading.loader import load_extraction
    from kg_builder_cli.ontology.buffer import OntologyBuffer

    logger.info("ingesting from {}", source)

    # Build CLI overrides
    overrides = {}
    if chunk_size is not None:
        overrides.setdefault("extract", {})["chunk_size"] = chunk_size
    if chunk_overlap is not None:
        overrides.setdefault("extract", {})["chunk_overlap"] = chunk_overlap
    if concurrency is not None:
        overrides.setdefault("extract", {})["concurrency"] = concurrency

    config = load_config(config_path=config_path, overrides=overrides if overrides else None)
    logger.info("config loaded: model={}, neo4j={}", config.llm.model, config.neo4j.uri)

    # Initialize ontology buffer
    buffer = None
    if ontology and ontology.suffix in (".yml", ".yaml"):
        buffer = OntologyBuffer.from_yaml(ontology, config.ontology_buffer)
        logger.info("ontology buffer loaded from {}", ontology)
    elif ontology is None:
        buffer = OntologyBuffer(config.ontology_buffer)

    # Collect files to process
    if source.is_dir():
        files = sorted(
            p for p in source.iterdir()
            if p.suffix.lower() in (".pdf", ".txt", ".md", ".docx", ".json", ".jsonl")
        )
    else:
        files = [source]

    if not files:
        logger.error("no supported files found in {}", source)
        raise typer.Exit(1)

    logger.info("found {} file(s) to ingest", len(files))

    for file_path in files:
        logger.info("processing: {}", file_path.name)
        result = ingest_document(file_path, config, buffer=buffer)
        logger.info(
            "extracted {} entities, {} relationships, {} facts",
            len(result.entities),
            len(result.relationships),
            len(result.facts),
        )

        # Load into Neo4j
        load_result = load_extraction(result, config)
        logger.info(
            "loaded: {} created, {} merged, {} relationships",
            load_result.nodes_created,
            load_result.nodes_merged,
            load_result.relationships_created,
        )

    # Flush ontology buffer after all files
    if buffer and config.ontology_buffer.flush_on_complete:
        flush_path = Path.cwd() / ".kg-builder" / "ontology.yml"
        buffer.flush(flush_path)
        logger.info("ontology buffer flushed: coverage={:.0%}", buffer.coverage())

    logger.info("ingestion complete")


@app.command()
def query(
    question: str = typer.Argument(..., help="Natural language question about the graph"),
):
    """Query the knowledge graph."""
    logger.info("query: {}", question)
    logger.warning("Query agent not yet implemented")


@app.command()
def init():
    """Initialize .kg-builder/ directory with default configuration."""
    from kg_builder_cli.config.defaults import DEFAULTS

    kg_dir = Path.cwd() / ".kg-builder"
    if kg_dir.exists():
        logger.info(".kg-builder/ already exists")
        return

    import yaml

    kg_dir.mkdir()
    (kg_dir / "schemas").mkdir()
    (kg_dir / "extractions").mkdir()
    (kg_dir / "memory").mkdir()
    (kg_dir / "migrations").mkdir()
    (kg_dir / "runs").mkdir()

    config_path = kg_dir / "config.yml"
    config_path.write_text(yaml.dump(DEFAULTS, default_flow_style=False, sort_keys=False))
    logger.info("created {} with default config", kg_dir)


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()

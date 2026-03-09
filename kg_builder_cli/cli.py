"""CLI entry points for kg-builder-cli."""
from __future__ import annotations

from pathlib import Path

import typer
from loguru import logger

app = typer.Typer(name="kg", help="Knowledge Graph Builder CLI")


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

    logger.info(f"Ingesting from {source}")

    # Build CLI overrides
    overrides = {}
    if chunk_size is not None:
        overrides.setdefault("extract", {})["chunk_size"] = chunk_size
    if chunk_overlap is not None:
        overrides.setdefault("extract", {})["chunk_overlap"] = chunk_overlap
    if concurrency is not None:
        overrides.setdefault("extract", {})["concurrency"] = concurrency

    config = load_config(config_path=config_path, overrides=overrides if overrides else None)
    logger.info(f"Config loaded: model={config.llm.model}, neo4j={config.neo4j.uri}")

    # Collect files to process
    if source.is_dir():
        files = sorted(
            p for p in source.iterdir()
            if p.suffix.lower() in (".pdf", ".txt", ".md", ".docx", ".json", ".jsonl")
        )
    else:
        files = [source]

    if not files:
        logger.error(f"No supported files found in {source}")
        raise typer.Exit(1)

    logger.info(f"Found {len(files)} file(s) to ingest")

    for file_path in files:
        logger.info(f"Processing: {file_path.name}")
        result = ingest_document(file_path, config)
        logger.info(
            f"Extracted {len(result.entities)} entities, "
            f"{len(result.relationships)} relationships, "
            f"{len(result.facts)} facts"
        )

        # Load into Neo4j
        load_result = load_extraction(result, config)
        logger.info(
            f"Loaded: {load_result.nodes_created} created, "
            f"{load_result.nodes_merged} merged, "
            f"{load_result.relationships_created} relationships"
        )

    logger.info("Ingestion complete")


@app.command()
def query(
    question: str = typer.Argument(..., help="Natural language question about the graph"),
):
    """Query the knowledge graph."""
    logger.info(f"Query: {question}")
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
    logger.info(f"Created {kg_dir} with default config")


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()

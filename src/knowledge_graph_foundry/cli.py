"""Knowledge Graph Foundry CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from loguru import logger
from rich.console import Console
from rich.table import Table
import typer

from knowledge_graph_foundry.settings import load_settings

app = typer.Typer(
    name="kgf",
    help="Knowledge Graph Foundry - build and maintain Neo4j knowledge graphs.",
    no_args_is_help=True,
)
console = Console()


def _foundry(config: Optional[Path] = None, event_log: bool = False):
    from knowledge_graph_foundry.events import enable_event_log
    from knowledge_graph_foundry.pipeline import Foundry

    settings = load_settings(config)
    if event_log or settings.event_log:
        enable_event_log(settings.event_log or "logs/kgf-events.jsonl")
    return Foundry(settings)


def _fail(message: str) -> None:
    console.print(f"[red]error:[/red] {message}")
    raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Show the installed version."""
    from importlib.metadata import version as pkg_version

    typer.echo(pkg_version("knowledge-graph-foundry"))


@app.command()
def init(
    purpose: str = typer.Argument(..., help="What the graph is for - drives construction"),
    seed: Optional[str] = typer.Option(
        None, help="Seed schema: YAML/JSON/OWL path or freeform text"
    ),
    config: Optional[Path] = typer.Option(None, help="Path to config.yml"),
) -> None:
    """Initialize the foundry: store purpose and optional seed, verify Neo4j."""
    foundry = _foundry(config)
    try:
        ontology = foundry.init_project(purpose, seed)
    except Exception as exc:
        _fail(str(exc))
    console.print(f"initialized - purpose: [bold]{purpose}[/bold]")
    if ontology.types:
        console.print(f"seeded types: {', '.join(sorted(ontology.types))}")
    foundry.close()


@app.command()
def ingest(
    path: Path = typer.Argument(..., help="File, directory or zip to ingest"),
    config: Optional[Path] = typer.Option(None, help="Path to config.yml"),
    event_log: bool = typer.Option(False, "--event-log", help="Write JSONL event log"),
) -> None:
    """Ingest data through the full pipeline."""
    foundry = _foundry(config, event_log)
    try:
        summary = foundry.ingest(path)
    except Exception as exc:
        logger.exception("ingest failed")
        _fail(str(exc))
    console.print(
        f"ingested [bold]{summary['documents']}[/bold] documents: "
        f"{summary['entities']} entities, {summary['relationships']} relationships"
        + (" [green](ontology cured)[/green]" if summary.get("cured") else " (fluid)")
    )
    foundry.close()


@app.command()
def status(config: Optional[Path] = typer.Option(None, help="Path to config.yml")) -> None:
    """Show lifecycle state, counts, ontology and drift."""
    foundry = _foundry(config)
    try:
        info = foundry.status()
    except Exception as exc:
        _fail(str(exc))
    table = Table(show_header=False, box=None)
    table.add_row("state", info["fsm_state"])
    if info.get("purpose"):
        table.add_row("purpose", info["purpose"])
        table.add_row("entities", str(info["entities"]))
        table.add_row("relationships", str(info["relationships"]))
        table.add_row("documents", str(info.get("documents_processed", 0)))
        table.add_row("cured", str(info.get("cured", False)))
        table.add_row("types", ", ".join(info.get("types", [])) or "-")
        if info.get("latest_metrics"):
            m = info["latest_metrics"]
            table.add_row(
                "stability",
                f"jsd={m.get('js_divergence', 0):.4f} "
                f"chao1={m.get('chao1_coverage', 0):.3f} "
                f"dH={m.get('entropy_shannon_delta', 0):.4f}",
            )
        if info.get("drift"):
            table.add_row("drift", str(info["drift"]))
    console.print(table)
    foundry.close()


@app.command()
def optimize(config: Optional[Path] = typer.Option(None, help="Path to config.yml")) -> None:
    """Run GraphRAG optimization: communities, summaries, quality scorecard."""
    foundry = _foundry(config)
    try:
        result = foundry.optimize()
    except Exception as exc:
        _fail(str(exc))
    console.print(json.dumps(result, indent=2, default=str))
    foundry.close()


@app.command()
def calibrate(
    ground_truth: Path = typer.Argument(
        ..., help="Ground-truth pairs JSON: [{left_id, right_id, same}]"
    ),
    events: Optional[Path] = typer.Option(
        None, help="Resolution event log JSONL (default: settings.event_log)"
    ),
    output: Optional[Path] = typer.Option(
        None, help="Artifact output (default: settings.resolution.calibration_path)"
    ),
    config: Optional[Path] = typer.Option(None, help="Path to config.yml"),
) -> None:
    """Fit a per-corpus isotonic calibration artifact from resolution events and
    ground-truth pairs (H157/H142). Offline-fit and runtime-frozen: the resolver
    loads the artifact when resolution.calibration_path points at it."""
    from knowledge_graph_foundry.resolution.calibration import fit_calibration_from_events

    settings = load_settings(config)
    events_path = events or Path(settings.event_log or "logs/kgf-events.jsonl")
    out_path = output or (
        Path(settings.resolution.calibration_path)
        if settings.resolution.calibration_path
        else None
    )
    if out_path is None:
        _fail("no output: set resolution.calibration_path in config or pass --output")
    if not events_path.exists():
        _fail(f"event log not found: {events_path}")
    calibrator = fit_calibration_from_events(
        events_path, ground_truth, settings.resolution.calibration_min_observations
    )
    if calibrator is None:
        _fail("too few matched labels to fit a curve - resolver keeps its fixed threshold")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(calibrator.to_json())
    console.print(f"calibration artifact written to [bold]{out_path}[/bold]")


@app.command()
def repurpose(
    purpose: str = typer.Argument(..., help="The new use case driving future extraction"),
    seed: Optional[str] = typer.Option(
        None, help="Optional extra seed types: YAML/JSON/OWL path or freeform text"
    ),
    config: Optional[Path] = typer.Option(None, help="Path to config.yml"),
) -> None:
    """Change the graph's use case in place (old purpose kept in history)."""
    foundry = _foundry(config)
    try:
        result = foundry.repurpose(purpose, seed)
    except Exception as exc:
        _fail(str(exc))
    console.print(f"repurposed - now: [bold]{result['purpose']}[/bold]")
    console.print(
        f"[dim]previous: {result['previous_purpose']} (change #{result['purpose_changes']})[/dim]"
    )
    if result["seeded_types_added"]:
        console.print(f"seeded types added: {', '.join(result['seeded_types_added'])}")
    foundry.close()


@app.command()
def repair(
    question: str = typer.Argument(..., help="The failing question to repair the graph for"),
    sources: list[Path] = typer.Argument(..., help="Source documents to re-extract with focus"),
    config: Optional[Path] = typer.Option(None, help="Path to config.yml"),
) -> None:
    """Targeted repair: re-extract named documents focused on a failing question."""
    foundry = _foundry(config)
    try:
        result = foundry.repair(question, [str(s) for s in sources])
    except Exception as exc:
        _fail(str(exc))
    console.print(json.dumps(result, indent=2, default=str))
    foundry.close()


@app.command()
def query(
    question: str = typer.Argument(..., help="Question to answer over the graph"),
    config: Optional[Path] = typer.Option(None, help="Path to config.yml"),
) -> None:
    """Answer a question grounded in the knowledge graph."""
    foundry = _foundry(config)
    try:
        result = foundry.query(question)
    except Exception as exc:
        _fail(str(exc))
    console.print(result["answer"])
    if result.get("supporting_entities"):
        console.print(f"[dim]supported by: {', '.join(result['supporting_entities'])}[/dim]")
    foundry.close()


@app.command()
def wipe(
    yes: bool = typer.Option(False, "--yes", help="Confirm deletion"),
    config: Optional[Path] = typer.Option(None, help="Path to config.yml"),
) -> None:
    """Delete ALL graph content and the control metanode."""
    if not yes:
        _fail("refusing to wipe without --yes")
    foundry = _foundry(config)
    foundry.wipe()
    console.print("graph wiped")
    foundry.close()


@app.command()
def tui(config: Optional[Path] = typer.Option(None, help="Path to config.yml")) -> None:
    """Launch the interactive dashboard."""
    from knowledge_graph_foundry.tui.app import FoundryApp

    settings = load_settings(config)
    FoundryApp(settings).run()


def main() -> None:
    app()


if __name__ == "__main__":
    main()

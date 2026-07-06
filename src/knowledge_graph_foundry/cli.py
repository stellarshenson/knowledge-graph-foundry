"""Knowledge Graph Foundry CLI entry point."""

import typer

app = typer.Typer(
    name="kgf", help="Knowledge Graph Foundry - build and maintain Neo4j knowledge graphs."
)


@app.command()
def version() -> None:
    """Show the installed Knowledge Graph Foundry version."""
    from importlib.metadata import version as pkg_version

    typer.echo(pkg_version("knowledge-graph-foundry"))


def main() -> None:
    app()


if __name__ == "__main__":
    main()

"""Textual TUI application for kg-builder-cli."""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, RichLog, Static


class KGBuilderApp(App):
    """Knowledge Graph Builder TUI."""

    CSS = """
    #command-panel {
        width: 30;
        dock: left;
        padding: 1;
        border-right: solid $primary;
    }
    #log-panel {
        padding: 1;
    }
    #status-bar {
        dock: bottom;
        height: 3;
        padding: 0 1;
        background: $surface;
        border-top: solid $primary;
    }
    .command-btn {
        width: 100%;
        margin: 1 0;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("i", "ingest", "Ingest"),
        ("s", "status", "Status"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="command-panel"):
                yield Static("Commands", classes="title")
                yield Button("Ingest", id="btn-ingest", classes="command-btn")
                yield Button("Query", id="btn-query", classes="command-btn")
                yield Button("Init", id="btn-init", classes="command-btn")
                yield Button("Status", id="btn-status", classes="command-btn")
            with Vertical(id="log-panel"):
                yield RichLog(id="log", highlight=True, markup=True)
        with Horizontal(id="status-bar"):
            yield Static("Entities: -  |  Relationships: -  |  Status: ready", id="status-text")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#log", RichLog)
        log.write("[bold]Knowledge Graph Builder CLI[/bold]")
        log.write("Ready. Use the command panel or keyboard shortcuts.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        log = self.query_one("#log", RichLog)
        if event.button.id == "btn-ingest":
            log.write("[yellow]Ingest command - use CLI: kg ingest <path>[/yellow]")
        elif event.button.id == "btn-query":
            log.write("[yellow]Query command - not yet implemented[/yellow]")
        elif event.button.id == "btn-init":
            log.write("[yellow]Init command - use CLI: kg init[/yellow]")
        elif event.button.id == "btn-status":
            log.write("[yellow]Status - checking Neo4j connection...[/yellow]")

    def action_ingest(self) -> None:
        log = self.query_one("#log", RichLog)
        log.write("[yellow]Ingest command - use CLI: kg ingest <path>[/yellow]")

    def action_status(self) -> None:
        log = self.query_one("#log", RichLog)
        log.write("[yellow]Status check - not yet implemented[/yellow]")

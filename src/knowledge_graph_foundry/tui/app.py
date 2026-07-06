"""Foundry dashboard - lifecycle state, live ingestion, stability, drift,
event feed. Duoptimum palette (cyan + orange on dark blue-grey); state is
conveyed by colour + text label, never icon glyphs.
"""

from __future__ import annotations

from importlib.metadata import version as pkg_version
import os
from pathlib import Path

os.environ.setdefault("COLORTERM", "truecolor")

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, RichLog, Static

from knowledge_graph_foundry.events import subscribe, unsubscribe
from knowledge_graph_foundry.settings import Settings

VERSION = pkg_version("knowledge-graph-foundry")

CYAN = "#21a8e4"
CYAN_BRIGHT = "#46bcf0"
ORANGE = "#da8230"
MINT = "#3fb950"
ROSE = "#ef4444"

FEED_SIGNALS = [
    "document.started",
    "document.completed",
    "document.skipped",
    "extraction.warning",
    "resolution.merge",
    "ontology.type_emerged",
    "ontology.type_confirmed",
    "curing.metrics",
    "curing.cured",
    "curing.forced",
    "drift.warning",
    "drift.decision",
    "fsm.transition",
    "load.completed",
    "propositions.generated",
    "densify.completed",
    "query.abstained",
]


class FoundryApp(App):
    TITLE = "Knowledge Graph Foundry"

    CSS = f"""
    Screen {{ background: #1a1f25; color: #c3c3c3; }}
    #app-header {{ height: 1; background: #2a313a; }}
    #hdr-title {{ width: 1fr; color: {CYAN_BRIGHT}; padding-left: 1; }}
    #hdr-version {{ width: auto; color: #7d8791; padding-right: 1; }}
    #panels {{ height: auto; }}
    .panel {{
        background: #252b32; border: solid #404b54; margin: 1 1 0 1;
        padding: 0 1; height: auto;
    }}
    .panel-title {{ color: {CYAN_BRIGHT}; }}
    #ingest-row {{ height: 3; margin: 0 1; }}
    #ingest-path {{ background: #303841; border: solid #404b54; }}
    #ingest-path:focus {{ border: solid {CYAN}; }}
    #feed {{
        background: #252b32; border: solid #404b54; margin: 1 1;
        height: 1fr; padding: 0 1;
    }}
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
    ]

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self._foundry = None
        self._receivers: list[tuple[str, object]] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="app-header"):
            yield Static("Knowledge Graph Foundry", id="hdr-title")
            yield Static(f"v{VERSION}", id="hdr-version")
        with Horizontal(id="panels"):
            with Vertical(classes="panel", id="status-panel"):
                yield Static("STATUS", classes="panel-title")
                yield Static("connecting...", id="status-body")
            with Vertical(classes="panel", id="stability-panel"):
                yield Static("STABILITY", classes="panel-title")
                yield Static("no metrics yet", id="stability-body")
            with Vertical(classes="panel", id="drift-panel"):
                yield Static("DRIFT", classes="panel-title")
                yield Static("pre-cure", id="drift-body")
        with Horizontal(id="ingest-row"):
            yield Input(
                placeholder="path to ingest (file, directory or zip) - Enter to run",
                id="ingest-path",
                select_on_focus=False,
            )
        yield RichLog(id="feed", markup=True, wrap=True)

    # -- lifecycle -------------------------------------------------------

    def on_mount(self) -> None:
        for name in FEED_SIGNALS:
            receiver = self._make_receiver(name)
            subscribe(name, receiver)
            self._receivers.append((name, receiver))
        self.action_refresh()

    def on_unmount(self) -> None:
        for name, receiver in self._receivers:
            unsubscribe(name, receiver)

    def _make_receiver(self, name: str):
        def receiver(sender, **payload):
            self.call_from_thread(self._on_event, name, payload)

        return receiver

    # -- event handling ----------------------------------------------------

    def _on_event(self, name: str, payload: dict) -> None:
        feed = self.query_one("#feed", RichLog)
        colour = "#c3c3c3"
        if "warning" in name or name == "document.skipped":
            colour = ORANGE
        elif name in ("curing.cured", "resolution.merge", "load.completed"):
            colour = MINT
        elif "drift" in name:
            colour = ROSE if payload.get("action") in ("recure", "rebuild") else ORANGE
        detail = " ".join(
            f"{k}={v}"
            for k, v in payload.items()
            if isinstance(v, (str, int, float)) and k not in ("history",)
        )[:160]
        feed.write(f"[{colour}]{name}[/] {detail}")

        if name == "curing.metrics":
            self._update_stability(payload)
        if name in ("drift.warning", "drift.decision"):
            body = self.query_one("#drift-body", Static)
            action = payload.get("action", "warn")
            colour = ROSE if action in ("recure", "rebuild") else ORANGE
            body.update(f"[{colour}]{action}[/] jsd={payload.get('jsd', 0):.4f}")
        if name in ("fsm.transition", "curing.cured", "document.completed"):
            self.action_refresh()

    def _update_stability(self, metrics: dict) -> None:
        body = self.query_one("#stability-body", Static)
        jsd = metrics.get("js_divergence", float("nan"))
        chao1 = metrics.get("chao1_coverage", 0.0)
        entropy_delta = metrics.get("entropy_shannon_delta", float("nan"))
        types = int(metrics.get("unique_types", 0))
        converged = (
            jsd < self.settings.curing.jsd_threshold
            and chao1 > self.settings.curing.chao1_threshold
            and abs(entropy_delta) < self.settings.curing.entropy_delta_threshold
        )
        state = f"[{MINT}]converging[/]" if converged else f"[{ORANGE}]fluid[/]"
        body.update(
            f"jsd {jsd:.4f}  chao1 {chao1:.3f}\ndH {entropy_delta:.4f}  types {types}  {state}"
        )

    # -- actions ------------------------------------------------------------

    def action_refresh(self) -> None:
        self.run_worker(self._refresh_status, thread=True, exclusive=True, group="status")

    def _refresh_status(self) -> None:
        try:
            foundry = self._get_foundry()
            info = foundry.status()
        except Exception as exc:
            self.call_from_thread(
                self.query_one("#status-body", Static).update,
                f"[{ROSE}]ERROR: neo4j unreachable[/]\n{str(exc)[:80]}",
            )
            return
        lines = [
            f"state [{CYAN}]{info['fsm_state']}[/]",
            f"purpose {info.get('purpose', '-')[:40] or '-'}",
            f"entities {info.get('entities', 0)}  rels {info.get('relationships', 0)}",
            f"docs {info.get('documents_processed', 0)}  "
            f"cured {'[' + MINT + ']yes[/]' if info.get('cured') else 'no'}",
            f"types {', '.join(info.get('types', [])[:8]) or '-'}",
        ]
        self.call_from_thread(self.query_one("#status-body", Static).update, "\n".join(lines))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "ingest-path":
            return
        path = Path(event.value.strip())
        if not event.value.strip():
            return
        feed = self.query_one("#feed", RichLog)
        if not path.exists():
            feed.write(f"[{ROSE}]ERROR:[/] path does not exist: {path}")
            return
        feed.write(f"[{CYAN}]ingest starting:[/] {path}")
        self.run_worker(lambda: self._run_ingest(path), thread=True, group="ingest")

    def _run_ingest(self, path: Path) -> None:
        feed = self.query_one("#feed", RichLog)
        try:
            summary = self._get_foundry().ingest(path)
        except Exception as exc:
            self.call_from_thread(feed.write, f"[{ROSE}]ERROR: ingest failed - {exc}[/]")
            return
        self.call_from_thread(
            feed.write,
            f"[{MINT}]ingest complete[/] documents={summary['documents']} "
            f"entities={summary['entities']} relationships={summary['relationships']}",
        )
        self.call_from_thread(self.action_refresh)

    def _get_foundry(self):
        if self._foundry is None:
            from knowledge_graph_foundry.pipeline import Foundry

            self._foundry = Foundry(self.settings)
        return self._foundry

    def get_system_commands(self, screen):
        for command in super().get_system_commands(screen):
            if command.title != "Change theme":
                yield command

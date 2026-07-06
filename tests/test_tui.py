"""Headless tests for the TUI dashboard."""

import asyncio
from unittest.mock import MagicMock, patch

from knowledge_graph_foundry.settings import Settings
from knowledge_graph_foundry.tui.app import FoundryApp


def _app() -> FoundryApp:
    return FoundryApp(Settings())


class TestDashboard:
    def test_renders_with_neo4j_down(self):
        """Dashboard shows an error banner instead of crashing when the
        graph is unreachable."""

        async def scenario():
            app = _app()
            with patch.object(app, "_get_foundry", side_effect=RuntimeError("refused")):
                async with app.run_test(size=(100, 30)) as pilot:
                    await pilot.pause()
                    body = app.query_one("#status-body").render()
                    assert "neo4j unreachable" in str(body)

        asyncio.run(scenario())

    def test_status_panel_renders_state(self):
        async def scenario():
            app = _app()
            foundry = MagicMock()
            foundry.status.return_value = {
                "fsm_state": "STABLE",
                "purpose": "compare CPAP machines",
                "entities": 42,
                "relationships": 17,
                "documents_processed": 5,
                "cured": True,
                "types": ["Product", "Component"],
            }
            with patch.object(app, "_get_foundry", return_value=foundry):
                async with app.run_test(size=(100, 30)) as pilot:
                    await pilot.pause()
                    body = str(app.query_one("#status-body").render())
                    assert "STABLE" in body
                    assert "42" in body

        asyncio.run(scenario())

    def test_resize_does_not_crash(self):
        async def scenario():
            app = _app()
            with patch.object(app, "_get_foundry", side_effect=RuntimeError("down")):
                async with app.run_test(size=(100, 30)) as pilot:
                    await pilot.resize_terminal(40, 12)
                    await pilot.pause()
                    await pilot.resize_terminal(140, 50)
                    await pilot.pause()

        asyncio.run(scenario())

    def test_stability_panel_updates_from_metrics_event(self):
        async def scenario():
            app = _app()
            with patch.object(app, "_get_foundry", side_effect=RuntimeError("down")):
                async with app.run_test(size=(100, 30)) as pilot:
                    await pilot.pause()
                    app._update_stability(
                        {
                            "js_divergence": 0.001,
                            "chao1_coverage": 0.99,
                            "entropy_shannon_delta": 0.0001,
                            "unique_types": 8,
                        }
                    )
                    await pilot.pause()
                    body = str(app.query_one("#stability-body").render())
                    assert "0.0010" in body
                    assert "converging" in body

        asyncio.run(scenario())

    def test_ingest_rejects_missing_path(self):
        async def scenario():
            app = _app()
            with patch.object(app, "_get_foundry", side_effect=RuntimeError("down")):
                async with app.run_test(size=(100, 30)) as pilot:
                    await pilot.pause()
                    field = app.query_one("#ingest-path")
                    field.value = "/nonexistent/nowhere"
                    await pilot.pause()
                    field.post_message(field.Submitted(field, field.value))
                    await pilot.pause()
                    lines = "".join(str(s) for s in app.query_one("#feed").lines)
                    assert "does not exist" in lines

        asyncio.run(scenario())

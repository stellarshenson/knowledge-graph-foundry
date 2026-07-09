"""CLI tests via typer's runner with a mocked Foundry."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from knowledge_graph_foundry.cli import app
from knowledge_graph_foundry.pipeline import FoundryError

runner = CliRunner()


class TestCli:
    def test_version(self):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert result.stdout.strip()

    def test_no_args_shows_help(self):
        result = runner.invoke(app, [])
        assert "init" in result.stdout
        assert "ingest" in result.stdout

    def test_ingest_before_init_fails_with_message(self, tmp_path):
        foundry = MagicMock()
        foundry.ingest.side_effect = FoundryError("project not initialized - run `kgf init` first")
        (tmp_path / "doc.md").write_text("hello")
        with patch("knowledge_graph_foundry.cli._foundry", return_value=foundry):
            result = runner.invoke(app, ["ingest", str(tmp_path / "doc.md")])
        assert result.exit_code == 1
        assert "kgf init" in result.output

    def test_init_prints_purpose(self):
        foundry = MagicMock()
        foundry.init_project.return_value = MagicMock(types={"Product": None})
        with patch("knowledge_graph_foundry.cli._foundry", return_value=foundry):
            result = runner.invoke(app, ["init", "compare CPAP machines"])
        assert result.exit_code == 0
        assert "compare CPAP machines" in result.output

    def test_wipe_requires_yes(self):
        result = runner.invoke(app, ["wipe"])
        assert result.exit_code == 1
        assert "--yes" in result.output

    def test_wipe_with_yes(self):
        foundry = MagicMock()
        with patch("knowledge_graph_foundry.cli._foundry", return_value=foundry):
            result = runner.invoke(app, ["wipe", "--yes"])
        assert result.exit_code == 0
        foundry.wipe.assert_called_once()

    def test_status_renders_state(self):
        foundry = MagicMock()
        foundry.status.return_value = {"fsm_state": "EMPTY"}
        with patch("knowledge_graph_foundry.cli._foundry", return_value=foundry):
            result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "EMPTY" in result.output

    def test_query_prints_answer(self):
        foundry = MagicMock()
        foundry.query.return_value = {
            "answer": "AirSense 11 covers 4-20 cmH2O",
            "supporting_entities": ["AirSense 11"],
        }
        with patch("knowledge_graph_foundry.cli._foundry", return_value=foundry):
            result = runner.invoke(app, ["query", "pressure range?"])
        assert result.exit_code == 0
        assert "AirSense 11" in result.output

    def test_calibrate_writes_artifact(self, tmp_path):
        import json

        events = tmp_path / "events.jsonl"
        gt = tmp_path / "gt.json"
        out = tmp_path / "calib.json"
        lines, truth = [], []
        for i in range(12):
            p = i / 11
            lines.append(json.dumps(
                {"event": "resolution.defer", "left_id": f"l{i}", "right_id": f"r{i}", "posterior": p}
            ))
            truth.append({"left_id": f"l{i}", "right_id": f"r{i}", "same": p >= 0.5})
        events.write_text("\n".join(lines) + "\n")
        gt.write_text(json.dumps(truth))

        settings = MagicMock()
        settings.event_log = str(events)
        settings.resolution.calibration_path = str(out)
        settings.resolution.calibration_min_observations = 5
        with patch("knowledge_graph_foundry.cli.load_settings", return_value=settings):
            result = runner.invoke(app, ["calibrate", str(gt)])
        assert result.exit_code == 0
        assert out.exists()

    def test_calibrate_no_output_fails(self, tmp_path):
        gt = tmp_path / "gt.json"
        gt.write_text("[]")
        settings = MagicMock()
        settings.event_log = None
        settings.resolution.calibration_path = None
        with patch("knowledge_graph_foundry.cli.load_settings", return_value=settings):
            result = runner.invoke(app, ["calibrate", str(gt)])
        assert result.exit_code == 1

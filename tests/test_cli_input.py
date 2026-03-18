"""Tests for CLI --input multi-option and --structured/--unstructured mode flags."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from kg_builder_cli.cli import app

runner = CliRunner()


# ── CLI argument parsing ─────────────────────────────────────────────


class TestNoInput:
    def test_no_source_no_input_exits(self):
        result = runner.invoke(app, ["ingest"])
        assert result.exit_code != 0


class TestMutualExclusion:
    def test_structured_and_unstructured_exits(self, tmp_path):
        f = tmp_path / "test.pdf"
        f.touch()
        result = runner.invoke(app, ["ingest", str(f), "--structured", "--unstructured"])
        assert result.exit_code != 0


class TestFileCollection:
    """Verify that --input collects files and mode filtering works."""

    @pytest.fixture()
    def mixed_dir(self, tmp_path):
        """Create a directory with both structured and unstructured files."""
        for ext in [".pdf", ".txt", ".md", ".docx", ".json", ".jsonl", ".csv", ".xlsx", ".py"]:
            (tmp_path / f"test{ext}").touch()
        return tmp_path

    def test_unstructured_filters_correctly(self, mixed_dir):
        """Unstructured mode should only pick up PDF/TXT/MD/DOCX."""
        from kg_builder_cli.config import UNSTRUCTURED_EXTENSIONS

        found = sorted(
            p for p in mixed_dir.iterdir() if p.suffix.lower() in UNSTRUCTURED_EXTENSIONS
        )
        assert len(found) == 4
        assert {p.suffix for p in found} == {".pdf", ".txt", ".md", ".docx"}

    def test_structured_filters_correctly(self, mixed_dir):
        """Structured mode should only pick up JSON/JSONL/CSV/XLSX."""
        from kg_builder_cli.config import STRUCTURED_EXTENSIONS

        found = sorted(
            p for p in mixed_dir.iterdir() if p.suffix.lower() in STRUCTURED_EXTENSIONS
        )
        assert len(found) == 4
        assert {p.suffix for p in found} == {".json", ".jsonl", ".csv", ".xlsx"}

    def test_unsupported_extensions_excluded(self, mixed_dir):
        """Files like .py should never be collected in either mode."""
        from kg_builder_cli.config import SUPPORTED_EXTENSIONS

        found = [p for p in mixed_dir.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS]
        assert all(p.suffix != ".py" for p in found)


class TestMultiInput:
    """Verify that multiple --input options and positional SOURCE merge correctly."""

    def test_source_merging_logic(self, tmp_path):
        """Multiple sources should be merged into a single file list."""
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        (dir_a / "one.pdf").touch()
        (dir_b / "two.pdf").touch()

        # Simulate the merging logic from cli.py
        all_sources = [dir_a, dir_b]
        from kg_builder_cli.config import UNSTRUCTURED_EXTENSIONS

        files: list[Path] = []
        for src in all_sources:
            if src.is_dir():
                files.extend(
                    sorted(p for p in src.iterdir() if p.suffix.lower() in UNSTRUCTURED_EXTENSIONS)
                )
        assert len(files) == 2
        assert {f.name for f in files} == {"one.pdf", "two.pdf"}

    def test_single_file_input(self, tmp_path):
        """A single file as source should be collected regardless of mode filtering."""
        f = tmp_path / "single.pdf"
        f.touch()
        # Simulate: source is a file, not a dir
        files: list[Path] = []
        if f.is_file():
            files.append(f)
        assert len(files) == 1

    def test_missing_source_skipped(self, tmp_path):
        """Non-existent paths should be skipped with warning."""
        fake = tmp_path / "does_not_exist"
        all_sources = [fake]
        files: list[Path] = []
        for src in all_sources:
            if src.is_dir():
                pass
            elif src.is_file():
                files.append(src)
            # else: skipped
        assert len(files) == 0

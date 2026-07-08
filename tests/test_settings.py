"""Tests for settings loading and precedence."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from knowledge_graph_foundry.settings import Settings, load_settings


class TestDefaults:
    def test_missing_config_uses_defaults(self, tmp_path, monkeypatch):
        monkeypatch.delenv("NEO4J_URI", raising=False)
        s = load_settings(tmp_path / "nope.yml")
        assert s.llm.engine == "frontier"
        assert s.curing.jsd_threshold == 0.02

    def test_invalid_value_fails_fast(self):
        with pytest.raises(ValidationError):
            Settings(llm={"engine": "quantum"})

    def test_extraction_recipe_defaults_to_single(self):
        assert Settings().extraction.recipe == "single"

    def test_invalid_extraction_recipe_fails_fast(self):
        with pytest.raises(ValidationError):
            Settings(extraction={"recipe": "bogus"})


class TestPrecedence:
    def test_config_file_overrides_defaults(self, tmp_path: Path):
        cfg = tmp_path / "config.yml"
        cfg.write_text("curing:\n  jsd_threshold: 0.05\n")
        s = load_settings(cfg)
        assert s.curing.jsd_threshold == 0.05

    def test_explicit_config_beats_env(self, tmp_path: Path, monkeypatch):
        # regression for the 2026-07-07 wrong-instance ingest: a .env NEO4J_URI
        # must not override a uri the config file sets explicitly
        cfg = tmp_path / "config.yml"
        cfg.write_text("neo4j:\n  uri: bolt://from-file:7687\n")
        monkeypatch.setenv("NEO4J_URI", "bolt://from-env:7687")
        s = load_settings(cfg)
        assert s.neo4j.uri == "bolt://from-file:7687"

    def test_env_fills_config_gap(self, tmp_path: Path, monkeypatch):
        cfg = tmp_path / "config.yml"
        cfg.write_text("neo4j:\n  user: someone\n")
        monkeypatch.setenv("NEO4J_URI", "bolt://from-env:7687")
        s = load_settings(cfg)
        assert s.neo4j.uri == "bolt://from-env:7687"
        assert s.neo4j.user == "someone"

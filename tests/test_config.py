"""Tests for config loading, merging, and interpolation."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from kgf.settings import load_config
from kgf.settings.loader import _deep_merge, _interpolate_env


class TestLoadConfigDefaults:
    def test_load_config_defaults_only(self, tmp_path):
        """No config file, no overrides -> AppConfig with defaults."""
        config = load_config(config_path=tmp_path / "nonexistent.yml")
        # provider and model are None by default - must be explicitly configured
        assert config.llm.provider is None
        assert config.llm.model is None
        assert config.extract.chunk_size == 2000
        assert config.load.batch_size == 500

    def test_load_config_yaml_merge(self, tmp_path):
        """Partial YAML overrides deep-merged with defaults."""
        config_file = tmp_path / "config.yml"
        config_file.write_text(yaml.dump({
            "llm": {"temperature": 0.5},
            "extract": {"chunk_size": 1000},
        }))
        config = load_config(config_path=config_file)
        assert config.llm.temperature == 0.5
        assert config.extract.chunk_size == 1000
        # defaults preserved
        assert config.llm.provider is None
        assert config.extract.chunk_overlap == 200

    def test_load_config_env_interpolation(self, tmp_path, monkeypatch):
        """Environment variables resolved via ${VAR:default} syntax."""
        monkeypatch.setenv("TEST_NEO4J_URI", "bolt://testhost:7687")
        config_file = tmp_path / "config.yml"
        config_file.write_text(yaml.dump({
            "neo4j": {"uri": "${TEST_NEO4J_URI:bolt://localhost:7687}"},
        }))
        config = load_config(config_path=config_file)
        assert config.neo4j.uri == "bolt://testhost:7687"

    def test_load_config_cli_overrides_win(self, tmp_path):
        """CLI overrides beat YAML and defaults."""
        config_file = tmp_path / "config.yml"
        config_file.write_text(yaml.dump({"extract": {"chunk_size": 1000}}))
        config = load_config(
            config_path=config_file,
            overrides={"extract": {"chunk_size": 500}},
        )
        assert config.extract.chunk_size == 500


class TestDeepMerge:
    def test_deep_merge_nested(self):
        """Three-level nesting preserved."""
        base = {"a": {"b": {"c": 1, "d": 2}, "e": 3}}
        override = {"a": {"b": {"c": 10}}}
        result = _deep_merge(base, override)
        assert result["a"]["b"]["c"] == 10
        assert result["a"]["b"]["d"] == 2
        assert result["a"]["e"] == 3


class TestInterpolateEnv:
    def test_interpolate_with_default(self, monkeypatch):
        """Unset var falls back to default."""
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)
        result = _interpolate_env("${NONEXISTENT_VAR:fallback_value}")
        assert result == "fallback_value"

    def test_interpolate_set_var(self, monkeypatch):
        """Set env var replaces pattern."""
        monkeypatch.setenv("MY_VAR", "actual_value")
        result = _interpolate_env("prefix_${MY_VAR}_suffix")
        assert result == "prefix_actual_value_suffix"

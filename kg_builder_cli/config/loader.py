"""Config loading: YAML parsing, env var interpolation, defaults, CLI overrides."""

from __future__ import annotations

import copy
import os
import re
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from kg_builder_cli.types.config import AppConfig

from .defaults import DEFAULTS

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override values win."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


_ENV_VAR_DEFAULT_PATTERN = re.compile(r"\$\{([^}:]+)(?::([^}]*))?\}")


def _interpolate_env(value: Any) -> Any:
    """Replace ${VAR_NAME} or ${VAR_NAME:default} patterns with environment values.

    Handles strings, dicts, and lists recursively. Unresolved variables
    without a default are replaced with empty string.
    """
    if isinstance(value, str):
        return _ENV_VAR_DEFAULT_PATTERN.sub(
            lambda m: os.environ.get(m.group(1), m.group(2) or ""), value
        )
    if isinstance(value, dict):
        return {k: _interpolate_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env(item) for item in value]
    return value


def load_config(
    config_path: Path | None = None,
    overrides: dict | None = None,
) -> AppConfig:
    """Load configuration with defaults, YAML file, env interpolation, and overrides.

    Resolution order (highest wins):
        1. overrides dict (CLI flags)
        2. config.yml values (with ${VAR} resolved from .env / environment)
        3. Built-in defaults

    Args:
        config_path: Explicit path to config.yml. When None, looks for
            .kg-builder/config.yml in the current working directory.
        overrides: Dict of CLI overrides to apply on top.

    Returns:
        Validated AppConfig instance.
    """
    # Load .env before resolving any ${VAR} references
    load_dotenv()

    # Start with built-in defaults
    merged = copy.deepcopy(DEFAULTS)

    # Determine config file location
    if config_path is None:
        config_path = Path.cwd() / ".kg-builder" / "config.yml"

    # Layer YAML values on top of defaults
    if config_path.is_file():
        with open(config_path) as f:
            yaml_data = yaml.safe_load(f)
        if yaml_data and isinstance(yaml_data, dict):
            merged = _deep_merge(merged, yaml_data)

    # Resolve ${VAR} patterns from environment
    merged = _interpolate_env(merged)

    # Apply CLI overrides last
    if overrides:
        merged = _deep_merge(merged, overrides)

    return AppConfig(**merged)

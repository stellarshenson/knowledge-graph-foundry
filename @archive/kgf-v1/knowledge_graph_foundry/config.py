"""Central configuration for Knowledge Graph Foundry.

Single source of truth for application identity, critical paths, and logger setup.
Restores the copier-data-science template pattern with KGF-specific extensions.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys

from dotenv import load_dotenv
from loguru import logger

# ── Logger setup ───────────────────────────────────────────────────────
#
# In TTY mode, route through tqdm.write so progress bars and log lines
# don't collide.  In non-TTY mode (pipes, background jobs, CI),
# tqdm.write buffers indefinitely and never flushes, so fall back to
# plain stderr which auto-flushes on every write.

logger.remove()

if sys.stdout.isatty():
    try:
        from tqdm import tqdm

        logger.add(
            lambda msg: tqdm.write(msg, end="", file=sys.stdout),
            colorize=True,
        )
    except ModuleNotFoundError:
        logger.add(sys.stdout, colorize=True)
else:
    logger.add(sys.stderr, colorize=False)

# ── Environment ────────────────────────────────────────────────────────

load_dotenv()

# ── Application identity ───────────────────────────────────────────────

APP_NAME = "Knowledge Graph Foundry"
APP_SHORT = "knowledge_graph_foundry"

try:
    APP_VERSION = version("knowledge_graph_foundry")
except PackageNotFoundError:
    APP_VERSION = "0.0.0"

# ── Project paths (copier-data-science template) ───────────────────────

PROJ_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJ_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXTERNAL_DATA_DIR = DATA_DIR / "external"
MODELS_DIR = PROJ_ROOT / "models"
REPORTS_DIR = PROJ_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

# ── KGF runtime paths ─────────────────────────────────────────────────

UNSTRUCTURED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}
STRUCTURED_EXTENSIONS = {".json", ".jsonl", ".csv", ".xlsx"}
SUPPORTED_EXTENSIONS = UNSTRUCTURED_EXTENSIONS | STRUCTURED_EXTENSIONS

CONFIG_DIR_NAME = ".knowledge_graph_foundry"


def config_dir(root: Path | None = None) -> Path:
    """Return the .knowledge_graph_foundry/ config directory path."""
    return (root or Path.cwd()) / CONFIG_DIR_NAME


def config_file(root: Path | None = None) -> Path:
    """Return path to .knowledge_graph_foundry/config.yml."""
    return config_dir(root) / "config.yml"


def ontology_file(root: Path | None = None) -> Path:
    """Return path to .knowledge_graph_foundry/ontology.yml."""
    return config_dir(root) / "ontology.yml"


def memory_dir(root: Path | None = None) -> Path:
    """Return path to .knowledge_graph_foundry/memory/."""
    return config_dir(root) / "memory"


def migrations_dir(root: Path | None = None) -> Path:
    """Return path to .knowledge_graph_foundry/migrations/."""
    return config_dir(root) / "migrations"

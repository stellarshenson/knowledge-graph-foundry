"""Shared test fixtures for kg-builder-cli."""
from __future__ import annotations

from pathlib import Path

import pytest

from knowledge_graph_foundry.types.extraction import Entity

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CASSETTES_DIR = FIXTURES_DIR / "llm_cassettes"


@pytest.fixture
def cassette_dir() -> Path:
    """Path to the llm_cassettes fixture directory."""
    return CASSETTES_DIR


def load_cassette(name: str):
    """Load a cassette by name (without .json extension) and return a ReplayClient."""
    from tests.llm_cassette import ReplayClient

    path = CASSETTES_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Cassette not found: {path}")
    return ReplayClient.from_cassette_file(path)


@pytest.fixture
def sample_entities() -> list[Entity]:
    """Six entities across Person/Organization/Product types."""
    return [
        Entity(id="product_resmart_cpap", name="RESmart CPAP", type="Product",
               description="CPAP device by BMC Medical", source_chunks=["a1b2c3d4e5f6"],
               confidence=0.95),
        Entity(id="org_bmc_medical", name="BMC Medical", type="Organization",
               description="Medical device manufacturer", source_chunks=["b2c3d4e5f6a1"],
               confidence=0.9),
        Entity(id="spec_pressure_range", name="Pressure Range", type="Specification",
               description="4-20 cmH2O", properties={"min": 4, "max": 20, "unit": "cmH2O"},
               source_chunks=["a1b2c3d4e5f6"], confidence=0.92),
        Entity(id="feature_epr", name="EPR Technology", type="Feature",
               description="Expiratory Pressure Relief", source_chunks=["a1b2c3d4e5f6"],
               confidence=0.88),
        Entity(id="product_auto_cpap", name="RESmart Auto CPAP", type="Product",
               description="Auto-titrating CPAP", source_chunks=["c3d4e5f6a1b2"],
               confidence=0.93),
        Entity(id="feature_smartflex", name="SmartFlex", type="Feature",
               description="Pressure relief technology", source_chunks=["c3d4e5f6a1b2"],
               confidence=0.85),
    ]

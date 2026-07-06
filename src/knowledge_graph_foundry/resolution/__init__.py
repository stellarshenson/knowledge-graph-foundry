"""Entity resolution: Bayesian multi-signal merging, decoupled from type."""

from knowledge_graph_foundry.resolution.bayesian import evidence
from knowledge_graph_foundry.resolution.calibration import PosteriorCalibrator
from knowledge_graph_foundry.resolution.resolver import (
    ResolutionResult,
    remap_relationships,
    resolve_entities,
)

__all__ = [
    "PosteriorCalibrator",
    "ResolutionResult",
    "evidence",
    "remap_relationships",
    "resolve_entities",
]

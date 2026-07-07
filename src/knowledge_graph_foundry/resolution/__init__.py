"""Entity resolution: Bayesian multi-signal merging, decoupled from type."""

from knowledge_graph_foundry.resolution.bayesian import evidence
from knowledge_graph_foundry.resolution.blocking import ann_candidates
from knowledge_graph_foundry.resolution.calibration import (
    PosteriorCalibrator,
    TemperatureScaler,
)
from knowledge_graph_foundry.resolution.identity_stack import V2IdentityStack
from knowledge_graph_foundry.resolution.judge import MatchVerdict, judge_pair
from knowledge_graph_foundry.resolution.resolver import (
    ResolutionResult,
    remap_relationships,
    resolve_entities,
)

__all__ = [
    "MatchVerdict",
    "PosteriorCalibrator",
    "ResolutionResult",
    "TemperatureScaler",
    "V2IdentityStack",
    "ann_candidates",
    "evidence",
    "judge_pair",
    "remap_relationships",
    "resolve_entities",
]

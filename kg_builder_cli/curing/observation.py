"""Per-resolution observation collection for calibration ground truth.

Records every resolution decision as a structured observation during a run.
At curing time, derives ground truth from type clustering outcomes and
aggregates into KGFTypeCalibration nodes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math

from loguru import logger


@dataclass
class CrossTypeObservation:
    """Single cross-type resolution decision."""

    norm_name: str
    type_a: str
    type_b: str
    raw_posterior: float
    prior: float
    lr_desc: float
    lr_emb: float
    lr_cooc: float
    action: str  # "merged", "blocked", "deferred"
    doc_index: int
    has_hierarchy: bool
    sibling: bool


@dataclass
class TypeAssignmentObservation:
    """Single Bayesian type resolution decision."""

    entity_name: str
    type_before: str
    type_after: str
    posterior: dict[str, float]
    entropy: float
    was_remapped: bool
    escalated_to_llm: bool
    doc_index: int


@dataclass
class ObservationCollector:
    """Collects resolution observations during a run for post-hoc calibration."""

    _cross_type: list[CrossTypeObservation] = field(default_factory=list)
    _type_assignment: list[TypeAssignmentObservation] = field(default_factory=list)

    def record_cross_type(self, obs: CrossTypeObservation) -> None:
        """Record a cross-type resolution observation."""
        self._cross_type.append(obs)

    def record_type_assignment(self, obs: TypeAssignmentObservation) -> None:
        """Record a type assignment observation."""
        self._type_assignment.append(obs)

    @property
    def cross_type_count(self) -> int:
        return len(self._cross_type)

    @property
    def type_assignment_count(self) -> int:
        return len(self._type_assignment)

    def derive_ground_truth(self, type_mapping: dict[str, str]) -> list[tuple[float, bool]]:
        """Derive (raw_posterior, was_correct) pairs from type clustering ground truth.

        was_correct = True if the resolution action aligned with clustering outcome:
        - merged pair where both types mapped to same cluster -> correct merge
        - blocked pair where types mapped to different clusters -> correct block
        - merged pair where types mapped to different clusters -> incorrect merge
        - blocked pair where types mapped to same cluster -> incorrect block
        """
        pairs: list[tuple[float, bool]] = []

        for obs in self._cross_type:
            # Map both types through the clustering
            canonical_a = type_mapping.get(obs.type_a, obs.type_a)
            canonical_b = type_mapping.get(obs.type_b, obs.type_b)
            same_cluster = canonical_a == canonical_b

            if obs.action in ("merged", "hierarchy_merge", "multi_facet"):
                # Merge action: correct if types belong to same cluster
                pairs.append((obs.raw_posterior, same_cluster))
            elif obs.action == "blocked":
                # Block action: correct if types belong to different clusters
                pairs.append((obs.raw_posterior, not same_cluster))
            # "deferred" actions are excluded - no definitive ground truth

        return pairs

    def derive_type_assignment_truth(
        self, type_mapping: dict[str, str]
    ) -> list[tuple[float, bool]]:
        """Derive (max_posterior, was_correct) pairs for type assignment.

        was_correct = True if the assigned type maps to the same canonical
        as the entity's eventual final type after clustering.
        """
        pairs: list[tuple[float, bool]] = []

        for obs in self._type_assignment:
            if not obs.posterior:
                continue
            max_prob = max(obs.posterior.values())
            canonical_assigned = type_mapping.get(obs.type_after, obs.type_after)
            # The entity's type_after is what was assigned; check if it survived clustering
            was_correct = canonical_assigned == type_mapping.get(obs.type_after, obs.type_after)
            pairs.append((max_prob, was_correct))

        return pairs

    def aggregate_calibration(self) -> dict[str, dict]:
        """Aggregate observations into per-type calibration data.

        Returns {type_name: {mean_posterior, observation_count, remap_count}}
        to persist in KGFTypeCalibration nodes.
        """
        type_stats: dict[str, dict] = {}

        # Aggregate cross-type observations by type
        for obs in self._cross_type:
            for t in (obs.type_a, obs.type_b):
                if t not in type_stats:
                    type_stats[t] = {
                        "posterior_sum": 0.0,
                        "observation_count": 0,
                        "remap_count": 0,
                    }
                type_stats[t]["posterior_sum"] += obs.raw_posterior
                type_stats[t]["observation_count"] += 1

        # Aggregate type assignment observations
        for obs in self._type_assignment:
            t = obs.type_after
            if t not in type_stats:
                type_stats[t] = {
                    "posterior_sum": 0.0,
                    "observation_count": 0,
                    "remap_count": 0,
                }
            max_prob = max(obs.posterior.values()) if obs.posterior else 0.0
            type_stats[t]["posterior_sum"] += max_prob
            type_stats[t]["observation_count"] += 1
            if obs.was_remapped:
                type_stats[t]["remap_count"] += 1

        # Compute means
        result: dict[str, dict] = {}
        for type_name, stats in type_stats.items():
            count = stats["observation_count"]
            result[type_name] = {
                "mean_posterior": stats["posterior_sum"] / count if count > 0 else 0.0,
                "observation_count": count,
                "remap_count": stats["remap_count"],
            }

        if result:
            logger.info(
                "observation aggregation: {} types, {} cross-type obs, {} assignment obs",
                len(result),
                len(self._cross_type),
                len(self._type_assignment),
            )

        return result

    def compute_type_correctness_rates(self, type_mapping: dict[str, str]) -> dict[str, float]:
        """Compute per-type correctness rate from cross-type ground truth.

        For each type, counts how many resolution decisions involving that type
        were correct vs total, returning the accuracy rate.
        """
        type_correct: dict[str, int] = {}
        type_total: dict[str, int] = {}

        for obs in self._cross_type:
            canonical_a = type_mapping.get(obs.type_a, obs.type_a)
            canonical_b = type_mapping.get(obs.type_b, obs.type_b)
            same_cluster = canonical_a == canonical_b

            if obs.action == "deferred":
                continue

            was_correct = (
                same_cluster
                if obs.action in ("merged", "hierarchy_merge", "multi_facet")
                else not same_cluster
            )

            for t in (obs.type_a, obs.type_b):
                type_total[t] = type_total.get(t, 0) + 1
                if was_correct:
                    type_correct[t] = type_correct.get(t, 0) + 1

        return {t: type_correct.get(t, 0) / type_total[t] for t in type_total if type_total[t] > 0}


def _rank(values: list[float]) -> list[float]:
    """Assign average ranks to values (1-based, handles ties)."""
    indexed = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j + 1) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank
        i = j
    return ranks


def compute_spearman_correlations(
    type_metrics: dict[str, dict[str, float]],
    correctness_rates: dict[str, float],
) -> dict[str, float]:
    """Compute Spearman rank correlation between each metric and correctness rate.

    Returns {metric_name: spearman_rho}. Metrics with fewer than 5 valid
    data points are excluded.
    """
    _MIN_TYPES = 5
    common_types = sorted(set(type_metrics.keys()) & set(correctness_rates.keys()))
    if len(common_types) < _MIN_TYPES:
        return {}

    # Get metric names from first type
    metric_names = list(next(iter(type_metrics.values())).keys())

    correlations: dict[str, float] = {}
    for metric in metric_names:
        x_vals = [type_metrics[t].get(metric, float("nan")) for t in common_types]
        # Filter NaN pairs - keep aligned indices
        valid_idx = [i for i, x in enumerate(x_vals) if not math.isnan(x)]
        if len(valid_idx) < _MIN_TYPES:
            continue
        x_filtered = [x_vals[i] for i in valid_idx]
        y_filtered = [correctness_rates[common_types[i]] for i in valid_idx]
        x_ranks = _rank(x_filtered)
        y_ranks = _rank(y_filtered)
        n = len(x_ranks)
        d_sq_sum = sum((xr - yr) ** 2 for xr, yr in zip(x_ranks, y_ranks))
        rho = 1.0 - (6.0 * d_sq_sum) / (n * (n**2 - 1))
        correlations[metric] = round(rho, 4)

    return correlations

"""Information-theoretic stability metrics for schema curing."""

from __future__ import annotations

import math


class StabilityMetrics:
    """Computes information-theoretic metrics from type frequency distributions.

    Purely computational - does not make curing decisions. Tracks metric history
    for post-hoc analysis of which metrics best predict schema stabilization.
    """

    def __init__(self, variance_window: int = 5):
        self._variance_window = variance_window
        self._history: list[dict[str, float]] = []
        self._prev_probs: list[float] | None = None
        self._type_counts_history: list[int] = []
        self._total_occurrences_history: list[int] = []

    def record(self, frequencies: dict[str, int]) -> dict[str, float]:
        """Compute all metrics from current type frequencies, append to history.

        Args:
            frequencies: mapping of type name to occurrence count.

        Returns:
            Flat dict of metric_name -> value. Returns empty dict if frequencies
            is empty.
        """
        if not frequencies:
            return {}

        counts = list(frequencies.values())
        total = sum(counts)
        probs = [c / total for c in counts]
        n_types = len(counts)

        self._type_counts_history.append(n_types)
        self._total_occurrences_history.append(total)

        metrics: dict[str, float] = {}

        # Core distribution stats
        metrics["unique_types"] = float(n_types)
        metrics["total_occurrences"] = float(total)
        metrics["singletons"] = float(sum(1 for c in counts if c == 1))
        metrics["doubletons"] = float(sum(1 for c in counts if c == 2))

        # Shannon entropy
        entropy = self._shannon_entropy(probs)
        metrics["entropy_shannon"] = entropy
        if self._history:
            prev_entropy = self._history[-1].get("entropy_shannon", entropy)
            metrics["entropy_shannon_delta"] = abs(entropy - prev_entropy)
        else:
            metrics["entropy_shannon_delta"] = float("nan")

        # Divergence metrics (require previous distribution)
        if self._prev_probs is not None:
            metrics["kl_divergence"] = self._kl_divergence(self._prev_probs, probs)
            metrics["js_divergence"] = self._js_divergence(self._prev_probs, probs)
        else:
            metrics["kl_divergence"] = float("nan")
            metrics["js_divergence"] = float("nan")

        # Type accumulation rate
        metrics["type_accumulation_rate"] = self._type_accumulation_rate()

        # Gini coefficient
        metrics["gini_coefficient"] = self._gini_coefficient(counts)

        # Zipf R-squared
        metrics["zipf_r_squared"] = self._zipf_r_squared(counts)

        # Heaps' beta
        metrics["heaps_beta"] = self._heaps_beta()

        # Chao1 and ACE
        singletons = int(metrics["singletons"])
        doubletons = int(metrics["doubletons"])
        chao1_est = self._chao1(n_types, singletons, doubletons)
        metrics["chao1_estimate"] = chao1_est
        metrics["chao1_coverage"] = n_types / chao1_est if chao1_est > 0 else 1.0

        metrics["ace_estimate"] = self._ace(counts, n_types)

        # Rolling variance for key metrics
        self._history.append(metrics)
        self._prev_probs = probs

        # Compute rolling variances after appending to history
        for key in ("entropy_shannon", "js_divergence", "gini_coefficient", "chao1_coverage"):
            var_key = f"{key}_var"
            metrics[var_key] = self._rolling_variance(key)

        # Update the stored entry with variance values
        self._history[-1] = dict(metrics)

        # Emit stability metrics signal
        from kg_builder_cli.events import signals as evt_signals
        from kg_builder_cli.events import types as etypes

        evt_signals.stability_metrics_recorded.send(
            evt_signals.stability_metrics_recorded,
            event=etypes.StabilityMetricsRecorded(
                doc_index=len(self._history) - 1,
                entity_count=int(metrics.get("total_occurrences", 0)),
                type_count=int(metrics.get("unique_types", 0)),
                entropy_shannon=metrics.get("entropy_shannon", 0.0),
                entropy_shannon_delta=metrics.get("entropy_shannon_delta", 0.0),
                kl_divergence=metrics.get("kl_divergence", 0.0),
                js_divergence=metrics.get("js_divergence", 0.0),
                type_accumulation_rate=metrics.get("type_accumulation_rate", 0.0),
                gini_coefficient=metrics.get("gini_coefficient", 0.0),
                zipf_r_squared=metrics.get("zipf_r_squared", 0.0),
                heaps_beta=metrics.get("heaps_beta", 0.0),
                chao1_estimate=metrics.get("chao1_estimate", 0.0),
                chao1_coverage=metrics.get("chao1_coverage", 0.0),
                ace_estimate=metrics.get("ace_estimate", 0.0),
                rolling_jsd_var=metrics.get("js_divergence_var", 0.0),
                rolling_entropy_var=metrics.get("entropy_shannon_var", 0.0),
            ),
        )

        # Emit periodic full-state snapshot every 5 documents
        if len(self._history) % 5 == 0:
            evt_signals.stability_snapshot.send(
                evt_signals.stability_snapshot,
                event=etypes.StabilitySnapshot(
                    doc_index=len(self._history) - 1,
                    metrics_summary=dict(metrics),
                ),
            )

        return dict(metrics)

    def to_dict(self) -> dict:
        """Serialize metrics state for cross-run persistence."""
        return {
            "variance_window": self._variance_window,
            "history": self._history,
            "prev_probs": self._prev_probs,
            "type_counts_history": self._type_counts_history,
            "total_occurrences_history": self._total_occurrences_history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> StabilityMetrics:
        """Restore metrics from serialized state."""
        m = cls(variance_window=data.get("variance_window", 5))
        m._history = data.get("history", [])
        m._prev_probs = data.get("prev_probs")
        m._type_counts_history = data.get("type_counts_history", [])
        m._total_occurrences_history = data.get("total_occurrences_history", [])
        return m

    def history(self) -> list[dict[str, float]]:
        """Return full metric history for post-hoc analysis."""
        return list(self._history)

    def latest(self) -> dict[str, float] | None:
        """Return most recent metrics, or None if no records."""
        return dict(self._history[-1]) if self._history else None

    # --- Private metric implementations ---

    @staticmethod
    def _shannon_entropy(probs: list[float]) -> float:
        """H(P) = -sum(p * log2(p)) for p > 0."""
        return -sum(p * math.log2(p) for p in probs if p > 0)

    @staticmethod
    def _kl_divergence(p: list[float], q: list[float]) -> float:
        """KL(P || Q) with additive smoothing to avoid division by zero.

        When distributions have different lengths, the shorter one is padded
        with zeros (then smoothed).
        """
        max_len = max(len(p), len(q))
        # Pad shorter distribution
        p_padded = list(p) + [0.0] * (max_len - len(p))
        q_padded = list(q) + [0.0] * (max_len - len(q))

        # Additive smoothing (Laplace)
        eps = 1e-10
        p_smooth = [pi + eps for pi in p_padded]
        q_smooth = [qi + eps for qi in q_padded]
        p_total = sum(p_smooth)
        q_total = sum(q_smooth)
        p_norm = [pi / p_total for pi in p_smooth]
        q_norm = [qi / q_total for qi in q_smooth]

        return sum(pi * math.log2(pi / qi) for pi, qi in zip(p_norm, q_norm))

    @classmethod
    def _js_divergence(cls, p: list[float], q: list[float]) -> float:
        """Jensen-Shannon divergence: JSD(P || Q) = 0.5*KL(P||M) + 0.5*KL(Q||M).

        Symmetric, bounded [0, 1] when using log2.
        """
        max_len = max(len(p), len(q))
        p_padded = list(p) + [0.0] * (max_len - len(p))
        q_padded = list(q) + [0.0] * (max_len - len(q))

        # Renormalize after padding
        p_sum = sum(p_padded) or 1.0
        q_sum = sum(q_padded) or 1.0
        p_norm = [pi / p_sum for pi in p_padded]
        q_norm = [qi / q_sum for qi in q_padded]

        m = [(pi + qi) / 2 for pi, qi in zip(p_norm, q_norm)]
        return 0.5 * cls._kl_divergence(p_norm, m) + 0.5 * cls._kl_divergence(q_norm, m)

    def _type_accumulation_rate(self) -> float:
        """New types per document (dV/dN). 0 if first document."""
        if len(self._type_counts_history) < 2:
            return float(self._type_counts_history[-1]) if self._type_counts_history else 0.0
        return float(self._type_counts_history[-1] - self._type_counts_history[-2])

    @staticmethod
    def _gini_coefficient(counts: list[int]) -> float:
        """Gini coefficient from frequency counts. 0 = perfectly equal, 1 = maximally unequal."""
        n = len(counts)
        if n == 0:
            return 0.0
        sorted_counts = sorted(counts)
        total = sum(sorted_counts)
        if total == 0:
            return 0.0
        cumulative = 0.0
        weighted_sum = 0.0
        for i, c in enumerate(sorted_counts):
            cumulative += c
            weighted_sum += (2 * (i + 1) - n - 1) * c
        return weighted_sum / (n * total)

    @staticmethod
    def _zipf_r_squared(counts: list[int]) -> float:
        """R-squared of log(rank) vs log(frequency) linear fit.

        Requires >= 3 types with frequency > 0. Returns nan otherwise.
        """
        positive = sorted([c for c in counts if c > 0], reverse=True)
        if len(positive) < 3:
            return float("nan")

        n = len(positive)
        log_ranks = [math.log(i + 1) for i in range(n)]
        log_freqs = [math.log(f) for f in positive]

        # Linear regression: log_freq = a + b * log_rank
        sum_x = sum(log_ranks)
        sum_y = sum(log_freqs)
        sum_xy = sum(x * y for x, y in zip(log_ranks, log_freqs))
        sum_x2 = sum(x * x for x in log_ranks)

        mean_x = sum_x / n
        mean_y = sum_y / n

        ss_xx = sum_x2 - n * mean_x * mean_x
        ss_xy = sum_xy - n * mean_x * mean_y

        if ss_xx == 0:
            return float("nan")

        b = ss_xy / ss_xx
        a = mean_y - b * mean_x

        # R-squared
        ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(log_ranks, log_freqs))
        ss_tot = sum((y - mean_y) ** 2 for y in log_freqs)

        if ss_tot == 0:
            return 1.0  # All values identical
        return 1.0 - ss_res / ss_tot

    def _heaps_beta(self) -> float:
        """Heaps' law exponent: V = K * N^beta.

        Estimated as slope of log(V) vs log(N) over history.
        Requires >= 3 data points. Returns nan otherwise.
        """
        if len(self._type_counts_history) < 3:
            return float("nan")

        # Use all history points
        points = [
            (n_total, n_types)
            for n_total, n_types in zip(
                self._total_occurrences_history,
                self._type_counts_history,
            )
            if n_total > 0 and n_types > 0
        ]
        if len(points) < 3:
            return float("nan")

        log_n = [math.log(p[0]) for p in points]
        log_v = [math.log(p[1]) for p in points]

        n = len(points)
        sum_x = sum(log_n)
        sum_y = sum(log_v)
        sum_xy = sum(x * y for x, y in zip(log_n, log_v))
        sum_x2 = sum(x * x for x in log_n)

        mean_x = sum_x / n
        ss_xx = sum_x2 - n * mean_x * mean_x

        if ss_xx == 0:
            return 0.0

        mean_y = sum_y / n
        ss_xy = sum_xy - n * mean_x * mean_y
        return ss_xy / ss_xx

    @staticmethod
    def _chao1(observed: int, singletons: int, doubletons: int) -> float:
        """Chao1 species richness estimator.

        Uses bias-corrected form when doubletons == 0.
        """
        if singletons == 0:
            return float(observed)
        if doubletons == 0:
            # Bias-corrected form
            return observed + singletons * (singletons - 1) / 2
        return observed + (singletons * singletons) / (2 * doubletons)

    @staticmethod
    def _ace(counts: list[int], observed: int) -> float:
        """Abundance-based Coverage Estimator (ACE).

        Rare species threshold k=10. If no rare species, returns observed count.
        """
        rare_threshold = 10
        rare = [c for c in counts if 0 < c <= rare_threshold]
        abundant = [c for c in counts if c > rare_threshold]

        s_rare = len(rare)
        s_abund = len(abundant)

        if s_rare == 0:
            return float(observed)

        n_rare = sum(rare)
        singletons = sum(1 for c in rare if c == 1)

        if n_rare == 0:
            return float(observed)

        c_ace = 1.0 - singletons / n_rare
        if c_ace == 0:
            return float(observed)

        # Coefficient of variation squared
        gamma_sq = max(
            (s_rare / c_ace)
            * sum(
                i * (i - 1) * sum(1 for c in rare if c == i) for i in range(1, rare_threshold + 1)
            )
            / (n_rare * (n_rare - 1))
            - 1.0,
            0.0,
        )

        return s_abund + s_rare / c_ace + (singletons / c_ace) * gamma_sq

    def _rolling_variance(self, key: str) -> float:
        """Variance of a metric over the last W entries in history."""
        w = self._variance_window
        values = [h[key] for h in self._history[-w:] if key in h and not math.isnan(h[key])]
        if len(values) < 2:
            return float("nan")
        mean = sum(values) / len(values)
        return sum((v - mean) ** 2 for v in values) / len(values)

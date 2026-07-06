"""Calibration of Bayesian posteriors.

Two calibrators. TemperatureScaler is the R7/SOTA-preferred method: a single
parameter fit on a held-out set, robust with few labels and cheap to persist.
PosteriorCalibrator (isotonic) is retained for large label sets but gated -
isotonic is non-parametric and overfits on tiny collected-pair sets (v1 fit a
2-knot curve on 25 noisy pairs). Below the label floor, calibrate nothing and
use a fixed documented threshold instead.
"""

from __future__ import annotations

import json
import math
from typing import Optional

from loguru import logger


class PosteriorCalibrator:
    def __init__(self, x_points: list[float], y_points: list[float]):
        self._x = x_points
        self._y = y_points

    def calibrate(self, raw_posterior: float) -> float:
        """Map raw posterior to calibrated probability via linear interpolation."""
        if not self._x or not self._y:
            return raw_posterior
        if raw_posterior <= self._x[0]:
            return self._y[0]
        if raw_posterior >= self._x[-1]:
            return self._y[-1]
        lo, hi = 0, len(self._x) - 1
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if self._x[mid] <= raw_posterior:
                lo = mid
            else:
                hi = mid
        x0, x1 = self._x[lo], self._x[hi]
        y0, y1 = self._y[lo], self._y[hi]
        if x1 == x0:
            return y0
        t = (raw_posterior - x0) / (x1 - x0)
        return y0 + t * (y1 - y0)

    @classmethod
    def fit(
        cls,
        raw_posteriors: list[float],
        labels: list[bool],
        min_observations: int = 50,
    ) -> Optional["PosteriorCalibrator"]:
        if len(raw_posteriors) < min_observations:
            logger.debug(
                "calibration skipped: {} samples < {} minimum",
                len(raw_posteriors),
                min_observations,
            )
            return None
        from sklearn.isotonic import IsotonicRegression

        iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
        iso.fit(raw_posteriors, [1.0 if v else 0.0 for v in labels])
        return cls(iso.X_thresholds_.tolist(), iso.y_thresholds_.tolist())

    def to_json(self) -> str:
        return json.dumps({"kind": "isotonic", "x": self._x, "y": self._y})

    @classmethod
    def from_json(cls, data: str) -> "PosteriorCalibrator":
        parsed = json.loads(data)
        return cls(parsed["x"], parsed["y"])


def _clip(p: float, eps: float = 1e-6) -> float:
    return min(1.0 - eps, max(eps, p))


class TemperatureScaler:
    """Single-parameter calibrator: p_cal = sigmoid(logit(p) / T).

    Preferred over isotonic for few labels (R7) - one parameter cannot overfit
    a small held-out set the way a non-parametric curve does. T is found by a
    deterministic coarse-to-fine search minimizing held-out log-loss.
    """

    def __init__(self, temperature: float):
        self.temperature = temperature

    def calibrate(self, raw_posterior: float) -> float:
        logit = math.log(_clip(raw_posterior) / (1.0 - _clip(raw_posterior)))
        return 1.0 / (1.0 + math.exp(-logit / self.temperature))

    @staticmethod
    def _log_loss(temperature: float, posteriors: list[float], labels: list[bool]) -> float:
        scaler = TemperatureScaler(temperature)
        loss = 0.0
        for p, y in zip(posteriors, labels):
            c = _clip(scaler.calibrate(p))
            loss -= math.log(c) if y else math.log(1.0 - c)
        return loss / len(posteriors)

    @classmethod
    def fit(
        cls,
        posteriors: list[float],
        labels: list[bool],
        min_labels: int = 100,
    ) -> Optional["TemperatureScaler"]:
        """Fit T on a held-out set. Returns None below min_labels - the caller
        then uses a fixed documented threshold rather than any learned curve."""
        if len(posteriors) < min_labels:
            logger.debug("temperature scaling skipped: {} < {}", len(posteriors), min_labels)
            return None
        best_t, best_loss = 1.0, float("inf")
        grid = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0]
        for t in grid:
            loss = cls._log_loss(t, posteriors, labels)
            if loss < best_loss:
                best_loss, best_t = loss, t
        # fine search around the best coarse point
        for delta in (-0.2, -0.1, 0.1, 0.2):
            t = round(best_t + delta, 3)
            if t <= 0:
                continue
            loss = cls._log_loss(t, posteriors, labels)
            if loss < best_loss:
                best_loss, best_t = loss, t
        return cls(best_t)

    def to_json(self) -> str:
        return json.dumps({"kind": "temperature", "temperature": self.temperature})

    @classmethod
    def from_json(cls, data: str) -> "TemperatureScaler":
        return cls(json.loads(data)["temperature"])

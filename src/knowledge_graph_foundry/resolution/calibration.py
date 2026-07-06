"""Isotonic calibration of Bayesian posteriors.

Fits sklearn IsotonicRegression on (raw_posterior, was_correct) observations
and applies the curve by linear interpolation. The fitted curve persists to
the graph metanode as JSON. Ported from v1 (mechanism validated; needs
>= min_observations to fit).
"""

from __future__ import annotations

import json
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
        return json.dumps({"x": self._x, "y": self._y})

    @classmethod
    def from_json(cls, data: str) -> "PosteriorCalibrator":
        parsed = json.loads(data)
        return cls(parsed["x"], parsed["y"])

"""Isotonic calibration for Bayesian posteriors.

Fits sklearn.isotonic.IsotonicRegression on (raw_posterior, was_correct)
pairs collected during a run. Persists the calibration curve and applies
it on subsequent runs to produce calibrated probabilities.
"""

from __future__ import annotations

import json

from loguru import logger


class PosteriorCalibrator:
    """Apply isotonic calibration to raw posteriors."""

    _MIN_SAMPLES = 20

    def __init__(self, x_points: list[float], y_points: list[float]):
        """Initialize from persisted calibration curve."""
        self._x = x_points
        self._y = y_points

    def calibrate(self, raw_posterior: float) -> float:
        """Map raw posterior to calibrated probability via linear interpolation."""
        if not self._x or not self._y:
            return raw_posterior

        # Clamp to observed range
        if raw_posterior <= self._x[0]:
            return self._y[0]
        if raw_posterior >= self._x[-1]:
            return self._y[-1]

        # Binary search for interpolation bracket
        lo, hi = 0, len(self._x) - 1
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if self._x[mid] <= raw_posterior:
                lo = mid
            else:
                hi = mid

        # Linear interpolation
        x0, x1 = self._x[lo], self._x[hi]
        y0, y1 = self._y[lo], self._y[hi]
        if x1 == x0:
            return y0
        t = (raw_posterior - x0) / (x1 - x0)
        return y0 + t * (y1 - y0)

    @classmethod
    def fit(cls, raw_posteriors: list[float], labels: list[bool]) -> PosteriorCalibrator | None:
        """Fit isotonic regression from observation data.

        Returns None if insufficient data or sklearn unavailable.
        """
        if len(raw_posteriors) < cls._MIN_SAMPLES:
            logger.info(
                "calibration skipped: {} samples < {} minimum",
                len(raw_posteriors),
                cls._MIN_SAMPLES,
            )
            return None

        try:
            from sklearn.isotonic import IsotonicRegression
        except ImportError:
            logger.warning("sklearn not available, calibration skipped")
            return None

        y_true = [1.0 if label else 0.0 for label in labels]
        iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
        iso.fit(raw_posteriors, y_true)

        # Extract the fitted curve points
        x_points = iso.X_thresholds_.tolist()
        y_points = iso.y_thresholds_.tolist()

        logger.info(
            "calibration fitted: {} samples -> {} curve points",
            len(raw_posteriors),
            len(x_points),
        )
        return cls(x_points, y_points)

    def to_points(self) -> tuple[list[float], list[float]]:
        """Export (x_points, y_points) for persistence."""
        return list(self._x), list(self._y)

    @property
    def n_samples(self) -> int:
        """Number of curve points."""
        return len(self._x)

    def to_json(self) -> str:
        """Serialize curve to JSON string."""
        return json.dumps({"x": self._x, "y": self._y})

    @classmethod
    def from_json(cls, data: str) -> PosteriorCalibrator:
        """Deserialize from JSON string."""
        parsed = json.loads(data)
        return cls(parsed["x"], parsed["y"])

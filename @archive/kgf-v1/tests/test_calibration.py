"""Tests for PosteriorCalibrator isotonic calibration."""

import pytest

from knowledge_graph_foundry.curing.calibration import PosteriorCalibrator


class TestCalibrate:
    def test_identity_mapping(self):
        """Simple two-point curve that maps identity."""
        cal = PosteriorCalibrator([0.0, 1.0], [0.0, 1.0])
        assert cal.calibrate(0.5) == pytest.approx(0.5)
        assert cal.calibrate(0.0) == pytest.approx(0.0)
        assert cal.calibrate(1.0) == pytest.approx(1.0)

    def test_interpolation(self):
        """Linear interpolation between points."""
        cal = PosteriorCalibrator([0.0, 0.5, 1.0], [0.0, 0.8, 1.0])
        # Between 0.0 and 0.5: maps to 0.0-0.8 linearly
        assert cal.calibrate(0.25) == pytest.approx(0.4)
        # Between 0.5 and 1.0: maps to 0.8-1.0 linearly
        assert cal.calibrate(0.75) == pytest.approx(0.9)

    def test_clamp_below_range(self):
        """Values below range clamp to first y value."""
        cal = PosteriorCalibrator([0.2, 0.8], [0.1, 0.9])
        assert cal.calibrate(0.0) == pytest.approx(0.1)

    def test_clamp_above_range(self):
        """Values above range clamp to last y value."""
        cal = PosteriorCalibrator([0.2, 0.8], [0.1, 0.9])
        assert cal.calibrate(1.0) == pytest.approx(0.9)

    def test_monotonic_output(self):
        """Output should be monotonically non-decreasing for increasing input."""
        cal = PosteriorCalibrator([0.0, 0.3, 0.6, 1.0], [0.0, 0.5, 0.7, 1.0])
        prev = -1.0
        for x in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
            y = cal.calibrate(x)
            assert y >= prev, f"Not monotonic at x={x}: {y} < {prev}"
            prev = y


class TestFit:
    def test_insufficient_samples(self):
        """Fit returns None with too few samples."""
        result = PosteriorCalibrator.fit([0.5] * 10, [True] * 10)
        assert result is None

    def test_fit_returns_calibrator(self):
        """Fit with enough data returns a PosteriorCalibrator."""
        try:
            import sklearn  # noqa: F401
        except ImportError:
            pytest.skip("sklearn not installed")

        # Create synthetic data: low posteriors mostly incorrect, high mostly correct
        raw = [0.1] * 15 + [0.9] * 15
        labels = [False] * 12 + [True] * 3 + [False] * 3 + [True] * 12
        cal = PosteriorCalibrator.fit(raw, labels)
        assert cal is not None
        assert cal.n_samples > 0
        # Low raw should map to lower calibrated
        assert cal.calibrate(0.1) < cal.calibrate(0.9)

    def test_fit_calibrate_roundtrip(self):
        """Fit + calibrate should produce calibrated values."""
        try:
            import sklearn  # noqa: F401
        except ImportError:
            pytest.skip("sklearn not installed")

        raw = [0.2] * 10 + [0.5] * 10 + [0.8] * 10
        labels = [False] * 10 + [True] * 5 + [False] * 5 + [True] * 10
        cal = PosteriorCalibrator.fit(raw, labels)
        assert cal is not None
        # Calibrated values should be between 0 and 1
        for x in [0.1, 0.3, 0.5, 0.7, 0.9]:
            y = cal.calibrate(x)
            assert 0.0 <= y <= 1.0


class TestSerialization:
    def test_to_from_points(self):
        cal = PosteriorCalibrator([0.0, 0.5, 1.0], [0.0, 0.8, 1.0])
        x, y = cal.to_points()
        cal2 = PosteriorCalibrator(x, y)
        assert cal2.calibrate(0.25) == pytest.approx(cal.calibrate(0.25))

    def test_to_from_json(self):
        cal = PosteriorCalibrator([0.0, 0.5, 1.0], [0.0, 0.8, 1.0])
        json_str = cal.to_json()
        cal2 = PosteriorCalibrator.from_json(json_str)
        assert cal2.calibrate(0.25) == pytest.approx(cal.calibrate(0.25))

    def test_n_samples(self):
        cal = PosteriorCalibrator([0.0, 0.5, 1.0], [0.0, 0.8, 1.0])
        assert cal.n_samples == 3

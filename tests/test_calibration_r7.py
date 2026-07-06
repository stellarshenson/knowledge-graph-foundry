"""Tests for R7 calibration hardening: temperature scaling + label floor."""

import random

from knowledge_graph_foundry.resolution.calibration import (
    PosteriorCalibrator,
    TemperatureScaler,
)


class TestLabelFloor:
    def test_temperature_none_below_floor(self):
        assert TemperatureScaler.fit([0.6] * 20, [True] * 20, min_labels=100) is None

    def test_isotonic_none_below_floor(self):
        assert PosteriorCalibrator.fit([0.5] * 20, [True] * 20, min_observations=100) is None


class TestTemperatureScaler:
    def test_identity_temperature_is_near_noop(self):
        s = TemperatureScaler(1.0)
        assert abs(s.calibrate(0.7) - 0.7) < 1e-6

    def test_high_temperature_pulls_toward_half(self):
        s = TemperatureScaler(5.0)
        assert 0.5 < s.calibrate(0.9) < 0.9

    def test_monotone(self):
        s = TemperatureScaler(2.0)
        assert s.calibrate(0.9) > s.calibrate(0.5) > s.calibrate(0.1)

    def test_fit_reduces_logloss_on_overconfident_scores(self):
        """Overconfident posteriors (extreme, but ~50% correct) should fit a
        temperature > 1 that softens them."""
        rng = random.Random(3)
        posteriors, labels = [], []
        for _ in range(300):
            p = rng.choice([0.02, 0.98])
            posteriors.append(p)
            labels.append(rng.random() < 0.5)  # scores uninformative -> need softening
        scaler = TemperatureScaler.fit(posteriors, labels, min_labels=100)
        assert scaler is not None
        assert scaler.temperature > 1.0

    def test_json_roundtrip(self):
        s = TemperatureScaler(2.5)
        restored = TemperatureScaler.from_json(s.to_json())
        assert restored.temperature == 2.5

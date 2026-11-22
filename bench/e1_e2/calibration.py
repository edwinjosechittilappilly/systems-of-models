"""Calibrators fitted only on calibration data, never on test data."""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize_scalar
from sklearn.isotonic import IsotonicRegression


def _probabilities(probabilities):
    p = np.asarray(probabilities, dtype=float)
    if p.ndim != 2 or p.shape[1] < 2 or not np.isfinite(p).all() or np.any(p < 0):
        raise ValueError("Expected finite nonnegative multiclass probabilities")
    sums = p.sum(axis=1, keepdims=True)
    if np.any(sums <= 0):
        raise ValueError("Each probability vector must have positive mass")
    return p / sums


def apply_temperature(probabilities, temperature):
    if not np.isfinite(temperature) or temperature <= 0:
        raise ValueError("Temperature must be positive")
    p = _probabilities(probabilities)
    logits = np.log(np.clip(p, 1e-12, 1)) / temperature
    logits -= logits.max(axis=1, keepdims=True)
    weights = np.exp(logits)
    return weights / weights.sum(axis=1, keepdims=True)


def fit_temperature(probabilities, labels):
    """Fit a scalar temperature by minimizing calibration multiclass log loss."""
    p = _probabilities(probabilities)
    labels = np.asarray(labels, dtype=int)
    if len(labels) != len(p) or not len(p) or (labels < 0).any() or (labels >= p.shape[1]).any():
        raise ValueError("Labels must correspond to the probability vectors")

    def loss(log_temperature):
        calibrated = apply_temperature(p, np.exp(log_temperature))
        return -np.log(np.clip(calibrated[np.arange(len(p)), labels], 1e-12, 1)).mean()

    result = minimize_scalar(loss, bounds=(-6, 6), method="bounded")
    if not result.success:
        raise RuntimeError("Temperature optimization failed")
    return float(np.exp(result.x))


def fit_isotonic(probabilities, labels):
    """Fit correctness of the originally predicted class as a function of its probability."""
    p = _probabilities(probabilities)
    labels = np.asarray(labels, dtype=int)
    if len(labels) != len(p) or not len(p) or (labels < 0).any() or (labels >= p.shape[1]).any():
        raise ValueError("Labels must correspond to the probability vectors")
    winner = p.argmax(axis=1)
    return IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(p.max(axis=1), winner == labels)


def apply_isotonic(probabilities, calibrator):
    """Redistribute non-winning mass proportionally; uniform if it was zero.

    Isotonic calibration estimates correctness of the original prediction. It
    can change the winning class, so preserve the original prediction separately
    when computing selective risk or top-label reliability.
    """
    p = _probabilities(probabilities)
    n, k = p.shape
    winner = p.argmax(axis=1)
    old_top = p[np.arange(n), winner]
    new_top = np.asarray(calibrator.predict(old_top), dtype=float)
    remaining = p.copy()
    remaining[np.arange(n), winner] = 0
    remaining_sum = remaining.sum(axis=1, keepdims=True)
    default = np.ones_like(p)
    default[np.arange(n), winner] = 0
    remaining = np.divide(remaining, remaining_sum, out=default / (k - 1), where=remaining_sum > 0)
    remaining *= (1 - new_top)[:, None]
    remaining[np.arange(n), winner] = new_top
    return remaining

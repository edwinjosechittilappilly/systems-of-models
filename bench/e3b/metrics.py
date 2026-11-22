"""Offline metrics for discovery and selective prediction on held-out episodes."""

from __future__ import annotations

from collections.abc import Hashable, Sequence
from math import inf, isfinite, sqrt
from statistics import NormalDist
from typing import Any

import numpy as np


def discovery_metrics(predicted: Sequence[Hashable], gold: Sequence[Hashable]) -> dict[str, float | int]:
    """Compare unique predicted and gold identifiers as sets.

    Returns TP, FP, FN, precision and recall. Empty denominators produce NaN,
    not perfect scores. Duplicate identifiers count only once.
    """
    predicted_set, gold_set = set(predicted), set(gold)
    tp = len(predicted_set & gold_set)
    fp, fn = len(predicted_set - gold_set), len(gold_set - predicted_set)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else float("nan"),
        "recall": tp / (tp + fn) if tp + fn else float("nan"),
    }


def _ranked(confidence: Sequence[float], correct: Sequence[bool]) -> list[tuple[float, bool]]:
    if len(confidence) != len(correct):
        raise ValueError("confidence and correct must have the same length")
    if any(not isfinite(float(c)) or not 0 <= float(c) <= 1 for c in confidence):
        raise ValueError("confidence must contain finite probabilities in [0, 1]")
    return sorted(zip(map(float, confidence), correct, strict=True), key=lambda row: row[0], reverse=True)


def risk_coverage(confidence: Sequence[float], correct: Sequence[bool]) -> tuple[np.ndarray, np.ndarray]:
    """Return coverage and error rate at each attainable confidence threshold.

    Ties are served together, so the result is independent of their input order.
    Coverage uses all supplied examples as its denominator. Empty input gives two
    empty arrays. Refusals must be omitted by the caller or represented separately.
    """
    ranked = _ranked(confidence, correct)
    coverage, risk = [], []
    errors = 0
    for i, (score, hit) in enumerate(ranked):
        errors += not hit
        if i + 1 == len(ranked) or ranked[i + 1][0] != score:
            coverage.append((i + 1) / len(ranked))
            risk.append(errors / (i + 1))
    return np.asarray(coverage, dtype=float), np.asarray(risk, dtype=float)


def aurc(confidence: Sequence[float], correct: Sequence[bool]) -> float:
    """Integrate threshold risk as a right-continuous step function over coverage.

    Each tied group contributes its risk times its coverage increment; empty
    input has undefined AURC (NaN). Lower is better.
    """
    coverage, risk = risk_coverage(confidence, correct)
    if not len(coverage):
        return float("nan")
    return float(np.dot(np.diff(np.r_[0.0, coverage]), risk))


def calibrate_threshold(confidence: Sequence[float], correct: Sequence[bool], *, max_error: float = 0.05) -> float:
    """Choose the highest-coverage threshold with empirical error <= max_error.

    Thresholds serve every example with confidence >= threshold; equal scores
    are indivisible. All thresholds are considered, including after a failing
    prefix. Returns positive infinity if no nonempty group qualifies, including
    empty calibration data. This is an empirical constraint, not a risk bound.
    """
    if not 0 <= max_error <= 1:
        raise ValueError("max_error must be in [0, 1]")
    ranked = _ranked(confidence, correct)
    errors, threshold = 0, inf
    for i, (score, hit) in enumerate(ranked):
        errors += not hit
        if (i + 1 == len(ranked) or ranked[i + 1][0] != score) and errors / (i + 1) <= max_error:
            threshold = score
    return threshold


def wilson(successes: int, n: int, *, alpha: float = 0.05) -> tuple[float, float]:
    """Two-sided Wilson interval for a binomial proportion; n=0 gives NaNs."""
    if not 0 < alpha < 1 or n < 0 or not 0 <= successes <= n:
        raise ValueError("require 0 < alpha < 1 and 0 <= successes <= n")
    if not n:
        return float("nan"), float("nan")
    z = NormalDist().inv_cdf(1 - alpha / 2)
    p = successes / n
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def cluster_bootstrap(
    values: Sequence[float], clusters: Sequence[Hashable], *, resamples: int = 2000, seed: int = 0, alpha: float = 0.05
) -> tuple[float, float]:
    """Percentile CI for the observation-weighted mean, resampling whole clusters.

    Draw the original number of distinct clusters with replacement per replicate,
    retaining all observations in each selected cluster. A fixed seed makes the
    interval reproducible. Empty inputs return NaNs. Values must be finite.
    """
    if len(values) != len(clusters):
        raise ValueError("values and clusters must have the same length")
    if resamples < 1 or not 0 < alpha < 1:
        raise ValueError("require resamples >= 1 and 0 < alpha < 1")
    if any(not isfinite(float(value)) for value in values):
        raise ValueError("values must be finite")
    if not len(values):
        return float("nan"), float("nan")
    grouped: dict[Hashable, list[float]] = {}
    for cluster, value in zip(clusters, values, strict=True):
        grouped.setdefault(cluster, []).append(float(value))
    sums = np.asarray([sum(group) for group in grouped.values()])
    sizes = np.asarray([len(group) for group in grouped.values()])
    rng = np.random.default_rng(seed)
    means = np.empty(resamples)
    for i in range(resamples):
        indices = rng.integers(0, len(sums), size=len(sums))
        means[i] = sums[indices].sum() / sizes[indices].sum()
    low, high = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return float(low), float(high)


def aurc_cluster_bootstrap(
    confidence: Sequence[float],
    correct: Sequence[bool],
    clusters: Sequence[Hashable],
    *,
    resamples: int = 2000,
    seed: int = 0,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Percentile CI for AURC, resampling whole task clusters with replacement.

    Each replicate draws as many clusters as in the input and retains all rows
    from each drawn cluster, including duplicates when a cluster is drawn twice.
    Confidence and correctness follow :func:`aurc`; a fixed seed reproduces the
    interval. Empty inputs yield NaNs. Refusals are omitted by the caller.
    """
    if len(confidence) != len(clusters):
        raise ValueError("confidence, correct and clusters must have the same length")
    _ranked(confidence, correct)
    if resamples < 1 or not 0 < alpha < 1:
        raise ValueError("require resamples >= 1 and 0 < alpha < 1")
    if not len(confidence):
        return float("nan"), float("nan")
    grouped: dict[Hashable, list[int]] = {}
    for i, cluster in enumerate(clusters):
        grouped.setdefault(cluster, []).append(i)
    groups = list(grouped.values())
    rng = np.random.default_rng(seed)
    areas = np.empty(resamples)
    for i in range(resamples):
        selected = rng.integers(0, len(groups), size=len(groups))
        indices = [index for group in selected for index in groups[group]]
        areas[i] = aurc([confidence[index] for index in indices], [correct[index] for index in indices])
    low, high = np.quantile(areas, [alpha / 2, 1 - alpha / 2])
    return float(low), float(high)


def summary_metrics(
    predictions: Sequence[Any | None],
    teacher: Sequence[Any | None],
    gold: Sequence[Any | None],
    clusters: Sequence[Hashable],
    *,
    training_majority: Any | None,
    resamples: int = 2000,
    seed: int = 0,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Summarize coverage, selective teacher/gold accuracy and a majority baseline.

    Inputs are aligned episode-level labels. None means refusal for predictions
    and unavailable reference for teacher/gold. Returns
    ``n``, ``served``, ``coverage``, ``majority_label`` and four accuracy records:
    ``teacher``, ``gold``, ``majority_teacher`` and ``majority_gold``. Each
    record has ``n``, ``correct``, ``accuracy``, ``wilson_ci`` and
    ``cluster_bootstrap_ci``. Coverage counts non-refusals over all episodes.
    Teacher/gold accuracy uses only non-refusals with that reference.
    ``training_majority`` is the label selected on training data, evaluated
    against each available reference on all episodes. Pass None if no training
    label is available. Missing denominators give NaN, and a missing majority
    label gives no baseline.
    """
    n = len(predictions)
    if any(len(seq) != n for seq in (teacher, gold, clusters)):
        raise ValueError("all inputs must have the same length")
    result: dict[str, Any] = {
        "n": n,
        "served": sum(p is not None for p in predictions),
        "coverage": sum(p is not None for p in predictions) / n if n else float("nan"),
        "majority_label": training_majority,
    }
    for name, reference in (("teacher", teacher), ("gold", gold)):
        for prefix, guesses in ((name, predictions), (f"majority_{name}", [training_majority] * n)):
            rows = [
                (guess == label, cluster)
                for guess, label, cluster in zip(guesses, reference, clusters, strict=True)
                if guess is not None and label is not None
            ]
            hits = [int(hit) for hit, _ in rows]
            result[prefix] = {
                "n": len(rows),
                "correct": sum(hits),
                "accuracy": sum(hits) / len(rows) if rows else float("nan"),
                "wilson_ci": wilson(sum(hits), len(rows), alpha=alpha),
                "cluster_bootstrap_ci": cluster_bootstrap(
                    hits, [cluster for _, cluster in rows], resamples=resamples, seed=seed, alpha=alpha
                ),
            }
    return result

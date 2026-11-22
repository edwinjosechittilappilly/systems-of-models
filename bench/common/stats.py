"""Statistics used by every experiment: intervals, paired bootstrap, calibration and selective-prediction metrics."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np
from scipy import stats as _stats

Array = np.ndarray


def wilson(successes: int, n: int, *, alpha: float = 0.05) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return (0.0, 1.0)
    z = _stats.norm.ppf(1 - alpha / 2)
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (float(centre - half), float(centre + half))


def clopper_pearson_upper(errors: int, n: int, *, alpha: float = 0.05) -> float:
    """One-sided exact upper bound on an error rate."""
    if n == 0:
        return 1.0
    if errors >= n:
        return 1.0
    return float(_stats.beta.ppf(1 - alpha, errors + 1, n - errors))


def bootstrap(
    statistic: Callable[[Array], float], n_items: int, *, resamples: int = 2000, seed: int = 0, alpha: float = 0.05
) -> tuple[float, float, float]:
    """Item-level (cluster) bootstrap: ``statistic(indices)`` on the full set and a percentile interval."""
    rng = np.random.default_rng(seed)
    point = statistic(np.arange(n_items))
    draws = np.array([statistic(rng.integers(0, n_items, n_items)) for _ in range(resamples)])
    low, high = np.quantile(draws, [alpha / 2, 1 - alpha / 2])
    return float(point), float(low), float(high)


def paired_difference(a: Sequence[float], b: Sequence[float], **kwargs: float | int) -> tuple[float, float, float]:
    """Mean of ``a - b`` with a bootstrap interval over paired items."""
    a_arr, b_arr = np.asarray(a, float), np.asarray(b, float)
    return bootstrap(lambda idx: float(np.mean(a_arr[idx] - b_arr[idx])), len(a_arr), **kwargs)  # type: ignore[arg-type]


def ece(confidence: Sequence[float], correct: Sequence[bool], *, bins: int = 15) -> float:
    """Expected calibration error with equal-mass bins."""
    conf = np.asarray(confidence, float)
    hit = np.asarray(correct, float)
    order = np.argsort(conf)
    total = 0.0
    for chunk in np.array_split(order, bins):
        if len(chunk):
            total += len(chunk) * abs(conf[chunk].mean() - hit[chunk].mean())
    return total / len(conf)


def brier(probabilities: Array, labels: Sequence[int]) -> float:
    """Multiclass Brier score: mean squared error between the probability vector and the one-hot label."""
    probs = np.asarray(probabilities, float)
    onehot = np.zeros_like(probs)
    onehot[np.arange(len(probs)), np.asarray(labels, int)] = 1.0
    return float(np.mean(np.sum((probs - onehot) ** 2, axis=1)))


def nll(probabilities: Array, labels: Sequence[int], *, floor: float = 1e-6) -> float:
    probs = np.asarray(probabilities, float)
    picked = probs[np.arange(len(probs)), np.asarray(labels, int)]
    return float(-np.mean(np.log(np.clip(picked, floor, 1.0))))


def risk_coverage(signal: Sequence[float], correct: Sequence[bool]) -> tuple[Array, Array]:
    """Coverage and selective risk when serving the most confident items first (ties broken by order)."""
    sig = np.asarray(signal, float)
    err = 1.0 - np.asarray(correct, float)
    order = np.argsort(-sig, kind="stable")
    cumulative = np.cumsum(err[order])
    served = np.arange(1, len(sig) + 1)
    return served / len(sig), cumulative / served


def aurc(signal: Sequence[float], correct: Sequence[bool]) -> float:
    """Area under the risk-coverage curve (lower is better)."""
    coverage, risk = risk_coverage(signal, correct)
    return float(np.trapezoid(risk, coverage))


def auroc(scores: Sequence[float], positives: Sequence[bool]) -> float:
    """Probability a random positive scores above a random negative (ties count half)."""
    s = np.asarray(scores, float)
    p = np.asarray(positives, bool)
    pos, neg = s[p], s[~p]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    ranks = _stats.rankdata(np.concatenate([pos, neg]))
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))

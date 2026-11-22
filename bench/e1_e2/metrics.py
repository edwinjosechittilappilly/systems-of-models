"""Paired, item-level statistics for E1 and E2.

Threshold rule: for each S1 and metric, tau* = the smallest tau on the FULL
calibration split whose S1 selective accuracy among served items (signal >= tau)
is >= A2 - 0.01; if none qualifies, tau* = 1.0 (always escalate). Report
coverage at tau*. Then apply tau* unchanged on test.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from bench.common.stats import aurc, bootstrap


def choose_threshold(signal, correct, teacher_accuracy, grid):
    """Return threshold, calibration coverage, and whether fallback forces escalation."""
    signal = np.asarray(signal, dtype=float)
    correct = np.asarray(correct, dtype=bool)
    for tau in sorted(grid):
        served = np.isfinite(signal) & (signal >= tau)
        if served.any() and correct[served].mean() >= teacher_accuracy - 0.01:
            return float(tau), float(served.mean()), False
    return 1.0, 0.0, True


def choose_joint_threshold(signal, fit_probability, correct, teacher_accuracy):
    """Maximize calibration coverage subject to the original selective-accuracy rule.

    Both thresholds are chosen on calibration, not test. Ties in coverage pick
    the smallest choice threshold, then the smallest fit threshold. Coverage is
    a cost proxy, not an estimate of conditional teacher cost.
    """
    signal = np.asarray(signal, dtype=float)
    fit = np.asarray(fit_probability, dtype=float)
    correct = np.asarray(correct, dtype=bool)
    if not len(signal) or len(signal) != len(fit) or len(signal) != len(correct):
        raise ValueError("Inputs must be nonempty and paired by item")
    valid = np.isfinite(signal) & np.isfinite(fit)
    if not valid.any():
        return 1.0, 1.0, 0.0, True
    choice_values = np.unique(signal[np.isfinite(signal)])
    fit_values = np.unique(fit[np.isfinite(fit)])
    choice_index = np.searchsorted(choice_values, signal[valid])
    fit_index = np.searchsorted(fit_values, fit[valid])
    shape = (len(choice_values), len(fit_values))
    counts = np.zeros(shape, dtype=np.int32)
    hits = np.zeros(shape, dtype=np.int32)
    np.add.at(counts, (choice_index, fit_index), 1)
    np.add.at(hits, (choice_index, fit_index), correct[valid].astype(np.int32))
    counts = counts[::-1, ::-1].cumsum(axis=0, dtype=np.int32).cumsum(axis=1, dtype=np.int32)[::-1, ::-1]
    hits = hits[::-1, ::-1].cumsum(axis=0, dtype=np.int32).cumsum(axis=1, dtype=np.int32)[::-1, ::-1]
    eligible = (counts > 0) & (hits >= (teacher_accuracy - 0.01) * counts)
    if not eligible.any():
        return 1.0, 1.0, 0.0, True
    best_count = int(np.max(counts, where=eligible, initial=0))
    choice_i, fit_i = np.argwhere(eligible & (counts == best_count))[0]
    return float(choice_values[choice_i]), float(fit_values[fit_i]), best_count / len(signal), False


def cascade_sweep(
    signal,
    s1_correct,
    s2_correct,
    s1_cost,
    s2_cost,
    s1_latency,
    s2_latency,
    grid,
    *,
    fit_probability=None,
    fit_threshold=0.0,
):
    """Calculate the paired cascade and usage-weighted break-even at each threshold.

    Missing S1 signals escalate. Costs must be known; this function rejects unknowns
    instead of imputing zero. Latencies represent the sequential critical path.
    """
    signal = np.asarray(signal, dtype=float)
    s1_correct = np.asarray(s1_correct, dtype=bool)
    s2_correct = np.asarray(s2_correct, dtype=bool)
    c1, c2 = np.asarray(s1_cost, dtype=float), np.asarray(s2_cost, dtype=float)
    l1, l2 = np.asarray(s1_latency, dtype=float), np.asarray(s2_latency, dtype=float)
    n = len(signal)
    fit = None if fit_probability is None else np.asarray(fit_probability, dtype=float)
    if fit is not None and len(fit) != n:
        raise ValueError("Fit probabilities must be paired by item")
    if not n or any(len(x) != n for x in (s1_correct, s2_correct, c1, c2, l1, l2)):
        raise ValueError("Inputs must be nonempty and paired by item")
    if not np.all(np.isfinite(c1)) or not np.all(np.isfinite(c2)):
        raise ValueError("Unknown cost cannot be treated as zero")
    rows = []
    mean2 = c2.mean()
    for tau in grid:
        escalate = ~np.isfinite(signal) | (signal < tau)
        if fit is not None:
            escalate |= ~np.isfinite(fit) | (fit < fit_threshold)
        selected_cost = c2[escalate].mean() if escalate.any() else np.nan
        latency = l1 + np.where(escalate, l2, 0)
        rows.append(
            {
                "tau": float(tau),
                "accuracy": float(np.where(escalate, s2_correct, s1_correct).mean()),
                "escalation_rate": float(escalate.mean()),
                "cost_per_request": float(np.mean(c1 + np.where(escalate, c2, 0))),
                "latency_p50": float(np.percentile(latency, 50)),
                "latency_p95": float(np.percentile(latency, 95)),
                "breakeven_usage_weighted": float((mean2 - c1.mean()) / selected_cost) if selected_cost > 0 else np.nan,
                "breakeven_list_price": float(1 - c1.mean() / mean2) if mean2 > 0 else np.nan,
                "escalated_s2_cost": float(selected_cost),
                "average_s2_cost": float(mean2),
            }
        )
    return pd.DataFrame(rows)


def paired_aurc_difference(probability, confidence, correct, *, resamples=2000, seed=0):
    """AURC(probability) - AURC(confidence), bootstrapped over paired items."""
    p, c, y = np.asarray(probability, float), np.asarray(confidence, float), np.asarray(correct, bool)
    if not (len(p) == len(c) == len(y)) or not len(p):
        raise ValueError("Inputs must be nonempty and paired by item")
    if not (np.isfinite(p).all() and np.isfinite(c).all()):
        raise ValueError("Compare signals on the same items with observed values")
    return bootstrap(lambda idx: aurc(p[idx], y[idx]) - aurc(c[idx], y[idx]), len(p), resamples=resamples, seed=seed)

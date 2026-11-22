"""Worked examples for the E1 threshold and paired economics."""

import numpy as np
import pytest

from bench.common.stats import risk_coverage
from bench.e1_e2.metrics import cascade_sweep, choose_joint_threshold, choose_threshold, paired_aurc_difference


def test_threshold_uses_calibration_selective_accuracy_and_fallback():
    signal = [0.1, 0.5, 0.9, 1.0]
    correct = [False, False, True, True]
    assert choose_threshold(signal, correct, 1.0, [0.0, 0.5, 0.8]) == (0.8, 0.5, False)
    assert choose_threshold(signal, [False] * 4, 1.0, [0.0, 1.0]) == (1.0, 0.0, True)


def test_joint_threshold_maximizes_coverage_on_observed_calibration_values():
    choice = [0.2, 0.6, 0.9, 0.9]
    fit = [0.9, 0.1, 0.9, 0.9]
    correct = [False, False, True, True]
    assert choose_joint_threshold(choice, fit, correct, 1.0) == (0.6, 0.9, 0.5, False)
    assert choose_joint_threshold(choice, fit, [False] * 4, 1.0) == (1.0, 1.0, 0.0, True)


def test_fit_gate_escalates_low_or_missing_fit():
    row = cascade_sweep(
        [0.9, 0.9],
        [False, True],
        [True, False],
        [1, 1],
        [2, 2],
        [1, 1],
        [1, 1],
        [0.5],
        fit_probability=[0.2, 0.9],
        fit_threshold=0.5,
    ).iloc[0]
    assert row.escalation_rate == 0.5
    assert row.accuracy == 1.0


def test_break_even_uses_unconditional_baseline_and_conditional_escalation_cost():
    result = cascade_sweep([0.2, 0.8], [False, True], [True, False], [1, 1], [6, 2], [1, 1], [10, 2], [0.5]).iloc[0]
    assert result.accuracy == 1.0
    assert result.escalation_rate == 0.5
    assert result.cost_per_request == 4.0
    assert result.breakeven_usage_weighted == pytest.approx(0.5)
    assert result.breakeven_list_price == pytest.approx(0.75)
    assert result.escalated_s2_cost == 6.0
    assert result.average_s2_cost == 4.0


def test_unknown_cost_is_not_free():
    with pytest.raises(ValueError, match="Unknown cost"):
        cascade_sweep([0.1], [True], [True], [np.nan], [1], [1], [1], [0.5])


def test_missing_gate_signal_escalates_even_at_zero_threshold():
    row = cascade_sweep([np.nan, 1.0], [False, True], [True, False], [1, 1], [2, 2], [1, 1], [1, 1], [0]).iloc[0]
    assert row.escalation_rate == 0.5
    assert row.accuracy == 1.0


def test_paired_aurc_identical_signals_have_zero_difference():
    point, low, high = paired_aurc_difference([0.2, 0.8, 0.5], [0.2, 0.8, 0.5], [False, True, True], resamples=30)
    assert (point, low, high) == (0.0, 0.0, 0.0)


def test_paired_aurc_ranks_refusals_last_without_dropping_them():
    point, low, high = paired_aurc_difference(
        [0.9, -np.inf, 0.1], [0.9, -np.inf, 0.1], [True, False, False], resamples=30
    )
    assert (point, low, high) == (0.0, 0.0, 0.0)
    coverage, risk = risk_coverage([0.9, -np.inf, 0.1], [True, False, False])
    np.testing.assert_allclose(coverage, [1 / 3, 2 / 3, 1])
    np.testing.assert_allclose(risk, [0, 0.5, 2 / 3])

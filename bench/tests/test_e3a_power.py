"""Offline tests for audit power, control alarms and rate selection."""

import pytest

from bench.e3a.power import find_minimum_audit_rate, simulate_power

BASE = dict(
    epsilon=0.1, alpha=0.05, baseline_error=0.0, coverage=1.0, horizon=100, pre_shift_horizon=0, seed=41, repetitions=32
)


def test_strong_shift_is_detected_and_control_has_no_false_alarms():
    result = simulate_power(**BASE, severity=1.0, audit_rate=1.0)
    assert result.power == 1.0
    assert result.confidence_interval[0] >= 0.8
    assert result.false_alarm == 0.0
    assert result.pre_shift_false_alarms == result.misses == 0
    assert all(delay is not None and 1 <= delay <= 100 for delay in result.detection_delays)
    assert result.audit_detection_delays == result.detection_delays


def test_no_audits_or_no_coverage_are_censored_not_detections():
    for coverage, rate in [(1.0, 0.0), (0.0, 1.0)]:
        params = {**BASE, "coverage": coverage}
        result = simulate_power(**params, severity=1.0, audit_rate=rate)
        assert result.power == result.false_alarm == 0.0
        assert result.misses == BASE["repetitions"]
        assert result.detection_delays == (None,) * BASE["repetitions"]
        assert result.audit_detection_delays == result.detection_delays


def test_pre_shift_alarm_is_not_a_detection():
    result = simulate_power(**{**BASE, "baseline_error": 1.0, "pre_shift_horizon": 100}, severity=0.0, audit_rate=1.0)
    assert result.false_alarm == 1.0
    assert result.pre_shift_false_alarms == result.misses == BASE["repetitions"]
    assert result.power == 0.0
    assert all(delay is None for delay in result.detection_delays)


def test_identical_seed_replays_and_zero_shift_matches_control():
    params = {**BASE, "baseline_error": 0.3, "coverage": 0.7, "horizon": 80}
    first = simulate_power(**params, severity=0.0, audit_rate=0.8)
    assert first == simulate_power(**params, severity=0.0, audit_rate=0.8)
    assert first.power == first.false_alarm
    assert first.confidence_interval == first.false_alarm_confidence_interval
    assert all(
        a <= t
        for a, t in zip(first.audit_detection_delays, first.detection_delays, strict=True)
        if a is not None and t is not None
    )


def test_rate_search_returns_lowest_feasible_candidate_or_none():
    search = find_minimum_audit_rate(**BASE, severity=1.0, rates=[1.0, 0.0, 1.0])
    assert [result.audit_rate for result in search.results] == [0.0, 1.0]
    assert search.minimum_rate == 1.0
    impossible = find_minimum_audit_rate(**{**BASE, "horizon": 1}, severity=1.0, rates=[0.0, 1.0])
    assert impossible.minimum_rate is None


def test_lower_bound_not_point_estimate_drives_search():
    search = find_minimum_audit_rate(**{**BASE, "repetitions": 2}, severity=1.0, rates=[1.0])
    assert search.results[0].power == 1.0
    assert search.results[0].confidence_interval[0] < 0.8
    assert search.minimum_rate is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"epsilon": 0.0},
        {"alpha": 1.0},
        {"baseline_error": -0.1},
        {"baseline_error": 0.9, "severity": 0.2},
        {"coverage": 1.1},
        {"horizon": 0},
        {"pre_shift_horizon": -1},
        {"repetitions": 0},
        {"audit_rate": -0.1},
    ],
)
def test_invalid_simulation_parameters_are_rejected(overrides):
    with pytest.raises(ValueError, match="must"):
        simulate_power(**{**BASE, "severity": 0.1, "audit_rate": 0.5, **overrides})


def test_empty_or_invalid_search_candidates_are_rejected():
    for rates in ([], [-0.1], [1.1]):
        with pytest.raises(ValueError, match="rates must"):
            find_minimum_audit_rate(**BASE, severity=0.1, rates=rates)

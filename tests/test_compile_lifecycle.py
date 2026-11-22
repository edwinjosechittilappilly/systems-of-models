"""Offline checks for split-sample promotion and sequential audit guarantees."""

import math
import random

import pytest

from som.compile.lifecycle import CompiledDecision
from som.questions import ChoiceAnswer, Refusal


def answer(value="a", score=0.9):
    return ChoiceAnswer("choice", value, {value: score})


def promoted(*, epsilon=0.1, alpha=0.05, audit_rate=1.0):
    decision = CompiledDecision(epsilon=epsilon, alpha=alpha, n_cal=1, n_val=60, audit_rate=audit_rate)
    decision.start_shadow()
    for _ in range(61):
        decision.observe_shadow(answer(), answer())
    assert decision.attempt_promotion().promoted
    return decision


def test_split_sample_threshold_and_clopper_pearson_alpha_spending():
    decision = CompiledDecision(
        epsilon=0.2,
        alpha=0.05,
        n_cal=4,
        n_val=20,
        audit_rate=0.5,
        min_coverage=0.5,
        max_promotion_attempts=2,
    )
    decision.start_shadow()
    decision.observe_shadow(answer(score=0.8), answer("b"))
    for _ in range(3):
        decision.observe_shadow(answer(score=0.9), answer())
    for _ in range(20):
        decision.observe_shadow(answer(), answer())
    result = decision.attempt_promotion()
    assert result.promoted
    assert result.threshold == math.nextafter(0.8, math.inf)
    assert (result.calibration_served, result.calibration_errors) == (3, 0)
    assert (result.validation_served, result.validation_errors) == (20, 0)
    assert result.upper_bound == pytest.approx(0.1684335290)
    assert decision.route(answer(score=0.8)) == "escalate"
    assert decision.route(answer(score=0.9)) == "serve"
    assert decision.route(Refusal("choice")) == "escalate"
    assert (decision.total_count, decision.served_count, decision.coverage) == (3, 1, 1 / 3)


def test_nonzero_error_clopper_pearson_bound():
    decision = CompiledDecision(epsilon=0.5, alpha=0.05, n_cal=1, n_val=10, audit_rate=0)
    decision.start_shadow()
    decision.observe_shadow(answer(), answer())
    decision.observe_shadow(answer(), answer("b"))
    for _ in range(9):
        decision.observe_shadow(answer(), answer())
    result = decision.attempt_promotion()
    assert result.promoted
    assert result.upper_bound == pytest.approx(0.3941633024)


def test_validation_rejects_and_retry_requires_fresh_disjoint_window():
    decision = CompiledDecision(epsilon=0.2, alpha=0.05, n_cal=2, n_val=20, audit_rate=0, max_promotion_attempts=2)
    decision.start_shadow()
    for _ in range(2):
        decision.observe_shadow(answer(), answer())
    for _ in range(20):
        decision.observe_shadow(answer(), answer("b"))
    result = decision.attempt_promotion()
    assert not result.promoted and result.validation_errors == 20 and result.upper_bound == 1
    assert decision.state == "shadow"
    assert decision.route(answer()) == "escalate"
    with pytest.raises(RuntimeError, match="complete"):
        decision.attempt_promotion()
    for _ in range(22):
        decision.observe_shadow(answer(), answer())
    assert decision.attempt_promotion().promoted


def test_no_calibration_coverage_and_no_validation_served_cannot_promote():
    decision = CompiledDecision(epsilon=0.2, alpha=0.05, n_cal=2, n_val=20, audit_rate=0, min_coverage=0.6)
    decision.start_shadow()
    decision.observe_shadow(answer(), answer())
    decision.observe_shadow(Refusal("choice"), answer())
    for _ in range(20):
        decision.observe_shadow(answer(), answer())
    assert not decision.attempt_promotion().promoted
    with pytest.raises(RuntimeError, match="exhausted"):
        decision.observe_shadow(answer(), answer())

    empty_val = CompiledDecision(epsilon=0.2, alpha=0.05, n_cal=1, n_val=20, audit_rate=0)
    empty_val.start_shadow()
    empty_val.observe_shadow(answer(), answer())
    for _ in range(20):
        empty_val.observe_shadow(Refusal("choice"), answer())
    result = empty_val.attempt_promotion()
    assert not result.promoted and result.validation_served == 0 and result.upper_bound is None


def test_shift_demotes_and_counts_detection_in_all_routed_requests():
    decision = promoted()
    for _ in range(1, 101):
        assert decision.route(answer()) == "serve"
        if decision.record_audit(answer(), answer("b")):
            break
    else:
        pytest.fail("strong shift was not detected")
    assert decision.state == "demoted"
    assert decision.detection_time == decision.audit_count
    assert decision.audit_count == decision.audit_errors
    assert decision.e_value >= 20
    assert decision.route(answer()) == "escalate"
    assert not decision.should_audit(random.Random(0))
    with pytest.raises(RuntimeError, match="audits"):
        decision.record_audit(answer(), answer("b"))


def test_audit_e_process_false_demotion_is_controlled_under_null():
    alpha = epsilon = 0.05
    streams = 500
    false_alarms = 0
    for seed in range(streams):
        rng = random.Random(seed)
        decision = promoted(epsilon=epsilon, alpha=alpha)
        for _ in range(2000):
            decision.route(answer())
            reference = answer("b") if rng.random() < epsilon else answer()
            if decision.record_audit(answer(), reference):
                false_alarms += 1
                break
    mc_standard_error = math.sqrt(alpha * (1 - alpha) / streams)
    assert false_alarms / streams <= alpha + 3 * mc_standard_error


def test_audit_sampling_and_invalid_references():
    never = promoted(audit_rate=0)
    always = promoted(audit_rate=1)
    assert not never.should_audit(random.Random(1))
    assert always.should_audit(random.Random(1))
    with pytest.raises(ValueError, match="reference"):
        always.record_audit(answer(), Refusal("choice"))
    with pytest.raises(ValueError, match="same question"):
        always.record_audit(answer(), ChoiceAnswer("other", "a"))
    assert always.audit_count == 0


def test_rejects_invalid_configuration_and_signals():
    for kwargs in (
        {"epsilon": 0},
        {"epsilon": 1},
        {"alpha": 0},
        {"n_cal": 0},
        {"max_promotion_attempts": 0},
        {"audit_rate": 2},
        {"min_coverage": -1},
        {"metric": "unknown"},
    ):
        params = dict(epsilon=0.1, alpha=0.05, n_cal=1, n_val=60, audit_rate=0.1)
        params.update(kwargs)
        with pytest.raises(ValueError, match=r"must|unknown"):
            CompiledDecision(**params)
    decision = promoted()
    with pytest.raises(ValueError, match="signal"):
        decision.route(answer(score=float("nan")))


def test_high_epsilon_audit_betting_factors_remain_positive():
    decision = promoted(epsilon=0.9)
    for _ in range(20):
        decision.route(answer())
        assert not decision.record_audit(answer(), answer())
    assert 0 < decision.e_value < 1

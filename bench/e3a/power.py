"""Offline Monte Carlo power for the actual compiled-decision audit process.

This is a planning model, not an estimate of the dev-stream effect: callers must
supply the observed increase in served error. Errors, coverage and audit draws
are independent Bernoulli variables. A freshly promoted decision is monitored
before and after the shift; a matched no-shift control estimates false alarms.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterable
from dataclasses import dataclass

from bench.common.stats import wilson
from som.compile import CompiledDecision
from som.questions import ChoiceAnswer, Refusal


@dataclass(frozen=True)
class PowerResult:
    """Monte Carlo outcomes; delay entries are None for censored repetitions.

    Power counts demotions after the shift divided by *all* repetitions, so a
    pre-shift demotion is not credited as detection. False alarms are measured
    over the entire matched control stream. Delays count tickets or audits
    from the shift, inclusive of the detecting ticket/audit.
    """

    audit_rate: float
    repetitions: int
    power: float
    confidence_interval: tuple[float, float]
    false_alarm: float
    false_alarm_confidence_interval: tuple[float, float]
    pre_shift_false_alarms: int
    misses: int
    detection_delays: tuple[int | None, ...]
    audit_detection_delays: tuple[int | None, ...]


@dataclass(frozen=True)
class AuditRateSearch:
    """Results for every tested candidate, with None when none meets target."""

    minimum_rate: float | None
    results: tuple[PowerResult, ...]


def _promoted(epsilon: float, alpha: float, audit_rate: float) -> CompiledDecision:
    # Synthetic error-free shadow data isolate audit power conditional on a
    # successful promotion. The actual promotion procedure is still exercised.
    n = max(1, math.ceil(math.log(min(alpha, 0.05)) / math.log1p(-epsilon))) + 1
    decision = CompiledDecision(epsilon=epsilon, alpha=alpha, n_cal=n, n_val=n, audit_rate=audit_rate)
    answer = ChoiceAnswer("power", "correct", {"correct": 1.0})
    decision.start_shadow()
    for _ in range(2 * n):
        decision.observe_shadow(answer, answer)
    if not decision.attempt_promotion().promoted:
        raise RuntimeError("could not construct a promoted audit decision")
    return decision


def _trajectory(
    *,
    epsilon: float,
    alpha: float,
    baseline_error: float,
    severity: float,
    coverage: float,
    audit_rate: float,
    pre_shift_horizon: int,
    horizon: int,
    seed: int,
) -> tuple[int | None, int | None]:
    decision = _promoted(epsilon, alpha, audit_rate)
    # Separate streams keep coverage and audit selection independent of error.
    source = random.Random(seed)
    covered_rng, error_rng, audit_rng = (random.Random(source.getrandbits(128)) for _ in range(3))
    answer = ChoiceAnswer("power", "correct", {"correct": 1.0})
    wrong = ChoiceAnswer("power", "wrong", {"wrong": 1.0})
    refusal = Refusal("power")
    audits_at_shift = 0
    for ticket in range(pre_shift_horizon + horizon):
        if ticket == pre_shift_horizon:
            audits_at_shift = decision.audit_count
        served = covered_rng.random() < coverage
        error = error_rng.random() < baseline_error + (severity if ticket >= pre_shift_horizon else 0.0)
        if decision.route(answer if served else refusal) == "serve" and decision.should_audit(audit_rng):
            if decision.record_audit(answer, wrong if error else answer):
                return ticket, decision.audit_count - audits_at_shift if ticket >= pre_shift_horizon else None
    return None, None


def simulate_power(
    *,
    severity: float,
    epsilon: float,
    alpha: float,
    baseline_error: float,
    coverage: float,
    horizon: int,
    audit_rate: float,
    seed: int,
    repetitions: int,
    pre_shift_horizon: int = 1200,
) -> PowerResult:
    """Simulate shifted and matched control streams with the real e-process.

    ``severity`` is the absolute increase in error probability among served
    tickets (not the fraction of changed traffic). ``horizon`` is the number
    of post-shift tickets. Confidence intervals are two-sided 95% Wilson
    intervals over independent Monte Carlo repetitions, distinct from the
    e-process's per-stream ``alpha``.
    """
    if not 0 < epsilon < 1 or not 0 < alpha < 1:
        raise ValueError("epsilon and alpha must lie strictly between 0 and 1")
    if not 0 <= baseline_error <= 1 or not 0 <= severity <= 1 - baseline_error:
        raise ValueError("baseline_error and severity must define valid error probabilities")
    if not 0 <= coverage <= 1 or not 0 <= audit_rate <= 1:
        raise ValueError("coverage and audit_rate must be between 0 and 1")
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (horizon, pre_shift_horizon, repetitions, seed)):
        raise ValueError("horizons, repetitions and seed must be integers")
    if horizon <= 0 or pre_shift_horizon < 0 or repetitions <= 0:
        raise ValueError("horizon and repetitions must be positive; pre_shift_horizon must be nonnegative")

    seeds = random.Random(seed)
    delays: list[int | None] = []
    audit_delays: list[int | None] = []
    pre_false = controls = 0
    for _ in range(repetitions):
        trial_seed = seeds.getrandbits(128)
        common = dict(
            epsilon=epsilon, alpha=alpha, baseline_error=baseline_error, coverage=coverage,
            audit_rate=audit_rate, pre_shift_horizon=pre_shift_horizon, horizon=horizon, seed=trial_seed,
        )
        ticket, audit_delay = _trajectory(**common, severity=severity)
        control_ticket, _ = _trajectory(**common, severity=0.0)
        controls += int(control_ticket is not None)
        pre_false += int(ticket is not None and ticket < pre_shift_horizon)
        detected = ticket is not None and ticket >= pre_shift_horizon
        delays.append(ticket - pre_shift_horizon + 1 if detected and ticket is not None else None)
        audit_delays.append(audit_delay if detected else None)
    detections = sum(delay is not None for delay in delays)
    return PowerResult(
        audit_rate=audit_rate, repetitions=repetitions, power=detections / repetitions,
        confidence_interval=wilson(detections, repetitions), false_alarm=controls / repetitions,
        false_alarm_confidence_interval=wilson(controls, repetitions), pre_shift_false_alarms=pre_false,
        misses=repetitions - detections, detection_delays=tuple(delays), audit_detection_delays=tuple(audit_delays),
    )


def find_minimum_audit_rate(
    *,
    severity: float,
    epsilon: float,
    alpha: float,
    baseline_error: float,
    coverage: float,
    horizon: int,
    seed: int,
    repetitions: int,
    pre_shift_horizon: int = 1200,
    rates: Iterable[float] = tuple(i / 20 for i in range(21)),
    target: float = 0.8,
) -> AuditRateSearch:
    """Find the smallest *candidate* meeting target on its 95% lower bound.

    All candidates are evaluated: finite-sample power need not be monotonic in
    audit rate because the e-process also observes the extra non-errors. No
    feasible candidate is represented explicitly by ``minimum_rate=None``.
    """
    if not 0 < target < 1:
        raise ValueError("target must lie strictly between 0 and 1")
    candidates = sorted(set(rates))
    if not candidates or any(not 0 <= rate <= 1 for rate in candidates):
        raise ValueError("rates must be a nonempty collection of probabilities")
    results = tuple(simulate_power(
        severity=severity, epsilon=epsilon, alpha=alpha, baseline_error=baseline_error,
        coverage=coverage, horizon=horizon, audit_rate=rate, seed=seed, repetitions=repetitions,
        pre_shift_horizon=pre_shift_horizon,
    ) for rate in candidates)
    minimum = next((result.audit_rate for result in results if result.confidence_interval[0] >= target), None)
    return AuditRateSearch(minimum_rate=minimum, results=results)

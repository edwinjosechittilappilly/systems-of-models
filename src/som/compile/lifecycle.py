"""Split-sample promotion and anytime-valid audit demotion for compiled decisions.

Promotion assumes independent calibration/validation examples and spends a fixed share
of alpha on each disjoint attempt. Audits must be sampled independently of their
unknown errors; conditional audit error at most epsilon makes the mixture a
nonnegative supermartingale, even under adaptive stopping. References measure
agreement, not correctness unless they are ground truth.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Protocol

from som.gate import Metric, signal
from som.questions import Answer, Refusal


class _Random(Protocol):
    def random(self) -> float: ...


@dataclass(frozen=True)
class PromotionResult:
    attempt: int
    threshold: float | None
    calibration_served: int
    calibration_errors: int
    validation_served: int
    validation_errors: int
    upper_bound: float | None
    promoted: bool
    tau_rule: Literal["upper_bound", "margin"]
    calibration_bound: float | None


def _binomial_cdf(k: int, n: int, p: float) -> float:
    if p <= 0:
        return 1.0
    if p >= 1:
        return 0.0 if k < n else 1.0
    terms = [
        math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * math.log(p) + (n - i) * math.log1p(-p)
        for i in range(k + 1)
    ]
    peak = max(terms)
    return min(1.0, math.exp(peak) * sum(math.exp(term - peak) for term in terms))


def _upper_bound(errors: int, total: int, alpha: float) -> float:
    if errors == total:
        return 1.0
    if errors == 0:
        return -math.expm1(math.log(alpha) / total)
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if _binomial_cdf(errors, total, mid) > alpha:
            lo = mid
        else:
            hi = mid
    return hi


class CompiledDecision:
    """Gate typed answers after independent shadow calibration and validation.

    Call ``start_shadow``, then ``observe_shadow`` exactly n_cal+n_val times,
    then ``attempt_promotion``. A failed attempt consumes its entire window;
    retry with a new window. Route every request, randomly audit served answers,
    and pass each audited answer and its reference to ``record_audit``.
    Detection time counts routed requests since promotion, including escalations.

    ``tau_rule="upper_bound"`` selects the lowest threshold with calibration
    Clopper-Pearson upper bound at most epsilon, using ``alpha_cal``. The
    alternative ``"margin"`` requires empirical error at most
    ``calibration_margin * epsilon``. The reported calibration bound is
    descriptive after threshold selection, not a simultaneous confidence
    guarantee; only the independent validation bound controls promotion.
    Small calibration windows may not provide enough evidence even with zero
    errors; increase ``n_cal`` or explicitly choose the margin rule.
    Audit bets form an equally weighted geometric grid ending at 0.95/epsilon.

    Counts and coverage start at promotion and stop at demotion. A rejected or
    demoted decision is final: recompilation requires a new instance and a
    fresh, independently allocated alpha budget. Choice answers use string
    values; stringify integer or boolean reference values before constructing
    a ChoiceAnswer so equality measures the intended agreement.
    """

    def __init__(
        self,
        *,
        epsilon: float,
        alpha: float,
        n_cal: int,
        n_val: int,
        audit_rate: float,
        metric: Metric = "probability",
        max_promotion_attempts: int = 1,
        min_coverage: float = 0.0,
        tau_rule: Literal["upper_bound", "margin"] = "upper_bound",
        alpha_cal: float = 0.05,
        calibration_margin: float = 0.6,
    ) -> None:
        if not 0 < epsilon < 1 or not 0 < alpha < 1:
            raise ValueError("epsilon and alpha must lie strictly between 0 and 1")
        if not 0 <= audit_rate <= 1 or not 0 <= min_coverage <= 1:
            raise ValueError("audit_rate and min_coverage must be between 0 and 1")
        if any(isinstance(n, bool) or not isinstance(n, int) or n <= 0 for n in (n_cal, n_val, max_promotion_attempts)):
            raise ValueError("window sizes and max_promotion_attempts must be positive integers")
        if metric not in ("probability", "confidence", "margin"):
            raise ValueError("unknown metric")
        if tau_rule not in ("upper_bound", "margin"):
            raise ValueError("unknown tau_rule")
        if not 0 < alpha_cal < 1 or not 0 < calibration_margin < 1:
            raise ValueError("alpha_cal and calibration_margin must lie strictly between 0 and 1")
        self.epsilon = epsilon
        self.alpha = alpha
        self.n_cal = n_cal
        self.n_val = n_val
        self.audit_rate = audit_rate
        self.metric = metric
        self.max_promotion_attempts = max_promotion_attempts
        self.min_coverage = min_coverage
        self.tau_rule = tau_rule
        self.alpha_cal = alpha_cal
        self.calibration_margin = calibration_margin
        self.state: Literal["candidate", "shadow", "promoted", "demoted", "rejected"] = "candidate"
        self.tau: float | None = None
        self.promotion_attempts = 0
        self.last_promotion: PromotionResult | None = None
        self.total_count = 0
        self.served_count = 0
        self.audit_count = 0
        self.audit_errors = 0
        self.detection_time: int | None = None
        self._window: list[tuple[float | None, bool]] = []
        self._log_wealth = [0.0] * 9
        self._lambdas = [(0.95 / epsilon) * 2 ** (i - 8) for i in range(9)]

    @property
    def coverage(self) -> float:
        return self.served_count / self.total_count if self.total_count else 0.0

    @property
    def e_value(self) -> float:
        peak = max(self._log_wealth)
        log_mean = peak + math.log(sum(math.exp(x - peak) for x in self._log_wealth) / len(self._log_wealth))
        return math.exp(log_mean) if log_mean < 709 else math.inf

    def start_shadow(self) -> None:
        if self.state not in ("candidate", "shadow"):
            raise RuntimeError("only a candidate can enter shadow")
        if self._window:
            raise RuntimeError("cannot discard a partially collected window")
        if self.promotion_attempts >= self.max_promotion_attempts:
            raise RuntimeError("promotion attempts exhausted")
        self.state = "shadow"

    def _score(self, answer: Answer) -> float | None:
        value = signal(answer, self.metric)
        if value is None:
            return None
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("answer signal must be finite and between 0 and 1")
        return value

    @staticmethod
    def _error(answer: Answer, reference: Answer) -> bool:
        if isinstance(reference, Refusal):
            raise ValueError("a refused reference cannot establish error")
        if answer.name != reference.name:
            raise ValueError("answer and reference must address the same question")
        return answer.value != reference.value

    def observe_shadow(self, answer: Answer, reference: Answer) -> None:
        if self.state != "shadow":
            raise RuntimeError("shadow observation requires shadow state")
        if self.promotion_attempts >= self.max_promotion_attempts:
            raise RuntimeError("promotion attempts exhausted")
        if len(self._window) >= self.n_cal + self.n_val:
            raise RuntimeError("shadow window is full; attempt promotion first")
        self._window.append((self._score(answer), self._error(answer, reference)))

    def attempt_promotion(self) -> PromotionResult:
        if self.state != "shadow" or len(self._window) != self.n_cal + self.n_val:
            raise RuntimeError("promotion requires a complete shadow window")
        if self.promotion_attempts >= self.max_promotion_attempts:
            raise RuntimeError("promotion attempts exhausted")
        self.promotion_attempts += 1
        cal, val = self._window[: self.n_cal], self._window[self.n_cal :]
        self._window = []
        scores = sorted({s for s, _ in cal if s is not None and s < 1})
        thresholds = [0.0, *(math.nextafter(s, math.inf) for s in scores)]
        tau = None
        cal_n = cal_errors = val_n = val_errors = 0
        bound = cal_bound = None
        for threshold in thresholds:
            selected = [error for score, error in cal if score is not None and score >= threshold]
            if not selected or len(selected) / self.n_cal < self.min_coverage:
                continue
            errors = sum(selected)
            candidate_bound = _upper_bound(errors, len(selected), self.alpha_cal)
            acceptable = (
                candidate_bound <= self.epsilon
                if self.tau_rule == "upper_bound"
                else errors / len(selected) <= self.calibration_margin * self.epsilon
            )
            if acceptable:
                tau, cal_n, cal_errors, cal_bound = threshold, len(selected), errors, candidate_bound
                break
        if tau is not None:
            selected = [error for score, error in val if score is not None and score >= tau]
            val_n, val_errors = len(selected), sum(selected)
            if val_n:
                bound = _upper_bound(val_errors, val_n, self.alpha / self.max_promotion_attempts)
        promoted = bound is not None and bound <= self.epsilon
        if promoted:
            self.state = "promoted"
            self.tau = tau
        elif self.promotion_attempts >= self.max_promotion_attempts:
            self.state = "rejected"
        result = PromotionResult(
            self.promotion_attempts,
            tau,
            cal_n,
            cal_errors,
            val_n,
            val_errors,
            bound,
            promoted,
            self.tau_rule,
            cal_bound,
        )
        self.last_promotion = result
        return result

    def route(self, answer: Answer) -> Literal["serve", "escalate"]:
        score = self._score(answer)
        served = self.state == "promoted" and self.tau is not None and score is not None and score >= self.tau
        if self.state == "promoted":
            self.total_count += 1
            self.served_count += int(served)
        return "serve" if served else "escalate"

    def should_audit(self, rng: _Random) -> bool:
        """Draw an audit decision for a served answer, independently of its error."""
        return self.state == "promoted" and rng.random() < self.audit_rate

    def record_audit(self, answer: Answer, reference: Answer) -> bool:
        """Update the audit e-process; return whether this audit caused demotion."""
        if self.state != "promoted":
            raise RuntimeError("audits require promoted state")
        score = self._score(answer)
        if score is None or self.tau is None or score < self.tau:
            raise ValueError("only served answers may be audited")
        error = self._error(answer, reference)
        self.audit_count += 1
        self.audit_errors += int(error)
        for i, fraction in enumerate(self._lambdas):
            self._log_wealth[i] += math.log1p(fraction * (int(error) - self.epsilon))
        if self.e_value >= 1 / self.alpha:
            self.state = "demoted"
            self.detection_time = self.total_count
            return True
        return False

"""Gate: ask a cheap System 1 first, escalate to a stronger system when the answer is not sure enough."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from som.envelope import Escalation, Threshold
from som.questions import Answer, Predicate, PredicateAnswer, Question, Refusal
from som.systems import Decider, Decision, Input
from som.trace import TraceStore

Metric = Literal["probability", "confidence", "margin"]
Mode = Literal["gate", "shadow"]


def breakeven_rate(s1_cost: float, s2_cost: float) -> float:
    """Escalation rate below which a gate is cheaper than calling System 2 for everything: ``1 - c1/c2``.

    Assumes every request pays ``s1_cost`` and every escalated request costs the same ``s2_cost`` as an average
    request. Escalated requests are often longer and harder, so measure the realised rate instead of trusting this.
    """
    if s2_cost <= 0:
        raise ValueError("s2_cost must be positive")
    return 1.0 - s1_cost / s2_cost


def signal(answer: Answer, metric: Metric) -> float | None:
    """The number a gate compares with its threshold."""
    if isinstance(answer, Refusal):
        return None
    if metric == "probability":
        return answer.top_probability
    if metric == "confidence":
        return answer.confidence
    margin = getattr(answer, "margin", None)
    return margin if margin is not None else answer.top_probability


@dataclass
class GateResult:
    """The served answer, which system served it, and both decisions (``s2`` is None when S1 was sure)."""

    answer: Answer
    served_by: Literal["s1", "s2"]
    s1: Decision
    s2: Decision | None
    escalation: Escalation | None

    @property
    def value(self) -> Any:
        return self.answer.value

    @property
    def cost(self) -> float:
        return self.s1.envelope.cost.amount + (self.s2.envelope.cost.amount if self.s2 else 0.0)

    @property
    def latency_ms(self) -> float:
        return self.s1.envelope.latency_ms + (self.s2.envelope.latency_ms if self.s2 else 0.0)

    @property
    def agreed(self) -> bool | None:
        """In shadow mode or after an escalation: did System 1 give the same answer as System 2?"""
        if self.s2 is None:
            return None
        name = self.answer.name
        return self.s1.answers[name].value == self.s2.answers[name].value


class Gate:
    """Serve one typed question from ``s1`` when its answer clears ``threshold``; otherwise escalate to ``s2``.

    ``metric`` picks the gate signal: ``probability`` (the chosen answer's probability, default), ``confidence``
    (the vendor's peakedness statistic) or ``margin`` (top minus runner-up). ``fit`` is an optional companion
    predicate ("does any option fit?"); when its probability is below ``fit_threshold`` the request escalates as
    out of answer space. ``mode="shadow"`` always calls both and serves ``s2``: use it to measure agreement before
    trusting ``s1``.
    """

    def __init__(
        self,
        s1: Decider,
        s2: Decider,
        question: Question,
        *,
        threshold: float = 0.8,
        metric: Metric = "probability",
        fit: Predicate | None = None,
        fit_threshold: float = 0.5,
        mode: Mode = "gate",
        store: TraceStore | None = None,
    ) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be in [0, 1]")
        self.s1, self.s2, self.question = s1, s2, question
        self.threshold, self.metric, self.mode = threshold, metric, mode
        self.fit, self.fit_threshold = fit, fit_threshold
        self.store = store

    def _check(self, decision: Decision) -> Escalation | None:
        name = self.question.name
        answer = decision.answers[name]
        if isinstance(answer, Refusal):
            return Escalation(
                self.s2_system,
                "refusal",
                Threshold(f"answers.{name}.{self.metric}", "lt", self.threshold, None),
                question_names=[name],
                detail=answer.reason,
            )
        if self.fit is not None:
            fit = decision.answers[self.fit.name]
            probability = fit.probability if isinstance(fit, PredicateAnswer) else None
            if probability is None or probability < self.fit_threshold:
                return Escalation(
                    self.s2_system,
                    "out_of_answer_space",
                    Threshold(f"answers.{self.fit.name}.probability", "lt", self.fit_threshold, probability),
                    question_names=[self.fit.name],
                )
        observed = signal(answer, self.metric)
        if observed is None or observed < self.threshold:
            return Escalation(
                self.s2_system,
                "low_confidence",
                Threshold(f"answers.{name}.{self.metric}", "lt", self.threshold, observed),
                question_names=[name],
            )
        return None

    @property
    def s2_system(self) -> str:
        return self.s2.system

    def __call__(self, input: Input, *, metadata: Mapping[str, str] | None = None) -> GateResult:
        questions: list[Question] = [self.question] + ([self.fit] if self.fit is not None else [])
        first = self.s1.decide(input, questions)
        trace_id = first.envelope.trace_ref.trace_id
        escalation = self._check(first)
        second: Decision | None = None
        if escalation is not None or self.mode == "shadow":
            second = self.s2.decide(input, [self.question], trace_id=trace_id)
        if escalation is not None and second is not None:
            escalation.performed = True
            escalation.downstream_response_id = second.envelope.id
            escalation.prior_answers = [a.to_contract() for n, a in first.answers.items() if n != self.question.name]
            first.envelope.status = "escalated"
            first.envelope.escalation = escalation
        served = second if second is not None else first
        served_by: Literal["s1", "s2"] = "s1" if second is None else "s2"
        result = GateResult(served.answers[self.question.name], served_by, first, second, escalation)
        if self.store is not None:
            extra = dict(metadata or {})
            self.store.add_envelope(first.envelope, role="s1", question=self.question.name, **extra)
            if second is not None:
                self.store.add_envelope(second.envelope, role="s2", question=self.question.name, **extra)
            self.store.add(
                "gate",
                question=self.question.name,
                trace_id=trace_id,
                served_by=served_by,
                value=result.value,
                s1_value=first.answers[self.question.name].value,
                s2_value=None if second is None else second.answers[self.question.name].value,
                signal=signal(first.answers[self.question.name], self.metric),
                cost=result.cost,
                **extra,
            )
        return result

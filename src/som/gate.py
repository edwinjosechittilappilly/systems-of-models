"""Gate: ask a cheap System 1 first, escalate to a stronger system when the answer is not sure enough."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from som.envelope import Cost, Escalation, SystemId, Threshold
from som.questions import Answer, Predicate, PredicateAnswer, Question, Refusal
from som.systems import Decider, Decision, Input
from som.trace import TraceStore, annotate_gate, span

Metric = Literal["probability", "confidence", "margin"]
Mode = Literal["gate", "shadow"]


def breakeven_rate(s1_cost: float, s2_cost: float) -> float:
    """List-price break-even escalation rate ``1 - c1/c2``: below it, a gate is cheaper than always calling S2.

    Assumes escalated requests cost as much as an average request. They are usually longer and harder; use
    :func:`usage_weighted_breakeven` with measured costs instead.
    """
    if s2_cost <= 0:
        raise ValueError("s2_cost must be positive")
    return 1.0 - s1_cost / s2_cost


def usage_weighted_breakeven(
    mean_s1: float, mean_s2: float, mean_s2_escalated: float, *, overhead_per_request: float = 0.0
) -> float:
    """Break-even escalation rate from measured costs: ``(E[C2] - E[C1] - O/N) / E[C2 | escalated]``.

    ``mean_s2`` is the average S2 cost over all requests (the always-S2 baseline), ``mean_s2_escalated`` the average
    over the requests the gate actually escalates, and ``overhead_per_request`` any amortised extra (shadow calls,
    audits, compilation).
    """
    if mean_s2_escalated <= 0:
        raise ValueError("mean_s2_escalated must be positive")
    return (mean_s2 - mean_s1 - overhead_per_request) / mean_s2_escalated


def signal(answer: Answer, metric: Metric) -> float | None:
    """The number a gate compares with its threshold; None means "escalate"."""
    if isinstance(answer, Refusal):
        return None
    if metric == "probability":
        return answer.top_probability
    if metric == "confidence":
        return answer.confidence
    return answer.margin


@dataclass
class GateResult:
    """The served answer, which system served it, and both decisions (``s2`` is None when S1 was sure)."""

    answer: Answer
    served_by: Literal["s1", "s2"]
    s1: Decision
    s2: Decision | None
    escalation: Escalation | None
    fit: Answer | None = None
    """The serving system's answer to the companion predicate, when the gate has one."""
    s1_in_scope: bool | None = None
    """Whether S1 said an option fits, judged with the gate's ``fit_threshold`` (None without a companion predicate
    or when the fit answer was refused)."""
    s2_in_scope: bool | None = None
    """The same for S2; None when S2 was not called."""

    @property
    def in_scope(self) -> bool | None:
        """Whether the serving system said an option fits. When False, :attr:`value` is None."""
        return self.s1_in_scope if self.served_by == "s1" else self.s2_in_scope

    @property
    def value(self) -> Any:
        """The served answer's value; None when the serving system refused (see :attr:`refused`) or said no option
        fits (see :attr:`in_scope`)."""
        if self.in_scope is False:
            return None
        return self.answer.value

    @property
    def refused(self) -> bool:
        """True when no system produced an in-space answer (S1 escalated and S2 also refused). Callers must handle
        this case, and the out-of-scope case (``in_scope`` False), where :attr:`value` is also None: route to a
        person, retry with more context, or fail the request."""
        return isinstance(self.answer, Refusal)

    @property
    def cost(self) -> Cost:
        """Total cost of the request (S1 plus any S2 call), with a per-system breakdown and the weakest basis."""
        parts = [(self.s1.envelope.system, self.s1.envelope.cost, self.s1.envelope.id)]
        if self.s2 is not None:
            parts.append((self.s2.envelope.system, self.s2.envelope.cost, self.s2.envelope.id))
        return Cost.total(parts)

    @property
    def latency_ms(self) -> float:
        return self.s1.envelope.latency_ms + (self.s2.envelope.latency_ms if self.s2 else 0.0)

    @property
    def agreed(self) -> bool | None:
        """In shadow mode or after an escalation: did System 1 give the same answer as System 2? Saying that nothing
        fits counts as the answer None, so two out-of-scope verdicts agree whatever labels they were forced to pick.
        """
        if self.s2 is None:
            return None
        name = self.answer.name
        first = None if self.s1_in_scope is False else self.s1.answers[name].value
        second = None if self.s2_in_scope is False else self.s2.answers[name].value
        return first == second


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
    def s2_system(self) -> SystemId:
        return self.s2.system

    def _in_scope(self, fit: Answer | None) -> bool | None:
        """Read a fit answer with the same cutoff the gate escalates on; a bare (probability-free) answer is taken
        at its value."""
        if self.fit is None or not isinstance(fit, PredicateAnswer):
            return None
        if fit.probability is None:
            return bool(fit.raw_value)
        return fit.probability >= self.fit_threshold

    def __call__(self, input: Input, *, metadata: Mapping[str, str] | None = None) -> GateResult:
        questions: list[Question] = [self.question] + ([self.fit] if self.fit is not None else [])
        with span(f"gate {self.question.name}") as gate_ref:
            trace_id = gate_ref.trace_id
            first = self.s1.decide(input, questions, trace_id=trace_id)
            escalation = self._check(first)
            second: Decision | None = None
            if escalation is not None or self.mode == "shadow":
                # S2 answers the companion predicate too, so it can also say that nothing fits.
                second = self.s2.decide(input, questions, trace_id=trace_id)
            if escalation is not None and second is not None:
                escalation.performed = True
                escalation.downstream_response_id = second.envelope.id
                escalation.prior_answers = [
                    a.to_contract() for n, a in first.answers.items() if n != self.question.name
                ]
                first.envelope.status = "escalated"
                first.envelope.escalation = escalation
            served = second if second is not None else first
            served_by: Literal["s1", "s2"] = "s1" if second is None else "s2"
            annotate_gate(served_by, escalation.reason if escalation is not None else None)
        extra = dict(metadata or {})
        for decision in (first, second):
            if decision is not None:
                decision.envelope.metadata.update(extra)
        fit_name = self.fit.name if self.fit is not None else None
        result = GateResult(
            served.answers[self.question.name],
            served_by,
            first,
            second,
            escalation,
            served.answers.get(fit_name) if fit_name else None,
            self._in_scope(first.answers.get(fit_name) if fit_name else None),
            self._in_scope(second.answers.get(fit_name)) if fit_name and second is not None else None,
        )
        if self.store is not None:
            self.store.add_envelope(first.envelope, role="s1", question=self.question.name, metadata=extra)
            if second is not None:
                self.store.add_envelope(second.envelope, role="s2", question=self.question.name, metadata=extra)
            self.store.add(
                "gate",
                question=self.question.name,
                trace_id=trace_id,
                served_by=served_by,
                value=result.value,
                refused=result.refused,
                in_scope=result.in_scope,
                s1_value=first.answers[self.question.name].value,
                s2_value=None if second is None else second.answers[self.question.name].value,
                signal=signal(first.answers[self.question.name], self.metric),
                cost=result.cost.amount,
                cost_basis=result.cost.basis,
                metadata=extra,
            )
        return result

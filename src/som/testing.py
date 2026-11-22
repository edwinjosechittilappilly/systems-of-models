"""Offline stand-ins for real systems, for tests and for trying a gate without API keys."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from typing import Any

from som.envelope import Cost, Envelope, Implementation, SystemId, Usage
from som.questions import Answer, Question, Refusal
from som.systems import Decision, Input
from som.trace import span

AnswerFn = Callable[[Input, Question], Answer]
_TODAY = date.today().isoformat()


class FunctionDecider:
    """A :class:`~som.systems.Decider` that answers with a Python function and charges a fixed cost per call.

    As System 1 (the default) the function must return contract answers: probabilities on predicates and
    choices, a probability per level on scores, or a :class:`~som.questions.Refusal`. As System 2 it may return bare
    values (``ChoiceAnswer(name, choice)``)."""

    def __init__(
        self,
        answer: AnswerFn,
        *,
        system: SystemId = "s1.decision",
        name: str = "local/function",
        cost_per_call: float = 0.0,
        latency_ms: float = 0.0,
    ) -> None:
        self.answer, self.system, self.name = answer, system, name
        self.cost_per_call, self.latency_ms = cost_per_call, latency_ms
        self.calls = 0

    def decide(self, input: Input, questions: Sequence[Question], *, trace_id: str | None = None) -> Decision:
        self.calls += 1
        answers = {q.name: self.answer(input, q) for q in questions}
        if self.system == "s1.decision":
            for answer in answers.values():
                if not isinstance(answer, Refusal) and answer.top_probability is None:
                    raise ValueError(f"System 1 answer {answer.name!r} needs probabilities (see FunctionDecider)")
        with span(f"decide {self.name}", trace_id=trace_id) as ref:
            body: dict[str, Any]
            if self.system == "s1.decision":
                body = {"answers": [a.to_contract() for a in answers.values()]}
            else:
                text = {name: a.value for name, a in answers.items()}
                body = {
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": str(text)}],
                        }
                    ],
                    "output_parsed": text,
                    "reasoning": {"reasoning_tokens": 0},
                }
            provider, _, model = self.name.partition("/")
            envelope = Envelope(
                system=self.system,
                body=body,
                cost=Cost(
                    amount=self.cost_per_call,
                    basis="list_price",
                    rate_card={"source": "fixed cost per call (som.testing.FunctionDecider)", "retrieved_at": _TODAY},
                    usage=Usage(),
                ),
                latency_ms=self.latency_ms,
                trace_ref=ref,
                implementation=Implementation(provider=provider, model=model or provider),
            )
        return Decision(envelope=envelope, answers=answers)

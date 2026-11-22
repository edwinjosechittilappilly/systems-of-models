"""Offline stand-ins for real systems, for tests and for trying a gate without API keys."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from som.envelope import Cost, Envelope, Implementation, SystemId, Usage
from som.questions import Answer, Question
from som.systems import Decision, Input
from som.trace import span

AnswerFn = Callable[[Input, Question], Answer]


class FunctionDecider:
    """A :class:`~som.systems.Decider` that answers with a Python function and charges a fixed cost per call."""

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
                    rate_card={"source": "fixed cost per call (som.testing.FunctionDecider)"},
                    usage=Usage(),
                ),
                latency_ms=self.latency_ms,
                trace_ref=ref,
                implementation=Implementation(provider=provider, model=model or provider),
            )
        return Decision(envelope=envelope, answers=answers)

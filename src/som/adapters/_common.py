"""Helpers shared by adapters: typed questions as JSON Schema, prompts for generative models, envelope assembly."""

from __future__ import annotations

import json
import time
import warnings
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from som import pricing
from som.envelope import (
    ConfidenceBasis,
    Cost,
    Envelope,
    Implementation,
    Status,
    SystemId,
    TraceRef,
    Usage,
)
from som.questions import (
    Answer,
    Choice,
    ChoiceAnswer,
    Predicate,
    PredicateAnswer,
    Question,
    Refusal,
    Score,
    ScoreAnswer,
)
from som.systems import Input

ANSWER_INSTRUCTIONS = (
    "Answer each question about the input. Return only the JSON object the schema describes: one key per question, "
    "with true/false for yes-no questions, one of the listed values for choice questions, and the level number for "
    "score questions."
)


@dataclass
class Clock:
    started: float
    ended: float | None = None

    @property
    def ms(self) -> float:
        return ((self.ended or time.perf_counter()) - self.started) * 1000.0


@contextmanager
def timed() -> Iterator[Clock]:
    clock = Clock(time.perf_counter())
    try:
        yield clock
    finally:
        clock.ended = time.perf_counter()


def render_input(input: Input) -> str:
    """Text a generative model reads. Structured input becomes indented JSON; messages become a transcript."""
    if isinstance(input, str):
        return input
    if isinstance(input, Mapping):
        return json.dumps(input, indent=2, ensure_ascii=False, default=str)
    lines = []
    for message in input:
        content = message.get("content", "")
        text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, default=str)
        lines.append(f"{message.get('role', 'user')}: {text}")
    return "\n".join(lines)


def render_questions(questions: Sequence[Question]) -> str:
    """The questions as plain text, with option and level descriptions the JSON Schema cannot carry."""
    blocks = []
    for question in questions:
        lines = [f"- {question.name}: {question.instructions}"]
        if isinstance(question, Predicate):
            if question.true_means:
                lines.append(f"    true means: {question.true_means}")
            if question.false_means:
                lines.append(f"    false means: {question.false_means}")
        elif isinstance(question, Choice):
            for option in question.options:
                lines.append(f"    {option.value}" + (f": {option.description}" if option.description else ""))
        else:
            for index, label in enumerate(question.levels):
                lines.append(f"    {index}: {label}")
        blocks.append("\n".join(lines))
    return "Questions:\n" + "\n".join(blocks)


def user_prompt(input: Input, questions: Sequence[Question]) -> str:
    return f"Input:\n{render_input(input)}\n\n{render_questions(questions)}"


def answers_schema(questions: Sequence[Question]) -> dict[str, Any]:
    """A strict JSON Schema (OpenAI structured-output subset) with one property per question."""
    properties: dict[str, Any] = {}
    for question in questions:
        if isinstance(question, Predicate):
            properties[question.name] = {"type": "boolean", "description": question.instructions}
        elif isinstance(question, Choice):
            properties[question.name] = {
                "type": "string",
                "enum": question.values,
                "description": question.instructions,
            }
        else:
            properties[question.name] = {
                "type": "integer",
                "enum": list(range(len(question.levels))),
                "description": question.instructions,
            }
    return {
        "type": "object",
        "properties": properties,
        "required": [question.name for question in questions],
        "additionalProperties": False,
    }


def parse_answers(questions: Sequence[Question], data: Mapping[str, Any]) -> dict[str, Answer]:
    """Typed answers from a generative model's JSON. Missing or out-of-space values become refusals."""
    answers: dict[str, Answer] = {}
    for question in questions:
        value = data.get(question.name)
        if isinstance(question, Predicate) and isinstance(value, bool):
            answers[question.name] = PredicateAnswer(question.name, None, raw_value=value)
        elif isinstance(question, Choice) and value in question.values:
            answers[question.name] = ChoiceAnswer(question.name, str(value))
        elif isinstance(question, Score) and isinstance(value, int) and 0 <= value < len(question.levels):
            answers[question.name] = ScoreAnswer(question.name, float(value), labels=question.levels)
        else:
            answers[question.name] = Refusal(question.name, "out_of_answer_space")
    return answers


def s2_body(text: str, parsed: Any, *, reasoning_tokens: int | None, effort: str | None) -> dict[str, Any]:
    reasoning: dict[str, Any] = {"reasoning_tokens": reasoning_tokens or 0}
    if effort is not None:
        reasoning["effort"] = effort
    return {
        "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}],
        "output_text": text,
        "output_parsed": parsed,
        "reasoning": reasoning,
    }


def s1_confidence(answers: Mapping[str, Answer]) -> float | None:
    """Envelope-level S1 confidence: the lowest chosen-answer probability across the questions."""
    probabilities = [a.top_probability for a in answers.values() if a.top_probability is not None]
    return min(probabilities) if probabilities else None


def price(
    provider: str, model: str, usage: Usage, *, rate_card: pricing.RateCard | None, fallback_model: str | None = None
) -> Cost:
    """List-price cost from the caller's rate card, else the built-in table (returned model, then requested).

    With no rate card the cost is ``unknown`` (null amount) and a warning names the fix; a call never fails over
    pricing.
    """
    if rate_card is not None:
        return rate_card.cost(usage)
    for candidate in dict.fromkeys(m for m in (model, fallback_model) if m):
        try:
            return pricing.lookup(provider, candidate).cost(usage)
        except pricing.UnknownPriceError:
            continue
    warnings.warn(
        f"no rate card for {provider}/{model}; cost recorded as unknown. Pass rate_card= or call som.pricing.register.",
        stacklevel=3,
    )
    return Cost.unknown(usage)


def envelope(
    *,
    system: SystemId,
    body: dict[str, Any],
    cost: Cost,
    latency_ms: float,
    trace_ref: TraceRef,
    provider: str,
    model: str,
    endpoint: str,
    confidence: float | None = None,
    confidence_basis: ConfidenceBasis | None = None,
    status: Status = "completed",
    response_id: str | None = None,
) -> Envelope:
    built = Envelope(
        system=system,
        body=body,
        cost=cost,
        latency_ms=latency_ms,
        trace_ref=trace_ref,
        confidence=confidence,
        confidence_basis=confidence_basis,
        status=status,
        implementation=Implementation(provider=provider, model=model, endpoint=endpoint),
    )
    if response_id:
        built.id = response_id
    return built

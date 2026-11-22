"""Anthropic Messages adapter for structured System 2 decisions."""

from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence
from typing import Any

from som import pricing
from som.adapters._common import (
    ANSWER_INSTRUCTIONS,
    answers_schema,
    envelope,
    parse_answers,
    parse_json_object,
    price,
    s2_body,
    timed,
    user_prompt,
)
from som.envelope import Cost, SystemId, Usage
from som.questions import Question
from som.systems import Decision, Input
from som.trace import annotate, span


def _get(obj: Any, key: str, default: Any = None) -> Any:
    return obj.get(key, default) if isinstance(obj, Mapping) else getattr(obj, key, default)


class Anthropic:
    """Answer typed questions using the Anthropic Messages API's JSON output format."""

    system: SystemId = "s2.reasoning"

    def __init__(
        self,
        model: str = "claude-sonnet-4-5",
        *,
        client: Any = None,
        max_tokens: int = 4096,
        rate_card: pricing.RateCard | None = None,
        instructions: str = ANSWER_INSTRUCTIONS,
    ) -> None:
        if client is None:
            try:
                import anthropic
            except ImportError as error:  # pragma: no cover
                raise ImportError("install the Anthropic extra: pip install 'systems-of-models[anthropic]'") from error
            client = anthropic.Anthropic()
        self.model, self.name, self.client = model, f"anthropic/{model}", client
        self.max_tokens, self.rate_card, self.instructions = max_tokens, rate_card, instructions

    def decide(self, input: Input, questions: Sequence[Question], *, trace_id: str | None = None) -> Decision:
        with span(f"chat {self.name}", trace_id=trace_id) as ref:
            with timed() as clock:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=self.instructions,
                    messages=[{"role": "user", "content": user_prompt(input, questions)}],
                    output_config={"format": {"type": "json_schema", "schema": answers_schema(questions)}},
                )
            text = "".join(
                _get(block, "text", "") for block in (_get(response, "content") or []) if _get(block, "type") == "text"
            )
            parsed = parse_json_object(text)
            refused = _get(response, "stop_reason") == "refusal"
            raw_usage = _get(response, "usage")
            cached = _get(raw_usage, "cache_read_input_tokens")
            cache_creation = int(_get(raw_usage, "cache_creation_input_tokens", 0) or 0)
            usage = Usage(
                input_tokens=int(_get(raw_usage, "input_tokens", 0) or 0) + int(cached or 0) + cache_creation,
                output_tokens=int(_get(raw_usage, "output_tokens", 0) or 0),
                cached_tokens=cached,
            )
            returned = str(_get(response, "model") or self.model)
            if cache_creation:
                warnings.warn(
                    "Anthropic cache creation pricing is not supported by RateCard; cost recorded as unknown.",
                    stacklevel=2,
                )
                cost = Cost.unknown(usage)
            else:
                cost = price("anthropic", returned, usage, rate_card=self.rate_card, fallback_model=self.model)
            result = envelope(
                system="s2.reasoning",
                body=s2_body(text, parsed, reasoning_tokens=None, effort=None),
                cost=cost,
                latency_ms=clock.ms,
                trace_ref=ref,
                provider="anthropic",
                model=returned,
                endpoint="POST /v1/messages",
                status="incomplete"
                if _get(response, "stop_reason") in ("max_tokens", "refusal", "model_context_window_exceeded")
                else "completed",
                response_id=_get(response, "id"),
            )
            annotate(result, "chat")
        return Decision(result, parse_answers(questions, parsed, refused=refused))

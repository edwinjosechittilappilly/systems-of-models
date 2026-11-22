"""Google Gemini adapter for structured System 2 decisions."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from som import pricing
from som.adapters._common import (
    ANSWER_INSTRUCTIONS,
    answers_schema,
    envelope,
    parse_answers,
    price,
    s2_body,
    timed,
    user_prompt,
)
from som.envelope import Usage
from som.questions import Question
from som.systems import Decision, Input
from som.trace import annotate, span


def _get(obj: Any, key: str, default: Any = None) -> Any:
    return obj.get(key, default) if isinstance(obj, Mapping) else getattr(obj, key, default)


class Gemini:
    """Answer typed questions with the Google Gen AI SDK's JSON Schema output."""

    system = "s2.reasoning"

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        *,
        client: Any = None,
        rate_card: pricing.RateCard | None = None,
        instructions: str = ANSWER_INSTRUCTIONS,
    ) -> None:
        if client is None:
            try:
                from google import genai
            except ImportError as error:  # pragma: no cover
                raise ImportError("install the Gemini extra: pip install 'systems-of-models[gemini]'") from error
            client = genai.Client()
        self.model, self.name, self.client = model, f"gemini/{model}", client
        self.rate_card, self.instructions = rate_card, instructions

    def decide(self, input: Input, questions: Sequence[Question], *, trace_id: str | None = None) -> Decision:
        with span(f"chat {self.name}", trace_id=trace_id) as ref:
            with timed() as clock:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=user_prompt(input, questions),
                    config={
                        "system_instruction": self.instructions,
                        "response_mime_type": "application/json",
                        "response_json_schema": answers_schema(questions),
                    },
                )
            candidates = _get(response, "candidates") or []
            candidate = candidates[0] if candidates else None
            content = _get(candidate, "content")
            parts = _get(content, "parts") or []
            text = "".join(
                _get(part, "text") or "" for part in parts if not _get(part, "thought", False)
            )
            try:
                parsed = json.loads(text) if text else {}
            except json.JSONDecodeError:
                parsed = {}
            if not isinstance(parsed, Mapping):
                parsed = {}
            raw_usage = _get(response, "usage_metadata")
            thoughts = _get(raw_usage, "thoughts_token_count")
            usage = Usage(
                input_tokens=int(_get(raw_usage, "prompt_token_count", 0) or 0),
                output_tokens=int(_get(raw_usage, "candidates_token_count", 0) or 0) + int(thoughts or 0),
                cached_tokens=_get(raw_usage, "cached_content_token_count"),
                reasoning_tokens=thoughts,
            )
            returned = str(_get(response, "model_version") or self.model)
            finish = _get(candidate, "finish_reason")
            finish = _get(finish, "value", finish)
            result = envelope(
                system="s2.reasoning",
                body=s2_body(text, parsed, reasoning_tokens=thoughts, effort=None),
                cost=price("gemini", returned, usage, rate_card=self.rate_card, fallback_model=self.model),
                latency_ms=clock.ms,
                trace_ref=ref,
                provider="gemini",
                model=returned,
                endpoint="generateContent",
                status="completed" if finish == "STOP" else "incomplete",
                response_id=_get(response, "response_id"),
            )
            annotate(result, "chat")
        return Decision(result, parse_answers(questions, parsed))

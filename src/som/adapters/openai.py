"""OpenAI adapters: Decisions (System 1), Responses and Chat Completions (System 2 with structured output).

Each takes the ``openai.OpenAI`` client you already have (or builds one from the environment). ``OpenAIChat`` also
covers OpenAI-compatible servers: Ollama, vLLM, OpenRouter and a LiteLLM proxy (see its class methods).
"""

from __future__ import annotations

import os
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
    s1_confidence,
    s2_body,
    timed,
    user_prompt,
)
from som.envelope import Cost, SystemId, Usage
from som.questions import Answer, ChoiceAnswer, PredicateAnswer, Question, Refusal, ScoreAnswer
from som.systems import Decision, Input
from som.trace import annotate, span


def _client(client: Any, **kwargs: Any) -> Any:
    if client is not None:
        return client
    try:
        import openai
    except ImportError as error:  # pragma: no cover
        raise ImportError("install the OpenAI extra: pip install 'systems-of-models[openai]'") from error
    return openai.OpenAI(**{k: v for k, v in kwargs.items() if v is not None})


def _get(obj: Any, *path: str) -> Any:
    for key in path:
        if obj is None:
            return None
        obj = obj.get(key) if isinstance(obj, Mapping) else getattr(obj, key, None)
    return obj


def _decision_input(input: Input) -> Any:
    if isinstance(input, str):
        return input
    if isinstance(input, Mapping):
        return [{"role": "user", "content": [{"type": "input_json", "data": dict(input)}]}]
    return list(input)


def _decision_answer(question: Question, raw: Any) -> Answer:
    kind = _get(raw, "type")
    if kind == "predicate":
        return PredicateAnswer(question.name, float(_get(raw, "probability")))
    if kind == "choice":
        probabilities = {str(_get(p, "value")): float(_get(p, "probability")) for p in _get(raw, "probabilities")}
        return ChoiceAnswer(question.name, str(_get(raw, "choice")), probabilities, _get(raw, "confidence"))
    if kind == "score":
        levels = sorted(_get(raw, "probabilities"), key=lambda p: int(_get(p, "value")))
        return ScoreAnswer(
            question.name,
            float(_get(raw, "score")),
            tuple(float(_get(p, "probability")) for p in levels),
            tuple(str(_get(p, "label")) for p in levels),
            _get(raw, "confidence"),
        )
    return Refusal(question.name, "unspecified")


class OpenAIDecisions:
    """System 1 adapter for ``POST /v1/decisions`` (``gpt-6-luna``)."""

    system: SystemId = "s1.decision"

    def __init__(
        self, model: str = "gpt-6-luna", *, client: Any = None, rate_card: pricing.RateCard | None = None
    ) -> None:
        self.model, self.name, self.rate_card = model, f"openai-decisions/{model}", rate_card
        self.client = _client(client)

    def decide(self, input: Input, questions: Sequence[Question], *, trace_id: str | None = None) -> Decision:
        with span(f"decide {self.name}", trace_id=trace_id) as ref:
            with timed() as clock:
                response = self.client.decisions.create(
                    model=self.model,
                    input=_decision_input(input),
                    questions=[question.to_contract() for question in questions],
                )
            raw_answers = {str(_get(a, "name")): a for a in _get(response, "answers")}
            answers = {q.name: _decision_answer(q, raw_answers.get(q.name)) for q in questions}
            usage = Usage(
                input_tokens=int(_get(response, "usage", "input_tokens") or 0),
                output_tokens=int(_get(response, "usage", "output_tokens") or 0),
                cached_tokens=_get(response, "usage", "input_tokens_details", "cached_tokens"),
            )
            returned = str(_get(response, "model") or self.model)
            confidence = s1_confidence(answers)
            result = envelope(
                system="s1.decision",
                body={"answers": [answers[q.name].to_contract() for q in questions]},
                cost=price("openai-decisions", returned, usage, rate_card=self.rate_card, fallback_model=self.model),
                latency_ms=clock.ms,
                trace_ref=ref,
                provider="openai",
                model=returned,
                endpoint="POST /v1/decisions",
                confidence=confidence,
                confidence_basis="model_probability" if confidence is not None else None,
                response_id=_get(response, "id"),
            )
            annotate(result, "decide")
        return Decision(result, answers)


class OpenAIResponses:
    """System 2 adapter: a reasoning model answers typed questions through the Responses API's structured output."""

    system: SystemId = "s2.reasoning"

    def __init__(
        self,
        model: str = "gpt-6.1-terra",
        *,
        reasoning_effort: str | None = "low",
        client: Any = None,
        rate_card: pricing.RateCard | None = None,
        instructions: str = ANSWER_INSTRUCTIONS,
    ) -> None:
        self.model, self.name = model, f"openai/{model}"
        self.reasoning_effort, self.rate_card, self.instructions = reasoning_effort, rate_card, instructions
        self.client = _client(client)

    def decide(self, input: Input, questions: Sequence[Question], *, trace_id: str | None = None) -> Decision:
        with span(f"chat {self.name}", trace_id=trace_id) as ref:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "instructions": self.instructions,
                "input": user_prompt(input, questions),
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "answers",
                        "schema": answers_schema(questions),
                        "strict": True,
                    }
                },
            }
            if self.reasoning_effort is not None:
                kwargs["reasoning"] = {"effort": self.reasoning_effort}
            with timed() as clock:
                response = self.client.responses.create(**kwargs)
            # SDK objects expose output_text as a property; raw JSON (proxies, recorded responses) does not.
            text = str(
                _get(response, "output_text")
                or "".join(
                    str(_get(part, "text") or "")
                    for item in (_get(response, "output") or [])
                    for part in (_get(item, "content") or [])
                    if _get(part, "type") == "output_text"
                )
            )
            parsed = parse_json_object(text)
            refused = any(
                _get(part, "type") == "refusal"
                for item in (_get(response, "output") or [])
                for part in (_get(item, "content") or [])
            )
            usage = Usage(
                input_tokens=int(_get(response, "usage", "input_tokens") or 0),
                output_tokens=int(_get(response, "usage", "output_tokens") or 0),
                cached_tokens=_get(response, "usage", "input_tokens_details", "cached_tokens"),
                reasoning_tokens=_get(response, "usage", "output_tokens_details", "reasoning_tokens"),
            )
            returned = str(_get(response, "model") or self.model)
            incomplete = _get(response, "status") == "incomplete"
            body = s2_body(text, parsed, reasoning_tokens=usage.reasoning_tokens, effort=self.reasoning_effort)
            if incomplete:
                body["incomplete_details"] = {"reason": str(_get(response, "incomplete_details", "reason") or "")}
            result = envelope(
                system="s2.reasoning",
                body=body,
                cost=price("openai", returned, usage, rate_card=self.rate_card, fallback_model=self.model),
                latency_ms=clock.ms,
                trace_ref=ref,
                provider="openai",
                model=returned,
                endpoint="POST /v1/responses",
                status="incomplete" if incomplete else "completed",
                response_id=_get(response, "id"),
            )
            annotate(result, "chat")
        return Decision(result, parse_answers(questions, parsed, refused=refused))


class OpenAIChat:
    """System 2 adapter over Chat Completions with a JSON Schema response format.

    Works with any OpenAI-compatible server. ``provider`` names it in envelopes and selects pricing: ``local=True``
    records ``cost.basis = local_measured``; ``openrouter`` uses the provider-reported ``usage.cost`` (basis
    ``provider_reported``).
    """

    system: SystemId = "s2.reasoning"

    def __init__(
        self,
        model: str,
        *,
        client: Any = None,
        base_url: str | None = None,
        api_key: str | None = None,
        provider: str = "openai",
        local: bool = False,
        rate_card: pricing.RateCard | None = None,
        instructions: str = ANSWER_INSTRUCTIONS,
        extra_body: Mapping[str, Any] | None = None,
    ) -> None:
        self.model, self.provider, self.local = model, provider, local
        self.name, self.rate_card, self.instructions = f"{provider}/{model}", rate_card, instructions
        self.extra_body = dict(extra_body or {})
        self.client = _client(client, base_url=base_url, api_key=api_key)

    @classmethod
    def ollama(cls, model: str, *, base_url: str | None = None) -> OpenAIChat:
        url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        return cls(model, base_url=url, api_key="ollama", provider="ollama", local=True)

    @classmethod
    def vllm(cls, model: str, *, base_url: str = "http://localhost:8000/v1") -> OpenAIChat:
        return cls(
            model, base_url=base_url, api_key=os.environ.get("VLLM_API_KEY", "vllm"), provider="vllm", local=True
        )

    @classmethod
    def openrouter(cls, model: str, *, api_key: str | None = None) -> OpenAIChat:
        return cls(
            model,
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key or os.environ.get("OPENROUTER_API_KEY"),
            provider="openrouter",
            extra_body={"usage": {"include": True}},
        )

    def _cost(self, usage: Usage, response: Any, returned: str) -> Cost:
        if self.local:
            return pricing.local_cost(usage)
        reported = _get(response, "usage", "cost")
        if reported is not None and self.provider == "openrouter":
            # OpenRouter returns the charge in credits; one credit is one US dollar.
            return Cost(amount=float(reported), basis="provider_reported", usage=usage)
        return price(self.provider, returned, usage, rate_card=self.rate_card, fallback_model=self.model)

    def decide(self, input: Input, questions: Sequence[Question], *, trace_id: str | None = None) -> Decision:
        with span(f"chat {self.name}", trace_id=trace_id) as ref:
            with timed() as clock:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.instructions},
                        {"role": "user", "content": user_prompt(input, questions)},
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {"name": "answers", "schema": answers_schema(questions), "strict": True},
                    },
                    **({"extra_body": self.extra_body} if self.extra_body else {}),
                )
            choice = _get(response, "choices")[0]
            text = str(_get(choice, "message", "content") or "")
            parsed = parse_json_object(text)
            refused = bool(_get(choice, "message", "refusal"))
            truncated = _get(choice, "finish_reason") == "length"
            usage = Usage(
                input_tokens=int(_get(response, "usage", "prompt_tokens") or 0),
                output_tokens=int(_get(response, "usage", "completion_tokens") or 0),
                cached_tokens=_get(response, "usage", "prompt_tokens_details", "cached_tokens"),
                reasoning_tokens=_get(response, "usage", "completion_tokens_details", "reasoning_tokens"),
            )
            returned = str(_get(response, "model") or self.model)
            result = envelope(
                system="s2.reasoning",
                body=s2_body(text, parsed, reasoning_tokens=usage.reasoning_tokens, effort=None),
                cost=self._cost(usage, response, returned),
                latency_ms=clock.ms,
                trace_ref=ref,
                provider=self.provider,
                model=returned,
                endpoint="POST /v1/chat/completions",
                status="incomplete" if truncated else "completed",
                response_id=_get(response, "id"),
            )
            annotate(result, "chat")
        return Decision(result, parse_answers(questions, parsed, refused=refused))

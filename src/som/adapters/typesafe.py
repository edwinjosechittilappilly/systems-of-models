"""TypeSafe Jev (``POST /v1/systemone``): a System 1 decision model with calibrated probabilities.

Plain HTTP through ``httpx``; the TypeSafe SDK is not required. Pass your own ``httpx.Client`` to reuse connection
pools and proxies. Answers keep Jev's probabilities; the envelope confidence is the lowest chosen-answer probability
(basis ``model_probability``), while each Choice/Score answer also keeps Jev's own ``confidence`` (a peakedness
statistic, not P(correct)).
"""

from __future__ import annotations

import os
import time
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from som.adapters._common import envelope, price, s1_confidence, timed
from som.envelope import Usage
from som.pricing import RateCard
from som.questions import (
    Answer,
    Choice,
    ChoiceAnswer,
    Predicate,
    PredicateAnswer,
    Question,
    Refusal,
    ScoreAnswer,
)
from som.systems import Decision, Input
from som.trace import annotate, span

DEFAULT_BASE_URL = "https://api.typesafe.ai"
_RETRY_STATUS = {429, 529}


def _question(question: Question) -> dict[str, Any]:
    if isinstance(question, Predicate):
        payload: dict[str, Any] = {"type": "noul", "instructions": question.instructions}
        if question.true_means or question.false_means:
            payload["criteria"] = {"true": question.true_means, "false": question.false_means}
        return payload
    if isinstance(question, Choice):
        return {
            "type": "choice",
            "instructions": question.instructions,
            "criteria": {option.value: option.description or option.value for option in question.options},
        }
    return {"type": "score", "instructions": question.instructions, "criteria": list(question.levels)}


def _state(input: Input) -> Any:
    if isinstance(input, (str, Mapping)):
        return input
    return {"conversation": list(input)}


def _answer(question: Question, raw: Mapping[str, Any]) -> Answer:
    kind = raw.get("type")
    if kind == "noul":
        return PredicateAnswer(question.name, float(raw["noul"]))
    if kind == "choice":
        return ChoiceAnswer(
            question.name,
            str(raw["choice"]),
            {str(k): float(v) for k, v in raw["probabilities"].items()},
            raw.get("confidence"),
        )
    if kind == "score":
        keys = sorted(raw["probabilities"], key=int)
        legend = raw.get("legend", {})
        return ScoreAnswer(
            question.name,
            float(raw["score"]),
            tuple(float(raw["probabilities"][k]) for k in keys),
            tuple(str(legend.get(k, k)) for k in keys),
            raw.get("confidence"),
        )
    return Refusal(question.name, "unspecified")


class TypeSafe:
    """System 1 adapter for TypeSafe Jev. ``model`` may be an alias (``jev-preview``) or a version (``jev-1.14.0``)."""

    system = "s1.decision"

    def __init__(
        self,
        model: str = "jev-latest",
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.Client | None = None,
        rate_card: RateCard | None = None,
        timeout: float = 60.0,
        max_retries: int = 4,
        long_context: bool = False,
    ) -> None:
        key = api_key or os.environ.get("TYPESAFE_API_KEY")
        if not key:
            raise ValueError("TypeSafe needs api_key= or the TYPESAFE_API_KEY environment variable")
        self.model, self.name = model, f"typesafe/{model}"
        self.rate_card, self.max_retries = rate_card, max_retries
        self._client = client or httpx.Client(timeout=timeout)
        self._url = base_url.rstrip("/") + "/v1/systemone"
        self._headers = {"Authorization": f"Bearer {key}"}
        if long_context:
            self._headers["TypeSafe-Danger-Zone-Long-Context"] = "true"

    def request_body(self, input: Input, questions: Sequence[Question]) -> dict[str, Any]:
        """The exact JSON sent to ``/v1/systemone``; log it to make any answer reproducible."""
        return {"model": self.model, "state": _state(input), "questions": {q.name: _question(q) for q in questions}}

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(self.max_retries + 1):
            response = self._client.post(self._url, json=body, headers=self._headers)
            if response.status_code not in _RETRY_STATUS or attempt == self.max_retries:
                response.raise_for_status()
                data: dict[str, Any] = response.json()
                return data
            delay = float(response.headers.get("retry-after", 0) or 0) or min(2.0**attempt, 30.0)
            time.sleep(delay)
        raise AssertionError("unreachable")

    def decide(self, input: Input, questions: Sequence[Question], *, trace_id: str | None = None) -> Decision:
        with span(f"decide {self.name}", trace_id=trace_id) as ref:
            with timed() as clock:
                data = self._post(self.request_body(input, questions))
            answers = {q.name: _answer(q, data["answers"][q.name]) for q in questions}
            usage = Usage(
                input_tokens=int(data["usage"]["input_tokens"]), output_tokens=int(data["usage"]["output_tokens"])
            )
            returned = str(data.get("model", self.model))
            confidence = s1_confidence(answers)
            result = envelope(
                system="s1.decision",
                body={"answers": [answers[q.name].to_contract() for q in questions]},
                cost=price("typesafe", returned, usage, rate_card=self.rate_card, fallback_model=self.model),
                latency_ms=clock.ms,
                trace_ref=ref,
                provider="typesafe",
                model=returned,
                endpoint="POST /v1/systemone",
                confidence=confidence,
                confidence_basis="model_probability" if confidence is not None else None,
            )
            annotate(result, "decide")
        return Decision(result, answers)

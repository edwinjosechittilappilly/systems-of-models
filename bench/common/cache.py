"""Content-addressed cache of every paid call, so runs replay for free and reproducibly.

Each entry is one JSON line in ``bench/cache/<namespace>.jsonl``: the SHA-256 of the canonical request payload, the
request itself, the response, and when it was recorded. ``mode="replay"`` refuses to call the network (a missing
entry is an error), ``mode="record"`` calls only on a miss, ``mode="refresh"`` always calls and appends.

:class:`CachedDecider` wraps any :class:`som.systems.Decider`. A replayed decision returns the recorded envelope
(its cost, latency and model are those of the original call), so cost accounting is identical on replay.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Literal

from som.envelope import Cost, CostItem, Envelope, Implementation, TraceRef, Usage
from som.questions import (
    Answer,
    ChoiceAnswer,
    PredicateAnswer,
    Question,
    Refusal,
    ScoreAnswer,
)
from som.systems import Decision, Input

Mode = Literal["replay", "record", "refresh"]
CACHE_DIR = Path(__file__).resolve().parents[1] / "cache"


class CacheMiss(LookupError):
    """Replay mode found no recorded response for a request."""


def request_key(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class JsonCache:
    """One namespace of cached request/response pairs. Thread-safe for appends."""

    def __init__(self, namespace: str, *, mode: Mode = "record", directory: Path = CACHE_DIR) -> None:
        self.mode = mode
        self.path = directory / f"{namespace}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, list[dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self.hits = self.misses = 0
        if self.path.exists():
            with self.path.open(encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        entry = json.loads(line)
                        self._entries.setdefault(entry["key"], []).append(entry)

    def get_or_call(self, payload: Any, call: Callable[[], Any], *, sample: int = 0) -> Any:
        """Return the cached response for ``payload`` (the ``sample``-th recording), calling ``call`` on a miss.

        ``sample`` > 0 asks for an independent repeat of the same request, e.g. to measure teacher variance.
        """
        key = request_key(payload)
        recorded = self._entries.get(key, [])
        if self.mode != "refresh" and sample < len(recorded):
            self.hits += 1
            return recorded[sample]["response"]
        if self.mode == "replay":
            raise CacheMiss(f"{self.path.name}: no recording #{sample} for request {key[:12]}")
        self.misses += 1
        response = call()
        entry = {"key": key, "request": payload, "response": response, "recorded_at": time.time()}
        with self._lock:
            self._entries.setdefault(key, []).append(entry)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        return response

    def __len__(self) -> int:
        return sum(len(v) for v in self._entries.values())


def answer_to_dict(answer: Answer) -> dict[str, Any]:
    if isinstance(answer, PredicateAnswer):
        return {"type": "predicate", "name": answer.name, "probability": answer.probability, "raw": answer.raw_value}
    if isinstance(answer, ChoiceAnswer):
        return {
            "type": "choice",
            "name": answer.name,
            "choice": answer.choice,
            "probabilities": answer.probabilities,
            "confidence": answer.confidence,
        }
    if isinstance(answer, ScoreAnswer):
        return {
            "type": "score",
            "name": answer.name,
            "score": answer.score,
            "probabilities": list(answer.probabilities),
            "labels": list(answer.labels),
            "confidence": answer.confidence,
        }
    return {"type": "refusal", "name": answer.name, "reason": answer.reason}


def answer_from_dict(data: dict[str, Any]) -> Answer:
    kind = data["type"]
    if kind == "predicate":
        return PredicateAnswer(data["name"], data["probability"], raw_value=data.get("raw"))
    if kind == "choice":
        return ChoiceAnswer(data["name"], data["choice"], dict(data["probabilities"]), data.get("confidence"))
    if kind == "score":
        return ScoreAnswer(
            data["name"],
            data["score"],
            tuple(data["probabilities"]),
            tuple(data["labels"]),
            data.get("confidence"),
        )
    return Refusal(data["name"], data.get("reason", "unspecified"))


def envelope_from_dict(data: dict[str, Any]) -> Envelope:
    """Rebuild an :class:`Envelope` from its ``to_dict()`` form (used for cache replay)."""
    cost = data["cost"]
    usage_raw = cost.get("usage")
    usage = None
    if usage_raw is not None:
        usage = Usage(
            input_tokens=usage_raw.get("input_tokens", 0),
            output_tokens=usage_raw.get("output_tokens", 0),
            cached_tokens=(usage_raw.get("input_tokens_details") or {}).get("cached_tokens"),
            reasoning_tokens=(usage_raw.get("output_tokens_details") or {}).get("reasoning_tokens"),
            tool_calls=usage_raw.get("tool_calls"),
            model_calls=usage_raw.get("model_calls"),
        )
    rebuilt = Envelope(
        system=data["system"],
        body=data["body"],
        cost=Cost(
            amount=cost["amount"],
            basis=cost["basis"],
            currency=cost.get("currency", "USD"),
            rate_card=cost.get("rate_card"),
            usage=usage,
            breakdown=[
                CostItem(i["system"], i["amount"], i["basis"], i.get("response_id")) for i in cost.get("breakdown", [])
            ],
        ),
        latency_ms=data["latency_ms"],
        trace_ref=TraceRef(**data["trace_ref"]),
        confidence=data.get("confidence"),
        confidence_basis=data.get("confidence_basis"),
        status=data.get("status", "completed"),
        implementation=Implementation(**data["implementation"]) if data.get("implementation") else None,
        metadata=data.get("metadata", {}),
    )
    rebuilt.id = data["id"]
    rebuilt.system_version = data["system_version"]
    rebuilt.created_at = data.get("created_at", rebuilt.created_at)
    return rebuilt


def _input_payload(input: Input) -> Any:
    return input if isinstance(input, (str, dict)) else list(input)


class CachedDecider:
    """A Decider that records every decision and replays it on repeat (envelope cost and latency included)."""

    def __init__(self, inner: Any, cache: JsonCache, *, pin_model: bool = True) -> None:
        self.inner, self.cache = inner, cache
        self.name, self.system = inner.name, inner.system
        self.pinned_model: str | None = None
        self.pin_model = pin_model

    def decide(
        self, input: Input, questions: Sequence[Question], *, trace_id: str | None = None, sample: int = 0
    ) -> Decision:
        payload = {
            "decider": self.name,
            "input": _input_payload(input),
            "questions": [q.to_contract() | _question_extras(q) for q in questions],
        }

        def call() -> dict[str, Any]:
            decision = self.inner.decide(input, questions, trace_id=trace_id)
            return {
                "envelope": decision.envelope.to_dict(),
                "answers": {name: answer_to_dict(a) for name, a in decision.answers.items()},
            }

        recorded = self.cache.get_or_call(payload, call, sample=sample)
        envelope = envelope_from_dict(recorded["envelope"])
        model = envelope.implementation.model if envelope.implementation else None
        if self.pin_model and model is not None:
            if self.pinned_model is None:
                self.pinned_model = model
            elif model != self.pinned_model:
                raise RuntimeError(f"{self.name}: model changed mid-run ({self.pinned_model} -> {model})")
        if trace_id is not None:
            envelope.trace_ref = TraceRef(trace_id=trace_id, span_id=envelope.trace_ref.span_id)
        return Decision(envelope, {name: answer_from_dict(a) for name, a in recorded["answers"].items()})


def _question_extras(question: Question) -> dict[str, Any]:
    """Fields that change the request but are not in the contract form (Jev noul criteria, option descriptions)."""
    extras: dict[str, Any] = {}
    true_means = getattr(question, "true_means", None)
    false_means = getattr(question, "false_means", None)
    if true_means or false_means:
        extras["criteria"] = {"true": true_means, "false": false_means}
    return extras


__all__ = [
    "CacheMiss",
    "CachedDecider",
    "JsonCache",
    "answer_from_dict",
    "answer_to_dict",
    "envelope_from_dict",
    "request_key",
]

"""The response envelope shared by every system, as Python dataclasses.

``Envelope.to_dict()`` produces JSON that validates against ``schemas/envelope.schema.json`` and, given a matching
``body``, against the system schema named by ``system`` (``s1.decision`` -> ``s1-decision``).
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from som import schemas

CONTRACT_VERSION = "1.1.0"
"""Version of the contracts this package implements; sent as ``system_version``."""

SystemId = Literal["s1.decision", "s2.reasoning", "s3.search", "s4.agentic", "s5.self_evolving"]
ConfidenceBasis = Literal[
    "model_probability",
    "distribution_peakedness",
    "verifier_score",
    "ensemble_agreement",
    "outcome_check",
    "self_report",
    "none",
]
CostBasis = Literal["billed", "list_price", "local"]
Status = Literal["completed", "incomplete", "escalated", "failed"]

_SCHEMA_FOR_SYSTEM = {
    "s1.decision": "s1-decision",
    "s2.reasoning": "s2-reasoning",
    "s3.search": "s3-search",
    "s4.agentic": "s4-agentic",
    "s5.self_evolving": "s5-self-evolving",
}


def new_id(prefix: str) -> str:
    """Return a random identifier such as ``dec_3f9a...``."""
    return f"{prefix}_{secrets.token_hex(8)}"


def _drop_none(mapping: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if value is not None}


@dataclass
class Usage:
    """Token accounting with OpenAI Responses field names."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int | None = None
    reasoning_tokens: int | None = None
    tool_calls: int | None = None
    model_calls: int | None = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: Usage) -> Usage:
        def add(a: int | None, b: int | None) -> int | None:
            return None if a is None and b is None else (a or 0) + (b or 0)

        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cached_tokens=add(self.cached_tokens, other.cached_tokens),
            reasoning_tokens=add(self.reasoning_tokens, other.reasoning_tokens),
            tool_calls=add(self.tool_calls, other.tool_calls),
            model_calls=add(self.model_calls, other.model_calls),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }
        if self.cached_tokens is not None:
            data["input_tokens_details"] = {"cached_tokens": self.cached_tokens}
        if self.reasoning_tokens is not None:
            data["output_tokens_details"] = {"reasoning_tokens": self.reasoning_tokens}
        if self.tool_calls is not None:
            data["tool_calls"] = self.tool_calls
        if self.model_calls is not None:
            data["model_calls"] = self.model_calls
        return data


@dataclass
class CostItem:
    system: str
    amount: float
    response_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_none({"system": self.system, "amount": self.amount, "response_id": self.response_id})


@dataclass
class Cost:
    """Cost of one call. ``basis`` says whether the amount was billed, priced from a rate card, or local."""

    amount: float
    basis: CostBasis
    currency: str = "USD"
    rate_card: str | None = None
    usage: Usage | None = None
    breakdown: list[CostItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"amount": self.amount, "currency": self.currency, "basis": self.basis}
        if self.rate_card is not None:
            data["rate_card"] = self.rate_card
        if self.usage is not None:
            data["usage"] = self.usage.to_dict()
        if self.breakdown:
            data["breakdown"] = [item.to_dict() for item in self.breakdown]
        return data


@dataclass
class TraceRef:
    """W3C Trace Context identifiers (32 and 16 lower-case hex characters)."""

    trace_id: str
    span_id: str | None = None

    @classmethod
    def new(cls, trace_id: str | None = None) -> TraceRef:
        return cls(trace_id=trace_id or secrets.token_hex(16), span_id=secrets.token_hex(8))

    def to_dict(self) -> dict[str, Any]:
        return _drop_none({"trace_id": self.trace_id, "span_id": self.span_id})


@dataclass
class Implementation:
    provider: str
    model: str
    endpoint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _drop_none({"provider": self.provider, "model": self.model, "endpoint": self.endpoint})


@dataclass
class Threshold:
    metric: str
    operator: Literal["lt", "le", "gt", "ge", "eq", "ne", "outside"]
    value: float
    observed: float | None = None
    source: Literal["caller", "system_default", "meta_layer"] = "caller"

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "operator": self.operator,
            "value": self.value,
            "observed": self.observed,
            "source": self.source,
        }


@dataclass
class Escalation:
    """A handoff from one system to another, matching ``schemas/escalation.schema.json``."""

    escalate_to: str
    reason: str
    threshold: Threshold
    question_names: list[str] = field(default_factory=list)
    detail: str | None = None
    context_mode: Literal["full", "summary", "reference"] = "full"
    prior_answers: list[dict[str, Any]] = field(default_factory=list)
    performed: bool = False
    downstream_response_id: str | None = None
    escalation_id: str = field(default_factory=lambda: new_id("esc"))

    def to_dict(self) -> dict[str, Any]:
        reason: dict[str, Any] = {"code": self.reason}
        if self.detail:
            reason["detail"] = self.detail
        if self.question_names:
            reason["question_names"] = self.question_names
        handoff: dict[str, Any] = {"mode": self.context_mode}
        if self.prior_answers:
            handoff["prior_answers"] = self.prior_answers
        data: dict[str, Any] = {
            "escalation_id": self.escalation_id,
            "escalate_to": {"system": self.escalate_to},
            "reason": reason,
            "threshold": self.threshold.to_dict(),
            "context_handoff": handoff,
            "mode": "performed" if self.performed else "recommended",
        }
        if self.downstream_response_id is not None:
            data["downstream_response_id"] = self.downstream_response_id
        return data


@dataclass
class Envelope:
    """One system response: what answered, how sure it was, what it cost, how long it took, where its trace is."""

    system: SystemId
    body: dict[str, Any]
    cost: Cost
    latency_ms: float
    trace_ref: TraceRef
    confidence: float | None = None
    confidence_basis: ConfidenceBasis | None = None
    status: Status = "completed"
    escalation: Escalation | None = None
    implementation: Implementation | None = None
    error: tuple[str, str] | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    id: str = field(default_factory=lambda: new_id("resp"))
    system_version: str = CONTRACT_VERSION
    created_at: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "object": "system.response",
            "system": self.system,
            "system_version": self.system_version,
            "created_at": self.created_at,
            "status": self.status,
            "confidence": self.confidence,
            "cost": self.cost.to_dict(),
            "latency_ms": round(self.latency_ms, 3),
            "trace_ref": self.trace_ref.to_dict(),
            "body": self.body,
        }
        if self.confidence is not None:
            data["confidence_basis"] = self.confidence_basis or "none"
        if self.escalation is not None:
            data["escalation"] = self.escalation.to_dict()
        if self.implementation is not None:
            data["implementation"] = self.implementation.to_dict()
        if self.error is not None:
            data["error"] = {"code": self.error[0], "message": self.error[1]}
        if self.metadata:
            data["metadata"] = dict(self.metadata)
        return data

    def validate(self) -> None:
        """Raise ``jsonschema.ValidationError`` unless this envelope matches its system's response contract."""
        name = _SCHEMA_FOR_SYSTEM.get(self.system)
        if name is None:
            schemas.validate(self.to_dict(), "envelope")
        else:
            schemas.validate({"response": self.to_dict()}, name)

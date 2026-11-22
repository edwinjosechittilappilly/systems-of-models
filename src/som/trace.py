"""Trace identifiers, optional OpenTelemetry spans, and a trace store the compile loop reads.

Every envelope carries W3C trace/span IDs. With ``opentelemetry-api`` installed and a tracer provider configured,
each system call is also a span with OpenTelemetry GenAI attributes (``gen_ai.*``, Development status in the
semantic conventions), nested under whatever span is current. Without OpenTelemetry the IDs are still generated, so
envelopes from one request share a ``trace_id``.

Prompt and response text never goes into spans. The :class:`TraceStore` keeps what you hand it; keep it local.
"""

from __future__ import annotations

import copy
import importlib
import json
import secrets
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from som.envelope import Envelope, TraceRef

_otel: Any
try:  # optional dependency; imported dynamically so type checking does not depend on whether it is installed
    _otel = importlib.import_module("opentelemetry.trace")
except ImportError:
    _otel = None

_TRACER_NAME = "systems-of-models"


def _remote_parent(trace_id: str) -> Any:
    """An OpenTelemetry context whose parent is a remote span in ``trace_id``, so a new span joins that trace."""
    parent = _otel.SpanContext(
        trace_id=int(trace_id, 16),
        span_id=int(secrets.token_hex(8), 16),
        is_remote=True,
        trace_flags=_otel.TraceFlags(_otel.TraceFlags.SAMPLED),
    )
    return _otel.set_span_in_context(_otel.NonRecordingSpan(parent))


@contextmanager
def span(name: str, *, trace_id: str | None = None) -> Iterator[TraceRef]:
    """Open a span for one system call and yield its :class:`TraceRef`.

    The span joins the current OpenTelemetry span if there is one; otherwise it joins ``trace_id`` when given (so the
    calls of one cascade share a trace); otherwise it starts a new trace. Without OpenTelemetry the same rule applies
    to the generated IDs.
    """
    if _otel is not None:
        current = _otel.get_current_span().get_span_context()
        context = None if current.is_valid or trace_id is None else _remote_parent(trace_id)
        with _otel.get_tracer(_TRACER_NAME).start_as_current_span(name, context=context) as otel_span:
            ids = otel_span.get_span_context()
            if ids.is_valid:
                yield TraceRef(trace_id=format(ids.trace_id, "032x"), span_id=format(ids.span_id, "016x"))
                return
            # No SDK configured: the API hands out invalid no-op spans, so fall through to generated IDs.
            inherited = format(current.trace_id, "032x") if current.is_valid else None
            yield TraceRef(trace_id=inherited or trace_id or secrets.token_hex(16), span_id=secrets.token_hex(8))
            return
    yield TraceRef(trace_id=trace_id or secrets.token_hex(16), span_id=secrets.token_hex(8))


def annotate_gate(served_by: str, escalation_reason: str | None) -> None:
    """Record a gate's outcome on the current (gate) span."""
    if _otel is None:
        return
    current = _otel.get_current_span()
    if not current.is_recording():
        return
    attributes: dict[str, Any] = {"som.gate.served_by": served_by}
    if escalation_reason is not None:
        attributes["som.escalation.reason"] = escalation_reason
    current.set_attributes(attributes)


def annotate(envelope: Envelope, operation: str) -> None:
    """Attach GenAI semantic-convention attributes for ``envelope`` to the current span, if any."""
    if _otel is None:
        return
    current = _otel.get_current_span()
    if not current.is_recording():
        return
    attributes: dict[str, Any] = {"gen_ai.operation.name": operation, "som.system": envelope.system}
    if envelope.implementation is not None:
        attributes["gen_ai.provider.name"] = envelope.implementation.provider
        attributes["gen_ai.response.model"] = envelope.implementation.model
    attributes["gen_ai.response.id"] = envelope.id
    usage = envelope.cost.usage
    if usage is not None:
        attributes["gen_ai.usage.input_tokens"] = usage.input_tokens
        attributes["gen_ai.usage.output_tokens"] = usage.output_tokens
        if usage.reasoning_tokens is not None:
            attributes["gen_ai.usage.reasoning.output_tokens"] = usage.reasoning_tokens
    if envelope.cost.amount is not None:
        attributes["som.cost.amount"] = envelope.cost.amount
    attributes["som.cost.basis"] = envelope.cost.basis
    attributes["som.status"] = envelope.status
    if envelope.confidence is not None:
        attributes["som.confidence"] = envelope.confidence
    current.set_attributes(attributes)


class TraceStore:
    """Append-only record of envelopes and agent events (tool calls), optionally mirrored to a JSONL file."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.records: list[dict[str, Any]] = []
        self.path = Path(path) if path is not None else None

    def add(self, kind: str, **data: Any) -> dict[str, Any]:
        """Record an event. Nested data is deep-copied, so later changes to the caller's objects do not leak in."""
        record = {"kind": kind, "at": time.time(), **copy.deepcopy(data)}
        self.records.append(record)
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, default=str) + "\n")
        return record

    def add_envelope(self, envelope: Envelope, **data: Any) -> dict[str, Any]:
        return self.add("envelope", envelope=envelope.to_dict(), **data)

    def add_tool_call(self, tool: str, arguments: dict[str, Any], *, trace_id: str, **data: Any) -> dict[str, Any]:
        return self.add("tool_call", tool=tool, arguments=arguments, trace_id=trace_id, **data)

    def of_kind(self, kind: str) -> list[dict[str, Any]]:
        return [record for record in self.records if record["kind"] == kind]

    @classmethod
    def load(cls, path: str | Path) -> TraceStore:
        store = cls()
        with Path(path).open(encoding="utf-8") as handle:
            store.records = [json.loads(line) for line in handle if line.strip()]
        store.path = Path(path)
        return store

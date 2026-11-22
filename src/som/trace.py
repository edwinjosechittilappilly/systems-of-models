"""Trace identifiers, optional OpenTelemetry spans, and a trace store the compile loop reads.

Every envelope carries W3C trace/span IDs. With ``opentelemetry-api`` installed and a tracer provider configured,
each system call is also a span with OpenTelemetry GenAI attributes (``gen_ai.*``, Development status in the
semantic conventions), nested under whatever span is current. Without OpenTelemetry the IDs are still generated, so
envelopes from one request share a ``trace_id``.

Prompt and response text never goes into spans. The :class:`TraceStore` keeps what you hand it; keep it local.
"""

from __future__ import annotations

import json
import secrets
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from som.envelope import Envelope, TraceRef

try:  # pragma: no cover - exercised only when the optional dependency is installed
    from opentelemetry import trace as _otel
except ImportError:  # pragma: no cover
    _otel = None

_TRACER_NAME = "systems-of-models"


def _current_trace_id() -> str | None:
    if _otel is None:
        return None
    context = _otel.get_current_span().get_span_context()
    return format(context.trace_id, "032x") if context.is_valid else None


@contextmanager
def span(name: str, *, trace_id: str | None = None) -> Iterator[TraceRef]:
    """Open a span for one system call and yield its :class:`TraceRef`.

    Reuses ``trace_id`` when given (to keep a cascade in one trace), else the current OpenTelemetry trace, else a
    fresh random one.
    """
    if _otel is not None:
        tracer = _otel.get_tracer(_TRACER_NAME)
        with tracer.start_as_current_span(name) as otel_span:
            context = otel_span.get_span_context()
            if context.is_valid:
                yield TraceRef(trace_id=format(context.trace_id, "032x"), span_id=format(context.span_id, "016x"))
                return
            yield TraceRef(trace_id=trace_id or secrets.token_hex(16), span_id=secrets.token_hex(8))
            return
    yield TraceRef(trace_id=trace_id or _current_trace_id() or secrets.token_hex(16), span_id=secrets.token_hex(8))


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
        record = {"kind": kind, "at": time.time(), **data}
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

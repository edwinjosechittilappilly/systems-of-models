"""Agent traces persisted as ordered ``agent_step`` records in a local TraceStore."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from som.trace import TraceStore


@dataclass
class AgentStep:
    """One tool invocation and its returned value."""

    tool: str
    arguments: dict[str, Any]
    result: Any


@dataclass
class AgentTrace:
    """A single agent run, including its original input and ordered steps."""

    trace_id: str
    input: Any
    steps: list[AgentStep] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def save(self, store: TraceStore) -> None:
        """Append this trace to a store; inputs and results may contain sensitive data."""
        steps: list[AgentStep | None] = list(self.steps) or [None]
        for index, step in enumerate(steps):
            store.add(
                "agent_step",
                trace_id=self.trace_id,
                input=self.input,
                metadata=self.metadata,
                index=index,
                tool=step.tool if step else None,
                arguments=step.arguments if step else None,
                result=step.result if step else None,
            )

    @classmethod
    def load(cls, store: TraceStore) -> list[AgentTrace]:
        """Reconstruct traces from agent-step records in their stored order."""
        traces: dict[str, AgentTrace] = {}
        for record in store.of_kind("agent_step"):
            trace_id = record["trace_id"]
            if trace_id not in traces:
                traces[trace_id] = cls(trace_id, record["input"], metadata=record.get("metadata", {}))
            trace = traces[trace_id]
            if record.get("tool") is not None:
                trace.steps.append(AgentStep(record["tool"], record["arguments"], record.get("result")))
        return list(traces.values())


def save_traces(traces: list[AgentTrace], store: TraceStore) -> None:
    """Append a collection of traces to a store."""
    for trace in traces:
        trace.save(store)


def load_traces(store: TraceStore) -> list[AgentTrace]:
    """Load all agent traces from a store."""
    return AgentTrace.load(store)

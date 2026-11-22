"""Mine recurring trace decisions with explicit, empirical rejection rules.

Support counts observations (called traces for branches); copied values require an 80%
verbatim input match, and free text has at least ten observations and an 80% distinct
ratio, or exceeds the cardinality limit. Functional dependencies use majority
prediction on overlapping trace IDs, at 99% consistency. These are heuristics, not
proofs of causality; retrieval matches must identify a unique returned item.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from som.compile.traces import AgentTrace


@dataclass
class Example:
    """An observed decision and its originating input."""

    trace_id: str
    input: Any
    value: Any
    title: str | None = None


@dataclass
class Candidate:
    """A possible decision point, with observations and an optional rejection reason."""

    kind: str
    name: str
    tool: str
    argument: str | None
    examples: list[Example] = field(default_factory=list)
    values: list[Any] = field(default_factory=list)
    support: int = 0
    reason: str | None = None
    determinant: str | None = None


@dataclass
class MiningReport:
    """Accepted and rejected candidates, including reasons for every rejection."""

    accepted: list[Candidate]
    rejected: list[Candidate]

    def to_rows(self) -> list[dict[str, Any]]:
        """Return flat, CSV-writer-compatible rows for all candidates."""
        return [
            {
                "name": candidate.name,
                "kind": candidate.kind,
                "tool": candidate.tool,
                "argument": candidate.argument,
                "support": candidate.support,
                "cardinality": len(candidate.values),
                "values": json.dumps(candidate.values, ensure_ascii=False),
                "accepted": candidate.reason is None,
                "reason": candidate.reason,
                "determinant": candidate.determinant,
            }
            for candidate in [*self.accepted, *self.rejected]
        ]


def _key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _copied(value: Any, source: Any) -> bool:
    if isinstance(source, str):
        return (
            isinstance(value, (str, int, float))
            and not isinstance(value, bool)
            and bool(str(value))
            and str(value) in source
        )
    if isinstance(source, dict):
        return any(_copied(value, item) for item in source.values())
    if isinstance(source, list):
        return any(_copied(value, item) for item in source)
    return type(value) is type(source) and value == source


def _retrieved(trace: AgentTrace, index: int) -> tuple[Any, str | None] | None:
    result = trace.steps[index].result
    if (
        not isinstance(result, list)
        or not result
        or not all(isinstance(item, dict) and "id" in item for item in result)
    ):
        return None
    for later in trace.steps[index + 1 :]:
        scores = [
            sum(key in later.arguments and _key(value) == _key(later.arguments[key]) for key, value in item.items())
            for item in result
        ]
        best = max(scores)
        if best and scores.count(best) == 1:
            item = result[scores.index(best)]
            title = item.get("title", item.get("label"))
            return item["id"], str(title) if title is not None else None
    return None


def _dependent(candidate: Candidate, determinant: Candidate, min_support: int) -> bool:
    # A trace with repeated, different observations does not define a single trace-level value.
    def per_trace(examples: list[Example]) -> dict[str, str]:
        values: dict[str, set[str]] = defaultdict(set)
        for example in examples:
            values[example.trace_id].add(_key(example.value))
        return {trace_id: next(iter(items)) for trace_id, items in values.items() if len(items) == 1}

    left = per_trace(determinant.examples)
    right = per_trace(candidate.examples)
    common = left.keys() & right.keys()
    if len(common) < min_support or len(common) < len(right) * 0.99:
        return False
    groups: dict[str, Counter[str]] = defaultdict(Counter)
    for trace_id in common:
        groups[left[trace_id]][right[trace_id]] += 1
    return sum(max(counts.values()) for counts in groups.values()) / len(common) >= 0.99


def mine(
    traces: Iterable[AgentTrace],
    *,
    min_support: int,
    max_cardinality: int = 255,
    free_text_ratio: float = 0.8,
    copied_ratio: float = 0.8,
) -> MiningReport:
    """Mine tool arguments, tool-call branches and uniquely inferred retrieval choices."""
    if min_support < 1 or max_cardinality < 1:
        raise ValueError("min_support and max_cardinality must be positive")
    if not 0 < free_text_ratio <= 1 or not 0 < copied_ratio <= 1:
        raise ValueError("ratios must be in (0, 1]")
    traces = list(traces)
    if len({trace.trace_id for trace in traces}) != len(traces):
        raise ValueError("trace IDs must be unique")
    candidates: dict[tuple[str, str, str | None], Candidate] = {}

    def add(kind: str, tool: str, argument: str | None, example: Example) -> None:
        key = (kind, tool, argument)
        if key not in candidates:
            name = f"{tool}.{argument}" if argument is not None else f"{tool}.{kind}"
            candidates[key] = Candidate(kind, name, tool, argument)
        candidates[key].examples.append(example)

    tools = sorted({step.tool for trace in traces for step in trace.steps})
    for trace in traces:
        called = {step.tool for step in trace.steps}
        for tool in tools:
            add("branch", tool, None, Example(trace.trace_id, trace.input, tool in called))
        for index, step in enumerate(trace.steps):
            for argument, value in step.arguments.items():
                add("tool_argument", step.tool, argument, Example(trace.trace_id, trace.input, value))
            choice = _retrieved(trace, index)
            if choice is not None:
                value, title = choice
                add("retrieval_choice", step.tool, None, Example(trace.trace_id, trace.input, value, title))

    accepted: list[Candidate] = []
    rejected: list[Candidate] = []
    # A retrieval choice is preferred to its downstream consequences; branches precede arguments.
    order = {"retrieval_choice": 0, "branch": 1, "tool_argument": 2}
    for candidate in sorted(candidates.values(), key=lambda item: (order[item.kind], item.name)):
        distinct: dict[str, Any] = {}
        for example in candidate.examples:
            distinct.setdefault(_key(example.value), example.value)
        candidate.values = list(distinct.values())
        candidate.support = (
            sum(example.value is True for example in candidate.examples)
            if candidate.kind == "branch"
            else len(candidate.examples)
        )
        if candidate.support < min_support:
            candidate.reason = "rare"
        elif len(distinct) < 2:
            candidate.reason = "constant"
        elif (
            candidate.kind == "tool_argument"
            and sum(_copied(example.value, example.input) for example in candidate.examples) / len(candidate.examples)
            >= copied_ratio
        ):
            candidate.reason = "copied_from_input"
        elif len(distinct) > max_cardinality or (
            candidate.kind == "tool_argument"
            and len(candidate.examples) >= 10
            and len(distinct) / len(candidate.examples) >= free_text_ratio
        ):
            candidate.reason = "free_text"
        else:
            for other in accepted:
                if _dependent(candidate, other, min_support):
                    candidate.reason = "functional_dependency"
                    candidate.determinant = other.name
                    break
        (rejected if candidate.reason else accepted).append(candidate)
    return MiningReport(accepted, rejected)

"""Mine recurring trace decisions with explicit, empirical rejection rules.

Support is the number of observations that differ from the most common value (the minority count for binary
candidates). A value is *copied* when every scalar in it appears verbatim in the run's input, or when it was looked
up: its scalars equal whole field values in earlier tool results of the same run and no other observed value of the
candidate is there too (a list of options to choose from is not a lookup; booleans and None never count). 80% of
observations must be copied to reject. The default free-text rule rejects a distinct/occurrence ratio of at least
0.8 with ten or more observations, or cardinality above the limit. Functional dependencies use leave-one-out
prediction on overlapping traces; all are heuristics.
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
    """An observed decision, its originating input and what the agent had read before deciding."""

    trace_id: str
    input: Any
    value: Any
    title: str | None = None
    context: list[Any] = field(default_factory=list)
    """Results of the tool calls made before this decision in the same run."""


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
    """Accepted and rejected candidates and the number of ambiguous retrieval traces."""

    accepted: list[Candidate]
    rejected: list[Candidate]
    ambiguous_retrieval_count: int = 0

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
    """True when every scalar in ``value`` appears verbatim in ``source`` (text, or nested JSON-like data)."""
    if isinstance(value, dict):
        return bool(value) and all(_copied(item, source) for item in value.values())
    if isinstance(value, list):
        return bool(value) and all(_copied(item, source) for item in value)
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


def _fields(value: Any) -> set[str]:
    """Keys of the whole scalar field values in JSON-like data; booleans and None never identify a lookup."""
    if isinstance(value, dict):
        return set().union(*(_fields(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_fields(item) for item in value))
    if value is None or isinstance(value, bool) or value == "":
        return set()
    return {_key(value)}


def _scalars(value: Any) -> set[str] | None:
    """Keys of the scalars a value is built from, or None when it contains a boolean or None."""
    if isinstance(value, (dict, list)):
        parts = [_scalars(item) for item in (value.values() if isinstance(value, dict) else value)]
        if not parts or any(part is None for part in parts):
            return None
        return set().union(*(part for part in parts if part is not None))
    return _fields(value) or None


def _looked_up(example: Example, others: list[set[str]]) -> bool:
    """The value is in an earlier tool result as whole field values, and no other observed value is: the results
    point to this one value (a lookup) rather than list options to choose from."""
    mine = _scalars(example.value)
    if not mine or not example.context:
        return False
    fields = _fields(example.context)
    return mine <= fields and not any(other <= fields for other in others if other != mine)


def _id_argument(name: str) -> bool:
    return name == "id" or name.endswith(("_id", "_ids"))


def _retrieved(trace: AgentTrace, index: int) -> tuple[tuple[Any, str | None] | None, bool]:
    result = trace.steps[index].result
    if (
        not isinstance(result, list)
        or not result
        or not all(isinstance(item, dict) and "id" in item for item in result)
    ):
        return None, False
    ambiguous = False
    for later in trace.steps[index + 1 :]:
        # A later call that passes the item's id as an id argument (get_policy(entry_id=...)) follows that item.
        later_ids = {_key(value) for name, value in later.arguments.items() if _id_argument(name)}
        scores = [
            sum(key in later.arguments and _key(value) == _key(later.arguments[key]) for key, value in item.items())
            + int(_key(item["id"]) in later_ids)
            for item in result
        ]
        best = max(scores)
        if best and scores.count(best) == 1:
            item = result[scores.index(best)]
            title = item.get("title", item.get("label"))
            return (item["id"], str(title) if title is not None else None), False
        if best:
            ambiguous = True
    return None, ambiguous


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
    # A determinant must cover at least half the candidate's unambiguous traces.
    if len(common) < min_support or len(common) < len(right) * 0.5:
        return False
    groups: dict[str, Counter[str]] = defaultdict(Counter)
    for trace_id in common:
        groups[left[trace_id]][right[trace_id]] += 1
    correct = 0
    for counts in groups.values():
        for value, count in counts.items():
            # Predict each held-out observation using only the other observations.
            remaining = count - 1
            other_max = max((n for key, n in counts.items() if key != value), default=0)
            if remaining > other_max:
                correct += count
    return correct / len(common) >= 0.99


def mine(
    traces: Iterable[AgentTrace],
    *,
    min_support: int,
    min_minority: int | None = None,
    max_cardinality: int = 255,
    max_distinct_ratio: float = 0.8,
    copied_ratio: float = 0.8,
) -> MiningReport:
    """Mine decisions from traces.

    Binary candidates require ``min_minority`` observations of each value,
    defaulting to ``min_support``. Larger choices require ``min_support`` total
    observations. At least ten observations are required for the distinct-ratio
    free-text rule; the default rejection threshold is 0.8 (inclusive).
    Dependencies require at least ``min_support`` shared traces, at least half
    the candidate's traces, and 99% leave-one-out majority accuracy. The report
    counts distinct traces with an unresolved positive-score retrieval tie.
    """
    if min_support < 1 or max_cardinality < 1 or (min_minority is not None and min_minority < 1):
        raise ValueError("min_support, min_minority and max_cardinality must be positive")
    if not 0 < max_distinct_ratio <= 1 or not 0 < copied_ratio <= 1:
        raise ValueError("ratios must be in (0, 1]")
    if min_minority is None:
        min_minority = min_support
    traces = list(traces)
    if len({trace.trace_id for trace in traces}) != len(traces):
        raise ValueError("trace IDs must be unique")
    candidates: dict[tuple[str, str, str | None], Candidate] = {}
    ambiguous_retrieval_traces: set[str] = set()

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
            context = [earlier.result for earlier in trace.steps[:index] if earlier.result is not None]
            for argument, value in step.arguments.items():
                add("tool_argument", step.tool, argument, Example(trace.trace_id, trace.input, value, context=context))
            choice, ambiguous = _retrieved(trace, index)
            if ambiguous:
                ambiguous_retrieval_traces.add(trace.trace_id)
            if choice is not None:
                value, title = choice
                add("retrieval_choice", step.tool, None, Example(trace.trace_id, trace.input, value, title))

    accepted: list[Candidate] = []
    rejected: list[Candidate] = []
    # A retrieval choice is preferred to its downstream consequences; branches precede arguments.
    order = {"retrieval_choice": 0, "branch": 1, "tool_argument": 2}
    for candidate in sorted(candidates.values(), key=lambda item: (order[item.kind], item.name)):
        distinct: dict[str, Any] = {}
        counts: Counter[str] = Counter()
        for example in candidate.examples:
            key = _key(example.value)
            distinct.setdefault(key, example.value)
            counts[key] += 1
        candidate.values = list(distinct.values())
        # Support = observations that differ from the most common value. For two values this is the minority count;
        # for many values it keeps singleton classes of a real judgement while rejecting near-constant arguments.
        candidate.support = len(candidate.examples) - max(counts.values())
        copied = 0.0
        if candidate.kind == "tool_argument":
            others = [scalars for scalars in map(_scalars, candidate.values) if scalars]
            copied = sum(_copied(e.value, e.input) or _looked_up(e, others) for e in candidate.examples)
            copied /= len(candidate.examples)
        if copied >= copied_ratio:
            candidate.reason = "copied_from_context"
        elif len(distinct) > max_cardinality or (
            len(candidate.examples) >= 10 and len(distinct) / len(candidate.examples) >= max_distinct_ratio
        ):
            candidate.reason = "free_text"
        elif len(distinct) < 2:
            candidate.reason = "constant"
        elif candidate.support < (min_minority if len(distinct) == 2 else min_support):
            candidate.reason = "rare"
        else:
            for other in accepted:
                if _dependent(candidate, other, min_support):
                    candidate.reason = "functional_dependency"
                    candidate.determinant = other.name
                    break
        (rejected if candidate.reason else accepted).append(candidate)
    return MiningReport(accepted, rejected, len(ambiguous_retrieval_traces))

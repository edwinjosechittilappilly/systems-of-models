"""Convert published episodes and extract causally bounded tool-argument decisions.

A decision is made immediately before the assistant message containing the call.
Calls in the same message therefore share a state: neither sibling calls nor their
results are visible. Only tool results with a recorded earlier message index are
included. State retains the most recent 20 transcript messages and 20 results,
with each text or JSON value capped at 2,000 characters, identically for all
methods consuming the instance.

The miner's branch is an episode-wide "ever called" label, not a decision at a
known boundary. Neither a positive nor a negative can be assigned a common,
causally valid boundary from these traces, so branch candidates produce no
evaluable instances. Retrieval choices likewise lack a predecision boundary here.
"""

from __future__ import annotations

import json
from typing import Any

from bench.e3b.data import Episode
from som.compile import AgentStep, AgentTrace, Candidate

_MAX_ITEMS = 20
_MAX_CHARS = 2000


def _bounded(value: Any) -> Any:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(encoded) <= _MAX_CHARS:
        return value
    return {"truncated_json": encoded[:_MAX_CHARS]}


def to_trace(episode: Episode) -> AgentTrace:
    """Use user turns as the environment input and preserve ordered tool calls."""
    return AgentTrace(
        trace_id=episode.episode_id,
        input="\n".join(f"user: {turn.content}" for turn in episode.turns if turn.role == "user" and turn.content),
        steps=[
            AgentStep(call.name, call.arguments, call.result)
            for turn in episode.turns
            if turn.role == "assistant"
            for call in turn.tool_calls
        ],
        metadata={
            "episode_id": episode.episode_id,
            "task_id": episode.task_id,
            "model": episode.model,
            "domain": episode.domain,
            "trial": episode.trial,
        },
    )


def _gold(episode: Episode, candidate: Candidate) -> Any:
    values = [
        action["arguments"][candidate.argument]
        for action in episode.gold_actions
        if action.get("name") == candidate.tool
        and action.get("requestor", "assistant") == "assistant"
        and isinstance(action.get("arguments"), dict)
        and candidate.argument in action["arguments"]
    ]
    if not values:
        return None
    keys = {json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for value in values}
    return values[0] if len(keys) == 1 else None


def instances(episode: Episode, candidate: Candidate) -> list[dict[str, Any]]:
    """Return every observable argument occurrence; ambiguous gold is ``None``."""
    if candidate.kind != "tool_argument" or candidate.argument is None:
        return []

    rows: list[dict[str, Any]] = []
    transcript: list[dict[str, str]] = []
    prior_calls = []
    gold = _gold(episode, candidate)
    for turn in episode.turns:
        matching = [
            call
            for call in turn.tool_calls
            if turn.role == "assistant" and call.name == candidate.tool and candidate.argument in call.arguments
        ]
        if matching:
            observed = sorted(
                (call for call in prior_calls if call.result_index is not None and call.result_index < turn.index),
                key=lambda call: call.result_index,
            )
            state = {
                "transcript": transcript[-_MAX_ITEMS:],
                "tool_results": [
                    {"tool": call.name, "arguments": _bounded(call.arguments), "result": _bounded(call.result)}
                    for call in observed[-_MAX_ITEMS:]
                ],
            }
            for call in matching:
                rows.append(
                    {
                        "episode_id": episode.episode_id,
                        "task_id": episode.task_id,
                        "model": episode.model,
                        "domain": episode.domain,
                        "candidate": candidate.name,
                        "teacher": call.arguments[candidate.argument],
                        "gold": gold,
                        "state": state,
                    }
                )
        if turn.role in ("user", "assistant") and turn.content:
            transcript.append({"role": turn.role, "content": turn.content[-_MAX_CHARS:]})
        if turn.role == "assistant":
            prior_calls.extend(turn.tool_calls)
    return rows


def user_tools_only(state: dict[str, Any]) -> dict[str, Any]:
    """Remove assistant transcript text while retaining the identical bounded tool results."""
    return {
        "transcript": [message for message in state["transcript"] if message["role"] == "user"],
        "tool_results": state["tool_results"],
    }

"""Offline examples of tau2 trace conversion and decision extraction."""

from bench.e3b.data import Episode, ToolCall, Turn
from bench.e3b.extract import instances, to_trace, user_tools_only
from som.compile import Candidate


def episode():
    return Episode(
        episode_id="m/retail/1/0",
        model="m",
        domain="retail",
        task_id="1",
        trial=0,
        reward=1.0,
        turns=[
            Turn(0, "system", "private instructions"),
            Turn(1, "user", "Please help"),
            Turn(
                2,
                "assistant",
                "Looking up your order",
                [
                    ToolCall("a", "lookup", {"id": "123"}, {"status": "open"}, 3),
                ],
            ),
            Turn(4, "user", "Please cancel"),
            Turn(
                5,
                "assistant",
                "I will handle it",
                [
                    ToolCall("b", "change", {"mode": "cancel"}, {"secret": "later result"}, 6),
                    ToolCall("c", "change", {"mode": "refund"}, "another result", 7),
                ],
            ),
            Turn(8, "assistant", "Future response"),
        ],
        gold_actions=[{"name": "change", "arguments": {"mode": "cancel"}}],
    )


def test_trace_uses_user_messages_only_and_ordered_tool_steps():
    trace = to_trace(episode())
    assert trace.trace_id == "m/retail/1/0"
    assert trace.input == "user: Please help\nuser: Please cancel"
    assert [(step.tool, step.arguments, step.result) for step in trace.steps] == [
        ("lookup", {"id": "123"}, {"status": "open"}),
        ("change", {"mode": "cancel"}, {"secret": "later result"}),
        ("change", {"mode": "refund"}, "another result"),
    ]
    assert trace.metadata["task_id"] == "1"


def test_every_argument_occurrence_uses_same_predecision_prefix_for_parallel_calls():
    candidate = Candidate("tool_argument", "change.mode", "change", "mode")
    rows = instances(episode(), candidate)
    assert [row["teacher"] for row in rows] == ["cancel", "refund"]
    assert all(row["gold"] == "cancel" for row in rows)
    assert all(row["candidate"] == "change.mode" for row in rows)
    assert all(row["episode_id"] == "m/retail/1/0" and row["task_id"] == "1" for row in rows)
    assert all(row["model"] == "m" and row["domain"] == "retail" for row in rows)
    assert rows[0]["state"] == rows[1]["state"]
    state = rows[0]["state"]
    assert state["transcript"] == [
        {"role": "user", "content": "Please help"},
        {"role": "assistant", "content": "Looking up your order"},
        {"role": "user", "content": "Please cancel"},
    ]
    assert state["tool_results"] == [{"tool": "lookup", "arguments": {"id": "123"}, "result": {"status": "open"}}]
    assert "later result" not in str(state) and "Future response" not in str(state)
    assert "I will handle it" not in str(state) and "private instructions" not in str(state)


def test_gold_requires_exact_tool_and_argument_and_unanimous_values():
    item = episode()
    candidate = Candidate("tool_argument", "change.mode", "change", "mode")
    item.gold_actions = [
        {"name": "change_extra", "arguments": {"mode": "wrong"}},
        {"name": "change", "arguments": {"mode_extra": "wrong"}},
        {"name": "change", "arguments": {"mode": "cancel"}},
        {"name": "change", "arguments": {"mode": "cancel"}},
    ]
    assert [row["gold"] for row in instances(item, candidate)] == ["cancel", "cancel"]
    item.gold_actions.append({"name": "change", "arguments": {"mode": "refund"}})
    assert all(row["gold"] is None for row in instances(item, candidate))
    item.gold_actions = [{"name": "change", "arguments": {"mode_extra": "cancel"}}]
    assert all(row["gold"] is None for row in instances(item, candidate))


def test_unidentifiable_episode_wide_branch_has_no_evaluable_instances():
    assert instances(episode(), Candidate("branch", "change.branch", "change", None)) == []
    assert instances(episode(), Candidate("branch", "absent.branch", "absent", None)) == []


def test_unobserved_and_delayed_results_are_not_in_predecision_state():
    item = episode()
    item.turns[2].tool_calls[0].result_index = 6
    rows = instances(item, Candidate("tool_argument", "change.mode", "change", "mode"))
    assert rows[0]["state"]["tool_results"] == []
    item.turns[2].tool_calls[0].result_index = None
    rows = instances(item, Candidate("tool_argument", "change.mode", "change", "mode"))
    assert rows[0]["state"]["tool_results"] == []


def test_state_bounds_old_context_and_large_values_without_exposing_future():
    item = episode()
    item.turns = [Turn(i * 2, "user", f"message {i} " + "x" * 3000) for i in range(25)] + [
        Turn(51, "assistant", "", [ToolCall("a", "lookup", {}, {"data": "y" * 3000}, 52)]),
        Turn(53, "assistant", "", [ToolCall("b", "change", {"mode": "cancel"}, None)]),
    ]
    row = instances(item, Candidate("tool_argument", "change.mode", "change", "mode"))[0]
    assert len(row["state"]["transcript"]) == 20
    assert all(len(message["content"]) <= 2000 for message in row["state"]["transcript"])
    assert len(row["state"]["tool_results"][0]["result"]["truncated_json"]) == 2000


def test_user_tools_only_removes_assistant_text_without_changing_tools_or_original():
    state = instances(episode(), Candidate("tool_argument", "change.mode", "change", "mode"))[0]["state"]
    ablated = user_tools_only(state)
    assert ablated["transcript"] == [
        {"role": "user", "content": "Please help"},
        {"role": "user", "content": "Please cancel"},
    ]
    assert ablated["tool_results"] == state["tool_results"]
    assert len(state["transcript"]) == 3

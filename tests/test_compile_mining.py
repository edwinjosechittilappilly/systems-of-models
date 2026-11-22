"""Offline coverage of trace persistence and empirical decision mining."""

import csv
import io

import pytest

from som.compile.mining import mine
from som.compile.traces import AgentStep, AgentTrace, load_traces, save_traces
from som.trace import TraceStore


def test_agent_trace_round_trip_including_empty_trace(tmp_path):
    traces = [
        AgentTrace("a", {"ticket": "hello"}, [AgentStep("search", {"q": "hello"}, [{"id": "p1"}])], {"run": 1}),
        AgentTrace("b", "no calls"),
    ]
    path = tmp_path / "traces.jsonl"
    save_traces(traces, TraceStore(path))
    assert load_traces(TraceStore.load(path)) == traces


def test_miner_finds_choices_and_records_all_distractor_reasons():
    traces = []
    for i in range(40):
        # Three independent policy classes and a separate identity-check branch.
        group = i % 3
        entry = {"id": f"p{group}", "department": f"dept{group}", "title": f"Policy {group}"}
        alternatives = [{"id": f"p{j}", "department": f"dept{j}", "title": f"Policy {j}"} for j in range(3)]
        steps = [AgentStep("search", {}, alternatives)]
        if i % 2:
            steps.append(AgentStep("verify", {}, True))
        steps.append(
            AgentStep(
                "route",
                {
                    "department": entry["department"],
                    "queue": entry["department"],
                    "note": f"agent explanation number {i}",
                    "account": f"acct-{i}",
                    "fixed": "same",
                },
                None,
            )
        )
        if i == 0:
            steps.append(AgentStep("rare", {"flag": "yes"}, None))
        traces.append(AgentTrace(str(i), f"Please handle account acct-{i}", steps))

    report = mine(traces, min_support=3)
    accepted = {item.name: item for item in report.accepted}
    rejected = {item.name: item for item in report.rejected}
    assert accepted["search.retrieval_choice"].values == ["p0", "p1", "p2"]
    assert accepted["search.retrieval_choice"].examples[0].title == "Policy 0"
    assert set(accepted["verify.branch"].values) == {True, False}
    assert rejected["route.department"].reason == "functional_dependency"
    assert rejected["route.queue"].reason == "functional_dependency"
    assert rejected["route.note"].reason == "free_text"
    assert rejected["route.account"].reason == "copied_from_input"
    assert rejected["route.fixed"].reason == "constant"
    assert rejected["rare.branch"].reason == "rare"
    rows = report.to_rows()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    assert len(list(csv.DictReader(io.StringIO(output.getvalue())))) == len(rows)


def test_retrieval_ambiguity_does_not_invent_a_choice():
    traces = [
        AgentTrace(
            str(i),
            "ticket",
            [
                AgentStep("search", {}, [{"id": "a", "kind": "x"}, {"id": "b", "kind": "x"}]),
                AgentStep("use", {"kind": "x"}, None),
            ],
        )
        for i in range(4)
    ]
    report = mine(traces, min_support=2)
    assert all(candidate.kind != "retrieval_choice" for candidate in report.accepted + report.rejected)


def test_miner_rejects_duplicate_trace_ids_and_invalid_configuration():
    with pytest.raises(ValueError, match="unique"):
        mine([AgentTrace("x", "a"), AgentTrace("x", "b")], min_support=1)
    with pytest.raises(ValueError, match="min_support"):
        mine([], min_support=0)

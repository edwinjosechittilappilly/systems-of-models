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
                    "queue": f"{entry['department']}_queue",
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
    assert rejected["route.department"].reason == "copied_from_context"  # read off the chosen entry
    assert rejected["route.queue"].reason == "functional_dependency"
    assert rejected["route.queue"].determinant == "search.retrieval_choice"
    assert rejected["route.note"].reason == "free_text"
    assert rejected["route.account"].reason == "copied_from_context"
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
    assert report.ambiguous_retrieval_count == 4


def test_retrieval_dependencies_use_shared_traces_despite_ambiguous_choices():
    traces = []
    for i in range(48):
        department, priority = f"d{i % 4}", f"p{(i // 4) % 3}"
        chosen = {"id": f"id{i % 12}", "department": department, "priority": priority}
        other = (
            {"id": "other", "department": department, "priority": priority}
            if i < 12
            else {"id": "other", "department": "other", "priority": "other"}
        )
        traces.append(
            AgentTrace(
                str(i),
                "ticket",
                [
                    AgentStep("search", {}, [chosen, other]),
                    AgentStep("route", {"department": department, "priority": priority}, None),
                ],
            )
        )

    report = mine(traces, min_support=2)
    accepted = {item.name: item for item in report.accepted}
    rejected = {item.name: item for item in report.rejected}
    assert report.ambiguous_retrieval_count == 12
    assert "search.retrieval_choice" in accepted
    # Routing fields are read off the retrieved entry, so they are lookups, not separate judgements.
    assert rejected["route.department"].reason == "copied_from_context"
    assert rejected["route.priority"].reason == "copied_from_context"


def test_unique_retrieval_ids_are_not_decisions_or_determinants():
    traces = []
    for i in range(30):
        traces.append(
            AgentTrace(
                str(i),
                "ticket",
                [
                    AgentStep("search", {}, [{"id": f"id{i}"}, {"id": "other"}]),
                    AgentStep("use", {"id": f"id{i}"}, None),
                    AgentStep("route", {"action": ("cancel", "return", "exchange")[i % 3]}, None),
                ],
            )
        )
    report = mine(traces, min_support=2)
    rejected = {item.name: item for item in report.rejected}
    assert rejected["search.retrieval_choice"].reason == "free_text"
    assert rejected["search.retrieval_choice"].support == 29
    assert "route.action" in {item.name for item in report.accepted}


def test_many_valued_decision_counts_non_majority_support_even_with_singleton_values():
    traces = [
        AgentTrace(str(i), "ticket", [AgentStep("route", {"policy": f"policy-{i % 76 if i < 599 else 76}"}, None)])
        for i in range(600)
    ]
    report = mine(traces, min_support=10)
    choice = next(item for item in report.accepted if item.name == "route.policy")
    assert len(choice.values) == 77
    assert choice.support == 592
    assert sum(example.value == "policy-76" for example in choice.examples) == 1


def test_distinct_ratio_is_configurable_for_many_valued_decisions():
    traces = [
        AgentTrace(str(i), "ticket", [AgentStep("route", {"policy": f"policy-{i % 8}"}, None)]) for i in range(20)
    ]
    assert "route.policy" in {item.name for item in mine(traces, min_support=2).accepted}
    rejected = {item.name: item for item in mine(traces, min_support=2, max_distinct_ratio=0.4).rejected}
    assert rejected["route.policy"].reason == "free_text"


def test_singleton_determinant_groups_do_not_predict_their_own_values():
    traces = []
    for i in range(20):
        determinant = "common" if i < 18 else f"unique{i}"
        value = "yes" if i < 18 else "no"
        traces.append(
            AgentTrace(
                str(i), "ticket", [AgentStep("a", {"key": determinant}, None), AgentStep("b", {"value": value}, None)]
            )
        )
    report = mine(traces, min_support=1)
    assert {"a.key", "b.value"} <= {item.name for item in report.accepted}


def test_dependency_requires_moderate_overlap():
    traces = []
    for i in range(20):
        value = ("x", "y")[i % 2]
        steps = []
        if i < 8:
            steps.extend(
                [AgentStep("search", {}, [{"id": value}, {"id": "other"}]), AgentStep("use", {"id": value}, None)]
            )
        steps.append(AgentStep("route", {"kind": value}, None))
        traces.append(AgentTrace(str(i), "ticket", steps))
    report = mine(traces, min_support=2)
    assert "route.kind" in {item.name for item in report.accepted}


def test_support_is_the_least_common_value_for_branches_and_arguments():
    traces = []
    for i in range(20):
        steps = [AgentStep("route", {"kind": "unusual" if i == 0 else "usual"}, None)]
        if i:
            steps.append(AgentStep("near_always", {}, None))
        traces.append(AgentTrace(str(i), "ticket", steps))
    report = mine(traces, min_support=3)
    rejected = {item.name: item for item in report.rejected}
    for name in ("near_always.branch", "route.kind"):
        assert rejected[name].reason == "rare"
        assert rejected[name].support == 1


def test_near_constant_argument_with_three_values_is_rare():
    traces = [
        AgentTrace(str(i), "ticket", [AgentStep("lookup", {"top_k": 10 if i == 0 else 3 if i == 1 else 5}, None)])
        for i in range(1000)
    ]
    report = mine(traces, min_support=10)
    rejected = {item.name: item for item in report.rejected}
    assert rejected["lookup.top_k"].reason == "rare"
    assert rejected["lookup.top_k"].support == 2


def test_ids_read_from_earlier_tool_results_are_copied_not_decided():
    traces = []
    for i in range(40):
        orders = [f"#W{i}0", f"#W{i}1"]
        traces.append(
            AgentTrace(
                str(i),
                "I want to return something",
                [
                    AgentStep("get_user", {"user": "u"}, {"orders": orders, "payment": f"card_{i}"}),
                    AgentStep(
                        "return_items",
                        {
                            "order_id": orders[i % 2],
                            "items": [f"#W{i}0"],
                            "payment_method_id": f"card_{i}",
                            "reason": ("damaged", "wrong size", "late")[i % 3],
                        },
                        None,
                    ),
                ],
            )
        )
    report = mine(traces, min_support=5)
    rejected = {item.name: item for item in report.rejected}
    for name in ("return_items.order_id", "return_items.items", "return_items.payment_method_id"):
        assert rejected[name].reason == "copied_from_context"
    assert "return_items.reason" in {item.name for item in report.accepted}


def test_a_call_that_passes_a_retrieved_id_under_another_name_is_a_retrieval_choice():
    traces = []
    for i in range(60):
        entries = [{"id": f"p{j}", "title": f"Policy {j}"} for j in range(5)]
        chosen = f"p{i % 5}"
        traces.append(
            AgentTrace(
                str(i),
                f"ticket {i}",
                [
                    AgentStep("search_policy", {"query": f"q{i}"}, entries),
                    AgentStep("get_policy", {"entry_id": chosen}, {}),
                ],
            )
        )
    report = mine(traces, min_support=5)
    accepted = {item.name: item for item in report.accepted}
    rejected = {item.name: item for item in report.rejected}
    assert set(accepted["search_policy.retrieval_choice"].values) == {"p0", "p1", "p2", "p3", "p4"}
    assert accepted["search_policy.retrieval_choice"].examples[0].title == "Policy 0"
    assert rejected["get_policy.entry_id"].reason == "copied_from_context"
    assert report.ambiguous_retrieval_count == 0


def test_min_minority_can_be_lower_than_total_support():
    traces = [
        AgentTrace(str(i), "ticket", [AgentStep("route", {"kind": "minor" if i < 2 else "major"}, None)])
        for i in range(20)
    ]
    assert "route.kind" in {item.name for item in mine(traces, min_support=5, min_minority=2).accepted}


def test_no_evidence_and_resolved_ties_are_not_counted_as_ambiguous():
    traces = [
        AgentTrace("none", "ticket", [AgentStep("search", {}, [{"id": "a"}, {"id": "b"}])]),
        AgentTrace(
            "resolved",
            "ticket",
            [
                AgentStep("search", {}, [{"id": "a", "kind": "x"}, {"id": "b", "kind": "x"}]),
                AgentStep("filter", {"kind": "x"}, None),
                AgentStep("use", {"id": "a"}, None),
            ],
        ),
    ]
    report = mine(traces, min_support=1)
    assert report.ambiguous_retrieval_count == 0


def test_miner_rejects_duplicate_trace_ids_and_invalid_configuration():
    with pytest.raises(ValueError, match="unique"):
        mine([AgentTrace("x", "a"), AgentTrace("x", "b")], min_support=1)
    with pytest.raises(ValueError, match="min_support"):
        mine([], min_support=0)

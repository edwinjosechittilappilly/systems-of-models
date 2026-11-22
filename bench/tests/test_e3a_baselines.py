"""Offline behavioral tests for the fixed and nearest-neighbour baselines."""

from types import SimpleNamespace

import pytest

from bench.common.cache import JsonCache
from bench.e3a.baselines import run_baseline
from bench.e3a.local_models import EMBEDDING_NAMESPACE, CachedEmbedder
from bench.tasks.environment import PolicyKB
from som.questions import ChoiceAnswer


def envelope(cost, latency):
    return SimpleNamespace(cost=SimpleNamespace(amount=cost), latency_ms=latency)


def teacher(entry, *, missing=False):
    events = [] if missing else [{"tool": "get_policy", "entry_id": entry["id"]}]
    events += [{"tool": "route_ticket"}]
    return SimpleNamespace(
        events=events,
        route={"department": entry["department"], "priority": entry["priority"]},
        verified=entry["identity_check"],
        envelope=envelope(2.0, 10.0),
    )


def items(kb, entries, labels):
    return [
        {
            "index": i,
            "text": str(i),
            "ticket": {"account_id": f"acct{i}"},
            "gold": entries[label],
            "teacher": teacher(entries[label]),
            "kb": kb,
            "prompt_version": "v2",
        }
        for i, label in enumerate(labels)
    ]


class S1:
    def __init__(self, label):
        self.label = label
        self.questions = []

    def decide(self, text, questions):
        question = questions[0]
        self.questions.append(question)
        answer = ChoiceAnswer(question.name, self.label, {self.label: 1.0})
        return SimpleNamespace(answers={question.name: answer}, envelope=envelope(0.1, 1.0))


def run(data, arm, s1=None, **kwargs):
    args = dict(
        arm=arm,
        stream="dev",
        shift_at=3,
        warmup=1,
        n_cal=1,
        n_val=1,
        epsilon=0.9,
        alpha=0.9,
        audit_rate=0.0,
        seed=7,
        tau_rule="margin",
    )
    args.update(kwargs)
    return run_baseline(data, SimpleNamespace(s1=s1), **args)


def test_fixed_gate_promotes_with_real_shadow_and_does_not_read_unserved_teacher():
    kb = PolicyKB()
    entry = kb.get_entry(next(iter(kb._entries)))
    data = items(kb, [entry], [0, 0, 0, 0])

    class Poison:
        def __getattribute__(self, name):
            raise AssertionError("served ticket must not inspect teacher")

    data[3]["teacher"] = Poison()
    s1 = S1(entry["id"])
    rows = run(data, "fixed_gate", s1)
    assert [row["served_by"] for row in rows] == ["agent", "agent", "agent", "s1"]
    assert rows[2]["promoted"] and rows[3]["gold_joint_correct"]
    assert rows[3]["teacher_agreement"] is None
    assert rows[1]["shadow_cost_usd"] == 2 and rows[1]["cost_usd"] == 2.1
    assert rows[3]["agent_calls"] == 0 and rows[3]["s1_cost_usd"] == 0.1
    assert s1.questions[0].name == "governing_entry"
    assert (
        s1.questions[0].instructions
        == "Which policy title best matches the customer's request? Select the most directly applicable policy."
    )
    assert {o.value: o.description for o in s1.questions[0].options} == {
        e["id"]: e["title"] for e in kb._entries.values()
    }


def test_hash_change_rebuilds_gate_and_developer_question():
    kb = PolicyKB()
    entry = kb.get_entry(next(iter(kb._entries)))
    changed_entries = [dict(e) for e in kb._entries.values()]
    changed_entries[0]["title"] = "Changed title"
    changed = PolicyKB(entries=changed_entries)
    data = items(kb, [entry], [0] * 5)
    data[4]["kb"] = changed
    plain = run(data, "fixed_gate", S1(entry["id"]))
    s1 = S1(entry["id"])
    hashed = run(data, "fixed_gate_config_hash", s1)
    assert plain[4]["served_by"] == "s1"
    assert hashed[4]["served_by"] == "agent" and hashed[4]["shadow_cost_usd"] == 2
    assert {o.value: o.description for o in s1.questions[-1].options}[entry["id"]] == "Changed title"
    assert {o.value: o.description for o in s1.questions[0].options}[entry["id"]] == entry["title"]


def test_prompt_change_rebuilds_hash_gate_but_not_fixed_gate():
    kb = PolicyKB()
    entry = kb.get_entry(next(iter(kb._entries)))
    data = items(kb, [entry], [0] * 5)
    data[4]["prompt_version"] = "v3"
    plain = run(data, "fixed_gate", S1(entry["id"]))
    hashed = run(data, "fixed_gate_config_hash", S1(entry["id"]))
    assert plain[4]["served_by"] == "s1"
    assert hashed[4]["served_by"] == "agent"
    assert hashed[4]["shadow_cost_usd"] == 2


def test_missing_reference_choice_does_not_complete_shadow_window():
    kb = PolicyKB()
    entry = kb.get_entry(next(iter(kb._entries)))
    data = items(kb, [entry], [0] * 4)
    data[1]["teacher"] = teacher(entry, missing=True)
    rows = run(data, "fixed_gate", S1(entry["id"]))
    assert all(row["served_by"] == "agent" for row in rows)
    assert rows[3]["promoted"] and rows[1]["shadow_cost_usd"] == 2


def test_knn_audit_failure_invalidates_even_when_gold_agrees(tmp_path):
    kb = PolicyKB()
    entries = [kb.get_entry(key) for key in list(kb._entries)[:2]]
    data = items(kb, entries, [0, 0, 1, 0])
    data[2]["gold"] = entries[0]
    embedder = CachedEmbedder(
        JsonCache(EMBEDDING_NAMESPACE, directory=tmp_path), embed=lambda texts: [[1.0, 0.0] for _ in texts]
    )
    rows = run(data, "knn_cache", warmup=2, audit_rate=1.0, embedder=embedder)
    assert rows[1]["promoted"]
    assert rows[2]["served_by"] == "knn" and rows[2]["gold_joint_correct"]
    assert rows[2]["audited"] and rows[2]["demoted"] and rows[2]["audit_cost_usd"] == 2
    assert rows[3]["served_by"] == "agent" and rows[3]["agent_calls"] == 1


def test_unknown_paid_cost_is_not_silently_booked_as_zero():
    kb = PolicyKB()
    entry = kb.get_entry(next(iter(kb._entries)))
    data = items(kb, [entry], [0, 0])
    data[0]["teacher"].envelope.cost.amount = None
    with pytest.raises(ValueError, match="unknown cost"):
        run(data, "fixed_gate", S1(entry["id"]))

    data[0]["teacher"].envelope.cost.amount = 0.0

    class UnpricedS1(S1):
        def decide(self, text, questions):
            decision = super().decide(text, questions)
            decision.envelope.cost.amount = None
            return decision

    with pytest.raises(ValueError, match="unknown cost"):
        run(data, "fixed_gate", UnpricedS1(entry["id"]))

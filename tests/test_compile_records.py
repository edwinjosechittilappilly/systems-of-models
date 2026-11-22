import pytest

from som import schemas
from som.compile.records import agent_step, s5_record, state_ref, version_bump_record


def _envelope():
    return {
        "id": "evo-1",
        "contract_version": "2.0.0",
        "system": "s5.self_evolving",
        "system_version": "2.0.0",
        "confidence": None,
        "cost": {"amount": None, "currency": "USD", "basis": "unknown"},
        "latency_ms": 12,
        "trace_ref": {"trace_id": "0123456789abcdef0123456789abcdef"},
    }


def _arguments():
    return {
        "envelope": _envelope(),
        "modification_id": "mod-1",
        "target_ref": "router/decision",
        "operation": "add",
        "before": None,
        "after": {"a": 1},
        "evaluation": {
            "eval_suite": "held-out-1",
            "n": 100,
            "baseline": {"accuracy": 0.9},
            "candidate": {"accuracy": 0.95},
            "passed": True,
        },
        "rollback": {"strategy": "restore_snapshot", "snapshot_ref": "snapshot-1"},
        "status": "applied",
        "system": "s1.decision",
        "from_version": "2.0.0",
        "to_version": "2.0.1",
    }


def test_state_hash_is_stable_and_does_not_alias_input():
    value = {"a": 1}
    ref = state_ref(value)
    assert ref["content_hash"] == "sha256:015abd7f5cc57a2dd94b7590f04ad8084273905ee33ec5cebeae62276a97f862"
    value["a"] = 2
    assert ref["value"] == {"a": 1}
    assert state_ref({"b": 2, "a": 1}) == state_ref({"a": 1, "b": 2})
    with pytest.raises(ValueError, match="Out of range"):
        state_ref({"a": float("nan")})


@pytest.mark.parametrize(
    ("operation", "before", "after"),
    [
        ("add", None, {"a": 1}),
        ("remove", {"a": 1}, None),
    ],
)
def test_promotion_and_demotion_records_include_evidence_and_rollback(operation, before, after):
    args = _arguments()
    args.update(operation=operation, before=before, after=after)
    record = s5_record(**args)
    schemas.validate(record, "s5-self-evolving")
    modification = record["response"]["body"]["modifications"][0]
    assert modification["before"] == (None if before is None else state_ref(before))
    assert modification["after"] == (None if after is None else state_ref(after))
    assert modification["evaluation"] == args["evaluation"]
    assert modification["rollback"] == args["rollback"]
    args["evaluation"]["passed"] = False
    assert modification["evaluation"]["passed"] is True


def test_applied_change_requires_passing_evaluation():
    args = _arguments()
    args["evaluation"]["passed"] = False
    with pytest.raises(schemas.ValidationError):
        s5_record(**args)


def test_unapplied_change_can_record_no_version_effect():
    args = _arguments()
    args.update(status="rejected", to_version="2.0.0", bump="none")
    record = s5_record(**args)
    assert record["response"]["body"]["version_effect"]["bump"] == "none"


def test_version_bump_records_patch_and_links_s5_response():
    record = version_bump_record(
        record_id="bump-1",
        created_at="2026-11-22T12:00:00Z",
        author={"kind": "s5", "id": "compiler"},
        status="accepted",
        evidence={"metrics": {"accuracy": 0.95}},
        system="s1.decision",
        from_version="2.0.0",
        to_version="2.0.1",
        description="Promote decision",
        change_kind="capability_distilled",
        s5_response_ids=["evo-1"],
    )
    schemas.validate(record, "meta-layer")
    assert record["provenance"]["s5_response_ids"] == ["evo-1"]
    assert record["bump"] == "patch"


def test_invalid_version_effect_is_rejected():
    args = _arguments()
    args["to_version"] = "2.1.0"
    with pytest.raises(ValueError, match="next patch"):
        s5_record(**args)


def test_agent_step_validates_tool_call_and_observation():
    action = {
        "type": "tool_call",
        "call_id": "call-1",
        "tool": {"type": "function", "name": "evaluate"},
        "arguments": {"suite": "held-out"},
    }
    observation = {"call_id": "call-1", "content": [{"type": "text", "text": "passed"}]}
    step = agent_step(index=0, action=action, observation=observation, latency_ms=2)
    action["arguments"]["suite"] = "changed"
    assert step["action"]["arguments"]["suite"] == "held-out"
    assert step["observation"] == observation
    with pytest.raises(schemas.ValidationError):
        agent_step(index=-1, action={"type": "finish"})
    with pytest.raises(schemas.ValidationError):
        agent_step(index=0, action={"type": "tool_call"})

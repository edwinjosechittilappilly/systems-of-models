"""Compile a synthetic policy lookup, entirely offline.

Run from the repository root after installing the package:
    python examples/compile_from_traces.py

The writer and answerer are deterministic stand-ins, not trained models. The
separate synthetic shadow and audit streams demonstrate the API, not empirical
performance or the independence assumptions needed for statistical guarantees.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict
from typing import Any

from som.compile import AgentStep, AgentTrace, CompiledDecision, mine, write_question
from som.compile.records import s5_record, version_bump_record
from som.questions import ChoiceAnswer, Refusal

POLICIES = [
    {"id": "refund", "title": "Refund policy", "queue": "refunds"},
    {"id": "delivery", "title": "Delivery policy", "queue": "shipping"},
    {"id": "account", "title": "Account policy", "queue": "accounts"},
]


def make_trace(index: int) -> AgentTrace:
    policy = POLICIES[index % len(POLICIES)]
    ticket = f"Request {index}: help with {policy['id']}"
    return AgentTrace(
        trace_id=f"trace-{index:04d}",
        input=ticket,
        steps=[
            AgentStep(
                "search_policy", {"query": ticket}, [{"id": item["id"], "title": item["title"]} for item in POLICIES]
            ),
            AgentStep("get_policy", {"entry_id": policy["id"]}, policy),
            AgentStep("route", {"queue": policy["queue"]}, {"routed": True}),
        ],
    )


def stub_writer(context: dict[str, Any]) -> dict[str, str]:
    """Replace with a real writer when drafting a question for real traces."""
    return {"name": "policy_choice", "instructions": "Choose the policy governing the request."}


def answer(name: str, policy: str) -> ChoiceAnswer:
    # These probabilities are illustrative and are not calibrated model outputs.
    return ChoiceAnswer(name, policy, {policy: 0.95})


def envelope(response_id: str) -> dict[str, Any]:
    return {
        "id": response_id,
        "contract_version": "2.0.0",
        "system": "s5.self_evolving",
        "system_version": "2.0.0",
        "confidence": None,
        "cost": {"amount": None, "currency": "USD", "basis": "unknown"},
        "latency_ms": 0,
        "trace_ref": {"trace_id": "0123456789abcdef0123456789abcdef"},
    }


def show(label: str, value: Any) -> None:
    print(f"\n{label}")
    print(json.dumps(value, indent=2, sort_keys=True))


def main() -> None:
    traces = [make_trace(i) for i in range(1000)]
    report = mine(traces, min_support=50)
    show(
        "Mining report",
        {
            "traces": len(traces),
            "candidates": report.to_rows(),
            "ambiguous_retrieval_count": report.ambiguous_retrieval_count,
        },
    )
    candidate = next(item for item in report.accepted if item.name == "search_policy.retrieval_choice")
    question, provenance = write_question(candidate, stub_writer, seed=7)
    show("Draft question and provenance", {"question": question.to_contract(), "provenance": provenance})

    decision = CompiledDecision(epsilon=0.1, alpha=0.05, n_cal=60, n_val=60, audit_rate=1.0)
    print(f"\nLifecycle: {decision.state}", end="")
    decision.start_shadow()
    print(f" -> {decision.state}", end="")
    # Distinct synthetic requests from those used for mining; the first 60 are
    # calibration and the next 60 are held-out validation inside the gate.
    for i in range(1000, 1120):
        reference = POLICIES[i % len(POLICIES)]["id"]
        decision.observe_shadow(answer(question.name, reference), answer(question.name, reference))
    promotion = decision.attempt_promotion()
    print(f" -> {decision.state}")
    show("Promotion result", asdict(promotion))
    if not promotion.promoted:
        raise RuntimeError("synthetic shadow window did not promote")

    active_state = {"question": question.to_contract(), "threshold": decision.tau, "metric": decision.metric}
    promotion_evaluation = {
        "eval_suite": "synthetic-held-out-validation",
        "n": promotion.validation_served,
        "baseline": {},
        "candidate": {"errors": promotion.validation_errors, "error_upper_bound": promotion.upper_bound},
        "passed": promotion.promoted,
    }
    rollback = {
        "strategy": "feature_flag",
        "snapshot_ref": "policy-router-before-compilation",
        "trigger": {"metric": "audit_e_value", "operator": "ge", "value": 1 / decision.alpha},
    }
    promotion_s5 = s5_record(
        envelope=envelope("promotion-1"),
        modification_id="promote-policy",
        target_ref="router/policy_choice",
        operation="add",
        before=None,
        after=active_state,
        evaluation=promotion_evaluation,
        rollback=rollback,
        status="applied",
        system="s1.decision",
        from_version="2.0.0",
        to_version="2.0.1",
        rationale="Synthetic validation met the promotion threshold.",
    )
    promotion_meta = version_bump_record(
        record_id="version-promotion",
        created_at="2026-01-01T00:00:00Z",
        author={"kind": "s5", "id": "offline-example"},
        status="accepted",
        evidence={"metrics": {"validation_error_upper_bound": promotion.upper_bound}},
        system="s1.decision",
        from_version="2.0.0",
        to_version="2.0.1",
        description="Promote the compiled policy choice",
        change_kind="capability_distilled",
        s5_response_ids=["promotion-1"],
    )
    show("Promotion S5 record", promotion_s5)
    show("Promotion meta record", promotion_meta)

    rng = random.Random(7)
    # Audit selection happens before comparing with the reference. All served
    # answers are sampled here to make the offline demonstration reproducible.
    for i in range(30):
        policy = POLICIES[i % len(POLICIES)]["id"]
        predicted = answer(question.name, policy)
        if decision.route(predicted) == "serve" and decision.should_audit(rng):
            decision.record_audit(predicted, answer(question.name, policy))
    print(
        f"\nHealthy traffic: served={decision.served_count}, audits={decision.audit_count}, "
        f"errors={decision.audit_errors}, e_value={decision.e_value:.4f}"
    )
    print(f"Refusal routes to: {decision.route(Refusal(question.name))}")

    # Inject a complete distribution shift: the fixed answerer now consistently
    # disagrees with the reference. Stop as soon as the audit process demotes it.
    shift_requests = 0
    while decision.state == "promoted" and shift_requests < 1000:
        shift_requests += 1
        predicted = answer(question.name, "refund")
        if decision.route(predicted) == "serve" and decision.should_audit(rng):
            decision.record_audit(predicted, answer(question.name, "delivery"))
    if decision.state != "demoted":
        raise RuntimeError("synthetic shift did not trigger demotion")
    print(
        f"Shift: {shift_requests} requests -> {decision.state}; audits={decision.audit_count}, "
        f"errors={decision.audit_errors}, e_value={decision.e_value:.4f}, "
        f"detection_time={decision.detection_time}, coverage={decision.coverage:.3f}"
    )
    print(f"After demotion routes to: {decision.route(answer(question.name, 'refund'))}")

    demotion_evaluation = {
        "eval_suite": "synthetic-audit-demotion",
        "n": decision.audit_count,
        "baseline": {"e_value_threshold": 1 / decision.alpha},
        "candidate": {"e_value": decision.e_value, "audit_errors": decision.audit_errors},
        "passed": decision.e_value >= 1 / decision.alpha,
    }
    demotion_s5 = s5_record(
        envelope=envelope("demotion-1"),
        modification_id="demote-policy",
        target_ref="router/policy_choice",
        operation="remove",
        before=active_state,
        after=None,
        evaluation=demotion_evaluation,
        rollback=rollback,
        status="applied",
        system="s1.decision",
        from_version="2.0.1",
        to_version="2.0.2",
        rationale="The audit e-process crossed its demotion threshold; traffic escalates.",
    )
    demotion_meta = version_bump_record(
        record_id="version-demotion",
        created_at="2026-01-01T00:00:01Z",
        author={"kind": "s5", "id": "offline-example"},
        status="accepted",
        evidence={"metrics": {"e_value": decision.e_value, "audits": decision.audit_count}},
        system="s1.decision",
        from_version="2.0.1",
        to_version="2.0.2",
        description="Withdraw the compiled decision after the audit threshold was crossed",
        change_kind="rollback",
        s5_response_ids=["demotion-1"],
    )
    show("Demotion S5 record", demotion_s5)
    show("Demotion meta record", demotion_meta)


if __name__ == "__main__":
    main()

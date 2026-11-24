"""Fixed-question and nearest-neighbour E3a baselines.

Teacher results are materialized offline, but their labels are only inspected on
simulated agent calls. Costs and latencies use the original cached envelopes.
"""

from __future__ import annotations

import hashlib
import json
import random

from bench.e3a.local_models import KnnCache
from bench.tasks.environment import PolicyKB, SupportEnvironment

from som.compile.lifecycle import CompiledDecision
from som.questions import Choice, ChoiceAnswer, Refusal


def _entries(kb):
    # PolicyKB exposes exact lookup and search, but search returns only five rows.
    return [kb.get_entry(key) for key in sorted(kb._entries)]


def _hash(kb, prompt_version):
    return hashlib.sha256(
        json.dumps([_entries(kb), prompt_version], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _question(kb):
    entries = _entries(kb)
    return Choice(
        "governing_entry",
        "Which policy title best matches the customer's request? Select the most directly applicable policy.",
        {entry["id"]: entry["title"] for entry in entries},
    )


def _teacher_label(teacher, kb):
    label = None
    for event in teacher.events:
        if event.get("tool") == "route_ticket":
            break
        if event.get("tool") == "get_policy":
            label = event.get("entry_id")
    if not isinstance(label, str):
        return None
    try:
        kb.get_entry(label)
    except KeyError:
        return None
    return label


def _paid_cost(envelope):
    amount = envelope.cost.amount
    if amount is None:
        raise ValueError("Paid provider envelope has unknown cost")
    return amount


def _outcome(route, verified, gold):
    route = route or {}
    department = route.get("department") == gold["department"]
    priority = route.get("priority") == gold["priority"]
    identity = verified == gold["identity_check"]
    return department, priority, identity


def run_baseline(
    items,
    providers,
    *,
    arm,
    stream,
    shift_at,
    warmup,
    n_cal,
    n_val,
    epsilon,
    alpha,
    audit_rate,
    seed,
    embedder=None,
    max_promotion_attempts=1,
    tau_rule="upper_bound",
    alpha_cal=0.05,
    calibration_margin=0.6,
    min_coverage=0.0,
):
    """Simulate one arm on prepared stream items and return per-ticket rows.

    ``fixed_gate_config_hash`` rebuilds its question and gate on KB or prompt changes.
    Its epoch k spends alpha / (k * (k + 1)), bounded by alpha in total.
    kNN uses independent audits and invalidates after an observed disagreement.
    """
    if arm not in {"fixed_gate", "fixed_gate_config_hash", "knn_cache"}:
        raise ValueError(f"unknown baseline arm: {arm}")
    if warmup < 1 or not 0 <= audit_rate <= 1:
        raise ValueError("warmup must be positive and audit_rate must be in [0, 1]")
    if arm == "knn_cache" and embedder is None:
        raise ValueError("knn_cache requires a cached embedder")
    rng = random.Random(seed)
    knn = KnnCache(embedder, epsilon=epsilon) if arm == "knn_cache" else None
    warm_texts, warm_labels = [], []
    question = gate = kb_hash = None
    shadow_count = 0
    epoch = 0
    rows = []

    def new_gate():
        decision = CompiledDecision(
            epsilon=epsilon,
            alpha=gate_alpha,
            n_cal=n_cal,
            n_val=n_val,
            audit_rate=0,
            max_promotion_attempts=max_promotion_attempts,
            tau_rule=tau_rule,
            alpha_cal=alpha_cal,
            calibration_margin=calibration_margin,
            min_coverage=min_coverage,
        )
        decision.start_shadow()
        return decision

    for position, item in enumerate(items):
        kb, ticket, gold = item["kb"], item["ticket"], item["gold"]
        if question is None and knn is None:
            epoch += 1
            gate_alpha = alpha / (epoch * (epoch + 1)) if arm == "fixed_gate_config_hash" else alpha
            question, kb_hash, gate = _question(PolicyKB()), _hash(kb, item["prompt_version"]), new_gate()
        if arm == "fixed_gate_config_hash" and _hash(kb, item["prompt_version"]) != kb_hash:
            epoch += 1
            gate_alpha = alpha / (epoch * (epoch + 1))
            question, kb_hash, gate = _question(kb), _hash(kb, item["prompt_version"]), new_gate()
            shadow_count = 0
        costs = {name: 0.0 for name in ("s1", "agent", "shadow", "audit", "writer", "mining", "embedding")}
        latency = 0.0
        local_cpu_seconds = 0.0
        promoted = demoted = audited = False
        reference_kind = None
        prediction = None
        route = None
        verified = None
        if position < warmup:
            reference_kind = "agent"
        elif knn is not None:
            predicted = knn.predict(item["text"])
            costs["embedding"] += embedder.last_measurement.cost_usd
            latency += predicted.latency_ms
            local_cpu_seconds += predicted.cpu_seconds
            if predicted.served:
                prediction = predicted.label
            else:
                reference_kind = "agent"
        else:
            decision = providers.s1.decide(item["text"], [question])
            costs["s1"] += _paid_cost(decision.envelope)
            latency += decision.envelope.latency_ms or 0.0
            answer = decision.answers.get(question.name, Refusal(question.name))
            valid = isinstance(answer, ChoiceAnswer) and answer.value in question.values
            if gate.state == "shadow":
                reference_kind = "shadow"
            elif valid and gate.route(answer) == "serve":
                prediction = answer.value
            else:
                reference_kind = "agent"

        if prediction is not None:
            try:
                entry = kb.get_entry(prediction)
                env = SupportEnvironment(kb)
                verified = entry["identity_check"]
                route = env.substitute(
                    prediction,
                    ticket["account_id"],
                    verified,
                    amount=ticket.get("amount"),
                    merchant=ticket.get("merchant"),
                )
            except KeyError:
                prediction, reference_kind = None, "agent"
            if prediction is not None and knn is not None and rng.random() < audit_rate:
                reference_kind = "audit"
                audited = True

        teacher_agreement = None
        if reference_kind is not None:
            teacher = item["teacher"]
            label = _teacher_label(teacher, kb)
            costs[reference_kind] += _paid_cost(teacher.envelope)
            latency += teacher.envelope.latency_ms or 0.0
            if prediction is None:
                route, verified = teacher.route, teacher.verified
                teacher_agreement = True if route is not None else None
            else:
                teacher_agreement = (
                    teacher.route is not None
                    and route.get("department") == teacher.route.get("department")
                    and route.get("priority") == teacher.route.get("priority")
                    and verified == teacher.verified
                )
            if position < warmup and knn is not None and label is not None:
                warm_texts.append(item["text"])
                warm_labels.append(label)
            elif reference_kind == "shadow" and label is not None:
                gate.observe_shadow(answer, ChoiceAnswer(question.name, label))
                shadow_count += 1
                if shadow_count == n_cal + n_val:
                    result = gate.attempt_promotion()
                    promoted = result.promoted
                    shadow_count = 0
                    if not promoted and gate.state == "shadow":
                        gate.start_shadow()
            elif knn is not None and reference_kind == "audit":
                if label is not None and prediction != label:
                    knn.invalidate()
                    demoted = True
                elif label is not None:
                    knn.add(item["text"], label)
                    costs["embedding"] += embedder.last_measurement.cost_usd
                    latency += embedder.last_measurement.latency_ms
                    local_cpu_seconds += embedder.last_measurement.cpu_seconds
            elif knn is not None and label is not None and position >= warmup:
                knn.add(item["text"], label)
                costs["embedding"] += embedder.last_measurement.cost_usd
                latency += embedder.last_measurement.latency_ms
                local_cpu_seconds += embedder.last_measurement.cpu_seconds

        if knn is not None and position == warmup - 1 and warm_texts:
            knn.fit_warmup(warm_texts, warm_labels)
            costs["embedding"] += embedder.last_measurement.cost_usd
            latency += knn.fit_latency_ms
            local_cpu_seconds += knn.fit_cpu_seconds
            promoted = knn.threshold is not None
        department, priority, identity = _outcome(route, verified, gold)
        row = {
            "ticket_index": item["index"],
            "shift_at": shift_at,
            "arm": arm,
            "stream": stream,
            "gold_department_correct": department,
            "gold_priority_correct": priority,
            "gold_identity_correct": identity,
            "gold_joint_correct": department and priority and identity,
            "teacher_agreement": teacher_agreement,
            "served_by": "agent" if prediction is None else ("knn" if knn else "s1"),
            "prediction": prediction,
            "route": route,
            "verified": verified,
            "cost_usd": sum(costs.values()),
            "demoted": demoted,
            "audited": audited,
            "promoted": promoted,
            "agent_calls": int(reference_kind is not None),
            "latency_ms": latency,
            "local_cpu_seconds": local_cpu_seconds,
        }
        row.update({f"{name}_cost_usd": value for name, value in costs.items()})
        rows.append(row)
    return rows

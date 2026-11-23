"""Offline, paired lifecycle simulations for the E3a compilation arms.

Teacher results in the input are materialized references, not free labels: an
arm can inspect one only when it pays for an agent, shadow, or audit call.
The factorial arms share a per-epoch *training* label count; audit and shadow
labels are additional observations and their costs are accounted separately.
"""

from __future__ import annotations

import hashlib
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from bench.e3a.local_models import make_surrogate
from bench.e3a.metrics import discovery_rows, discovery_summary
from bench.tasks.environment import SupportEnvironment

from som import CONTRACT_VERSION
from som.compile import CompiledDecision, mine, write_question
from som.compile.records import s5_record, version_bump_record
from som.questions import Choice, ChoiceAnswer, Predicate, PredicateAnswer, Refusal

ARMS = ("s1_audit", "s1_refit", "surrogate_audit", "surrogate_refit", "escalation_only", "oracle_audit")
FACTORIAL = ARMS[:4]


def _teacher_labels(item):
    """Last get_policy before first route, and account-specific verification."""
    teacher = item["teacher"]
    if teacher.route is None:
        return None
    entry = None
    verified = False
    routed = False
    for event in teacher.events:
        if event.get("tool") == "route_ticket":
            routed = True
            break
        if event.get("tool") == "get_policy":
            entry = event.get("entry_id")
        if event.get("tool") == "verify_identity" and event.get("account_id") == item["ticket"]["account_id"]:
            verified = True
    if not routed or not isinstance(entry, str) or not entry:
        return None
    return entry, verified


def _trace_key(trace):
    return {
        "input": trace.input,
        "steps": [{"tool": step.tool, "arguments": step.arguments, "result": step.result} for step in trace.steps],
    }


def _cached_timing(cfg, key, timing):
    cache = cfg.get("timing_cache")
    return timing if cache is None else cache.get_or_call(key, lambda: timing)


def _mine_timed(traces, cfg, operation):
    started, cpu_started = time.perf_counter(), time.process_time()
    report = mine(traces, min_support=cfg["min_support"])
    timing = {"latency_ms": (time.perf_counter() - started) * 1000, "cpu_seconds": time.process_time() - cpu_started}
    key = {"operation": operation, "min_support": cfg["min_support"], "traces": [_trace_key(t) for t in traces]}
    return report, _cached_timing(cfg, key, timing)


def _training_pool(items):
    """Keep only teacher labels supported by that trace's mined D1 evidence."""
    eligibility = {}
    pool = []
    excluded_missing = excluded_retrieval = 0
    for item in items:
        key = id(item)
        if key not in eligibility:
            labels = _teacher_labels(item)
            if labels is None:
                eligibility[key] = "missing_teacher_decision"
            else:
                report = mine([item["teacher"].trace], min_support=1)
                candidates = report.accepted + report.rejected
                observed = any(
                    candidate.kind == "retrieval_choice"
                    and candidate.tool == "search_policy"
                    and any(example.value == labels[0] for example in candidate.examples)
                    for candidate in candidates
                )
                eligibility[key] = None if observed else "unmatched_retrieval"
        reason = eligibility[key]
        if reason == "missing_teacher_decision":
            excluded_missing += 1
        elif reason == "unmatched_retrieval":
            excluded_retrieval += 1
        else:
            pool.append(item)
    return pool, excluded_missing, excluded_retrieval


def _reference(question, value):
    if isinstance(question, Predicate):
        return PredicateAnswer(question.name, None, raw_value=value)
    return ChoiceAnswer(question.name, str(value))


def _amount(cost):
    if cost is None or cost.amount is None:
        raise ValueError("unpriced model call")
    return float(cost.amount)


@dataclass
class _Model:
    candidate: Any
    question: Any
    gate: CompiledDecision
    decider: Any
    surrogate: bool
    observed: int = 0


@dataclass
class _Arm:
    name: str
    rng: random.Random
    pool: list = field(default_factory=list)
    escalated: list = field(default_factory=list)
    models: list = field(default_factory=list)
    identity_map: dict[str, bool] = field(default_factory=dict)
    pending: bool = True
    generation: int = 0
    last_compile: int = -1
    version: int = 0
    rows: list = field(default_factory=list)


def _transition(arm, model, item, cfg, kind, elapsed_ms):
    """Record an actual gate transition and its observed evidence."""
    if cfg.get("s5_records") is None and cfg.get("meta_records") is None:
        return
    gate = model.gate
    state = {
        "candidate": model.candidate.name,
        "question": model.question.to_contract(),
        "threshold": gate.tau,
        "generation": arm.generation,
        "surrogate": model.surrogate,
    }
    if kind == "promotion":
        result = gate.last_promotion
        metrics = {
            "calibration_served": result.calibration_served,
            "calibration_errors": result.calibration_errors,
            "validation_served": result.validation_served,
            "validation_errors": result.validation_errors,
            "validation_upper_bound": result.upper_bound,
        }
        n = gate.n_cal + gate.n_val
        before, after, operation = None, state, "add"
        snapshot = f"{arm.name}/{model.candidate.name}"
        suite = "independent shadow calibration and validation"
    else:
        metrics = {
            "audit_count": gate.audit_count,
            "audit_errors": gate.audit_errors,
            "e_value": gate.e_value,
            "alpha": gate.alpha,
            "e_threshold": 1 / gate.alpha,
        }
        n = gate.audit_count
        before, after, operation = state, None, "remove"
        snapshot = f"{arm.name}/{model.candidate.name}"
        suite = "audit e-process demotion"
    identity = f"{cfg.get('stream', '')}:{arm.name}:{item['index']}:{model.candidate.name}:{arm.version}:{kind}"
    digest = hashlib.sha256(identity.encode()).hexdigest()
    response_id = f"evo_{digest[:24]}"
    now = datetime.now(timezone.utc)
    envelope = {
        "id": response_id,
        "contract_version": CONTRACT_VERSION,
        "system": "s5.self_evolving",
        "system_version": CONTRACT_VERSION,
        "confidence": None,
        "cost": {"amount": None, "currency": "USD", "basis": "unknown"},
        "latency_ms": elapsed_ms,
        "trace_ref": {"trace_id": item["teacher"].trace.trace_id},
        "created_at": int(now.timestamp()),
    }
    old, new = f"2.0.{arm.version}", f"2.0.{arm.version + 1}"
    record = s5_record(
        envelope=envelope,
        modification_id=f"mod_{digest[:24]}",
        target_ref=f"{arm.name}/{model.candidate.name}",
        operation=operation,
        before=before,
        after=after,
        evaluation={"eval_suite": suite, "n": n, "baseline": {}, "candidate": metrics, "passed": True},
        rollback={"strategy": "feature_flag", "snapshot_ref": snapshot},
        status="applied",
        system="s1.decision",
        from_version=old,
        to_version=new,
        rationale=(
            f"Gate {kind} at ticket {item['index']}; evaluation is against "
            f"{'gold' if arm.name == 'oracle_audit' and kind == 'demotion' else 'teacher'} labels."
        ),
    )
    meta = version_bump_record(
        record_id=f"bump_{digest[:24]}",
        created_at=now.isoformat().replace("+00:00", "Z"),
        author={"kind": "s5", "id": "e3a-lifecycle"},
        status="accepted",
        evidence={"metrics": metrics, "notes": suite},
        system="s1.decision",
        from_version=old,
        to_version=new,
        description=f"{kind} {model.candidate.name} in {arm.name}",
        change_kind="capability_distilled" if kind == "promotion" else "rollback",
        s5_response_ids=[response_id],
    )
    arm.version += 1
    if cfg.get("s5_records") is not None:
        cfg["s5_records"].append(record)
    if cfg.get("meta_records") is not None:
        cfg["meta_records"].append(meta)


def _compile(arm, selected, providers, cfg, index):
    traces = [item["teacher"].trace for item in selected]
    report, timing = _mine_timed(traces, cfg, "e3a_compilation_mining_v2")
    elapsed, mining_cpu = timing["latency_ms"], timing["cpu_seconds"]
    diagnostics = cfg.get("diagnostics")
    if diagnostics is not None:
        diagnostics.append(
            {
                "stream": cfg.get("stream"),
                "arm": arm.name,
                "ticket_index": index,
                "generation": arm.generation,
                "stage": "filtered",
                "candidates": discovery_rows(report),
                **discovery_summary(report),
            }
        )
    d1 = next((c for c in report.accepted if c.kind == "retrieval_choice" and c.tool == "search_policy"), None)
    if d1 is None:
        return False, 0.0, elapsed, "required_decision_not_mined", mining_cpu
    # The controlled policy fixes identity by entry. Learn the dependent value
    # only from this arm's observed training traces; unseen or tied entries
    # cannot be substituted.
    identities: dict[str, Counter] = defaultdict(Counter)
    for item in selected:
        entry, identity = _teacher_labels(item)
        identities[entry][identity] += 1
    identity_map = {
        entry: counts[True] > counts[False] for entry, counts in identities.items() if counts[True] != counts[False]
    }
    candidates = [d1]
    training = []
    for candidate in candidates:
        labels = [_teacher_labels(item)[0 if candidate is d1 else 1] for item in selected]
        if len(set(labels)) < 2:
            return False, 0.0, elapsed, "insufficient_label_classes", mining_cpu
        if any(str(label) not in {str(value) for value in candidate.values} for label in labels):
            return False, 0.0, elapsed, "label_outside_choice_space", mining_cpu
        training.append((candidate, labels))
    surrogate = arm.name.startswith("surrogate")
    new_models = []
    writer_cost = 0.0
    cpu_seconds = mining_cpu
    for candidate, labels in training:
        if surrogate:
            values = [str(v) for v in candidate.values]
            question = Choice(candidate.name, "Predict the observed teacher decision.", values)
            decider = make_surrogate(cfg["embedder"], values)
            decider.fit([item["text"] for item in selected], [str(value) for value in labels])
            elapsed += float(getattr(decider, "fit_metadata", {}).get("latency_ms", 0.0))
            cpu_seconds += float(getattr(decider, "fit_metadata", {}).get("cpu_seconds", 0.0))
        else:
            question = None
            for attempt in range(2):
                try:
                    question, _ = write_question(
                        candidate,
                        providers.writer,
                        n_samples=20,
                        seed=cfg["seed"] + arm.generation * 2 + attempt,
                    )
                except ValueError as exc:
                    if cfg.get("writer_failures") is not None:
                        cfg["writer_failures"].append(
                            {
                                "stream": cfg.get("stream"),
                                "arm": arm.name,
                                "ticket_index": index,
                                "candidate": candidate.name,
                                "attempt": attempt + 1,
                                "error": str(exc),
                            }
                        )
                elapsed += getattr(providers.writer, "last_latency_ms", None) or 0.0
                writer_cost += _amount(providers.writer.last_cost)
                if question is not None:
                    break
            if question is None:
                return False, writer_cost, elapsed, "writer_failed_after_retry", cpu_seconds
            decider = providers.s1
        # The sum over generations is bounded by alpha, and each decision gets
        # its own share; CompiledDecision further splits across attempts.
        alpha = cfg["alpha"] / (2 * (arm.generation + 1) * (arm.generation + 2))
        gate = CompiledDecision(
            epsilon=cfg["epsilon"],
            alpha=alpha,
            n_cal=cfg["n_cal"],
            n_val=cfg["n_val"],
            audit_rate=cfg["audit_rate"],
            metric=cfg["metric"],
            max_promotion_attempts=cfg["max_promotion_attempts"],
            tau_rule=cfg["tau_rule"],
        )
        gate.start_shadow()
        new_models.append(_Model(candidate, question, gate, decider, surrogate))
    arm.models, arm.identity_map = new_models, identity_map
    arm.pending = False
    arm.last_compile = index
    arm.generation += 1
    return True, writer_cost, elapsed, None, cpu_seconds


def _predict(model, text):
    result = model.decider.decide(text, [model.question])
    answer = result.answers[model.question.name]
    if model.surrogate and model.candidate.kind == "branch" and not isinstance(answer, Refusal):
        p = answer.probabilities.get("True")
        answer = PredicateAnswer(answer.name, p, raw_value=answer.value == "True")
    cpu = float(getattr(result.envelope, "metadata", {}).get("cpu_seconds", 0.0)) if model.surrogate else 0.0
    return answer, _amount(result.envelope.cost), result.envelope.latency_ms or 0.0, cpu


def _joint_reference(model, answer, labels, identity_map):
    """Encode joint mismatch while retaining the D1 answer's routing signal."""
    entry = answer.value
    expected = labels[0]
    if entry == expected and identity_map[entry] != labels[1]:
        expected = f"\x00identity_mismatch:{expected}"
    return _reference(model.question, expected)


def run_lifecycle(items, providers, config):
    """Simulate six arms; return arm-name to chronological per-ticket rows.

    Required config: ``embedder``. Optional ``diagnostics`` is a list populated
    with full mining candidate rows and ambiguity/discovery statistics.
    Refit cadence never interrupts a shadow attempt: a due refit is deferred
    until the next epoch after all current shadow windows have completed.
    """
    cfg = {
        "warmup": 200,
        "n_cal": 100,
        "n_val": 100,
        "epsilon": 0.20,
        "alpha": 0.05,
        "audit_rate": 0.2,
        "seed": 20261122,
        "refit_interval": 200,
        "max_promotion_attempts": 1,
        "tau_rule": "upper_bound",
        "metric": "probability",
        "min_support": 5,
        **config,
    }
    if cfg["warmup"] < 1 or cfg["refit_interval"] < 1:
        raise ValueError("warmup and refit_interval must be positive")
    arms = {name: _Arm(name, random.Random(cfg["seed"])) for name in ARMS}
    for pos, item in enumerate(items):
        epoch = pos >= cfg["warmup"] and (pos - cfg["warmup"]) % cfg["refit_interval"] == 0
        compiled = {}
        pool_counts = {}
        if epoch:
            # Fixed-size subsampling from each arm's observed, valid label pool;
            # never borrow labels from another arm or inspect unserved references.
            pools = {}
            for name, arm in arms.items():
                source = arm.escalated if name.endswith("_refit") and pos > cfg["warmup"] else arm.pool
                window = source[-cfg.get("training_window", cfg["warmup"]) :]
                raw, raw_timing = _mine_timed([entry["teacher"].trace for entry in window], cfg, "e3a_raw_discovery_v2")
                if cfg.get("diagnostics") is not None:
                    cfg["diagnostics"].append(
                        {
                            "stream": cfg.get("stream"),
                            "arm": name,
                            "ticket_index": item["index"],
                            "generation": arm.generation,
                            "stage": "raw",
                            "candidates": discovery_rows(raw),
                            **discovery_summary(raw),
                        }
                    )
                started, cpu_started = time.perf_counter(), time.process_time()
                pools[name], missing, unmatched = _training_pool(window)
                filter_timing = {
                    "latency_ms": (time.perf_counter() - started) * 1000,
                    "cpu_seconds": time.process_time() - cpu_started,
                }
                filter_key = {
                    "operation": "e3a_training_filter_v1",
                    "items": [
                        {
                            "trace": _trace_key(entry["teacher"].trace),
                            "events": entry["teacher"].events,
                            "route_present": entry["teacher"].route is not None,
                            "account_id": entry["ticket"]["account_id"],
                        }
                        for entry in window
                    ],
                }
                filter_timing = _cached_timing(cfg, filter_key, filter_timing)
                pool_counts[name] = (len(pools[name]), missing, unmatched, raw_timing, filter_timing)
            budget = min(len(pools[name]) for name in FACTORIAL)
            for name, arm in arms.items():
                if name.endswith("_refit"):
                    arm.pending = True
                if not arm.pending:
                    continue
                if any(model.gate.state == "shadow" for model in arm.models):
                    compiled[name] = (False, 0.0, 0.0, "shadow_in_progress", None, 0.0)
                    continue
                pool = pools[name]
                count = budget if name in FACTORIAL else min(budget, len(pool))
                if count < cfg["min_support"]:
                    compiled[name] = (False, 0.0, 0.0, "insufficient_training_labels", count, 0.0)
                    continue
                selected = random.Random(cfg["seed"] + (pos - cfg["warmup"]) // cfg["refit_interval"]).sample(
                    pool, count
                )
                ok, cost, latency, reason, cpu = _compile(arm, selected, providers, cfg, item["index"])
                compiled[name] = (ok, cost, latency, reason, count, cpu)
        for name, arm in arms.items():
            row = {
                "arm": name,
                "ticket_index": item["index"],
                "served_by": "agent",
                "promoted": False,
                "demoted": False,
                "audited": False,
                "agent_calls": 0,
                "teacher_agreement": None,
                "cost_agent": 0.0,
                "cost_s1": 0.0,
                "cost_shadow": 0.0,
                "cost_audit": 0.0,
                "cost_writer": 0.0,
                "cost_mining": 0.0,
                "cost_embedding": 0.0,
                "latency_ms": 0.0,
                "local_cpu_seconds": 0.0,
                "raw_mining_latency_ms": 0.0,
                "training_filter_latency_ms": 0.0,
                "training_label_count": None,
                "training_available_labels": None,
                "training_excluded_missing": None,
                "training_excluded_retrieval": None,
                "compile_status": None,
                "decisions": None,
            }
            if name in pool_counts:
                available, missing, unmatched, raw_timing, filter_timing = pool_counts[name]
                row.update(
                    training_available_labels=available,
                    training_excluded_missing=missing,
                    training_excluded_retrieval=unmatched,
                    raw_mining_latency_ms=raw_timing["latency_ms"],
                    training_filter_latency_ms=filter_timing["latency_ms"],
                )
            if name in compiled:
                ok, writer, latency, reason, count, cpu = compiled[name]
                row.update(
                    cost_writer=writer,
                    latency_ms=latency,
                    local_cpu_seconds=cpu,
                    training_label_count=count,
                    compile_status="compiled" if ok else reason,
                )
            if name in pool_counts:
                row["latency_ms"] += raw_timing["latency_ms"] + filter_timing["latency_ms"]
                row["local_cpu_seconds"] += raw_timing["cpu_seconds"] + filter_timing["cpu_seconds"]
            answers = []
            if pos >= cfg["warmup"] and arm.models:
                for model in arm.models:
                    answer, cost, latency, cpu = _predict(model, item["text"])
                    answers.append(answer)
                    row["cost_s1"] += cost
                    row["latency_ms"] += latency
                    row["local_cpu_seconds"] += cpu
            shadow = any(m.gate.state == "shadow" for m in arm.models)
            can_serve = bool(answers) and not shadow and all(m.gate.state == "promoted" for m in arm.models)
            routes = [m.gate.route(a) for m, a in zip(arm.models, answers, strict=True)]
            can_serve = (
                can_serve and all(x == "serve" for x in routes) and all(not isinstance(a, Refusal) for a in answers)
            )
            entry = answers[0].value if can_serve else None
            # Unknown labels cannot be substituted and must escalate.
            # Do not substitute an unseen or tied learned identity mapping.
            if can_serve and entry in arm.identity_map:
                try:
                    item["kb"].get_entry(entry)
                except KeyError:
                    can_serve = False
            else:
                can_serve = False
            verify = arm.identity_map[entry] if can_serve else None
            if can_serve:
                env = SupportEnvironment(item["kb"])
                route = env.substitute(
                    entry,
                    item["ticket"]["account_id"],
                    verify,
                    amount=item["ticket"].get("amount"),
                    merchant=item["ticket"].get("merchant"),
                )
                verified = verify
                row["served_by"] = "compiled"
                row["decisions"] = {"entry_id": entry, "verify": verify}
            else:
                route, verified = item["teacher"].route or {}, item["teacher"].verified
            row["route"] = route
            row["verified"] = verified
            row["predictions"] = {
                model.candidate.name: answer.value for model, answer in zip(arm.models, answers, strict=True)
            }
            row["predicted_entry"] = entry if can_serve else (answers[0].value if answers else None)
            row["predicted_verify"] = arm.identity_map.get(row["predicted_entry"])
            audit = (
                can_serve
                and name not in ("s1_refit", "surrogate_refit", "escalation_only")
                and arm.rng.random() < cfg["audit_rate"]
            )
            teacher_needed = not can_serve or audit
            labels = None
            if teacher_needed:
                labels = _teacher_labels(item)
                arm.pool.append(item)
                if not can_serve and (not shadow or pos < cfg["warmup"]):
                    arm.escalated.append(item)
                row["agent_calls"] = 1
                cost = _amount(item["teacher"].envelope.cost)
                row["cost_audit" if audit else "cost_shadow" if shadow else "cost_agent"] = cost
                row["latency_ms"] += item["teacher"].envelope.latency_ms or 0.0
            if labels is not None:
                if can_serve:
                    row["teacher_agreement"] = entry == labels[0] and verify == labels[1]
                else:
                    row["teacher_agreement"] = True
                for model, answer, routed in zip(arm.models, answers, routes, strict=True):
                    if model.gate.state == "shadow" and answer.value in arm.identity_map:
                        model.gate.observe_shadow(answer, _joint_reference(model, answer, labels, arm.identity_map))
                        model.observed += 1
                        if model.observed == cfg["n_cal"] + cfg["n_val"]:
                            started = time.perf_counter()
                            result = model.gate.attempt_promotion()
                            elapsed_ms = (time.perf_counter() - started) * 1000
                            if result.promoted:
                                _transition(arm, model, item, cfg, "promotion", elapsed_ms)
                            model.observed = 0
                            row["promoted"] |= result.promoted
                            if model.gate.state == "rejected":
                                arm.pending = True
                    elif (
                        model.gate.state == "promoted"
                        and answer.value in arm.identity_map
                        and (
                            (audit and routed == "serve")
                            or (name == "escalation_only" and not can_serve and routed == "serve")
                        )
                    ):
                        reference_labels = labels
                        if name == "oracle_audit":
                            reference_labels = (item["gold"]["id"], item["gold"]["identity_check"])
                        reference = _joint_reference(model, answer, reference_labels, arm.identity_map)
                        started = time.perf_counter()
                        demoted = model.gate.record_audit(answer, reference)
                        elapsed_ms = (time.perf_counter() - started) * 1000
                        if demoted:
                            _transition(arm, model, item, cfg, "demotion", elapsed_ms)
                            row["demoted"] = True
                            arm.pending = True
            row["audited"] = audit
            gold = item["gold"]
            row["gold_department_correct"] = route.get("department") == gold["department"]
            row["gold_priority_correct"] = route.get("priority") == gold["priority"]
            row["gold_identity_correct"] = verified == gold["identity_check"]
            row["gold_joint_correct"] = all(
                row[k] for k in ("gold_department_correct", "gold_priority_correct", "gold_identity_correct")
            )
            row["cost_usd"] = sum(
                row[k]
                for k in (
                    "cost_agent",
                    "cost_s1",
                    "cost_shadow",
                    "cost_audit",
                    "cost_writer",
                    "cost_mining",
                    "cost_embedding",
                )
            )
            arm.rows.append(row)
    return {name: arm.rows for name, arm in arms.items()}

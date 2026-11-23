from types import SimpleNamespace

from bench.e3a.lifecycle_runner import FACTORIAL, _joint_reference, run_lifecycle
from bench.tasks.environment import PolicyKB
from som.compile.traces import AgentStep, AgentTrace
from som.questions import ChoiceAnswer, Predicate, PredicateAnswer


def prepared(n, *, missing=False):
    entries = [
        dict(id=key, title=key, department=key, priority="normal", identity_check=key == "b") for key in ("a", "b")
    ]
    kb = PolicyKB(entries=entries)
    items = []
    for i in range(n):
        entry = ("a", "a", "b", "b")[i % 4]
        verify = entry == "b"
        text = f"{entry}:{verify}"
        ticket = {"account_id": f"acct{i}", "amount": None, "merchant": None}
        steps = [
            AgentStep("search_policy", {"query": text}, [{"id": "a", "title": "a"}, {"id": "b", "title": "b"}]),
            AgentStep("get_policy", {"entry_id": entry}, kb.get_entry(entry)),
        ]
        events = [{"tool": "get_policy", "entry_id": entry}]
        if verify:
            steps.append(AgentStep("verify_identity", {"account_id": ticket["account_id"]}, {}))
            events.append({"tool": "verify_identity", "account_id": ticket["account_id"]})
        steps.append(AgentStep("route_ticket", {}, {}))
        events.append({"tool": "route_ticket"})
        route = {"department": entry, "priority": "normal"}
        if missing:
            events = [{"tool": "route_ticket"}]
        teacher = SimpleNamespace(
            trace=AgentTrace(f"{i + 1:032x}", text, steps),
            events=events,
            route=route,
            verified=verify,
            envelope=SimpleNamespace(cost=SimpleNamespace(amount=0.1), latency_ms=2),
        )
        gold = {**kb.get_entry(entry), "identity_check": verify}
        items.append(
            dict(index=i, text=text, ticket=ticket, teacher=teacher, kb=kb, gold=gold, prompt_version="original")
        )
    return items


class Writer:
    last_cost = SimpleNamespace(amount=0.03)

    def __call__(self, context):
        return {
            "name": "verify" if context.get("tool") == "verify_identity" else "entry",
            "instructions": "Predict the decision",
        }


class Decider:
    def decide(self, text, questions):
        question = questions[0]
        entry, verify = text.split(":")
        if isinstance(question, Predicate):
            answer = PredicateAnswer(question.name, 0.99 if verify == "True" else 0.01)
        else:
            value = verify if set(question.values) == {"True", "False"} else entry
            answer = ChoiceAnswer(question.name, value, {v: 0.99 if v == value else 0.01 for v in question.values})
        return SimpleNamespace(
            answers={question.name: answer}, envelope=SimpleNamespace(cost=SimpleNamespace(amount=0.01), latency_ms=1)
        )


class Surrogate(Decider):
    def fit(self, inputs, labels):
        return self


def test_warmup_charges_every_arm_without_using_a_model():
    providers = SimpleNamespace(s1=Decider(), writer=Writer())
    rows = run_lifecycle(prepared(3), providers, {"warmup": 5, "embedder": None})
    assert len(rows) == 6
    for arm_rows in rows.values():
        assert [row["served_by"] for row in arm_rows] == ["agent"] * 3
        assert [row["cost_usd"] for row in arm_rows] == [0.1] * 3
        assert all(row["agent_calls"] == 1 for row in arm_rows)


def test_missing_teacher_decisions_skip_training_without_fabricating_labels():
    providers = SimpleNamespace(s1=Decider(), writer=Writer())
    rows = run_lifecycle(prepared(5, missing=True), providers, {"warmup": 4, "min_support": 1, "embedder": None})
    for arm_rows in rows.values():
        assert arm_rows[4]["compile_status"] == "insufficient_training_labels"
        assert arm_rows[4]["training_label_count"] == 0
        assert arm_rows[4]["served_by"] == "agent"
        assert arm_rows[4]["teacher_agreement"] is None


def test_failed_writer_is_retried_once_and_both_costs_are_booked(monkeypatch):
    monkeypatch.setattr("bench.e3a.lifecycle_runner.make_surrogate", lambda embedder, classes: Surrogate())

    from bench.e3a import lifecycle_runner

    original = lifecycle_runner.write_question
    seeds = []
    retry_markers = []

    def record_seed(*args, **kwargs):
        seeds.append(kwargs["seed"])
        return original(*args, **kwargs)

    monkeypatch.setattr(lifecycle_runner, "write_question", record_seed)

    class FailingWriter(Writer):
        def __call__(self, context):
            retry_markers.append(context.get("_e3a_retry"))
            return {}

    failures = []
    rows = run_lifecycle(
        prepared(10),
        SimpleNamespace(s1=Decider(), writer=FailingWriter()),
        {"warmup": 8, "min_support": 1, "embedder": None, "writer_failures": failures},
    )
    row = rows["s1_audit"][8]
    assert row["compile_status"] == "writer_failed_after_retry"
    assert row["cost_writer"] == 0.06
    assert row["served_by"] == "agent"
    assert [failure["attempt"] for failure in failures if failure["arm"] == "s1_audit"] == [1, 2]
    assert seeds[:2] == [20261122, 20261123]
    assert retry_markers[:2] == [None, 1]


def test_real_mining_shadow_promotion_and_audit_are_paired_and_costed(monkeypatch):
    monkeypatch.setattr("bench.e3a.lifecycle_runner.make_surrogate", lambda embedder, classes: Surrogate())
    diagnostics = []
    providers = SimpleNamespace(s1=Decider(), writer=Writer())
    rows = run_lifecycle(
        prepared(16),
        providers,
        {
            "warmup": 8,
            "min_support": 1,
            "n_cal": 2,
            "n_val": 2,
            "epsilon": 0.9,
            "alpha": 0.9,
            "tau_rule": "margin",
            "audit_rate": 1,
            "refit_interval": 50,
            "embedder": None,
            "diagnostics": diagnostics,
        },
    )
    assert [rows[name][8]["training_label_count"] for name in FACTORIAL] == [8] * 4
    assert all(rows[name][8]["compile_status"] == "compiled" for name in FACTORIAL)
    assert rows["s1_audit"][8]["cost_writer"] == 0.03
    assert rows["s1_audit"][7]["predicted_entry_probability"] is None
    assert rows["s1_audit"][8]["served_by"] == "agent"
    assert rows["s1_audit"][8]["predicted_entry_probability"] == 0.99
    assert any(row["promoted"] for row in rows["s1_audit"])
    served = next(row for row in rows["s1_audit"] if row["served_by"] == "compiled")
    assert served["audited"] and served["agent_calls"] == 1
    assert served["cost_audit"] == 0.1 and served["gold_joint_correct"]
    assert served["predicted_entry_probability"] == 0.99
    refit_served = next(row for row in rows["s1_refit"] if row["served_by"] == "compiled")
    assert not refit_served["audited"] and refit_served["agent_calls"] == 0
    assert all("ambiguous_retrieval_count" in item and item["candidates"] for item in diagnostics)


def test_refit_waits_for_shadow_window_to_finish(monkeypatch):
    monkeypatch.setattr("bench.e3a.lifecycle_runner.make_surrogate", lambda embedder, classes: Surrogate())
    providers = SimpleNamespace(s1=Decider(), writer=Writer())
    rows = run_lifecycle(
        prepared(20),
        providers,
        {
            "warmup": 8,
            "min_support": 1,
            "n_cal": 4,
            "n_val": 4,
            "epsilon": 0.9,
            "alpha": 0.9,
            "tau_rule": "margin",
            "refit_interval": 2,
            "embedder": None,
        },
    )
    for name in ("s1_refit", "surrogate_refit"):
        assert rows[name][8]["compile_status"] == "compiled"
        assert [rows[name][i]["compile_status"] for i in (10, 12, 14)] == ["shadow_in_progress"] * 3
        assert rows[name][15]["promoted"]


def test_unmatched_teacher_labels_are_excluded_before_equal_budget_sampling(monkeypatch):
    monkeypatch.setattr("bench.e3a.lifecycle_runner.make_surrogate", lambda embedder, classes: Surrogate())
    items = prepared(9)
    items[0]["teacher"].events[0]["entry_id"] = "unobserved"
    items[0]["teacher"].trace.steps[0].result = [{"id": "a", "title": "first"}, {"id": "a", "title": "second"}]
    diagnostics = []
    providers = SimpleNamespace(s1=Decider(), writer=Writer())
    rows = run_lifecycle(
        items,
        providers,
        {
            "warmup": 8,
            "min_support": 1,
            "embedder": None,
            "diagnostics": diagnostics,
        },
    )
    assert [rows[name][8]["training_label_count"] for name in FACTORIAL] == [7] * 4
    assert all(rows[name][8]["training_excluded_retrieval"] == 1 for name in FACTORIAL)
    assert all(rows[name][8]["training_available_labels"] == 7 for name in FACTORIAL)
    assert all(rows[name][8]["compile_status"] == "compiled" for name in FACTORIAL)
    reports = [report for report in diagnostics if report["arm"] == "s1_audit"]
    raw = next(report for report in reports if report["stage"] == "raw")
    filtered = next(report for report in reports if report["stage"] == "filtered")
    assert raw["ambiguous_retrieval_count"] == 1
    assert filtered["ambiguous_retrieval_count"] == 0


def test_question_writer_receives_at_most_twenty_examples(monkeypatch):
    monkeypatch.setattr("bench.e3a.lifecycle_runner.make_surrogate", lambda embedder, classes: Surrogate())

    class RecordingWriter(Writer):
        def __init__(self):
            self.sizes = []

        def __call__(self, context):
            self.sizes.append(len(context["samples"]))
            return super().__call__(context)

    writer = RecordingWriter()
    run_lifecycle(
        prepared(25), SimpleNamespace(s1=Decider(), writer=writer), {"warmup": 24, "min_support": 1, "embedder": None}
    )
    assert writer.sizes and set(writer.sizes) == {20}


def test_transition_records_are_emitted_only_for_real_promotions_and_demotions(monkeypatch):
    monkeypatch.setattr("bench.e3a.lifecycle_runner.make_surrogate", lambda embedder, classes: Surrogate())

    class ShiftedDecider(Decider):
        def decide(self, text, questions):
            if not text.startswith("!"):
                return super().decide(text, questions)
            entry, verify = text[1:].split(":")
            wrong = ("b" if entry == "a" else "a") + ":" + ("False" if verify == "True" else "True")
            return super().decide(wrong, questions)

    items = prepared(100)
    for item in items[20:]:
        item["text"] = "!" + item["text"]
    s5_records, meta_records = [], []
    rows = run_lifecycle(
        items,
        SimpleNamespace(s1=ShiftedDecider(), writer=Writer()),
        {
            "warmup": 8,
            "min_support": 1,
            "n_cal": 4,
            "n_val": 8,
            "epsilon": 0.5,
            "alpha": 0.9,
            "tau_rule": "margin",
            "audit_rate": 1,
            "refit_interval": 1000,
            "embedder": None,
            "s5_records": s5_records,
            "meta_records": meta_records,
        },
    )
    assert any(row["promoted"] for row in rows["s1_audit"])
    assert any(row["demoted"] for row in rows["s1_audit"])
    assert len(s5_records) == len(meta_records)
    operations = {record["response"]["body"]["modifications"][0]["operation"] for record in s5_records}
    assert operations == {"add", "remove"}
    assert all(
        meta["provenance"]["s5_response_ids"] == [record["response"]["id"]]
        for record, meta in zip(s5_records, meta_records, strict=True)
    )
    assert all(record["response"]["cost"]["basis"] == "unknown" for record in s5_records)
    for record, meta in zip(s5_records, meta_records, strict=True):
        modification = record["response"]["body"]["modifications"][0]
        if modification["operation"] == "remove":
            assert meta["changes"][0]["kind"] == "rollback"
            evidence = meta["evidence"]["metrics"]
            assert evidence["e_value"] >= 1 / evidence["alpha"]
            assert evidence["audit_count"] >= evidence["audit_errors"] > 0
        else:
            assert meta["changes"][0]["kind"] == "capability_distilled"


def test_no_transitions_produce_no_lifecycle_records():
    s5_records, meta_records = [], []
    run_lifecycle(
        prepared(3),
        SimpleNamespace(s1=Decider(), writer=Writer()),
        {"warmup": 5, "embedder": None, "s5_records": s5_records, "meta_records": meta_records},
    )
    assert s5_records == meta_records == []


def test_mining_latency_replays_for_logically_identical_traces(tmp_path, monkeypatch):
    from bench.common.cache import JsonCache

    monkeypatch.setattr("bench.e3a.lifecycle_runner.make_surrogate", lambda embedder, classes: Surrogate())
    providers = SimpleNamespace(s1=Decider(), writer=Writer())
    record_cache = JsonCache("mining", mode="record", directory=tmp_path)
    cfg = {"warmup": 8, "min_support": 1, "embedder": None, "timing_cache": record_cache}
    original = run_lifecycle(prepared(9), providers, cfg)
    replay_items = prepared(9)
    for i, item in enumerate(replay_items):
        item["teacher"].trace.trace_id = f"{i + 100:032x}"
    replay_cache = JsonCache("mining", mode="replay", directory=tmp_path)
    replay = run_lifecycle(replay_items, providers, {**cfg, "timing_cache": replay_cache})
    assert replay_cache.hits
    assert all(original[name][8]["latency_ms"] == replay[name][8]["latency_ms"] for name in FACTORIAL)


def test_surrogate_fit_and_prediction_cpu_are_each_counted_once(monkeypatch):
    class MeasuredSurrogate(Surrogate):
        def fit(self, inputs, labels):
            self.fit_metadata = {"cpu_seconds": "0.25"}
            return self

        def decide(self, text, questions):
            decision = super().decide(text, questions)
            decision.envelope.metadata = {"cpu_seconds": "0.125"}
            return decision

    class FixedTiming:
        def get_or_call(self, key, call):
            return {"latency_ms": 2.0, "cpu_seconds": 1.0}

    monkeypatch.setattr("bench.e3a.lifecycle_runner.make_surrogate", lambda embedder, classes: MeasuredSurrogate())
    rows = run_lifecycle(
        prepared(9),
        SimpleNamespace(s1=Decider(), writer=Writer()),
        {"warmup": 8, "min_support": 1, "embedder": None, "timing_cache": FixedTiming()},
    )
    assert rows["surrogate_audit"][8]["local_cpu_seconds"] == 3.375
    assert rows["s1_audit"][8]["local_cpu_seconds"] == 3.0
    assert rows["s1_audit"][8]["raw_mining_latency_ms"] == 2.0
    assert rows["s1_audit"][8]["training_filter_latency_ms"] == 2.0


def test_joint_reference_counts_identity_mismatch_even_when_entry_matches():
    model = SimpleNamespace(question=SimpleNamespace(name="entry"))
    answer = ChoiceAnswer("entry", "a", {"a": 0.9, "b": 0.1})
    assert _joint_reference(model, answer, ("a", False), {"a": False}).value == answer.value
    assert _joint_reference(model, answer, ("a", True), {"a": False}).value != answer.value
    assert _joint_reference(model, answer, ("b", False), {"a": False}).value != answer.value


def test_oracle_audit_uses_gold_when_teacher_decision_is_missing(monkeypatch):
    from som.compile import CompiledDecision

    monkeypatch.setattr("bench.e3a.lifecycle_runner.make_surrogate", lambda embedder, classes: Surrogate())
    original = CompiledDecision.record_audit
    comparisons = []

    def record(self, answer, reference):
        comparisons.append((answer.value, reference.value))
        return original(self, answer, reference)

    monkeypatch.setattr(CompiledDecision, "record_audit", record)
    items = prepared(16)
    items[-1]["teacher"].events = [{"tool": "route_ticket"}]
    items[-1]["gold"]["identity_check"] = not items[-1]["gold"]["identity_check"]
    rows = run_lifecycle(
        items,
        SimpleNamespace(s1=Decider(), writer=Writer()),
        {
            "warmup": 8,
            "min_support": 1,
            "n_cal": 2,
            "n_val": 2,
            "epsilon": 0.9,
            "alpha": 0.9,
            "tau_rule": "margin",
            "audit_rate": 1,
            "refit_interval": 50,
            "embedder": None,
        },
    )
    assert rows["oracle_audit"][-1]["audited"]
    assert rows["oracle_audit"][-1]["teacher_agreement"] is None
    assert sum(answer != reference for answer, reference in comparisons) == 1
